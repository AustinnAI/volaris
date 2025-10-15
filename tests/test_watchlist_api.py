from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.v1.watchlist import get_watchlist, set_watchlist
from app.api.v1.schemas.watchlist import WatchlistUpdateRequest
from app.config import settings
from app.services.watchlist import WatchlistService, WatchlistValidationError


@pytest.mark.asyncio
async def test_get_watchlist_returns_symbols(monkeypatch):
    db = AsyncMock()
    monkeypatch.setattr(WatchlistService, "get_symbols", AsyncMock(return_value=["SPY", "QQQ"]))

    response = await get_watchlist(db)
    assert response.symbols == ["SPY", "QQQ"]


@pytest.mark.asyncio
async def test_set_watchlist_requires_token(monkeypatch):
    monkeypatch.setattr(settings, "VOLARIS_API_TOKEN", "secret-token")
    db = AsyncMock()
    payload = WatchlistUpdateRequest(symbols=["SPY", "QQQ"])

    request = Request(scope={"type": "http", "headers": [(b"authorization", b"Bearer secret-token")]})
    setter = AsyncMock(return_value=["SPY", "QQQ"])
    monkeypatch.setattr(WatchlistService, "set_symbols", setter)

    response = await set_watchlist(request, payload, db)
    assert response.symbols == ["SPY", "QQQ"]
    setter.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_watchlist_rejects_invalid_payload(monkeypatch):
    monkeypatch.setattr(settings, "VOLARIS_API_TOKEN", "secret-token")
    db = AsyncMock()
    payload = WatchlistUpdateRequest(symbols=[""])
    monkeypatch.setattr(
        WatchlistService,
        "set_symbols",
        AsyncMock(side_effect=WatchlistValidationError("invalid")),
    )

    request = Request(scope={"type": "http", "headers": [(b"authorization", b"Bearer secret-token")]})

    with pytest.raises(HTTPException) as exc_info:
        await set_watchlist(request, payload, db)
    assert exc_info.value.status_code == 400
