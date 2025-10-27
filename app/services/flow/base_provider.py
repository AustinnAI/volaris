"""
Abstract base provider for options flow detection.

Defines the interface that all flow providers must implement,
enabling easy swapping between yfinance, Alpha Vantage, Unusual Whales, etc.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import TypedDict


class OptionContract(TypedDict):
    """Single option contract data."""

    contract_symbol: str  # e.g., "SPY250131C600"
    strike: Decimal
    expiration: datetime
    option_type: str  # "call" | "put"
    last_price: Decimal
    bid: Decimal
    ask: Decimal
    volume: int
    open_interest: int
    implied_volatility: float | None


class OptionChain(TypedDict):
    """Raw option chain data for a ticker."""

    symbol: str
    timestamp: datetime
    expirations: list[datetime]
    calls: list[OptionContract]
    puts: list[OptionContract]


class UnusualTrade(TypedDict):
    """Detected unusual options activity."""

    symbol: str
    contract_symbol: str  # e.g., "SPY250131C600"
    option_type: str  # "call" | "put"
    strike: Decimal
    expiration: datetime
    last_price: Decimal
    volume: int
    open_interest: int
    volume_oi_ratio: float
    premium: Decimal  # volume × price × 100
    anomaly_score: float  # 0-1 (higher = more unusual)
    flags: list[str]  # ["high_volume", "low_oi", "block_trade", "volume_spike"]
    detected_at: datetime


class FlowProvider(ABC):
    """Abstract base for options flow providers."""

    @abstractmethod
    async def get_option_chain(
        self, symbol: str, expiration: datetime | None = None
    ) -> OptionChain:
        """
        Fetch raw option chain data.

        Args:
            symbol: Ticker symbol (e.g., SPY, AAPL).
            expiration: Optional specific expiration date to filter.

        Returns:
            OptionChain with calls and puts.

        Raises:
            ValueError: If ticker not found or no options available.
        """

    @abstractmethod
    async def get_unusual_activity(
        self,
        symbol: str,
        min_score: float = 0.7,
        lookback_minutes: int = 60,
    ) -> list[UnusualTrade]:
        """
        Detect unusual options activity.

        Args:
            symbol: Ticker symbol (e.g., SPY, AAPL).
            min_score: Minimum anomaly score (0-1) to return.
            lookback_minutes: How far back to scan for unusual activity.

        Returns:
            List of unusual trades sorted by anomaly_score descending.

        Raises:
            ValueError: If ticker not found or data unavailable.
        """
