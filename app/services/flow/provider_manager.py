"""
Flow Provider Manager with fallback hierarchy.

Manages multiple flow providers and implements fallback logic
for resilience. Phase 3.0 MVP: yfinance only.
"""

from tenacity import retry, stop_after_attempt, wait_exponential

from app.utils.logger import app_logger

from .base_provider import FlowProvider, OptionChain, UnusualTrade
from .yfinance_provider import YFinanceFlowProvider


class FlowProviderManager:
    """
    Manages fallback hierarchy for options flow providers.

    Phase 3.0: yfinance only
    Phase 3.1: yfinance → Alpha Vantage
    Phase 3.2: Unusual Whales → yfinance → Alpha Vantage
    """

    def __init__(self):
        """Initialize provider manager with yfinance as primary."""
        self.providers: list[FlowProvider] = [
            YFinanceFlowProvider(),
        ]

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
    async def get_option_chain(self, symbol: str, expiration=None) -> OptionChain:
        """
        Get option chain from first available provider.

        Tries providers in order with retry logic.

        Args:
            symbol: Ticker symbol (e.g., SPY, AAPL).
            expiration: Optional expiration date filter.

        Returns:
            OptionChain from first successful provider.

        Raises:
            ValueError: If all providers fail.
        """
        for provider in self.providers:
            try:
                app_logger.info(
                    f"Fetching option chain for {symbol} from {provider.__class__.__name__}"
                )
                return await provider.get_option_chain(symbol, expiration)
            except Exception as e:
                app_logger.warning(f"{provider.__class__.__name__} failed for {symbol}: {e}")
                continue

        raise ValueError(f"All providers failed to fetch option chain for {symbol}")

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
    async def get_unusual_activity(
        self,
        symbol: str,
        min_score: float = 0.7,
        lookback_minutes: int = 60,
    ) -> list[UnusualTrade]:
        """
        Detect unusual activity from first available provider.

        Tries providers in order with retry logic.

        Args:
            symbol: Ticker symbol (e.g., SPY, AAPL).
            min_score: Minimum anomaly score threshold (0-1).
            lookback_minutes: Lookback period for activity detection.

        Returns:
            List of unusual trades from first successful provider.

        Raises:
            ValueError: If all providers fail.
        """
        for provider in self.providers:
            try:
                app_logger.info(
                    f"Detecting unusual activity for {symbol} from {provider.__class__.__name__}"
                )
                return await provider.get_unusual_activity(symbol, min_score, lookback_minutes)
            except Exception as e:
                app_logger.warning(f"{provider.__class__.__name__} failed for {symbol}: {e}")
                continue

        raise ValueError(f"All providers failed to detect activity for {symbol}")
