"""
Tests for price alert evaluation endpoint.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1 import alerts
from app.db.models import PriceAlertDirection


@pytest.mark.asyncio
async def test_evaluate_price_alerts_triggers(monkeypatch):
    """Price alerts that breach targets should be returned and deleted."""
    alert = SimpleNamespace(
        id=1,
        ticker=SimpleNamespace(symbol="SPY"),
        target_price=Decimal("100"),
        direction=PriceAlertDirection.ABOVE,
        channel_id="123",
        created_by="456",
        triggered_at=None,
    )

    result = MagicMock()
    result.scalars.return_value.all.return_value = [alert]

    db = AsyncMock()
    db.execute.return_value = result
    db.delete = AsyncMock()

    async def fake_prices(symbols):
        assert list(symbols) == ["SPY"]
        return {"SPY": Decimal("105")}

    monkeypatch.setattr(alerts, "_fetch_prices", fake_prices)

    response = await alerts.evaluate_price_alerts(db)

    assert len(response.triggered) == 1
    triggered = response.triggered[0]
    assert triggered.symbol == "SPY"
    assert triggered.current_price == Decimal("105")
    db.delete.assert_awaited_once_with(alert)


@pytest.mark.asyncio
async def test_evaluate_price_alerts_no_matches(monkeypatch):
    """Returns empty list when no alerts or no prices are available."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = []

    db = AsyncMock()
    db.execute.return_value = result

    response = await alerts.evaluate_price_alerts(db)

    assert response.triggered == []
