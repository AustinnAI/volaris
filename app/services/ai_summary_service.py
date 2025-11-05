"""
AI Summary Service (Phase 2 Enhancement).

Orchestrates LLM calls, Redis caching, and fallback logic for news summaries.
"""

import json

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.ai import (
    LLMError,
    SummaryResponse,
    build_cache_key,
    build_single_ticker_prompt,
    create_fallback_summary,
    get_llm_client,
)
from app.services.news_service import get_recent_news, get_ticker_sentiment
from app.utils.cache import cache
from app.utils.logger import app_logger


async def generate_ai_summary(
    db: AsyncSession, ticker: str, force_refresh: bool = False
) -> tuple[SummaryResponse, bool, bool]:
    """
    Generate AI-powered news summary with caching.

    Args:
        db: Database session.
        ticker: Ticker symbol.
        force_refresh: Skip cache and regenerate.

    Returns:
        Tuple of (SummaryResponse, fallback_used, cache_hit).
    """
    ticker = ticker.upper()

    # Get top K recent articles
    articles = await get_recent_news(db, ticker, limit=settings.SUMMARY_TOP_K, days=7)

    if not articles:
        app_logger.info(f"No articles found for {ticker}, returning empty fallback")
        empty_summary = create_fallback_summary(
            ticker, [], {"compound": 0.0, "trend": "stable"}, reason="No articles"
        )
        return empty_summary, True, False

    # Check if too few articles
    if len(articles) < 2:
        app_logger.info(f"Only {len(articles)} article(s) for {ticker}, using fallback")
        sentiment_data = await get_ticker_sentiment(db, ticker)
        fallback_summary = create_fallback_summary(
            ticker, articles, sentiment_data, reason="Insufficient articles"
        )
        return fallback_summary, True, False

    # Build cache key
    article_urls = [art.url for art in articles]
    cache_key = build_cache_key(ticker, article_urls)

    # Check cache (unless force_refresh)
    if not force_refresh:
        cached = await cache.get(cache_key)
        if cached:
            try:
                cached_data = json.loads(cached)
                summary = SummaryResponse(**cached_data)
                app_logger.info(
                    f"AI summary cache hit for {ticker}", extra={"cache_key": cache_key}
                )
                return summary, False, True
            except (json.JSONDecodeError, ValidationError) as e:
                app_logger.warning(
                    f"Invalid cached summary for {ticker}",
                    extra={"error": str(e), "cache_key": cache_key},
                )
                # Continue to regenerate

    # Get sentiment data
    sentiment_data = await get_ticker_sentiment(db, ticker)

    # Try LLM generation
    llm_client = get_llm_client()

    if not llm_client:
        app_logger.info(f"LLM disabled or not configured, using fallback for {ticker}")
        fallback_summary = create_fallback_summary(
            ticker, articles, sentiment_data, reason="LLM disabled"
        )
        return fallback_summary, True, False

    try:
        # Build prompt
        prompt = build_single_ticker_prompt(ticker, articles, sentiment_data)

        # Call LLM
        app_logger.info(
            f"Calling LLM for {ticker}",
            extra={
                "model": settings.LLM_MODEL,
                "provider": settings.LLM_PROVIDER,
                "article_count": len(articles),
            },
        )

        llm_response = await llm_client.summarize(
            prompt=prompt,
            model=settings.LLM_MODEL,
            max_tokens=settings.LLM_MAX_TOKENS,
            temperature=settings.LLM_TEMPERATURE,
        )

        # Validate response against schema
        try:
            summary = SummaryResponse(**llm_response)
        except ValidationError as e:
            app_logger.error(
                f"LLM response validation failed for {ticker}",
                extra={"error": str(e), "response": llm_response},
            )
            fallback_summary = create_fallback_summary(
                ticker, articles, sentiment_data, reason="Invalid LLM response"
            )
            return fallback_summary, True, False

        # Cache the result
        ttl_seconds = settings.LLM_SUMMARY_TTL_MINUTES * 60
        await cache.set(cache_key, summary.model_dump_json(), ttl_seconds)

        app_logger.info(
            f"AI summary generated and cached for {ticker}",
            extra={"cache_key": cache_key, "ttl_seconds": ttl_seconds},
        )

        return summary, False, False

    except LLMError as e:
        app_logger.error(
            f"LLM error for {ticker}, using fallback",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        fallback_summary = create_fallback_summary(
            ticker, articles, sentiment_data, reason=f"LLM error: {type(e).__name__}"
        )
        return fallback_summary, True, False

    except Exception as e:
        app_logger.error(
            f"Unexpected error generating AI summary for {ticker}",
            extra={"error": str(e)},
            exc_info=True,
        )
        fallback_summary = create_fallback_summary(
            ticker, articles, sentiment_data, reason="Unexpected error"
        )
        return fallback_summary, True, False
