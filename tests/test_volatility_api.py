"""Tests for volatility API endpoints."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.v1 import volatility as volatility_api
from app.core.strike_selection import IVRegime
from app.core.volatility import (
    ExpectedMoveEstimate,
    IVSummary,
    OptionSkew,
    TermStructurePoint,
)
from app.db.models import IVTerm
from app.services.exceptions import DataNotFoundError
from app.services.volatility_service import VolatilitySnapshot


@pytest.fixture
def sample_snapshot() -> VolatilitySnapshot:
    """Return a representative volatility snapshot."""
    return VolatilitySnapshot(
        symbol="SPY",
        underlying_price=Decimal("500"),
        iv_summary=IVSummary(
            term=IVTerm.D30,
            implied_vol=Decimal("0.28"),
            iv_rank=Decimal("45"),
            iv_percentile=Decimal("50"),
            regime=IVRegime.NEUTRAL,
            as_of=datetime(2024, 5, 1, tzinfo=UTC),
        ),
        term_structure=[
            TermStructurePoint(
                term=IVTerm.D7,
                implied_vol=Decimal("0.24"),
                iv_rank=Decimal("30"),
                iv_percentile=Decimal("35"),
                as_of=datetime(2024, 5, 1, tzinfo=UTC),
            ),
            TermStructurePoint(
                term=IVTerm.D30,
                implied_vol=Decimal("0.28"),
                iv_rank=Decimal("45"),
                iv_percentile=Decimal("50"),
                as_of=datetime(2024, 5, 1, tzinfo=UTC),
            ),
        ],
        expected_moves=[
            ExpectedMoveEstimate(
                label="1-7d",
                dte=5,
                expected_move=Decimal("5.10"),
                expected_move_pct=Decimal("1.02"),
                straddle_cost=Decimal("5.10"),
                call_strike=Decimal("500"),
                put_strike=Decimal("500"),
                as_of=datetime(2024, 5, 1, tzinfo=UTC),
            )
        ],
        skew=OptionSkew(
            dte=30,
            call_delta=Decimal("0.25"),
            put_delta=Decimal("-0.25"),
            call_iv=Decimal("0.30"),
            put_iv=Decimal("0.32"),
            skew=Decimal("-0.02"),
        ),
        warnings=["Option data is 6 hours old"],
    )


@pytest.mark.asyncio
async def test_get_iv_summary_returns_model(monkeypatch, sample_snapshot) -> None:
    """IV endpoint should convert service snapshot into response model."""

    async def fake_get_snapshot(cls, db, symbol):
        return sample_snapshot

    monkeypatch.setattr(
        volatility_api.VolatilityService,
        "get_snapshot",
        classmethod(fake_get_snapshot),
    )

    response = await volatility_api.get_iv_summary("spy", AsyncMock())

    assert response.symbol == "SPY"
    assert response.implied_vol == Decimal("0.28")
    assert response.regime == IVRegime.NEUTRAL.value
    assert response.warnings == sample_snapshot.warnings


@pytest.mark.asyncio
async def test_get_expected_move_returns_estimates(monkeypatch, sample_snapshot) -> None:
    """Expected move endpoint should return payload from snapshot."""

    async def fake_get_snapshot(cls, db, symbol):
        return sample_snapshot

    monkeypatch.setattr(
        volatility_api.VolatilityService,
        "get_snapshot",
        classmethod(fake_get_snapshot),
    )

    response = await volatility_api.get_expected_move("spy", AsyncMock())

    assert response.symbol == "SPY"
    assert len(response.estimates) == 1
    estimate = response.estimates[0]
    assert estimate.expected_move == Decimal("5.10")
    assert estimate.call_strike == Decimal("500")


@pytest.mark.asyncio
async def test_get_overview_raises_404(monkeypatch) -> None:
    """Volatility endpoints should convert DataNotFoundError to HTTP 404."""

    async def fake_get_snapshot(cls, db, symbol):
        raise DataNotFoundError("Ticker not found", provider="volaris")

    monkeypatch.setattr(
        volatility_api.VolatilityService,
        "get_snapshot",
        classmethod(fake_get_snapshot),
    )

    with pytest.raises(HTTPException) as exc_info:
        await volatility_api.get_volatility_overview("unknown", AsyncMock())

    assert exc_info.value.status_code == 404
