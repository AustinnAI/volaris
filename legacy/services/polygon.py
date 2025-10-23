"""Polygon.io API client for ticker snapshots and reference data."""

from __future__ import annotations

from app.config import settings
from app.services.base_client import BaseAPIClient
from app.services.exceptions import AuthenticationError, DataNotFoundError


class PolygonClient(BaseAPIClient):
    def __init__(self) -> None:
        if not settings.POLYGON_API_KEY:
            raise AuthenticationError("Polygon API key not configured", provider="Polygon")

        super().__init__(
            base_url=settings.POLYGON_API_BASE,
            provider_name="Polygon",
            timeout=15.0,
        )
        self.api_key = settings.POLYGON_API_KEY

    async def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def get_top_movers(self, direction: str) -> list[dict]:
        if direction not in {"gainers", "losers"}:
            raise ValueError("direction must be 'gainers' or 'losers'")

        endpoint = f"/v2/snapshot/locale/us/markets/stocks/{direction}"
        result = await self.get(endpoint, headers=await self._headers())
        return result.get("tickers", [])

    async def get_sp500_constituents(self) -> list[str]:
        # Polygon provides S&P 500 constituents via reference tickers filtered by index
        params = {
            "market": "stocks",
            "index": "gspc",
            "active": "true",
            "limit": 1000,
        }
        endpoint = "/v3/reference/tickers"
        result = await self.get(endpoint, headers=await self._headers(), params=params)
        results = result.get("results") or []
        if not results:
            raise DataNotFoundError("No constituents returned from Polygon", provider="Polygon")
        return [item.get("ticker", "").upper() for item in results if item.get("ticker")]

    async def get_news(self, symbol: str, limit: int = 5) -> list[dict]:
        params = {
            "ticker": symbol.upper(),
            "limit": limit,
            "order": "desc",
            "sort": "published_utc",
        }
        endpoint = "/v2/reference/news"
        result = await self.get(endpoint, headers=await self._headers(), params=params)
        return result.get("results", [])


polygon_client: PolygonClient | None

try:
    polygon_client = PolygonClient() if settings.POLYGON_API_KEY else None
except AuthenticationError:
    polygon_client = None
