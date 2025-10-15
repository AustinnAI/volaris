from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request

from app.api.v1 import market_data
from app.api.v1.market_data import MarketRefreshBatchRequest


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


@pytest.mark.asyncio
async def test_refresh_market_data_batch(monkeypatch):
    async def fake_prices(session, symbols, **kwargs):
        assert symbols == ["AAPL", "MSFT"]
        return 4

    async def fake_options(session, symbols, **kwargs):
        assert symbols == ["AAPL", "MSFT"]
        return 2

    async def fake_iv(session, symbols, **kwargs):
        assert symbols == ["AAPL", "MSFT"]
        return 5

    monkeypatch.setattr(market_data, "fetch_realtime_prices", fake_prices)
    monkeypatch.setattr(market_data, "fetch_option_chains", fake_options)
    monkeypatch.setattr(market_data, "compute_iv_metrics", fake_iv)

    payload = MarketRefreshBatchRequest(
        symbols=["aapl", "msft"],
        kinds=["price", "options", "iv"],
    )

    db = AsyncMock()
    request = Request(scope={"type": "http", "headers": []})
    result = await market_data.refresh_market_data_batch(request, payload, db)

    assert result["symbols"] == ["AAPL", "MSFT"]
    assert result["results"] == {"price": 4, "options": 2, "iv": 5}


@pytest.mark.asyncio
async def test_refresh_watchlist_endpoint(monkeypatch):
    async def fake_get_symbols(session):
        return ["SPY", "QQQ"]

    async def fake_refresh(db, symbols, kinds=None):
        assert symbols == ["SPY", "QQQ"]
        return {"symbols": symbols, "results": {"price": 2}}

    monkeypatch.setattr(market_data.WatchlistService, "get_symbols", fake_get_symbols)
    monkeypatch.setattr(market_data, "_refresh_symbols", fake_refresh)

    db = AsyncMock()
    request = Request(scope={"type": "http", "headers": []})
    result = await market_data.refresh_watchlist_data(request, db)

    assert result["symbols"] == ["SPY", "QQQ"]
    assert result["results"] == {"price": 2}
