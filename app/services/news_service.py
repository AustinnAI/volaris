"""News service layer - fetch, store, and analyze news articles with sentiment.

Handles:
- Fetching news from Finnhub
- Deduplication via URL unique constraint
- VADER sentiment analysis
- Aggregated sentiment metrics
- 30-day retention with pruning
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sentiment import aggregate_sentiment, analyze_sentiment
from app.db.models import NewsArticle, NewsSentimentLabel
from app.services.exceptions import DataNotFoundError
from app.services.finnhub import finnhub_client
from app.services.tickers import get_or_create_ticker
from app.utils.logger import app_logger


async def fetch_news_from_finnhub(
    symbol: str,
    from_date: datetime,
    to_date: datetime,
) -> list[dict]:
    """
    Fetch news articles from Finnhub API.

    Args:
        symbol: Ticker symbol
        from_date: Start date (inclusive)
        to_date: End date (inclusive)

    Returns:
        List of dicts with keys: headline, summary, source, url, published_at

    Raises:
        DataNotFoundError: If Finnhub client not configured
    """
    if not finnhub_client:
        raise DataNotFoundError("Finnhub client not configured", provider="Finnhub")

    symbol_upper = symbol.upper()
    app_logger.info(
        "Fetching news from Finnhub",
        extra={
            "symbol": symbol_upper,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
        },
    )

    # Convert to date objects (Finnhub client expects date, not datetime)
    from_date_obj = from_date.date() if hasattr(from_date, "date") else from_date
    to_date_obj = to_date.date() if hasattr(to_date, "date") else to_date

    raw_articles = await finnhub_client.get_company_news(symbol_upper, from_date_obj, to_date_obj)

    # Transform to our format
    articles = []
    for item in raw_articles:
        # Skip articles without required fields
        if not item.get("headline") or not item.get("url"):
            continue

        # Convert Unix timestamp to datetime
        published_at = None
        if item.get("datetime"):
            published_at = datetime.fromtimestamp(item["datetime"], tz=UTC)

        articles.append(
            {
                "headline": item["headline"],
                "summary": item.get("summary")
                or item.get("headline"),  # Use headline if no summary
                "source": item.get("source"),
                "url": item["url"],
                "published_at": published_at or datetime.now(UTC),
            }
        )

    app_logger.info(
        "Fetched news from Finnhub",
        extra={"symbol": symbol_upper, "article_count": len(articles)},
    )

    return articles


async def store_news_articles(
    db: AsyncSession,
    symbol: str,
    articles: list[dict],
    run_sentiment: bool = True,
) -> list[NewsArticle]:
    """
    Store news articles in database with sentiment analysis.

    Deduplicates by URL - existing articles are skipped.

    Args:
        db: Database session
        symbol: Ticker symbol
        articles: List of article dicts (from fetch_news_from_finnhub)
        run_sentiment: Whether to run VADER sentiment analysis (default: True)

    Returns:
        List of newly created NewsArticle objects

    Example:
        >>> articles = await fetch_news_from_finnhub("AAPL", from_date, to_date)
        >>> new_articles = await store_news_articles(db, "AAPL", articles)
        >>> await db.commit()
    """
    if not articles:
        return []

    ticker = await get_or_create_ticker(symbol.upper(), db)

    new_articles = []
    duplicate_count = 0

    for article_data in articles:
        url = article_data.get("url")
        if not url:
            continue

        # Check if article already exists (by URL)
        existing_stmt = select(NewsArticle).where(NewsArticle.url == url)
        result = await db.execute(existing_stmt)
        existing = result.scalar_one_or_none()

        if existing:
            duplicate_count += 1
            continue

        # Run sentiment analysis if enabled
        sentiment_score = None
        sentiment_label = None
        sentiment_compound = None

        if run_sentiment:
            # Analyze headline + summary for better accuracy
            text = article_data.get("headline", "")
            if article_data.get("summary"):
                text += " " + article_data["summary"]

            sentiment = analyze_sentiment(text)
            sentiment_score = Decimal(str(sentiment["score"]))
            sentiment_label = NewsSentimentLabel(sentiment["label"])
            sentiment_compound = Decimal(str(sentiment["compound"]))

        # Create article
        article = NewsArticle(
            ticker_id=ticker.id,
            headline=article_data["headline"][:512],  # Truncate to column limit
            summary=article_data.get("summary"),
            source=article_data.get("source"),
            url=url,
            published_at=article_data["published_at"],
            sentiment_score=sentiment_score,
            sentiment_label=sentiment_label,
            sentiment_compound=sentiment_compound,
        )

        db.add(article)
        new_articles.append(article)

    app_logger.info(
        "Stored news articles",
        extra={
            "symbol": symbol.upper(),
            "new_articles": len(new_articles),
            "duplicates_skipped": duplicate_count,
        },
    )

    return new_articles


async def get_recent_news(
    db: AsyncSession,
    symbol: str,
    limit: int = 10,
    days: int = 7,
) -> list[NewsArticle]:
    """
    Get recent news articles for a ticker.

    Args:
        db: Database session
        symbol: Ticker symbol
        limit: Maximum number of articles to return
        days: Number of days to look back

    Returns:
        List of NewsArticle objects (most recent first)

    Example:
        >>> articles = await get_recent_news(db, "AAPL", limit=5, days=7)
        >>> for article in articles:
        ...     print(f"{article.published_at}: {article.headline}")
    """
    ticker = await get_or_create_ticker(symbol.upper(), db)

    cutoff_date = datetime.now(UTC) - timedelta(days=days)

    stmt = (
        select(NewsArticle)
        .where(
            NewsArticle.ticker_id == ticker.id,
            NewsArticle.published_at >= cutoff_date,
        )
        .order_by(NewsArticle.published_at.desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    articles = list(result.scalars().all())

    app_logger.debug(
        "Retrieved recent news",
        extra={
            "symbol": symbol.upper(),
            "article_count": len(articles),
            "days": days,
            "limit": limit,
        },
    )

    return articles


async def get_ticker_sentiment(
    db: AsyncSession,
    symbol: str,
    days: int = 7,
) -> dict[str, float | int | str]:
    """
    Get aggregated sentiment for a ticker.

    Uses exponential recency weighting (24-hour half-life).

    Args:
        db: Database session
        symbol: Ticker symbol
        days: Number of days to analyze

    Returns:
        Dict with keys:
        - weighted_score: 0.0 - 1.0
        - compound: -1.0 to 1.0
        - label: "positive", "neutral", or "negative"
        - article_count: Number of articles analyzed
        - bullish_percent: % positive articles
        - bearish_percent: % negative articles

    Example:
        >>> sentiment = await get_ticker_sentiment(db, "AAPL", days=7)
        >>> print(f"{sentiment['label']}: {sentiment['weighted_score']:.2f}")
        positive: 0.68
    """
    ticker = await get_or_create_ticker(symbol.upper(), db)

    cutoff_date = datetime.now(UTC) - timedelta(days=days)

    stmt = select(NewsArticle).where(
        NewsArticle.ticker_id == ticker.id,
        NewsArticle.published_at >= cutoff_date,
        NewsArticle.sentiment_compound.isnot(None),  # Only articles with sentiment
    )

    result = await db.execute(stmt)
    articles = list(result.scalars().all())

    # Convert to dict format for aggregation
    article_dicts = [
        {
            "sentiment_compound": float(article.sentiment_compound),
            "published_at": article.published_at,
        }
        for article in articles
        if article.sentiment_compound is not None
    ]

    sentiment = aggregate_sentiment(article_dicts, decay_hours=24.0)

    app_logger.debug(
        "Aggregated ticker sentiment",
        extra={
            "symbol": symbol.upper(),
            "article_count": sentiment["article_count"],
            "label": sentiment["label"],
            "weighted_score": sentiment["weighted_score"],
        },
    )

    return sentiment


async def prune_old_articles(db: AsyncSession, days: int = 30) -> int:
    """
    Delete news articles older than specified days.

    Args:
        db: Database session
        days: Retention period (default: 30 days)

    Returns:
        Number of articles deleted

    Example:
        >>> deleted = await prune_old_articles(db, days=30)
        >>> await db.commit()
        >>> print(f"Deleted {deleted} old articles")
    """
    cutoff_date = datetime.now(UTC) - timedelta(days=days)

    stmt = delete(NewsArticle).where(NewsArticle.published_at < cutoff_date)

    result = await db.execute(stmt)
    deleted_count = result.rowcount or 0

    app_logger.info(
        "Pruned old news articles",
        extra={
            "deleted_count": deleted_count,
            "cutoff_date": cutoff_date.isoformat(),
            "retention_days": days,
        },
    )

    return deleted_count


async def refresh_news_for_symbol(
    db: AsyncSession,
    symbol: str,
    days: int = 7,
) -> int:
    """
    Fetch and store recent news for a symbol.

    Convenience wrapper around fetch + store.

    Args:
        db: Database session
        symbol: Ticker symbol
        days: Number of days to fetch

    Returns:
        Number of new articles stored

    Example:
        >>> new_count = await refresh_news_for_symbol(db, "AAPL", days=7)
        >>> await db.commit()
        >>> print(f"Stored {new_count} new articles")
    """
    to_date = datetime.now(UTC)
    from_date = to_date - timedelta(days=days)

    articles = await fetch_news_from_finnhub(symbol, from_date, to_date)
    new_articles = await store_news_articles(db, symbol, articles, run_sentiment=True)

    app_logger.info(
        "Refreshed news for symbol",
        extra={
            "symbol": symbol.upper(),
            "new_articles": len(new_articles),
            "days": days,
        },
    )

    return len(new_articles)
