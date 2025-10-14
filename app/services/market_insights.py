"""Higher-level market insight helpers (sentiment, top movers)."""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from app.config import settings
from app.services.exceptions import DataNotFoundError
from app.services.finnhub import finnhub_client
from app.services.polygon import polygon_client
from app.utils.cache import cache


async def fetch_sentiment(symbol: str) -> Dict:
    symbol_upper = symbol.upper()
    cache_key = f"sentiment:{symbol_upper}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    if not finnhub_client:
        raise DataNotFoundError("Finnhub client not configured", provider="Finnhub")

    recommendations_raw = await finnhub_client.get_recommendation_trends(symbol_upper)
    news_raw: List[Dict] = []
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

    def _weighted_score(strong: int, regular: int) -> Optional[float]:
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


async def get_top_movers(limit: int, sp500_symbols: Set[str]) -> Dict[str, List[Dict]]:
    if not polygon_client:
        raise DataNotFoundError(
            "Polygon client not configured for top movers",
            provider="Polygon",
        )

    raw_gainers = await polygon_client.get_top_movers("gainers")
    raw_losers = await polygon_client.get_top_movers("losers")

    def _to_float(value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _map(entry: Dict) -> Dict:
        return {
            "symbol": entry.get("ticker"),
            "price": _to_float(
                entry.get("lastTrade", {}).get("p") or entry.get("lastQuote", {}).get("p")
            ),
            "change": _to_float(entry.get("todaysChange")),
            "percent": _to_float(entry.get("todaysChangePerc")),
            "volume": entry.get("day", {}).get("v"),
        }

    gainers = [_map(item) for item in raw_gainers if item.get("ticker") in sp500_symbols][:limit]

    losers = [_map(item) for item in raw_losers if item.get("ticker") in sp500_symbols][:limit]

    return {"gainers": gainers, "losers": losers}
