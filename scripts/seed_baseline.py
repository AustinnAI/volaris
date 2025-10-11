"""Seed baseline tickers and default watchlist data."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure project root is on the import path when running as a script
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.database import async_session_maker
from app.db.models import Ticker, Watchlist, WatchlistItem

DEFAULT_TICKERS = [
    ("SPY", "SPDR S&P 500 ETF"),
    ("QQQ", "Invesco QQQ Trust"),
    ("IWM", "iShares Russell 2000 ETF"),
    ("DIA", "SPDR Dow Jones Industrial Average ETF"),
]


async def seed() -> None:
    """Insert baseline tickers and a default watchlist."""

    async with async_session_maker() as session:
        existing_symbols = {
            row[0] for row in await session.execute(select(Ticker.symbol))
        }

        for symbol, name in DEFAULT_TICKERS:
            if symbol in existing_symbols:
                continue
            session.add(Ticker(symbol=symbol, name=name, is_active=True))

        await session.flush()

        default_watchlist = await session.scalar(
            select(Watchlist)
            .where(Watchlist.is_default.is_(True))
            .options(selectinload(Watchlist.items))
        )
        if default_watchlist is None:
            default_watchlist = Watchlist(name="Core", is_default=True)
            session.add(default_watchlist)
            await session.flush()

        tickers = (
            await session.execute(
                select(Ticker).where(Ticker.symbol.in_([t[0] for t in DEFAULT_TICKERS]))
            )
        ).scalars().all()

        current_items = (
            await session.execute(
                select(WatchlistItem.ticker_id).where(
                    WatchlistItem.watchlist_id == default_watchlist.id
                )
            )
        ).scalars().all()
        current_members = set(current_items)
        rank = 1
        for ticker in tickers:
            if ticker.id in current_members:
                continue
            session.add(
                WatchlistItem(
                    watchlist_id=default_watchlist.id,
                    ticker_id=ticker.id,
                    rank=rank,
                )
            )
            rank += 1

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
