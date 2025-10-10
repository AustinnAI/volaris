"""
Databento API Client
Provides high-quality historical market data backfills.

Documentation: https://databento.com/docs/api-reference-historical
"""

from datetime import date, datetime
from typing import Dict, List, Optional
from app.config import settings
from app.services.base_client import BaseAPIClient
from app.services.exceptions import AuthenticationError, DataNotFoundError


class DatabentoClient(BaseAPIClient):
    """
    Databento API client for historical data backfills.

    Features:
    - High-quality historical OHLCV data
    - Trade and quote (MBO/MBP) data
    - Multiple datasets (XNAS, OPRA, etc.)
    - Time-series data export
    """

    def __init__(self):
        if not settings.DATABENTO_API_KEY:
            raise AuthenticationError(
                "Databento API key not configured",
                provider="Databento",
            )

        super().__init__(
            base_url=settings.DATABENTO_API_BASE,
            provider_name="Databento",
            timeout=60.0,  # Longer timeout for historical data
        )
        self.api_key = settings.DATABENTO_API_KEY

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with API key"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def get_timeseries(
        self,
        dataset: str,
        symbols: List[str],
        schema: str,
        start: date,
        end: Optional[date] = None,
        stype_in: str = "raw_symbol",
    ) -> Dict:
        """
        Get historical time-series data.

        Args:
            dataset: Dataset code (e.g., "XNAS.ITCH", "OPRA.PILLAR")
            symbols: List of symbols
            schema: Data schema (ohlcv-1m, ohlcv-1d, trades, mbp-1, etc.)
            start: Start date
            end: End date (default: start date)
            stype_in: Symbol type (raw_symbol, instrument_id, etc.)

        Returns:
            Time-series data response

        Example schemas:
            - "ohlcv-1m": 1-minute OHLCV bars
            - "ohlcv-1d": Daily OHLCV bars
            - "trades": Trade data
            - "mbp-1": Market-by-price level 1
        """
        endpoint = "/v0/timeseries.get_range"

        params = {
            "dataset": dataset,
            "symbols": ",".join(symbols),
            "schema": schema,
            "start": start.isoformat(),
            "stype_in": stype_in,
        }

        if end:
            params["end"] = end.isoformat()

        return await self.get(endpoint, headers=self._get_headers(), params=params)

    async def get_ohlcv_bars(
        self,
        symbol: str,
        start: date,
        end: Optional[date] = None,
        timeframe: str = "1m",
        dataset: str = "XNAS.ITCH",
    ) -> List[Dict]:
        """
        Get OHLCV bars for a symbol.

        Args:
            symbol: Stock symbol
            start: Start date
            end: End date
            timeframe: Timeframe (1m, 5m, 1h, 1d)
            dataset: Dataset to use

        Returns:
            List of OHLCV bars
        """
        schema_map = {
            "1m": "ohlcv-1m",
            "5m": "ohlcv-5m",
            "1h": "ohlcv-1h",
            "1d": "ohlcv-1d",
        }

        schema = schema_map.get(timeframe, "ohlcv-1m")

        result = await self.get_timeseries(
            dataset=dataset,
            symbols=[symbol],
            schema=schema,
            start=start,
            end=end,
        )

        # Note: Actual response format depends on output format (JSON/CSV/DBN)
        # This is a simplified version
        return result.get("data", [])

    async def list_datasets(self) -> List[Dict]:
        """
        List available datasets.

        Returns:
            List of dataset information
        """
        endpoint = "/v0/metadata.list_datasets"
        result = await self.get(endpoint, headers=self._get_headers())
        return result.get("datasets", [])

    async def get_dataset_range(self, dataset: str) -> Dict:
        """
        Get date range for a dataset.

        Args:
            dataset: Dataset code

        Returns:
            Dataset range information with start/end dates
        """
        endpoint = "/v0/metadata.get_dataset_range"
        params = {"dataset": dataset}
        return await self.get(endpoint, headers=self._get_headers(), params=params)

    async def get_cost_estimate(
        self,
        dataset: str,
        symbols: List[str],
        schema: str,
        start: date,
        end: Optional[date] = None,
    ) -> Dict:
        """
        Estimate the cost of a data request.

        Args:
            dataset: Dataset code
            symbols: List of symbols
            schema: Data schema
            start: Start date
            end: End date

        Returns:
            Cost estimate in USD

        Example response:
            {
                "cost": 1.50,
                "total_size": 1024000,
                "record_count": 50000
            }
        """
        endpoint = "/v0/timeseries.get_cost"

        params = {
            "dataset": dataset,
            "symbols": ",".join(symbols),
            "schema": schema,
            "start": start.isoformat(),
        }

        if end:
            params["end"] = end.isoformat()

        return await self.get(endpoint, headers=self._get_headers(), params=params)

    async def health_check(self) -> bool:
        """Check if Databento API is accessible"""
        try:
            # Try to list datasets as a simple health check
            await self.list_datasets()
            return True
        except Exception:
            return False


# Global client instance
databento_client = DatabentoClient() if settings.DATABENTO_API_KEY else None
