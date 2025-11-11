"""
Liquidity filtering service for identifying tradeable stocks.

Provides volume-based and index-based filtering to identify liquid stocks
suitable for short-dated options trading.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IndexConstituent, Ticker
from app.services.index_service import NASDAQ100_SYMBOL, SP500_SYMBOL
from app.utils.logger import app_logger

# Liquidity thresholds
MIN_AVG_VOLUME = 5_000_000  # 5M shares/day for high liquidity
MIN_AVG_DOLLAR_VOLUME = 100_000_000  # $100M/day for options liquidity


async def get_liquid_tickers(
    db: AsyncSession,
    strategy: Literal["index", "volume", "hybrid"] = "index",
    min_volume: int = MIN_AVG_VOLUME,
    include_sp500: bool = True,
) -> set[str]:
    """
    Get liquid, tradeable tickers using various filtering strategies.

    Args:
        db: Database session
        strategy: Filtering strategy
            - "index": Use NASDAQ-100 + optionally S&P 500 (fastest, no API calls)
            - "volume": Use volume threshold filtering (requires market data API)
            - "hybrid": Combine index membership + volume filtering
        min_volume: Minimum average daily volume threshold
        include_sp500: Include S&P 500 when using index strategy

    Returns:
        Set of liquid ticker symbols
    """
    if strategy == "index":
        return await _get_liquid_by_index(db, include_sp500)
    elif strategy == "volume":
        return await _get_liquid_by_volume(db, min_volume)
    elif strategy == "hybrid":
        # Get index members first, then filter by volume
        index_tickers = await _get_liquid_by_index(db, include_sp500)
        volume_tickers = await _get_liquid_by_volume(db, min_volume)
        return index_tickers & volume_tickers  # Intersection
    else:
        raise ValueError(f"Invalid strategy: {strategy}")


async def _get_liquid_by_index(
    db: AsyncSession,
    include_sp500: bool = True,
) -> set[str]:
    """Get liquid tickers based on index membership."""
    tickers = set()

    # Always include NASDAQ-100 (most liquid)
    stmt = (
        select(Ticker.symbol)
        .join(IndexConstituent, IndexConstituent.ticker_id == Ticker.id)
        .where(IndexConstituent.index_symbol == NASDAQ100_SYMBOL)
    )
    result = await db.execute(stmt)
    nasdaq100 = {row[0] for row in result.all()}
    tickers.update(nasdaq100)

    app_logger.debug(
        "Loaded NASDAQ-100 constituents for liquidity filter",
        extra={"count": len(nasdaq100)},
    )

    # Optionally include S&P 500
    if include_sp500:
        stmt = (
            select(Ticker.symbol)
            .join(IndexConstituent, IndexConstituent.ticker_id == Ticker.id)
            .where(IndexConstituent.index_symbol == SP500_SYMBOL)
        )
        result = await db.execute(stmt)
        sp500 = {row[0] for row in result.all()}
        tickers.update(sp500)

        app_logger.debug(
            "Loaded S&P 500 constituents for liquidity filter",
            extra={"count": len(sp500)},
        )

    return tickers


async def _get_liquid_by_volume(
    db: AsyncSession,
    min_volume: int = MIN_AVG_VOLUME,
) -> set[str]:
    """
    Get liquid tickers based on volume threshold.

    Note: This requires market data to be populated in the database.
    If volume data is not available, falls back to index-based filtering.
    """
    # TODO: Implement volume-based filtering using market_data table
    # This would query average volume over last 30 days and filter by min_volume
    # For now, fall back to index-based filtering

    app_logger.warning(
        "Volume-based liquidity filtering not yet implemented, falling back to index"
    )
    return await _get_liquid_by_index(db, include_sp500=True)


async def is_liquid_ticker(
    db: AsyncSession,
    symbol: str,
    strategy: Literal["index", "volume", "hybrid"] = "index",
) -> bool:
    """
    Check if a single ticker meets liquidity criteria.

    Args:
        db: Database session
        symbol: Ticker symbol to check
        strategy: Filtering strategy (index, volume, or hybrid)

    Returns:
        True if ticker is liquid, False otherwise
    """
    liquid_tickers = await get_liquid_tickers(db, strategy=strategy)
    return symbol.upper() in liquid_tickers


__all__ = [
    "get_liquid_tickers",
    "is_liquid_ticker",
    "MIN_AVG_VOLUME",
    "MIN_AVG_DOLLAR_VOLUME",
]
