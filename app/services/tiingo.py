"""
Tiingo API Client
Provides end-of-day (EOD) price data and IEX real-time quotes.

Documentation: https://api.tiingo.com/documentation/general/overview
"""

from datetime import date, datetime

from app.config import settings
from app.services.base_client import BaseAPIClient
from app.services.exceptions import AuthenticationError, DataNotFoundError


class TiingoClient(BaseAPIClient):
    """
    Tiingo API client for EOD data and real-time quotes.

    Features:
    - End-of-day price data (stocks, ETFs, mutual funds)
    - Intraday IEX data (real-time)
    - Historical price data
    - Metadata (ticker info, supported exchanges)
    """

    def __init__(self):
        if not settings.TIINGO_API_KEY:
            raise AuthenticationError(
                "Tiingo API key not configured",
                provider="Tiingo",
            )

        super().__init__(
            base_url=settings.TIINGO_API_BASE,
            provider_name="Tiingo",
            timeout=30.0,
        )
        self.api_key = settings.TIINGO_API_KEY

    def _get_headers(self) -> dict[str, str]:
        """Get headers with API key"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Token {self.api_key}",
        }

    async def get_ticker_metadata(self, ticker: str) -> dict:
        """
        Get metadata for a ticker.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL", "SPY")

        Returns:
            Ticker metadata including name, exchange, start/end dates

        Example response:
            {
                "ticker": "AAPL",
                "name": "Apple Inc",
                "exchangeCode": "NASDAQ",
                "startDate": "1980-12-12",
                "endDate": "2024-01-15",
                "description": "..."
            }
        """
        endpoint = f"/tiingo/daily/{ticker.upper()}"
        return await self.get(endpoint, headers=self._get_headers())

    async def get_eod_prices(
        self,
        ticker: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        """
        Get end-of-day historical prices.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date (default: 1 year ago)
            end_date: End date (default: today)

        Returns:
            List of daily OHLCV data

        Example response:
            [
                {
                    "date": "2024-01-15T00:00:00.000Z",
                    "close": 185.56,
                    "high": 186.40,
                    "low": 183.92,
                    "open": 184.35,
                    "volume": 50123456,
                    "adjClose": 185.56,
                    "adjHigh": 186.40,
                    "adjLow": 183.92,
                    "adjOpen": 184.35,
                    "adjVolume": 50123456,
                    "divCash": 0.0,
                    "splitFactor": 1.0
                }
            ]
        """
        endpoint = f"/tiingo/daily/{ticker.upper()}/prices"

        params = {}
        if start_date:
            params["startDate"] = start_date.isoformat()
        if end_date:
            params["endDate"] = end_date.isoformat()

        prices = await self.get(endpoint, headers=self._get_headers(), params=params)
        symbol = ticker.upper()
        if isinstance(prices, list):
            for item in prices:
                if isinstance(item, dict):
                    item.setdefault("symbol", symbol)
        return prices

    async def get_latest_price(self, ticker: str) -> dict:
        """
        Get the most recent EOD price.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Latest daily price data
        """
        prices = await self.get_eod_prices(ticker)
        if not prices:
            raise DataNotFoundError(
                f"No price data found for {ticker}",
                provider="Tiingo",
            )
        return prices[-1]  # Most recent is last

    async def get_iex_realtime_price(
        self,
        ticker: str,
    ) -> dict:
        """
        Get real-time IEX price data (intraday).

        Args:
            ticker: Stock ticker symbol

        Returns:
            Real-time price data

        Example response:
            {
                "ticker": "AAPL",
                "timestamp": "2024-01-15T15:59:00+00:00",
                "last": 185.56,
                "lastSize": 100,
                "tngoLast": 185.56,
                "prevClose": 184.35,
                "open": 184.50,
                "high": 186.40,
                "low": 183.92,
                "mid": 185.20,
                "volume": 50123456,
                "bidSize": 100,
                "bidPrice": 185.55,
                "askSize": 100,
                "askPrice": 185.57
            }
        """
        endpoint = f"/iex/{ticker.upper()}"
        result = await self.get(endpoint, headers=self._get_headers())

        # Tiingo returns a list with single item for latest quote
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return result

    async def get_iex_intraday_prices(
        self,
        ticker: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        resample_freq: str = "1min",
    ) -> list[dict]:
        """
        Get intraday price data from IEX.

        Args:
            ticker: Stock ticker symbol
            start_date: Start datetime
            end_date: End datetime
            resample_freq: Frequency (1min, 5min, 15min, 30min, 1hour)

        Returns:
            List of intraday OHLCV data

        Example response:
            [
                {
                    "date": "2024-01-15T09:30:00+00:00",
                    "open": 184.50,
                    "high": 184.75,
                    "low": 184.40,
                    "close": 184.60,
                    "volume": 125000
                }
            ]
        """
        endpoint = f"/iex/{ticker.upper()}/prices"

        params = {"resampleFreq": resample_freq}
        if start_date:
            params["startDate"] = start_date.isoformat()
        if end_date:
            params["endDate"] = end_date.isoformat()

        return await self.get(endpoint, headers=self._get_headers(), params=params)

    async def get_top_movers(self, list_type: str, limit: int = 10) -> list[dict]:
        """Return Tiingo top movers list (e.g., topgainers, toplosers)."""

        endpoint = "/tiingo/utilities/top"
        params = {"list": list_type, "limit": limit}
        return await self.get(endpoint, headers=self._get_headers(), params=params)

    async def health_check(self) -> bool:
        """Check if Tiingo API is accessible"""
        try:
            # Try to fetch a common ticker
            await self.get_ticker_metadata("SPY")
            return True
        except Exception:
            return False


# Global client instance
tiingo_client = TiingoClient() if settings.TIINGO_API_KEY else None
