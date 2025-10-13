import pytest
from unittest.mock import AsyncMock

from app.api.v1 import market_data


@pytest.mark.asyncio
async def test_refresh_price_endpoint(monkeypatch):
    async def fake_fetch(session, symbols, **kwargs):
        assert symbols == ["AAPL"]
        return 2

    monkeypatch.setattr(market_data, "fetch_realtime_prices", fake_fetch)

    db = AsyncMock()
    result = await market_data.refresh_price("aapl", db)
    assert result == {"inserted": 2}


@pytest.mark.asyncio
async def test_refresh_option_chain_endpoint(monkeypatch):
    async def fake_fetch(session, symbols, **kwargs):
        assert symbols == ["SPY"]
        return 1

    monkeypatch.setattr(market_data, "fetch_option_chains", fake_fetch)

    db = AsyncMock()
    result = await market_data.refresh_option_chain("spy", db)
    assert result == {"snapshots": 1}


@pytest.mark.asyncio
async def test_refresh_iv_metrics_endpoint(monkeypatch):
    async def fake_compute(session, symbols, **kwargs):
        assert symbols == ["QQQ"]
        return 3

    monkeypatch.setattr(market_data, "compute_iv_metrics", fake_compute)

    db = AsyncMock()
    result = await market_data.refresh_iv_metrics("qqq", db)
    assert result == {"metrics": 3}
