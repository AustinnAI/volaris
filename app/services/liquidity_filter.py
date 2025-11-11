"""
Liquidity filtering service for identifying tradeable stocks.

Provides volume-based and index-based filtering to identify liquid stocks
suitable for short-dated options trading.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IndexConstituent, PriceBar, Ticker, Timeframe
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
    lookback_days: int = 30,
) -> set[str]:
    """
    Get liquid tickers based on average daily volume threshold.

    Calculates average volume over the last N trading days using daily price bars.
    Only returns tickers with sufficient volume for liquid trading.

    Args:
        db: Database session
        min_volume: Minimum average daily volume (default: 5M shares)
        lookback_days: Number of days to calculate average (default: 30)

    Returns:
        Set of ticker symbols meeting volume threshold
    """
    # Calculate cutoff date for lookback period
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    # Query average daily volume per ticker
    # Use daily (1D) timeframe for volume calculations
    stmt = (
        select(
            Ticker.symbol,
            func.avg(PriceBar.volume).label("avg_volume"),
            func.count(PriceBar.id).label("bar_count"),
        )
        .join(PriceBar, Ticker.id == PriceBar.ticker_id)
        .where(PriceBar.timeframe == Timeframe.ONE_DAY)
        .where(PriceBar.timestamp >= cutoff_date)
        .where(PriceBar.volume.isnot(None))
        .group_by(Ticker.id, Ticker.symbol)
        .having(func.avg(PriceBar.volume) >= min_volume)
        .having(func.count(PriceBar.id) >= 10)  # At least 10 trading days of data
    )

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        app_logger.warning(
            "No volume data found in database, falling back to index-based filtering",
            extra={"lookback_days": lookback_days, "min_volume": min_volume},
        )
        return await _get_liquid_by_index(db, include_sp500=True)

    liquid_symbols = {row.symbol for row in rows}

    app_logger.info(
        "Volume-based liquidity filter applied",
        extra={
            "liquid_count": len(liquid_symbols),
            "min_volume": min_volume,
            "lookback_days": lookback_days,
        },
    )

    return liquid_symbols


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
