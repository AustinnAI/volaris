"""
Async API clients used by the Discord bot.

These lightweight wrappers keep HTTP concerns outside of cog command logic and
provide consistent error handling for the Volaris REST API.
"""

from __future__ import annotations

from typing import Any

import aiohttp


class StrategyRecommendationAPI:
    """Client wrapper for calling the Volaris strategy recommendation API."""

    def __init__(self, base_url: str, timeout: int = 30) -> None:
        """
        Initialize API client.

        Args:
            base_url: Base URL of the Volaris API (e.g., http://localhost:8000).
            timeout: Total request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        """Close the HTTP session and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def recommend_strategy(
        self,
        symbol: str,
        bias: str,
        dte: int,
        mode: str = "auto",
        max_risk: float | None = None,
        account_size: float | None = None,
        bias_reason: str | None = None,
    ) -> dict[str, Any]:
        """Call the strategy recommendation endpoint and return the JSON payload."""
        url = f"{self.base_url}/strategy/recommend"
        body: dict[str, Any] = {
            "underlying_symbol": symbol.upper(),
            "bias": bias,
            "target_dte": dte,
            "dte_tolerance": 3,
        }

        objectives: dict[str, Any] = {}
        constraints: dict[str, Any] = {}

        if account_size is not None:
            objectives["account_size"] = account_size

        if max_risk is not None:
            objectives["max_risk_per_trade"] = max_risk

        if bias_reason:
            objectives["bias_reason"] = bias_reason

        if mode == "credit":
            objectives["prefer_credit"] = True
            constraints["min_credit_pct"] = 25
        elif mode == "debit":
            objectives["prefer_credit"] = False

        if objectives:
            body["objectives"] = objectives

        if constraints:
            body["constraints"] = constraints

        session = await self._get_session()
        async with session.post(url, json=body) as response:
            if response.status == 404:
                data = await response.json()
                raise ValueError(data.get("detail", "No data available"))
            if response.status != 200:
                try:
                    data = await response.json()
                    error_msg = data.get("detail", f"HTTP {response.status}")
                except Exception:  # pylint: disable=broad-except
                    error_msg = f"HTTP {response.status}"
                raise aiohttp.ClientError(f"API error: {error_msg}")

            return await response.json()


