"""Services for managing index constituents (e.g., S&P 500)."""

from __future__ import annotations

from typing import Iterable, List, Set

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IndexConstituent, Ticker
from app.services.exceptions import DataNotFoundError
from app.services.finnhub import finnhub_client
from app.services.polygon import polygon_client
from app.services.tickers import get_or_create_ticker
from app.utils.logger import app_logger
from pathlib import Path
import csv
from app.services.sp500_scraper import fetch_sp500_symbols_wikipedia

SP500_SYMBOL = "^GSPC"


async def refresh_index_constituents(
    db: AsyncSession,
    index_symbol: str = SP500_SYMBOL,
) -> List[str]:
    """Refresh constituents for the given index symbol using Finnhub."""

    symbols: List[str] = []

    if polygon_client:
        try:
            symbols = await polygon_client.get_sp500_constituents()
        except Exception as exc:  # pylint: disable=broad-except
            app_logger.warning(
                "Polygon constituents unavailable, attempting Finnhub",
                extra={"error": str(exc)},
            )

    if not symbols and finnhub_client:
        try:
            response = await finnhub_client.get_index_constituents(index_symbol)
            symbols = response.get("constituents") or []
        except Exception as exc:  # pylint: disable=broad-except
            app_logger.warning(
                "Finnhub constituents unavailable, using CSV fallback",
                extra={"index": index_symbol, "error": str(exc)},
            )

    if not symbols:
        symbols = await fetch_sp500_symbols_wikipedia()

    if not symbols:
        return await _load_local_constituents(db, index_symbol)

    existing_stmt = select(IndexConstituent).where(IndexConstituent.index_symbol == index_symbol)
    result = await db.execute(existing_stmt)
    existing: list[IndexConstituent] = list(result.scalars().all())
    existing_map = {cons.ticker.symbol: cons for cons in existing}

    incoming: Set[str] = {symbol.upper() for symbol in symbols}

    # Add or update memberships
    for symbol in incoming:
        if symbol in existing_map:
            continue
        ticker = await get_or_create_ticker(symbol, db)
        membership = IndexConstituent(index_symbol=index_symbol, ticker_id=ticker.id)
        db.add(membership)

    # Remove stale memberships
    stale_symbols: Set[str] = set(existing_map.keys()) - incoming
    if stale_symbols:
        await db.execute(
            delete(IndexConstituent)
            .where(IndexConstituent.index_symbol == index_symbol)
            .where(IndexConstituent.ticker_id.in_(
                [existing_map[s].ticker_id for s in stale_symbols]
            ))
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


async def _load_local_constituents(db: AsyncSession, index_symbol: str) -> List[str]:
    """Fallback: hydrate constituents from bundled CSV."""
    csv_path = Path(__file__).parent.parent / "SP500.csv"
    if not csv_path.exists():
        raise DataNotFoundError(
            "No S&P 500 source available (Finnhub disabled and SP500.csv missing)",
            provider="Finnhub",
        )

    symbols: set[str] = set()
    with csv_path.open("r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            symbol = (row.get("Symbol") or "").strip()
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
) -> Set[str]:
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


async def ensure_sp500_constituents(db: AsyncSession, index_symbol: str = SP500_SYMBOL) -> List[str]:
    """Ensure the database has at least one batch of S&P 500 constituents."""
    existing = await get_index_constituents_symbols(db, index_symbol)
    if existing:
        return sorted(existing)
    app_logger.info("S&P 500 constituents missing; hydrating from Wikipedia fallback")
    return await refresh_index_constituents(db, index_symbol)
