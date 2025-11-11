"""Services for managing index constituents (e.g., S&P 500)."""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IndexConstituent, Ticker
from app.services.exceptions import DataNotFoundError
from app.services.finnhub import finnhub_client
from app.services.nasdaq100_scraper import (
    fetch_nasdaq100_symbols_wikipedia,
    load_nasdaq100_from_csv,
)
from app.services.sp500_scraper import fetch_sp500_symbols_wikipedia
from app.services.tickers import get_or_create_ticker
from app.utils.logger import app_logger

SP500_SYMBOL = "^GSPC"
NASDAQ100_SYMBOL = "^NDX"

# Priority indices for trading - ordered by liquidity preference
PRIORITY_INDICES = [NASDAQ100_SYMBOL, SP500_SYMBOL]


async def refresh_index_constituents(
    db: AsyncSession,
    index_symbol: str = SP500_SYMBOL,
) -> list[str]:
    """Refresh constituents for the given index symbol using Finnhub → Wikipedia → CSV fallback."""

    symbols: list[str] = []

    # V1: Try Finnhub first (Polygon removed)
    if finnhub_client:
        try:
            response = await finnhub_client.get_index_constituents(index_symbol)
            symbols = response.get("constituents") or []
        except Exception as exc:  # pylint: disable=broad-except
            app_logger.warning(
                "Finnhub constituents unavailable, using fallback",
                extra={"index": index_symbol, "error": str(exc)},
            )

    # Wikipedia fallback (index-specific)
    if not symbols:
        if index_symbol == NASDAQ100_SYMBOL:
            symbols = await fetch_nasdaq100_symbols_wikipedia()
        else:  # S&P 500 or other
            symbols = await fetch_sp500_symbols_wikipedia()

    # CSV fallback (index-specific)
    if not symbols:
        return await _load_local_constituents(db, index_symbol)

    existing_stmt = select(IndexConstituent).where(IndexConstituent.index_symbol == index_symbol)
    result = await db.execute(existing_stmt)
    existing: list[IndexConstituent] = list(result.scalars().all())
    existing_map = {cons.ticker.symbol: cons for cons in existing}

    incoming: set[str] = {symbol.upper() for symbol in symbols}

    # Add or update memberships
    for symbol in incoming:
        if symbol in existing_map:
            continue
        ticker = await get_or_create_ticker(symbol, db)
        membership = IndexConstituent(index_symbol=index_symbol, ticker_id=ticker.id)
        db.add(membership)

    # Remove stale memberships
    stale_symbols: set[str] = set(existing_map.keys()) - incoming
    if stale_symbols:
        await db.execute(
            delete(IndexConstituent)
            .where(IndexConstituent.index_symbol == index_symbol)
            .where(
                IndexConstituent.ticker_id.in_([existing_map[s].ticker_id for s in stale_symbols])
            )
        )

    app_logger.info(
        "Refreshed index constituents",
        extra={
            "index": index_symbol,
            "added": len(incoming - set(existing_map.keys())),
            "removed": len(stale_symbols),
        },
    )

    return sorted(incoming)


async def _load_local_constituents(db: AsyncSession, index_symbol: str) -> list[str]:
    """Fallback: hydrate constituents from bundled CSV."""
    # Determine CSV filename based on index
    if index_symbol == NASDAQ100_SYMBOL:
        csv_filename = "NASDAQ100.csv"
        index_name = "NASDAQ-100"
    else:
        csv_filename = "SP500.csv"
        index_name = "S&P 500"

    csv_path = Path(__file__).parent.parent / csv_filename

    # For NASDAQ-100, try the scraper's CSV loader first
    if index_symbol == NASDAQ100_SYMBOL:
        symbols_list = load_nasdaq100_from_csv()
        if symbols_list:
            symbols = set(symbols_list)
        elif not csv_path.exists():
            raise DataNotFoundError(
                f"No {index_name} source available (Finnhub/Wikipedia failed and {csv_filename} missing)",
                provider="Finnhub",
            )
        else:
            symbols = set()
    elif not csv_path.exists():
        raise DataNotFoundError(
            f"No {index_name} source available (Finnhub/Wikipedia failed and {csv_filename} missing)",
            provider="Finnhub",
        )
    else:
        symbols = set()

    # Load from CSV if not already loaded
    if not symbols and csv_path.exists():
        with csv_path.open("r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                symbol = (row.get("Symbol") or row.get("Ticker") or "").strip()
                if symbol:
                    symbols.add(symbol.upper())

    for symbol in symbols:
        ticker = await get_or_create_ticker(symbol, db)
        existing = await db.execute(
            select(IndexConstituent).where(
                IndexConstituent.index_symbol == index_symbol,
                IndexConstituent.ticker_id == ticker.id,
            )
        )
        if not existing.scalar_one_or_none():
            db.add(IndexConstituent(index_symbol=index_symbol, ticker_id=ticker.id))

    await db.commit()
    app_logger.info(
        "Loaded %s index constituents from local CSV fallback",
        len(symbols),
    )
    return sorted(symbols)


async def get_index_constituents_symbols(
    db: AsyncSession,
    index_symbol: str = SP500_SYMBOL,
) -> set[str]:
    stmt = (
        select(Ticker.symbol)
        .join(IndexConstituent, IndexConstituent.ticker_id == Ticker.id)
        .where(IndexConstituent.index_symbol == index_symbol)
    )
    result = await db.execute(stmt)
    return {row[0] for row in result.all()}


async def is_sp500_member(db: AsyncSession, symbol: str) -> bool:
    symbols = await get_index_constituents_symbols(db, SP500_SYMBOL)
    return symbol.upper() in symbols


async def ensure_sp500_constituents(
    db: AsyncSession, index_symbol: str = SP500_SYMBOL
) -> list[str]:
    """Ensure the database has at least one batch of S&P 500 constituents."""
    existing = await get_index_constituents_symbols(db, index_symbol)
    if existing:
        return sorted(existing)
    app_logger.info("S&P 500 constituents missing; hydrating from Wikipedia fallback")
    return await refresh_index_constituents(db, index_symbol)


async def get_priority_tickers(
    db: AsyncSession,
    include_sp500: bool = True,
) -> set[str]:
    """
    Get liquid, tradeable tickers prioritized by index membership.

    Returns NASDAQ-100 tickers first (most liquid tech/growth),
    then S&P 500 if include_sp500=True.

    Args:
        db: Database session
        include_sp500: Include S&P 500 tickers (default: True)

    Returns:
        Set of ticker symbols, prioritized by liquidity
    """
    tickers = set()

    # Always include NASDAQ-100 (highest priority)
    ndx_tickers = await get_index_constituents_symbols(db, NASDAQ100_SYMBOL)
    tickers.update(ndx_tickers)

    # Optionally include S&P 500 (broader coverage)
    if include_sp500:
        sp500_tickers = await get_index_constituents_symbols(db, SP500_SYMBOL)
        tickers.update(sp500_tickers)

    return tickers
