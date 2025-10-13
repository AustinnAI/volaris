"""
Tests for index service helpers.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services import index_service


@pytest.mark.asyncio
async def test_ensure_sp500_constituents_refreshes_when_empty(monkeypatch):
    session = AsyncMock()
    monkeypatch.setattr(
        index_service,
        "get_index_constituents_symbols",
        AsyncMock(return_value=set()),
    )
    refresh = AsyncMock(return_value=["AAPL", "MSFT"])
    monkeypatch.setattr(index_service, "refresh_index_constituents", refresh)

    symbols = await index_service.ensure_sp500_constituents(session)

    refresh.assert_awaited_once()
    assert symbols == ["AAPL", "MSFT"]


@pytest.mark.asyncio
async def test_ensure_sp500_constituents_returns_existing(monkeypatch):
    session = AsyncMock()
    monkeypatch.setattr(
        index_service,
        "get_index_constituents_symbols",
        AsyncMock(return_value={"AAPL", "MSFT"}),
    )
    refresh = AsyncMock()
    monkeypatch.setattr(index_service, "refresh_index_constituents", refresh)

    symbols = await index_service.ensure_sp500_constituents(session)

    refresh.assert_not_called()
    assert symbols == ["AAPL", "MSFT"]
