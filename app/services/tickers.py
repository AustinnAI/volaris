"""Utility helpers for ticker management."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Ticker


async def get_or_create_ticker(symbol: str, db: AsyncSession) -> Ticker:
    """Fetch ticker from database or create a new active record."""

    stmt = select(Ticker).where(Ticker.symbol == symbol)
    result = await db.execute(stmt)
    ticker = result.scalar_one_or_none()
    if ticker:
        return ticker

    ticker = Ticker(symbol=symbol, is_active=True)
    db.add(ticker)
    await db.flush()
    return ticker
