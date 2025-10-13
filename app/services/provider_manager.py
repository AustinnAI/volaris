"""
Provider Manager
Manages provider selection and fallback logic based on data type and availability.

Hierarchy (from spec):
- Schwab: Primary real-time (1m/5m)
- Alpaca: Minute delayed fallback
- Databento: Historical backfills
- Tiingo: EOD data
- Finnhub: Fundamentals & news
"""

from enum import Enum
from typing import Optional, List, Dict
from datetime import datetime

from app.services.schwab import schwab_client
from app.services.alpaca import alpaca_client
from app.services.databento import databento_client
from app.services.tiingo import tiingo_client
from app.services.finnhub import finnhub_client
from app.services.marketstack import marketstack_client
from app.utils.logger import app_logger


class DataType(str, Enum):
    """Types of market data"""
    REALTIME_MINUTE = "realtime_minute"  # 1m/5m real-time
    MINUTE_DELAYED = "minute_delayed"    # Minute bars (delayed)
    EOD = "eod"                          # End of day
    HISTORICAL = "historical"            # Historical backfills
    FUNDAMENTALS = "fundamentals"        # Company data
    NEWS = "news"                        # News & sentiment
    QUOTE = "quote"                      # Real-time quotes
    OPTIONS = "options"                  # Options chains


class ProviderManager:
    """
    Manages provider selection with fallback logic.

    Provider hierarchy:
    - Real-time (1m/5m): Schwab (primary) → Alpaca (fallback)
    - EOD: Tiingo
    - Historical: Databento
    - Fundamentals/News: Finnhub
    """

    def __init__(self):
        self.providers = {
            "schwab": schwab_client,
            "alpaca": alpaca_client,
            "databento": databento_client,
            "tiingo": tiingo_client,
            "finnhub": finnhub_client,
            "marketstack": marketstack_client,
        }

        # Provider hierarchy by data type
        self.hierarchy = {
            DataType.REALTIME_MINUTE: ["schwab", "alpaca"],
            DataType.MINUTE_DELAYED: ["alpaca", "schwab"],
            DataType.EOD: ["tiingo", "marketstack"],
            DataType.HISTORICAL: ["databento", "alpaca"],
            DataType.FUNDAMENTALS: ["finnhub"],
            DataType.NEWS: ["finnhub"],
            DataType.QUOTE: ["schwab", "alpaca", "tiingo"],
            DataType.OPTIONS: ["schwab"],
        }

    def get_provider(
        self,
        data_type: DataType,
        preferred: Optional[str] = None,
    ) -> Optional[object]:
        """
        Get the best available provider for a data type.

        Args:
            data_type: Type of data needed
            preferred: Preferred provider name (optional)

        Returns:
            Provider client instance or None if no provider available

        Example:
            provider = manager.get_provider(DataType.REALTIME_MINUTE)
            if provider:
                data = await provider.get_bars("SPY", timeframe="1Min")
        """
        # Try preferred provider first
        if preferred and preferred in self.providers:
            client = self.providers.get(preferred)
            if client:
                app_logger.info(f"Using preferred provider: {preferred}")
                return client

        # Fall back to hierarchy
        provider_list = self.hierarchy.get(data_type, [])

        for provider_name in provider_list:
            client = self.providers.get(provider_name)
            if client:
                app_logger.info(
                    f"Selected provider for {data_type.value}: {provider_name}"
                )
                return client

        app_logger.warning(f"No provider available for {data_type.value}")
        return None

    async def get_provider_health(self) -> Dict[str, bool]:
        """
        Check health of all configured providers.

        Returns:
            Dict mapping provider names to health status

        Example:
            {
                "schwab": True,
                "alpaca": True,
                "tiingo": True,
                "databento": False,
                "finnhub": True
            }
        """
        health_status = {}

        for name, client in self.providers.items():
            if client is None:
                health_status[name] = False
            else:
                try:
                    is_healthy = await client.health_check()
                    health_status[name] = is_healthy
                except Exception as e:
                    app_logger.error(f"{name} health check failed: {e}")
                    health_status[name] = False

        return health_status

    def get_configured_providers(self) -> List[str]:
        """
        Get list of configured (non-None) providers.

        Returns:
            List of provider names
        """
        return [name for name, client in self.providers.items() if client is not None]

    def get_available_data_types(self) -> Dict[DataType, List[str]]:
        """
        Get available data types and their providers.

        Returns:
            Dict mapping data types to list of available providers
        """
        available = {}

        for data_type, provider_list in self.hierarchy.items():
            available_providers = [
                p for p in provider_list if self.providers.get(p) is not None
            ]
            if available_providers:
                available[data_type] = available_providers

        return available


# Global provider manager instance
provider_manager = ProviderManager()
