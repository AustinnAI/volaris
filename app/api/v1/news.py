"""News & Sentiment API endpoints - Phase 2.

Provides:
- Recent news retrieval with sentiment
- Aggregated sentiment metrics
- Multi-ticker sentiment ranking
- Manual and batch refresh endpoints
- Old article pruning
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.ai import AISummaryAPIResponse, BatchSummaryRequest, BatchSummaryResponse, render_discord_markdown
from app.db.database import get_db
from app.services.ai_summary_service import generate_ai_summary
from app.services.index_service import get_index_constituents_symbols
from app.services.news_service import (
    get_latest_article_timestamp,
    get_recent_news,
    get_ticker_sentiment,
    is_stale,
    prune_old_articles,
    refresh_news_for_symbol,
)
from app.utils.cache import cache
from app.utils.logger import app_logger
from app.utils.market_hours import is_market_hours

router = APIRouter(prefix="/news", tags=["news"])


# -------------------------------------------------------------------------
# Response Models
# -------------------------------------------------------------------------


class NewsArticleResponse(BaseModel):
    """Single news article with sentiment."""

    headline: str
    summary: str | None
    source: str | None
    url: str
    published_at: datetime
    sentiment_score: float | None = Field(None, description="0.0 (bearish) to 1.0 (bullish)")
    sentiment_label: str | None = Field(None, description="positive, neutral, or negative")
    sentiment_compound: float | None = Field(None, description="VADER compound score (-1.0 to 1.0)")


class TickerNewsResponse(BaseModel):
    """News articles for a ticker."""

    symbol: str
    article_count: int
    articles: list[NewsArticleResponse]


class SentimentResponse(BaseModel):
    """Aggregated sentiment for a ticker."""

    symbol: str
    weighted_score: float = Field(description="0.0 (bearish) to 1.0 (bullish)")
    compound: float = Field(description="VADER compound score (-1.0 to 1.0)")
    label: str = Field(description="positive, neutral, or negative")
    article_count: int
    bullish_percent: int = Field(description="% of positive articles")
    bearish_percent: int = Field(description="% of negative articles")


class SentimentSummaryItem(BaseModel):
    """Sentiment summary for multi-ticker ranking."""

    symbol: str
    weighted_score: float
    compound: float
    label: str
    article_count: int
    bullish_percent: int
    bearish_percent: int


class SentimentSummaryResponse(BaseModel):
    """Multi-ticker sentiment ranking."""

    total_tickers: int
    tickers: list[SentimentSummaryItem]


class RefreshResponse(BaseModel):
    """News refresh result."""

    symbol: str
    new_articles: int
    message: str


class BatchRefreshResponse(BaseModel):
    """Batch refresh result."""

    total_symbols: int
    successful: int
    failed: int
    results: list[RefreshResponse]


class PruneResponse(BaseModel):
    """Article pruning result."""

    deleted_count: int
    message: str


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get("/{symbol}", response_model=TickerNewsResponse)
async def get_news(
    symbol: str,
    limit: int = Query(default=10, ge=1, le=100, description="Max articles to return"),
    days: int = Query(default=7, ge=1, le=30, description="Days to look back"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get recent news articles for a ticker with sentiment analysis.

    Returns articles sorted by most recent first.

    **Example:**
    ```bash
    curl -X GET "http://localhost:8000/api/v1/news/AAPL?limit=5&days=7"
    ```
    """
    try:
        # Check staleness before fetching
        latest_timestamp = await get_latest_article_timestamp(db, symbol.upper())
        now = datetime.now(UTC)
        stale = is_stale(latest_timestamp, now)

        # Auto-refresh if empty or stale
        should_refresh = latest_timestamp is None or stale

        if should_refresh:
            # Calculate age for logging
            age_hours = None
            if latest_timestamp:
                age_hours = (now - latest_timestamp).total_seconds() / 3600

            app_logger.info(
                "news_refresh_triggered",
                extra={
                    "ticker": symbol.upper(),
                    "reason": "empty" if latest_timestamp is None else "stale",
                    "age_hours": age_hours,
                    "during_market": is_market_hours(now),
                },
            )

            try:
                await refresh_news_for_symbol(db, symbol.upper(), days=days)
                await db.commit()
            except Exception as refresh_error:
                app_logger.warning(
                    "Auto-refresh failed, returning cached results",
                    extra={"symbol": symbol.upper(), "error": str(refresh_error)},
                )

        articles = await get_recent_news(db, symbol.upper(), limit=limit, days=days)

        return TickerNewsResponse(
            symbol=symbol.upper(),
            article_count=len(articles),
            articles=[
                NewsArticleResponse(
                    headline=article.headline,
                    summary=article.summary,
                    source=article.source,
                    url=article.url,
                    published_at=article.published_at,
                    sentiment_score=(
                        float(article.sentiment_score) if article.sentiment_score else None
                    ),
                    sentiment_label=(
                        article.sentiment_label.value if article.sentiment_label else None
                    ),
                    sentiment_compound=(
                        float(article.sentiment_compound) if article.sentiment_compound else None
                    ),
                )
                for article in articles
            ],
        )
    except Exception as e:
        app_logger.error(
            "Failed to get news",
            extra={"symbol": symbol.upper(), "error": str(e)},
        )
        raise HTTPException(status_code=500, detail=f"Failed to get news: {str(e)}")


