"""Marketstack API client for EOD price fallback."""

from __future__ import annotations

from app.config import settings
from app.services.base_client import BaseAPIClient
from app.services.exceptions import AuthenticationError, DataNotFoundError


class MarketstackClient(BaseAPIClient):
    def __init__(self) -> None:
        if not settings.MARKETSTACK_API_KEY:
            raise AuthenticationError("Marketstack API key not configured", provider="Marketstack")

        super().__init__(
            base_url=settings.MARKETSTACK_API_BASE,
            provider_name="Marketstack",
            timeout=15.0,
        )
        self.api_key = settings.MARKETSTACK_API_KEY

    async def get_eod(self, symbol: str, limit: int = 1) -> list[dict]:
        params = {
            "access_key": self.api_key,
            "symbols": symbol.upper(),
            "limit": limit,
        }
        endpoint = "/eod"
        result = await self.get(endpoint, params=params)
        data = result.get("data") or []
        if not data:
            raise DataNotFoundError(f"No EOD data for {symbol}", provider="Marketstack")
        return data

    async def get_latest(self, symbol: str) -> dict:
        data = await self.get_eod(symbol, limit=1)
        return data[0]

    async def health_check(self) -> bool:
        try:
            await self.get_latest("SPY")
            return True
        except Exception:
            return False


marketstack_client: MarketstackClient | None

try:
    marketstack_client = MarketstackClient() if settings.MARKETSTACK_API_KEY else None
except AuthenticationError:
    marketstack_client = None
