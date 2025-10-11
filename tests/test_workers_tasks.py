"""Tests for worker task utilities."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base
from app.db.models import (
    IVMetric,
    OptionChainSnapshot,
    OptionContract,
    PriceBar,
    Ticker,
    Timeframe,
)
from app.workers.tasks import (
    compute_iv_metrics,
    fetch_option_chains,
    fetch_realtime_prices,
)


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


class MockPriceProvider:
    provider_name = "schwab"

    async def get_price_history(self, **kwargs):
        return {
            "candles": [
                {
                    "datetime": 1_695_000_000_000,
                    "open": 440.0,
                    "high": 441.0,
                    "low": 439.5,
                    "close": 440.5,
                    "volume": 5000,
                }
            ]
        }


class MockOptionProvider:
    provider_name = "schwab"

    async def get_option_chain(self, *args, **kwargs):
        return {
            "underlyingPrice": 440.25,
            "callExpDateMap": {
                "2025-10-20:7": {
                    "440": [
                        {
                            "strikePrice": 440,
                            "putCall": "CALL",
                            "bid": 1.0,
                            "ask": 1.5,
                            "last": 1.2,
                            "mark": 1.25,
                            "impliedVolatility": 0.35,
                            "openInterest": 150,
                            "totalVolume": 10,
                        }
                    ]
                }
            },
            "putExpDateMap": {
                "2025-10-20:7": {
                    "440": [
                        {
                            "strikePrice": 440,
                            "putCall": "PUT",
                            "bid": 1.1,
                            "ask": 1.6,
                            "impliedVolatility": 0.38,
                            "openInterest": 120,
                            "totalVolume": 8,
                        }
                    ]
                }
            },
        }


@pytest.mark.asyncio
async def test_fetch_realtime_prices_inserts_price_bar(session: AsyncSession) -> None:
    ticker = Ticker(symbol="SPY", is_active=True)
    session.add(ticker)
    await session.commit()

    provider = MockPriceProvider()
    inserted = await fetch_realtime_prices(session, provider=provider, timeframe=Timeframe.ONE_MINUTE)
    assert inserted == 1

    result = await session.execute(select(PriceBar))
    bar = result.scalar_one()
    assert bar.close == Decimal("440.5")
    assert bar.volume == 5000


@pytest.mark.asyncio
async def test_fetch_option_chains_persists_snapshot_and_contracts(session: AsyncSession) -> None:
    ticker = Ticker(symbol="QQQ", is_active=True)
    session.add(ticker)
    await session.commit()

    provider = MockOptionProvider()
    created = await fetch_option_chains(session, provider=provider)
    assert created == 1

    snapshot = await session.scalar(select(OptionChainSnapshot))
    assert snapshot is not None
    assert snapshot.underlying_price == Decimal("440.25")

    contracts = (await session.execute(select(OptionContract))).scalars().all()
    assert len(contracts) == 2


@pytest.mark.asyncio
async def test_compute_iv_metrics_generates_records(session: AsyncSession) -> None:
    ticker = Ticker(symbol="IWM", is_active=True)
    session.add(ticker)
    await session.commit()

    provider = MockOptionProvider()
    await fetch_option_chains(session, provider=provider)

    metrics = await compute_iv_metrics(session)
    assert metrics > 0

    stored = (await session.execute(select(IVMetric))).scalars().all()
    assert stored, "Expected IV metrics to be created"