@router.get("/{symbol}/sentiment", response_model=SentimentResponse)
async def get_sentiment(
    symbol: str,
    days: int = Query(default=7, ge=1, le=30, description="Days to analyze"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get aggregated sentiment for a ticker.

    Uses exponential recency weighting (24-hour half-life) to prioritize recent articles.

    **Example:**
    ```bash
    curl -X GET "http://localhost:8000/api/v1/news/AAPL/sentiment?days=7"
    ```
    """
    # Try cache first
    cache_key = f"sentiment:{symbol.upper()}:{days}d"
    cached = await cache.get(cache_key)
    if cached:
        return SentimentResponse(**cached)

    try:
        # Check staleness before fetching sentiment
        latest_timestamp = await get_latest_article_timestamp(db, symbol.upper())
        now = datetime.now(UTC)
        stale = is_stale(latest_timestamp, now)

        # Auto-refresh if empty or stale
        should_refresh = latest_timestamp is None or stale

        if should_refresh:
            # Calculate age for logging
            age_hours = None
            if latest_timestamp:
                age_hours = (now - latest_timestamp).total_seconds() / 3600

            app_logger.info(
                "news_refresh_triggered",
                extra={
                    "ticker": symbol.upper(),
                    "reason": "empty" if latest_timestamp is None else "stale",
                    "age_hours": age_hours,
                    "during_market": is_market_hours(now),
                },
            )

            try:
                await refresh_news_for_symbol(db, symbol.upper(), days=days)
                await db.commit()
                # Invalidate sentiment cache after refresh
                await cache.delete(cache_key)
            except Exception as refresh_error:
                app_logger.warning(
                    "Auto-refresh failed for sentiment, returning cached results",
                    extra={"symbol": symbol.upper(), "error": str(refresh_error)},
                )

        sentiment = await get_ticker_sentiment(db, symbol.upper(), days=days)

        response = SentimentResponse(
            symbol=symbol.upper(),
            weighted_score=sentiment["weighted_score"],
            compound=sentiment["compound"],
            label=sentiment["label"],
            article_count=sentiment["article_count"],
            bullish_percent=sentiment["bullish_percent"],
            bearish_percent=sentiment["bearish_percent"],
        )

        # Cache for 10 minutes
        await cache.set(cache_key, response.model_dump(), ttl=settings.SENTIMENT_CACHE_SECONDS)

        return response

    except Exception as e:
        app_logger.error(
            "Failed to get sentiment",
            extra={"symbol": symbol.upper(), "error": str(e)},
        )
        raise HTTPException(status_code=500, detail=f"Failed to get sentiment: {str(e)}")


@router.get("/sentiment/summary", response_model=SentimentSummaryResponse)
async def get_sentiment_summary(
    symbols: str = Query(
        default="SPY,QQQ,IWM,DIA,AAPL,MSFT,TSLA,NVDA,GOOGL,AMZN",
        description="Comma-separated ticker symbols, 'sp500', 'nasdaq100', or 'liquid'",
    ),
    days: int = Query(default=7, ge=1, le=30, description="Days to analyze"),
    min_articles: int = Query(default=0, ge=0, le=50, description="Minimum article count filter (0=disabled)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get sentiment summary for multiple tickers, ranked by sentiment score.

    **Special values:**
    - `sp500`: All S&P 500 constituents (~503 tickers)
    - `nasdaq100`: NASDAQ-100 constituents (~100 liquid tech/growth stocks)
    - `liquid`: Combined NASDAQ-100 + S&P 500 for maximum coverage

    **Filtering:**
    - Use `min_articles` to filter tickers with low news coverage
    - Recommended: `min_articles=5` for tradeable stocks with sufficient news

    **Example:**
    ```bash
    # Get NASDAQ-100 sentiment with minimum 5 articles
    curl "http://localhost:8000/api/v1/news/sentiment/summary?symbols=nasdaq100&days=7&min_articles=5"

    # Get liquid stocks with news coverage
    curl "http://localhost:8000/api/v1/news/sentiment/summary?symbols=liquid&days=7&min_articles=5"
    ```
    """
    try:
        # Handle special index parameters
        symbols_lower = symbols.lower()
        if symbols_lower == "sp500":
            symbol_list = sorted(await get_index_constituents_symbols(db, "^GSPC"))
        elif symbols_lower == "nasdaq100":
            symbol_list = sorted(await get_index_constituents_symbols(db, "^NDX"))
        elif symbols_lower == "liquid":
            from app.services.index_service import get_priority_tickers
            symbol_set = await get_priority_tickers(db, include_sp500=True)
            symbol_list = sorted(symbol_set)
        else:
            symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

        if len(symbol_list) > 1500:
            raise HTTPException(
                status_code=400,
                detail="Too many symbols (max 1500).",
            )

        results = []
        for symbol in symbol_list:
            try:
                sentiment = await get_ticker_sentiment(db, symbol, days=days)
                results.append(
                    SentimentSummaryItem(
                        symbol=symbol,
                        weighted_score=sentiment["weighted_score"],
                        compound=sentiment["compound"],
                        label=sentiment["label"],
                        article_count=sentiment["article_count"],
                        bullish_percent=sentiment["bullish_percent"],
                        bearish_percent=sentiment["bearish_percent"],
                    )
                )
            except Exception as e:
                app_logger.warning(
                    "Failed to get sentiment for symbol",
                    extra={"symbol": symbol, "error": str(e)},
                )
                continue

        # Apply minimum article filter if specified
        if min_articles > 0:
            results = [r for r in results if r.article_count >= min_articles]

        # Sort by weighted_score descending (most bullish first)
        results.sort(key=lambda x: x.weighted_score, reverse=True)

        return SentimentSummaryResponse(
            total_tickers=len(results),
            tickers=results,
        )

    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(
            "Failed to get sentiment summary",
            extra={"error": str(e)},
        )
        raise HTTPException(status_code=500, detail=f"Failed to get sentiment summary: {str(e)}")


@router.post("/{symbol}/refresh", response_model=RefreshResponse)
async def refresh_news(
    symbol: str,
    days: int = Query(default=7, ge=1, le=30, description="Days to fetch"),
    db: AsyncSession = Depends(get_db),
):
    """
    Force refresh news for a ticker (on-demand).

    Fetches latest news from Finnhub, runs sentiment analysis, and stores in DB.

    **Example:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/news/AAPL/refresh?days=7"
    ```
    """
    try:
        new_count = await refresh_news_for_symbol(db, symbol.upper(), days=days)
        await db.commit()

        # Invalidate cache
        cache_key = f"sentiment:{symbol.upper()}:{days}d"
        await cache.delete(cache_key)

        return RefreshResponse(
            symbol=symbol.upper(),
            new_articles=new_count,
            message=f"Refreshed {new_count} new articles for {symbol.upper()}",
        )

    except Exception as e:
        await db.rollback()
        app_logger.error(
            "Failed to refresh news",
            extra={"symbol": symbol.upper(), "error": str(e)},
        )
        raise HTTPException(status_code=500, detail=f"Failed to refresh news: {str(e)}")


@router.post("/refresh/batch", response_model=BatchRefreshResponse)
async def batch_refresh_news(
    symbols: str = Query(
        default="liquid",
        description="Comma-separated symbols, 'sp500', 'nasdaq100', or 'liquid'",
    ),
    days: int = Query(default=7, ge=1, le=30, description="Days to fetch"),
    db: AsyncSession = Depends(get_db),
):
    """
    Batch refresh news for multiple tickers (GitHub Actions use).

    **Special values:**
    - `liquid`: Refresh NASDAQ-100 + S&P 500 (recommended, ~600 liquid stocks)
    - `nasdaq100`: Refresh NASDAQ-100 only (~100 stocks)
    - `sp500`: Refresh S&P 500 only (~503 stocks)

    **Example:**
    ```bash
    # Refresh liquid stocks (default for GitHub Actions)
    curl -X POST "http://localhost:8000/api/v1/news/refresh/batch?symbols=liquid&days=7"

    # Refresh NASDAQ-100 only
    curl -X POST "http://localhost:8000/api/v1/news/refresh/batch?symbols=nasdaq100&days=7"
    ```
    """
    try:
        # Parse symbols with index support
        symbols_lower = symbols.lower()
        if symbols_lower == "sp500":
            symbol_list = sorted(await get_index_constituents_symbols(db, "^GSPC"))
        elif symbols_lower == "nasdaq100":
            symbol_list = sorted(await get_index_constituents_symbols(db, "^NDX"))
        elif symbols_lower == "liquid":
            from app.services.index_service import get_priority_tickers
            symbol_set = await get_priority_tickers(db, include_sp500=True)
            symbol_list = sorted(symbol_set)
        else:
            symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

        if len(symbol_list) > 1500:
            raise HTTPException(
                status_code=400,
                detail="Too many symbols (max 1500)",
            )

        app_logger.info(
            "Starting batch news refresh",
            extra={"symbol_count": len(symbol_list), "days": days},
        )

        results = []
        successful = 0
        failed = 0

        for symbol in symbol_list:
            try:
                new_count = await refresh_news_for_symbol(db, symbol, days=days)
                await db.commit()

                results.append(
                    RefreshResponse(
                        symbol=symbol,
                        new_articles=new_count,
                        message=f"Success: {new_count} new articles",
                    )
                )
                successful += 1

                # Invalidate cache
                cache_key = f"sentiment:{symbol}:{days}d"
                await cache.delete(cache_key)

            except Exception as e:
                await db.rollback()
                app_logger.warning(
                    "Failed to refresh news for symbol",
                    extra={"symbol": symbol, "error": str(e)},
                )
                results.append(
                    RefreshResponse(
                        symbol=symbol,
                        new_articles=0,
                        message=f"Failed: {str(e)[:100]}",
                    )
                )
                failed += 1

        return BatchRefreshResponse(
            total_symbols=len(symbol_list),
            successful=successful,
            failed=failed,
            results=results,
        )

    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(
            "Failed batch news refresh",
            extra={"error": str(e)},
        )
        raise HTTPException(status_code=500, detail=f"Failed batch refresh: {str(e)}")


@router.post("/prune", response_model=PruneResponse)
async def prune_news(
    days: int = Query(default=30, ge=1, le=365, description="Retention period in days"),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete news articles older than specified days.

    **Example:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/news/prune?days=30"
    ```
    """
    try:
        deleted_count = await prune_old_articles(db, days=days)
        await db.commit()

        return PruneResponse(
            deleted_count=deleted_count,
            message=f"Deleted {deleted_count} articles older than {days} days",
        )

    except Exception as e:
        await db.rollback()
        app_logger.error(
            "Failed to prune news",
            extra={"error": str(e)},
        )
        raise HTTPException(status_code=500, detail=f"Failed to prune news: {str(e)}")


# -------------------------------------------------------------------------
# AI Summary Endpoints (Phase 2 Enhancement)
# -------------------------------------------------------------------------


@router.get("/{symbol}/summary", response_model=AISummaryAPIResponse)
async def get_summary(
    symbol: str,
    force_refresh: bool = Query(default=False, description="Skip cache and regenerate"),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate AI-powered market intelligence summary for a ticker.

    Uses LLM (OpenAI gpt-4o-mini by default) to analyze recent news articles
    and sentiment, producing structured insights with citations.

    Features:
    - Executive summary (2-3 sentences)
    - Key drivers with article citations
    - Sentiment snapshot (VADER metrics)
    - Risk flags and follow-up recommendations
    - Discord-optimized markdown output
    - 20-minute Redis cache (configurable)
    - Deterministic fallback if LLM unavailable

    **Example:**
    ```bash
    curl -X GET "http://localhost:8000/api/v1/news/SPY/summary"
    ```

    **Response includes:**
    - `structured`: Full SummaryResponse schema
    - `markdown`: Discord-ready formatted text
    - `fallback_used`: True if LLM failed/disabled
    - `cache_hit`: True if result from cache
    """
    try:
        # Auto-refresh news if stale or missing (same logic as /news and /sentiment endpoints)
        latest_timestamp = await get_latest_article_timestamp(db, symbol.upper())
        now = datetime.now(UTC)
        stale = is_stale(latest_timestamp, now)

        should_refresh = latest_timestamp is None or stale
        if should_refresh:
            age_hours = None
            if latest_timestamp:
                age_hours = (now - latest_timestamp).total_seconds() / 3600

            app_logger.info(
                "news_refresh_triggered_for_summary",
                extra={
                    "ticker": symbol.upper(),
                    "reason": "empty" if latest_timestamp is None else "stale",
                    "age_hours": age_hours,
                    "during_market": is_market_hours(now),
                },
            )

            try:
                await refresh_news_for_symbol(db, symbol.upper(), days=7)
                await db.commit()
            except Exception as refresh_error:
                app_logger.warning(
                    "Auto-refresh failed for summary, continuing with cached data",
                    extra={"symbol": symbol.upper(), "error": str(refresh_error)},
                )

        summary, fallback_used, cache_hit = await generate_ai_summary(db, symbol, force_refresh)

        markdown = render_discord_markdown(summary, fallback_used)

        return AISummaryAPIResponse(
            structured=summary,
            markdown=markdown,
            fallback_used=fallback_used,
            cache_hit=cache_hit,
        )

    except Exception as e:
        app_logger.error(
            f"Failed to generate AI summary for {symbol}",
            extra={"error": str(e)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Failed to generate AI summary: {str(e)}")


@router.post("/summary", response_model=BatchSummaryResponse)
async def batch_summary(
    request: BatchSummaryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate AI summaries for multiple tickers in batch.

    Useful for portfolio-wide analysis. Processes up to 20 tickers concurrently.

    **Request body:**
    ```json
    {
      "symbols": ["AAPL", "MSFT", "TSLA"],
      "force_refresh": false
    }
    ```

    **Features:**
    - Concurrent processing for performance
    - Individual error handling (failed tickers don't block others)
    - Respects cache for each ticker
    - Max 20 tickers per request

    **Example:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/news/summary" \\
      -H "Content-Type: application/json" \\
      -d '{"symbols": ["SPY", "QQQ", "AAPL"]}'
    ```
    """
    import asyncio
    from app.core.ai.schema import BatchSummaryItem

    symbols = [s.strip().upper() for s in request.symbols]

    async def process_ticker(symbol: str) -> BatchSummaryItem | None:
        """Process single ticker summary."""
        try:
            summary, fallback_used, cache_hit = await generate_ai_summary(
                db, symbol, request.force_refresh
            )
            markdown = render_discord_markdown(summary, fallback_used)

            return BatchSummaryItem(
                symbol=symbol,
                structured=summary,
                markdown=markdown,
                fallback_used=fallback_used,
                cache_hit=cache_hit,
            )
        except Exception as e:
            app_logger.warning(
                f"Failed to generate summary for {symbol} in batch",
                extra={"error": str(e)},
            )
            return None

    # Process all tickers concurrently
    results = await asyncio.gather(*[process_ticker(s) for s in symbols])

    # Filter out failures
    successful_summaries = [r for r in results if r is not None]

    return BatchSummaryResponse(
        total=len(symbols),
        successful=len(successful_summaries),
        summaries=successful_summaries,
    )
