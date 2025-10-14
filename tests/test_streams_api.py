"""
Tests for price stream evaluation endpoint.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1 import streams


@pytest.mark.asyncio
async def test_evaluate_price_streams_dispatch(monkeypatch):
    """Streams due for dispatch should emit payloads and update scheduling."""
    now = datetime.now(UTC)
    stream_obj = SimpleNamespace(
        id=7,
        ticker=SimpleNamespace(symbol="QQQ"),
        channel_id="999",
        interval_seconds=300,
        next_run_at=now - timedelta(seconds=10),
        created_by="111",
        last_price=None,
    )

    result = MagicMock()
    result.scalars.return_value.all.return_value = [stream_obj]

    db = AsyncMock()
    db.execute.return_value = result

    class FakeClient:
        async def get_quote(self, symbol: str):
            assert symbol == "QQQ"
            return {"quote": {"lastPrice": 402.5, "previousClose": 400.0}}

    def fake_extract(payload, symbol):
        return payload["quote"]

    monkeypatch.setattr(streams, "SchwabClient", FakeClient)
    monkeypatch.setattr(streams, "_extract_schwab_quote", fake_extract)

    response = await streams.evaluate_price_streams(db)

    assert len(response.streams) == 1
    dispatch = response.streams[0]
    assert dispatch.symbol == "QQQ"
    assert dispatch.price == 402.5
    assert dispatch.change == pytest.approx(2.5)
    assert stream_obj.last_price is not None
    assert stream_obj.next_run_at > now


@pytest.mark.asyncio
async def test_evaluate_price_streams_no_due_streams():
    """When no streams are scheduled, response is empty."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = []

    db = AsyncMock()
    db.execute.return_value = result

    response = await streams.evaluate_price_streams(db)

    assert response.streams == []
