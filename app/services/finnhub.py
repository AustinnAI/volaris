"""
Finnhub API Client
Provides company fundamentals, news, and market sentiment.

Documentation: https://finnhub.io/docs/api
"""

from datetime import datetime, date
from typing import Dict, List, Optional
from app.config import settings
from app.services.base_client import BaseAPIClient
from app.services.exceptions import AuthenticationError, DataNotFoundError


class FinnhubClient(BaseAPIClient):
    """
    Finnhub API client for fundamentals and news.

    Features:
    - Company profile and fundamentals
    - Market news and sentiment
    - Earnings calendar
    - SEC filings
    - Insider transactions
    - Technical indicators
    """

    def __init__(self):
        if not settings.FINNHUB_API_KEY:
            raise AuthenticationError(
                "Finnhub API key not configured",
                provider="Finnhub",
            )

        super().__init__(
            base_url=settings.FINNHUB_API_BASE,
            provider_name="Finnhub",
            timeout=30.0,
        )
        self.api_key = settings.FINNHUB_API_KEY

    def _get_params(self, extra_params: Optional[Dict] = None) -> Dict:
        """Get query params with API key"""
        params = {"token": self.api_key}
        if extra_params:
            params.update(extra_params)
        return params

    async def get_company_profile(self, symbol: str) -> Dict:
        """
        Get company profile.

        Args:
            symbol: Stock symbol

        Returns:
            Company profile data

        Example response:
            {
                "country": "US",
                "currency": "USD",
                "exchange": "NASDAQ NMS - GLOBAL MARKET",
                "ipo": "1980-12-12",
                "marketCapitalization": 2800000,
                "name": "Apple Inc",
                "phone": "14089961010",
                "shareOutstanding": 15550.061,
                "ticker": "AAPL",
                "weburl": "https://www.apple.com/",
                "logo": "https://static.finnhub.io/logo/...",
                "finnhubIndustry": "Technology"
            }
        """
        endpoint = "/stock/profile2"
        params = self._get_params({"symbol": symbol.upper()})
        return await self.get(endpoint, params=params)

    async def get_company_news(
        self,
        symbol: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> List[Dict]:
        """
        Get company news.

        Args:
            symbol: Stock symbol
            from_date: Start date (default: 30 days ago)
            to_date: End date (default: today)

        Returns:
            List of news articles

        Example response:
            [
                {
                    "category": "company news",
                    "datetime": 1610000000,
                    "headline": "Apple announces new product",
                    "id": 12345,
                    "image": "https://image.url",
                    "related": "AAPL",
                    "source": "Reuters",
                    "summary": "Apple Inc announced...",
                    "url": "https://article.url"
                }
            ]
        """
        endpoint = "/company-news"

        # Default to last 30 days if not specified
        if not from_date:
            from datetime import timedelta

            from_date = date.today() - timedelta(days=30)
        if not to_date:
            to_date = date.today()

        params = self._get_params(
            {
                "symbol": symbol.upper(),
                "from": from_date.isoformat(),
                "to": to_date.isoformat(),
            }
        )

        return await self.get(endpoint, params=params)

    async def get_market_news(
        self,
        category: str = "general",
        min_id: Optional[int] = None,
    ) -> List[Dict]:
        """
        Get general market news.

        Args:
            category: News category (general, forex, crypto, merger)
            min_id: Minimum news ID for pagination

        Returns:
            List of news articles
        """
        endpoint = "/news"
        params = self._get_params({"category": category})

        if min_id:
            params["minId"] = min_id

        return await self.get(endpoint, params=params)

    async def get_basic_financials(
        self,
        symbol: str,
        metric: str = "all",
    ) -> Dict:
        """
        Get company basic financials and metrics.

        Args:
            symbol: Stock symbol
            metric: Metric type (all, or specific metric)

        Returns:
            Financial metrics

        Example response:
            {
                "metric": {
                    "10DayAverageTradingVolume": 50000000,
                    "52WeekHigh": 200.00,
                    "52WeekLow": 150.00,
                    "52WeekLowDate": "2023-01-15",
                    "52WeekPriceReturnDaily": 0.25,
                    "beta": 1.2,
                    "marketCapitalization": 2800000,
                    "peNormalizedAnnual": 28.5
                },
                "series": {
                    "annual": {...},
                    "quarterly": {...}
                }
            }
        """
        endpoint = "/stock/metric"
        params = self._get_params(
            {
                "symbol": symbol.upper(),
                "metric": metric,
            }
        )
        return await self.get(endpoint, params=params)

    async def get_earnings_calendar(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        symbol: Optional[str] = None,
    ) -> Dict:
        """
        Get earnings calendar.

        Args:
            from_date: Start date
            to_date: End date
            symbol: Filter by symbol (optional)

        Returns:
            Earnings calendar data

        Example response:
            {
                "earningsCalendar": [
                    {
                        "date": "2024-01-30",
                        "epsActual": 2.10,
                        "epsEstimate": 2.05,
                        "hour": "amc",  # after market close
                        "quarter": 1,
                        "revenueActual": 120000000000,
                        "revenueEstimate": 118000000000,
                        "symbol": "AAPL",
                        "year": 2024
                    }
                ]
            }
        """
        endpoint = "/calendar/earnings"

        params = {}
        if from_date:
            params["from"] = from_date.isoformat()
        if to_date:
            params["to"] = to_date.isoformat()
        if symbol:
            params["symbol"] = symbol.upper()

        params = self._get_params(params)
        return await self.get(endpoint, params=params)

    async def get_quote(self, symbol: str) -> Dict:
        """
        Get real-time quote.

        Args:
            symbol: Stock symbol

        Returns:
            Quote data

        Example response:
            {
                "c": 185.56,  # Current price
                "d": 1.21,    # Change
                "dp": 0.66,   # Percent change
                "h": 186.40,  # High
                "l": 183.92,  # Low
                "o": 184.35,  # Open
                "pc": 184.35, # Previous close
                "t": 1610000000  # Timestamp
            }
        """
        endpoint = "/quote"
        params = self._get_params({"symbol": symbol.upper()})
        return await self.get(endpoint, params=params)

    async def get_recommendation_trends(self, symbol: str) -> List[Dict]:
        """
        Get analyst recommendation trends.

        Args:
            symbol: Stock symbol

        Returns:
            List of recommendation trends

        Example response:
            [
                {
                    "buy": 15,
                    "hold": 8,
                    "period": "2024-01-01",
                    "sell": 2,
                    "strongBuy": 10,
                    "strongSell": 0,
                    "symbol": "AAPL"
                }
            ]
        """
        endpoint = "/stock/recommendation"
        params = self._get_params({"symbol": symbol.upper()})
        return await self.get(endpoint, params=params)

    async def get_insider_transactions(
        self,
        symbol: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> Dict:
        """
        Get insider transactions.

        Args:
            symbol: Stock symbol
            from_date: Start date
            to_date: End date

        Returns:
            Insider transaction data
        """
        endpoint = "/stock/insider-transactions"

        params = {"symbol": symbol.upper()}
        if from_date:
            params["from"] = from_date.isoformat()
        if to_date:
            params["to"] = to_date.isoformat()

        params = self._get_params(params)
        return await self.get(endpoint, params=params)

    async def get_index_constituents(self, index_symbol: str) -> Dict:
        """Return constituents for a specific index (e.g., ^GSPC)."""
        endpoint = "/index/constituents"
        params = self._get_params({"symbol": index_symbol})
        return await self.get(endpoint, params=params)

    async def get_news_sentiment(self, symbol: str) -> Dict:
        """Return news sentiment statistics for a symbol."""
        endpoint = "/news-sentiment"
        params = self._get_params({"symbol": symbol.upper()})
        return await self.get(endpoint, params=params)

    async def health_check(self) -> bool:
        """Check if Finnhub API is accessible"""
        try:
            # Try to get a quote for SPY
            await self.get_quote("SPY")
            return True
        except Exception:
            return False


# Global client instance
finnhub_client = FinnhubClient() if settings.FINNHUB_API_KEY else None
