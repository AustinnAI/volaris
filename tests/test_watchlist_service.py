from unittest.mock import AsyncMock

import pytest

from app.services.watchlist import WatchlistService, WatchlistValidationError


def test_normalize_symbols_happy_path():
    symbols = WatchlistService.normalize_symbols(["spy", "QQQ", "spy", " msft "])
    assert symbols == ["SPY", "QQQ", "MSFT"]


def test_normalize_symbols_invalid_characters():
    with pytest.raises(WatchlistValidationError):
        WatchlistService.normalize_symbols(["SPY!", "QQQ"])


def test_normalize_symbols_length_guard():
    symbols = [f"SYM{i}" for i in range(9)]
    with pytest.raises(WatchlistValidationError):
        WatchlistService.normalize_symbols(symbols)


@pytest.mark.asyncio
async def test_set_symbols_updates_backends(monkeypatch):
    session = AsyncMock()
    session.commit = AsyncMock()

    redis_mock = AsyncMock(return_value=True)
    db_mock = AsyncMock()

    monkeypatch.setattr(WatchlistService, "_set_in_redis", redis_mock)
    monkeypatch.setattr(WatchlistService, "_set_in_db", db_mock)

    symbols = await WatchlistService.set_symbols(session, ["spy", "qqq"])

    assert symbols == ["SPY", "QQQ"]
    redis_mock.assert_awaited_once()
    db_mock.assert_awaited_once()
    session.commit.assert_awaited_once()
