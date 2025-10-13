"""
Async API clients used by the Discord bot.

These lightweight wrappers keep HTTP concerns outside of cog command logic and
provide consistent error handling for the Volaris REST API.
"""

from __future__ import annotations

from typing import Any, Optional

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

    async def recommend_strategy(
        self,
        symbol: str,
        bias: str,
        dte: int,
        mode: str = "auto",
        max_risk: Optional[float] = None,
        account_size: Optional[float] = None,
        bias_reason: Optional[str] = None,
    ) -> dict[str, Any]:
        """Call the strategy recommendation endpoint and return the JSON payload."""
        url = f"{self.base_url}/api/v1/strategy/recommend"
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

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
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

    async def create_alert(
        self,
        symbol: str,
        target_price: float,
        direction: str,
        channel_id: int,
        created_by: Optional[int] = None,
    ) -> dict[str, Any]:
        """Create a price alert."""
        url = f"{self.base_url}/api/v1/alerts/price"
        payload: dict[str, Any] = {
            "symbol": symbol.upper(),
            "target_price": target_price,
            "direction": direction,
            "channel_id": str(channel_id),
        }
        if created_by:
            payload["created_by"] = str(created_by)

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url, json=payload) as response:
                data = await response.json()
                if response.status not in (200, 201):
                    raise aiohttp.ClientError(data.get("detail", "Failed to create alert"))
                return data

    async def delete_alert(self, alert_id: int) -> None:
        """Delete a price alert."""
        url = f"{self.base_url}/api/v1/alerts/price/{alert_id}"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
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
        url = f"{self.base_url}/api/v1/alerts/price"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url) as response:
                data = await response.json()
                if response.status != 200:
                    raise aiohttp.ClientError(data.get("detail", "Failed to fetch alerts"))
                alerts = data.get("alerts", [])
                return alerts if isinstance(alerts, list) else []

    async def evaluate_alerts(self) -> list[dict[str, Any]]:
        """Evaluate server alerts and return any triggers."""
        url = f"{self.base_url}/api/v1/alerts/price/evaluate"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url) as response:
                data = await response.json()
                if response.status != 200:
                    raise aiohttp.ClientError(data.get("detail", "Failed to evaluate alerts"))
                triggered = data.get("triggered", [])
                return triggered if isinstance(triggered, list) else []


class PriceStreamAPI:
    """Client wrapper for managing recurring price streams."""

    def __init__(self, base_url: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def create_stream(
        self,
        symbol: str,
        channel_id: int,
        interval_seconds: int,
        created_by: Optional[int] = None,
    ) -> dict[str, Any]:
        """Create a price stream."""
        url = f"{self.base_url}/api/v1/streams/price"
        payload: dict[str, Any] = {
            "symbol": symbol.upper(),
            "channel_id": str(channel_id),
            "interval_seconds": interval_seconds,
        }
        if created_by:
            payload["created_by"] = str(created_by)

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url, json=payload) as response:
                data = await response.json()
                if response.status not in (200, 201):
                    raise aiohttp.ClientError(data.get("detail", "Failed to create stream"))
                return data

    async def list_streams(self) -> list[dict[str, Any]]:
        """Return all configured price streams."""
        url = f"{self.base_url}/api/v1/streams/price"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url) as response:
                data = await response.json()
                if response.status != 200:
                    raise aiohttp.ClientError(data.get("detail", "Failed to fetch streams"))
                streams = data.get("streams", [])
                return streams if isinstance(streams, list) else []

    async def delete_stream(self, stream_id: int) -> None:
        """Delete a price stream."""
        url = f"{self.base_url}/api/v1/streams/price/{stream_id}"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
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
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url) as response:
                data = await response.json()
                if response.status != 200:
                    raise aiohttp.ClientError(data.get("detail", "Failed to evaluate streams"))
                streams = data.get("streams", [])
                return streams if isinstance(streams, list) else []


class MarketInsightsAPI:
    """Client wrapper for sentiment and market insight endpoints."""

    def __init__(self, base_url: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def fetch_sentiment(self, symbol: str) -> dict[str, Any]:
        """Return ticker sentiment data."""
        url = f"{self.base_url}/api/v1/market/sentiment/{symbol.upper()}"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url) as response:
                data = await response.json()
                if response.status != 200:
                    raise aiohttp.ClientError(data.get("detail", "Failed to fetch sentiment"))
                return data

    async def fetch_top_movers(self, limit: int) -> dict[str, Any]:
        """Return top gainers/losers for the S&P 500."""
        url = f"{self.base_url}/api/v1/market/top?limit={limit}"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url) as response:
                data = await response.json()
                if response.status != 200:
                    raise aiohttp.ClientError(data.get("detail", "Failed to fetch top movers"))
                return data

    async def fetch_sp500_symbols(self) -> list[str]:
        """Return the list of S&P 500 constituents."""
        url = f"{self.base_url}/api/v1/market/sp500"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url) as response:
                data = await response.json()
                if response.status != 200:
                    raise aiohttp.ClientError(data.get("detail", "Failed to fetch constituents"))
                symbols = data.get("symbols", [])
                return symbols if isinstance(symbols, list) else []

    async def refresh_price(self, symbol: str) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1/market/refresh/price/{symbol.upper()}"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url) as response:
                data = await response.json()
                if response.status not in (200, 202):
                    raise aiohttp.ClientError(data.get("detail", "Failed to refresh price"))
                return data

    async def refresh_option_chain(self, symbol: str) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1/market/refresh/options/{symbol.upper()}"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url) as response:
                data = await response.json()
                if response.status not in (200, 202):
                    raise aiohttp.ClientError(data.get("detail", "Failed to refresh option chain"))
                return data

    async def refresh_iv_metrics(self, symbol: str) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1/market/refresh/iv/{symbol.upper()}"
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url) as response:
                data = await response.json()
                if response.status not in (200, 202):
                    raise aiohttp.ClientError(data.get("detail", "Failed to refresh IV metrics"))
                return data
