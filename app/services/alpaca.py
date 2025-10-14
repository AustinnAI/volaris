"""
Alpaca API Client
Provides minute-delayed historical market data.

Documentation: https://alpaca.markets/docs/market-data/
"""

from datetime import datetime

from app.config import settings
from app.services.base_client import BaseAPIClient
from app.services.exceptions import AuthenticationError


class AlpacaClient(BaseAPIClient):
    """
    Alpaca Markets API client for minute-delayed historical data.

    Features:
    - Historical bars (1min, 5min, 15min, 1hour, 1day)
    - Latest quotes and trades
    - Market snapshots
    - Multi-symbol batch requests
    """

    def __init__(self):
        if not settings.ALPACA_API_KEY or not settings.ALPACA_API_SECRET:
            raise AuthenticationError(
                "Alpaca API credentials not configured",
                provider="Alpaca",
            )

        super().__init__(
            base_url=settings.ALPACA_API_BASE,
            provider_name="Alpaca",
            timeout=30.0,
        )
        self.api_key = settings.ALPACA_API_KEY
        self.api_secret = settings.ALPACA_API_SECRET

    def _get_headers(self) -> dict[str, str]:
        """Get headers with API credentials"""
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
        }

    async def get_bars(
        self,
        symbol: str,
        timeframe: str = "1Min",
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict]:
        """
        Get historical price bars.

        Args:
            symbol: Stock symbol (e.g., "AAPL", "SPY")
            timeframe: Bar timeframe (1Min, 5Min, 15Min, 1Hour, 1Day)
            start: Start datetime (RFC3339 format or datetime object)
            end: End datetime
            limit: Max number of bars (default: 1000, max: 10000)

        Returns:
            List of OHLCV bars

        Example response:
            {
                "bars": [
                    {
                        "t": "2024-01-15T09:30:00Z",
                        "o": 184.50,
                        "h": 184.75,
                        "l": 184.40,
                        "c": 184.60,
                        "v": 125000,
                        "n": 1234,
                        "vw": 184.55
                    }
                ]
            }
        """
        endpoint = f"/v2/stocks/{symbol.upper()}/bars"

        params = {
            "timeframe": timeframe,
            "limit": min(limit, 10000),
        }

        if start:
            params["start"] = start.isoformat() if isinstance(start, datetime) else start
        if end:
            params["end"] = end.isoformat() if isinstance(end, datetime) else end

        result = await self.get(endpoint, headers=self._get_headers(), params=params)
        return result.get("bars", [])

    async def get_latest_bar(self, symbol: str) -> dict:
        """
        Get the most recent bar for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Latest bar data
        """
        endpoint = f"/v2/stocks/{symbol.upper()}/bars/latest"
        result = await self.get(endpoint, headers=self._get_headers())
        return result.get("bar", {})

    async def get_latest_quote(self, symbol: str) -> dict:
        """
        Get the latest quote (bid/ask).

        Args:
            symbol: Stock symbol

        Returns:
            Latest quote data

        Example response:
            {
                "quote": {
                    "t": "2024-01-15T15:59:00Z",
                    "ax": "Q",  # Ask exchange
                    "ap": 185.57,  # Ask price
                    "as": 100,  # Ask size
                    "bx": "Q",  # Bid exchange
                    "bp": 185.55,  # Bid price
                    "bs": 100,  # Bid size
                    "c": ["R"]  # Conditions
                }
            }
        """
        endpoint = f"/v2/stocks/{symbol.upper()}/quotes/latest"
        result = await self.get(endpoint, headers=self._get_headers())
        return result.get("quote", {})

    async def get_latest_trade(self, symbol: str) -> dict:
        """
        Get the latest trade.

        Args:
            symbol: Stock symbol

        Returns:
            Latest trade data
        """
        endpoint = f"/v2/stocks/{symbol.upper()}/trades/latest"
        result = await self.get(endpoint, headers=self._get_headers())
        return result.get("trade", {})

    async def get_snapshot(self, symbol: str) -> dict:
        """
        Get market snapshot (latest quote, trade, minute bar, daily bar).

        Args:
            symbol: Stock symbol

        Returns:
            Complete market snapshot

        Example response:
            {
                "symbol": "AAPL",
                "latestTrade": {...},
                "latestQuote": {...},
                "minuteBar": {...},
                "dailyBar": {...},
                "prevDailyBar": {...}
            }
        """
        endpoint = f"/v2/stocks/{symbol.upper()}/snapshot"
        result = await self.get(endpoint, headers=self._get_headers())
        return result.get("snapshot", result)

    async def get_multi_bars(
        self,
        symbols: list[str],
        timeframe: str = "1Min",
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
    ) -> dict[str, list[dict]]:
        """
        Get bars for multiple symbols in a single request.

        Args:
            symbols: List of stock symbols
            timeframe: Bar timeframe
            start: Start datetime
            end: End datetime
            limit: Max bars per symbol

        Returns:
            Dict mapping symbols to their bar data
        """
        endpoint = "/v2/stocks/bars"

        params = {
            "symbols": ",".join(s.upper() for s in symbols),
            "timeframe": timeframe,
            "limit": min(limit, 10000),
        }

        if start:
            params["start"] = start.isoformat() if isinstance(start, datetime) else start
        if end:
            params["end"] = end.isoformat() if isinstance(end, datetime) else end

        result = await self.get(endpoint, headers=self._get_headers(), params=params)
        return result.get("bars", {})

    async def health_check(self) -> bool:
        """Check if Alpaca API is accessible"""
        try:
            # Try to fetch latest quote for SPY
            await self.get_latest_quote("SPY")
            return True
        except Exception:
            return False


# Global client instance
alpaca_client = AlpacaClient() if (settings.ALPACA_API_KEY and settings.ALPACA_API_SECRET) else None
