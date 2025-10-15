"""Unit tests for volatility analytics helpers."""

from datetime import UTC, datetime
from decimal import Decimal

from app.core.strike_selection import IVRegime, OptionContractData
from app.core.volatility import (
    IVMetricSnapshot,
    compute_expected_move,
    compute_skew,
    summarize_iv,
)
from app.db.models import IVTerm


def _option(
    option_type: str,
    strike: str,
    mark: str,
    delta: str,
    iv: str,
) -> OptionContractData:
    """Helper to construct option contract data for tests."""
    price = Decimal(mark)
    return OptionContractData(
        strike=Decimal(strike),
        option_type=option_type,
        bid=price,
        ask=price,
        mark=price,
        delta=Decimal(delta),
        implied_vol=Decimal(iv),
        volume=None,
        open_interest=None,
    )


def test_compute_expected_move_returns_estimate() -> None:
    """Expected move should combine ATM call/put marks into a per-share estimate."""
    contracts = [
        _option("call", "100", "2.50", "0.52", "0.30"),
        _option("put", "100", "2.60", "-0.48", "0.32"),
        _option("call", "105", "1.40", "0.30", "0.28"),
    ]

    estimate = compute_expected_move(
        label="1-7d",
        contracts=contracts,
        underlying_price=Decimal("100"),
        dte=5,
        as_of=datetime(2024, 5, 1, tzinfo=UTC),
    )

    assert estimate is not None
    assert estimate.expected_move == Decimal("5.10")
    assert estimate.expected_move_pct.quantize(Decimal("0.01")) == Decimal("5.10")
    assert estimate.call_strike == Decimal("100")
    assert estimate.put_strike == Decimal("100")


def test_compute_expected_move_returns_none_when_missing_marks() -> None:
    """Expected move should return None when prices unavailable."""
    contracts = [
        OptionContractData(
            strike=Decimal("100"),
            option_type="call",
            bid=None,
            ask=None,
            mark=None,
            delta=Decimal("0.5"),
            implied_vol=Decimal("0.30"),
            volume=None,
            open_interest=None,
        ),
        _option("put", "100", "2.50", "-0.48", "0.32"),
    ]

    estimate = compute_expected_move(
        label="1-7d",
        contracts=contracts,
        underlying_price=Decimal("100"),
        dte=5,
        as_of=datetime(2024, 5, 1, tzinfo=UTC),
    )

    assert estimate is None


def test_compute_skew_uses_closest_delta_contracts() -> None:
    """Skew should compare ~25 delta call/put IVs."""
    contracts = [
        _option("call", "105", "1.40", "0.30", "0.28"),
        _option("call", "110", "0.90", "0.20", "0.26"),
        _option("put", "95", "1.20", "-0.30", "0.34"),
        _option("put", "90", "0.80", "-0.20", "0.29"),
    ]

    skew = compute_skew(
        contracts=contracts,
        underlying_price=Decimal("100"),
        dte=30,
    )

    assert skew is not None
    assert skew.skew == Decimal("0.28") - Decimal("0.34")
    assert skew.call_delta == Decimal("0.30")
    assert skew.put_delta == Decimal("-0.30")


def test_summarize_iv_prefers_thirty_day_term() -> None:
    """IV summary should select 30d term and classify regime."""
    metrics = [
        IVMetricSnapshot(
            term=IVTerm.D14,
            as_of=datetime(2024, 5, 1, tzinfo=UTC),
            implied_vol=Decimal("0.28"),
            iv_rank=Decimal("35"),
            iv_percentile=Decimal("40"),
        ),
        IVMetricSnapshot(
            term=IVTerm.D30,
            as_of=datetime(2024, 5, 1, tzinfo=UTC),
            implied_vol=Decimal("0.32"),
            iv_rank=Decimal("60"),
            iv_percentile=Decimal("65"),
        ),
    ]

    summary = summarize_iv(metrics, high_threshold=50.0, low_threshold=25.0)

    assert summary.term == IVTerm.D30
    assert summary.implied_vol == Decimal("0.32")
    assert summary.iv_rank == Decimal("60")
    assert summary.regime == IVRegime.HIGH
