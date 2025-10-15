"""Higher-level market insight helpers (sentiment, top movers)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import PriceBar, Ticker, Timeframe
from app.services.exceptions import DataNotFoundError
from app.services.finnhub import finnhub_client
from app.services.polygon import polygon_client
from app.utils.cache import cache


async def fetch_sentiment(symbol: str) -> dict:
    symbol_upper = symbol.upper()
    cache_key = f"sentiment:{symbol_upper}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    if not finnhub_client:
        raise DataNotFoundError("Finnhub client not configured", provider="Finnhub")

    recommendations_raw = await finnhub_client.get_recommendation_trends(symbol_upper)
    news_raw: list[dict] = []
    try:
        news_raw = await finnhub_client.get_company_news(symbol_upper)
    except Exception:
        news_raw = []

    if polygon_client:
        try:
            polygon_news = await polygon_client.get_news(symbol_upper, limit=5)
            news_raw.extend(polygon_news)
        except Exception:
            pass

    latest_recommendation = recommendations_raw[0] if recommendations_raw else None
    recent_news = [
        {
            "headline": item.get("headline"),
            "datetime": item.get("datetime"),
            "source": item.get("source"),
            "url": item.get("url"),
        }
        for item in news_raw[:5]
    ]

    strong_buy = latest_recommendation.get("strongBuy", 0) if latest_recommendation else 0
    buy = latest_recommendation.get("buy", 0) if latest_recommendation else 0
    sell = latest_recommendation.get("sell", 0) if latest_recommendation else 0
    strong_sell = latest_recommendation.get("strongSell", 0) if latest_recommendation else 0

    def _weighted_score(strong: int, regular: int) -> float | None:
        total = strong + regular
        if total == 0:
            return None
        score = (strong * 100 + regular * 50) / total
        return round(score)

    payload = {
        "symbol": symbol_upper,
        "bullish_percent": _weighted_score(strong_buy, buy),
        "bearish_percent": _weighted_score(strong_sell, sell),
        "recommendation_trend": latest_recommendation or {},
        "recent_news": recent_news,
    }

    await cache.set(cache_key, payload, ttl=settings.SENTIMENT_CACHE_SECONDS)
    return payload


async def get_top_movers(
    limit: int, sp500_symbols: set[str], db: AsyncSession | None = None
) -> dict[str, list[dict]]:
    """
    Get top gainers and losers from S&P 500.

    Uses in-house calculation from price_bars data (free, no external API needed).
    Calculates daily % change from today's OHLCV data.

    Args:
        limit: Number of gainers/losers to return
        sp500_symbols: Set of S&P 500 ticker symbols
        db: Database session (required for in-house calculation)

    Returns:
        {"gainers": [...], "losers": [...]}
    """
    # Use in-house calculation from price_bars (free, no API limits)
    if db is not None:
        try:
            return await _calculate_top_movers_from_db(limit, sp500_symbols, db)
        except DataNotFoundError:
            if polygon_client is None:
                raise
    return await _calculate_top_movers_from_polygon(limit, sp500_symbols)


async def _calculate_top_movers_from_db(
    limit: int, sp500_symbols: set[str], db: AsyncSession
) -> dict[str, list[dict]]:
    """Calculate top movers from price_bars data (no external API needed)."""

    # Get today's date range (market open to now)
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Query: Get most recent price bar for each S&P 500 ticker today
    # Calculate % change from (close - open) / open
    stmt = (
        select(
            Ticker.symbol,
            PriceBar.close,
            PriceBar.open,
            PriceBar.volume,
            (((PriceBar.close - PriceBar.open) / PriceBar.open) * 100).label("percent_change"),
            (PriceBar.close - PriceBar.open).label("price_change"),
        )
        .join(Ticker, PriceBar.ticker_id == Ticker.id)
        .where(
            Ticker.symbol.in_(sp500_symbols),
            PriceBar.timestamp >= today_start,
            PriceBar.timeframe == Timeframe.ONE_MINUTE,
        )
        .distinct(Ticker.symbol)
        .order_by(Ticker.symbol, desc(PriceBar.timestamp))
    )

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        # No price data for today - try yesterday's daily bars as fallback
        yesterday = today_start - timedelta(days=1)
        stmt_fallback = (
            select(
                Ticker.symbol,
                PriceBar.close,
                PriceBar.open,
                PriceBar.volume,
                (((PriceBar.close - PriceBar.open) / PriceBar.open) * 100).label("percent_change"),
                (PriceBar.close - PriceBar.open).label("price_change"),
            )
            .join(Ticker, PriceBar.ticker_id == Ticker.id)
            .where(
                Ticker.symbol.in_(sp500_symbols),
                PriceBar.timestamp >= yesterday,
                PriceBar.timeframe == Timeframe.DAILY,
            )
            .distinct(Ticker.symbol)
            .order_by(Ticker.symbol, desc(PriceBar.timestamp))
        )
        result = await db.execute(stmt_fallback)
        rows = result.all()

    if not rows:
        raise DataNotFoundError(
            "No price data available for top movers calculation. "
            "Enable scheduler or wait for price data to be populated.",
            provider="Internal",
        )

    # Convert to list of dicts
    movers = [
        {
            "symbol": row.symbol,
            "price": float(row.close),
            "change": float(row.price_change),
            "percent": float(row.percent_change),
            "volume": int(row.volume) if row.volume else None,
        }
        for row in rows
        if row.percent_change is not None
    ]

    # Sort by percent change
    gainers = sorted(movers, key=lambda x: x["percent"], reverse=True)[:limit]
    losers = sorted(movers, key=lambda x: x["percent"])[:limit]

    return {"gainers": gainers, "losers": losers}


async def _calculate_top_movers_from_polygon(
    limit: int, sp500_symbols: set[str]
) -> dict[str, list[dict]]:
    """Fallback to Polygon API when database data is unavailable."""

    if polygon_client is None:
        raise DataNotFoundError("Polygon client not configured", provider="Polygon")

    gainers_raw = await polygon_client.get_top_movers("gainers")
    losers_raw = await polygon_client.get_top_movers("losers")

    def _normalize(entries: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        for entry in entries:
            symbol = (entry.get("ticker") or "").upper()
            if symbol not in sp500_symbols:
                continue
            percent = entry.get("todaysChangePerc")
            if percent is None:
                continue
            change = entry.get("todaysChange")
            last_trade = entry.get("lastTrade") or {}
            day = entry.get("day") or {}
            price = (
                last_trade.get("p")
                or entry.get("lastPrice")
                or entry.get("close")
                or entry.get("price")
            )
            volume_raw = day.get("v") or entry.get("volume")
            volume = int(volume_raw) if isinstance(volume_raw, int | float) else None

            normalized.append(
                {
                    "symbol": symbol,
                    "price": float(price) if price is not None else None,
                    "change": float(change) if change is not None else None,
                    "percent": float(percent),
                    "volume": volume,
                }
            )
        return normalized

    gainers = _normalize(gainers_raw)[:limit]
    losers = _normalize(losers_raw)[:limit]

    if not gainers and not losers:
        raise DataNotFoundError("No Polygon data available for top movers", provider="Polygon")

    return {"gainers": gainers, "losers": losers}