class PriceAlertAPI:
    """Client wrapper for managing price alerts via the Volaris REST API."""

    def __init__(self, base_url: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        """Close the HTTP session and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def create_alert(
        self,
        symbol: str,
        target_price: float,
        direction: str,
        channel_id: int,
        created_by: int | None = None,
    ) -> dict[str, Any]:
        """Create a price alert."""
        url = f"{self.base_url}/alerts/price"
        payload: dict[str, Any] = {
            "symbol": symbol.upper(),
            "target_price": target_price,
            "direction": direction,
            "channel_id": str(channel_id),
        }
        if created_by:
            payload["created_by"] = str(created_by)

        session = await self._get_session()
        async with session.post(url, json=payload) as response:
            data = await response.json()
            if response.status not in (200, 201):
                raise aiohttp.ClientError(data.get("detail", "Failed to create alert"))
            return data

    async def delete_alert(self, alert_id: int) -> None:
        """Delete a price alert."""
        url = f"{self.base_url}/api/v1/alerts/price/{alert_id}"
        session = await self._get_session()
        async with session.delete(url) as response:
            if response.status == 204:
                return
            try:
                data = await response.json()
                message = data.get("detail", f"Failed to delete alert {alert_id}")
            except Exception:  # pylint: disable=broad-except
                message = f"Failed to delete alert {alert_id}"
            raise aiohttp.ClientError(message)

    async def list_alerts(self) -> list[dict[str, Any]]:
        """Return active server alerts."""
        url = f"{self.base_url}/alerts/price"
        session = await self._get_session()
        async with session.get(url) as response:
            data = await response.json()
            if response.status != 200:
                raise aiohttp.ClientError(data.get("detail", "Failed to fetch alerts"))
            alerts = data.get("alerts", [])
            return alerts if isinstance(alerts, list) else []

    async def evaluate_alerts(self) -> list[dict[str, Any]]:
        """Evaluate server alerts and return any triggers."""
        url = f"{self.base_url}/api/v1/alerts/price/evaluate"
        session = await self._get_session()
        async with session.post(url) as response:
            # Handle 502/503 (service not ready yet) gracefully
            if response.status in (502, 503):
                return []
            try:
                data = await response.json()
            except Exception:  # pylint: disable=broad-except
                # If response is HTML (service error), return empty
                return []
            if response.status == 404:
                # No alerts configured - return empty list
                return []
            if response.status != 200:
                raise aiohttp.ClientError(data.get("detail", "Failed to evaluate alerts"))
            triggered = data.get("triggered", [])
            return triggered if isinstance(triggered, list) else []


class PriceStreamAPI:
    """Client wrapper for managing recurring price streams."""

    def __init__(self, base_url: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        """Close the HTTP session and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def create_stream(
        self,
        symbol: str,
        channel_id: int,
        interval_seconds: int,
        created_by: int | None = None,
    ) -> dict[str, Any]:
        """Create a price stream."""
        url = f"{self.base_url}/streams/price"
        payload: dict[str, Any] = {
            "symbol": symbol.upper(),
            "channel_id": str(channel_id),
            "interval_seconds": interval_seconds,
        }
        if created_by:
            payload["created_by"] = str(created_by)

        session = await self._get_session()
        async with session.post(url, json=payload) as response:
            data = await response.json()
            if response.status not in (200, 201):
                raise aiohttp.ClientError(data.get("detail", "Failed to create stream"))
            return data

    async def list_streams(self) -> list[dict[str, Any]]:
        """Return all configured price streams."""
        url = f"{self.base_url}/streams/price"
        session = await self._get_session()
        async with session.get(url) as response:
            data = await response.json()
            if response.status != 200:
                raise aiohttp.ClientError(data.get("detail", "Failed to fetch streams"))
            streams = data.get("streams", [])
            return streams if isinstance(streams, list) else []

    async def delete_stream(self, stream_id: int) -> None:
        """Delete a price stream."""
        url = f"{self.base_url}/api/v1/streams/price/{stream_id}"
        session = await self._get_session()
        async with session.delete(url) as response:
            if response.status == 204:
                return
            try:
                data = await response.json()
                message = data.get("detail", f"Failed to delete stream {stream_id}")
            except Exception:  # pylint: disable=broad-except
                message = f"Failed to delete stream {stream_id}"
            raise aiohttp.ClientError(message)

    async def evaluate_streams(self) -> list[dict[str, Any]]:
        """Evaluate active streams and return payloads to broadcast."""
        url = f"{self.base_url}/api/v1/streams/price/evaluate"
        session = await self._get_session()
        async with session.post(url) as response:
            # Handle 502/503 (service not ready yet) gracefully
            if response.status in (502, 503):
                return []
            try:
                data = await response.json()
            except Exception:  # pylint: disable=broad-except
                # If response is HTML (service error), return empty
                return []
            if response.status == 404:
                # No streams configured - return empty list
                return []
            if response.status != 200:
                raise aiohttp.ClientError(data.get("detail", "Failed to evaluate streams"))
            streams = data.get("streams", [])
            return streams if isinstance(streams, list) else []


class VolatilityAPI:
    """Client wrapper for volatility analytics endpoints."""

    def __init__(self, base_url: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        """Close the HTTP session and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def fetch_overview(self, symbol: str) -> dict[str, Any]:
        """Return full volatility overview (summary, term structure, skew, EM)."""
        url = f"{self.base_url}/vol/overview/{symbol.upper()}"
        session = await self._get_session()
        async with session.get(url) as response:
            data = await response.json()
            if response.status != 200:
                raise aiohttp.ClientError(data.get("detail", "Failed to fetch volatility overview"))
            return data

    async def fetch_expected_move(self, symbol: str) -> dict[str, Any]:
        """Return expected move estimates for the symbol."""
        url = f"{self.base_url}/vol/expected-move/{symbol.upper()}"
        session = await self._get_session()
        async with session.get(url) as response:
            data = await response.json()
            if response.status != 200:
                raise aiohttp.ClientError(data.get("detail", "Failed to fetch expected move"))
            return data

    async def fetch_iv_summary(self, symbol: str) -> dict[str, Any]:
        """Return IV summary metrics for the symbol."""
        url = f"{self.base_url}/vol/iv/{symbol.upper()}"
        session = await self._get_session()
        async with session.get(url) as response:
            data = await response.json()
            if response.status != 200:
                raise aiohttp.ClientError(data.get("detail", "Failed to fetch IV metrics"))
            return data


class MarketInsightsAPI:
    """Client wrapper for sentiment, market refresh, and watchlist endpoints."""

    def __init__(self, base_url: str, timeout: int = 30, api_token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.api_token = api_token.strip() if api_token else None
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        """Close the HTTP session and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_token}"} if self.api_token else {}

    async def fetch_sentiment(self, symbol: str) -> dict[str, Any]:
        """Return ticker sentiment data."""
        url = f"{self.base_url}/market/sentiment/{symbol.upper()}"
        session = await self._get_session()
        async with session.get(url, headers=self._auth_headers()) as response:
            data = await response.json()
            if response.status != 200:
                raise aiohttp.ClientError(data.get("detail", "Failed to fetch sentiment"))
            return data

    async def fetch_top_movers(self, limit: int) -> dict[str, Any]:
        """Return top gainers/losers for the S&P 500."""
        url = f"{self.base_url}/market/top?limit={limit}"
        session = await self._get_session()
        async with session.get(url, headers=self._auth_headers()) as response:
            data = await response.json()
            if response.status != 200:
                raise aiohttp.ClientError(data.get("detail", "Failed to fetch top movers"))
            return data

    async def fetch_sp500_symbols(self) -> list[str]:
        """Return the list of S&P 500 constituents."""
        url = f"{self.base_url}/market/sp500"
        session = await self._get_session()
        async with session.get(url, headers=self._auth_headers()) as response:
            data = await response.json()
            if response.status != 200:
                raise aiohttp.ClientError(data.get("detail", "Failed to fetch constituents"))
            symbols = data.get("symbols", [])
            return symbols if isinstance(symbols, list) else []

    async def get_watchlist(self) -> list[str]:
        """Fetch the server-side watchlist."""
        url = f"{self.base_url}/watchlist"
        session = await self._get_session()
        async with session.get(url, headers=self._auth_headers()) as response:
            data = await response.json()
            if response.status != 200:
                raise aiohttp.ClientError(data.get("detail", "Failed to fetch watchlist"))
            symbols = data.get("symbols", [])
            return symbols if isinstance(symbols, list) else []

    async def set_watchlist(self, symbols: list[str]) -> list[str]:
        """Persist a new server watchlist."""
        url = f"{self.base_url}/watchlist"
        payload = {"symbols": symbols}
        headers = {"Content-Type": "application/json", **self._auth_headers()}
        session = await self._get_session()
        async with session.post(url, headers=headers, json=payload) as response:
            data = await response.json()
            if response.status != 200:
                raise aiohttp.ClientError(data.get("detail", "Failed to update watchlist"))
            updated = data.get("symbols", [])
            return updated if isinstance(updated, list) else []

    async def refresh_price(self, symbol: str) -> dict[str, Any]:
        url = f"{self.base_url}/market/refresh/price/{symbol.upper()}"
        session = await self._get_session()
        async with session.post(url, headers=self._auth_headers()) as response:
            data = await response.json()
            if response.status not in (200, 202):
                raise aiohttp.ClientError(data.get("detail", "Failed to refresh price"))
            return data

    async def refresh_option_chain(self, symbol: str) -> dict[str, Any]:
        url = f"{self.base_url}/market/refresh/options/{symbol.upper()}"
        session = await self._get_session()
        async with session.post(url, headers=self._auth_headers()) as response:
            data = await response.json()
            if response.status not in (200, 202):
                raise aiohttp.ClientError(data.get("detail", "Failed to refresh option chain"))
            return data

    async def refresh_iv_metrics(self, symbol: str) -> dict[str, Any]:
        url = f"{self.base_url}/market/refresh/iv/{symbol.upper()}"
        session = await self._get_session()
        async with session.post(url, headers=self._auth_headers()) as response:
            data = await response.json()
            if response.status not in (200, 202):
                raise aiohttp.ClientError(data.get("detail", "Failed to refresh IV metrics"))
            return data

    async def refresh_watchlist(self) -> dict[str, Any]:
        """Trigger refresh for the stored watchlist."""
        url = f"{self.base_url}/market/refresh/watchlist"
        headers = {"Content-Type": "application/json", **self._auth_headers()}
        session = await self._get_session()
        async with session.post(url, headers=headers) as response:
            data = await response.json()
            if response.status not in (200, 202):
                raise aiohttp.ClientError(data.get("detail", "Failed to refresh watchlist"))
            return data


class NewsAPI:
    """Client wrapper for Phase 2 News & Sentiment API."""

    def __init__(self, base_url: str, api_token: str = "", timeout: int = 30) -> None:
        """
        Initialize News API client.

        Args:
            base_url: Base URL of the Volaris API.
            api_token: Optional bearer token for authenticated endpoints.
            timeout: Total request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        """Close the HTTP session and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _auth_headers(self) -> dict[str, str]:
        """Return authorization headers if token is available."""
        return {"Authorization": f"Bearer {self.api_token}"} if self.api_token else {}

    async def get_news(self, symbol: str, limit: int = 10, days: int = 7) -> dict[str, Any]:
        """
        Get recent news articles with sentiment for a ticker.

        Args:
            symbol: Ticker symbol (e.g., AAPL).
            limit: Maximum number of articles to return (1-100).
            days: Lookback period in days (1-30).

        Returns:
            Response with articles and sentiment scores.
        """
        url = f"{self.base_url}/api/v1/news/{symbol.upper()}"
        params = {"limit": min(max(limit, 1), 100), "days": min(max(days, 1), 30)}
        session = await self._get_session()
        async with session.get(url, params=params) as response:
            data = await response.json()
            if response.status != 200:
                raise aiohttp.ClientError(
                    data.get("detail", f"Failed to fetch news: HTTP {response.status}")
                )
            return data

    async def get_sentiment(self, symbol: str, days: int = 7) -> dict[str, Any]:
        """
        Get aggregated news sentiment for a ticker.

        Args:
            symbol: Ticker symbol (e.g., AAPL).
            days: Lookback period in days (1-30).

        Returns:
            Aggregated sentiment scores with bullish/bearish percentages.
        """
        url = f"{self.base_url}/api/v1/news/{symbol.upper()}/sentiment"
        params = {"days": min(max(days, 1), 30)}
        session = await self._get_session()
        async with session.get(url, params=params) as response:
            data = await response.json()
            if response.status != 200:
                raise aiohttp.ClientError(
                    data.get("detail", f"Failed to fetch sentiment: HTTP {response.status}")
                )
            return data

    async def refresh_news(self, symbol: str, days: int = 7) -> dict[str, Any]:
        """
        Force refresh news articles for a ticker.

        Args:
            symbol: Ticker symbol (e.g., AAPL).
            days: Lookback period in days (1-30).

        Returns:
            Refresh result with count of new articles.
        """
        url = f"{self.base_url}/api/v1/news/{symbol.upper()}/refresh"
        params = {"days": min(max(days, 1), 30)}
        headers = {"Content-Type": "application/json", **self._auth_headers()}
        session = await self._get_session()
        async with session.post(url, params=params, headers=headers) as response:
            data = await response.json()
            if response.status != 200:
                raise aiohttp.ClientError(
                    data.get("detail", f"Failed to refresh news: HTTP {response.status}")
                )
            return data
