"""
Volatility Analytics Helpers
Pure functions for implied-volatility summaries, term structure, skew, and expected move calculations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Sequence

from app.core.strike_selection import IVRegime, OptionContractData
from app.db.models import IVTerm

# Ordered term buckets for consistent presentation (short to long dated)
TERM_ORDER: tuple[IVTerm, ...] = (
    IVTerm.D7,
    IVTerm.D14,
    IVTerm.D30,
    IVTerm.D60,
    IVTerm.D90,
)


@dataclass(slots=True, frozen=True)
class IVMetricSnapshot:
    """Latest IV metric for a specific term."""

    term: IVTerm
    as_of: datetime | None
    implied_vol: Decimal | None
    iv_rank: Decimal | None
    iv_percentile: Decimal | None


@dataclass(slots=True, frozen=True)
class IVSummary:
    """Primary IV snapshot with regime classification."""

    term: IVTerm | None
    implied_vol: Decimal | None
    iv_rank: Decimal | None
    iv_percentile: Decimal | None
    regime: IVRegime | None
    as_of: datetime | None


@dataclass(slots=True, frozen=True)
class TermStructurePoint:
    """Term structure entry capturing IV across expirations."""

    term: IVTerm
    implied_vol: Decimal | None
    iv_rank: Decimal | None
    iv_percentile: Decimal | None
    as_of: datetime | None


@dataclass(slots=True, frozen=True)
class OptionSkew:
    """Basic call/put skew snapshot using ~25 delta contracts."""

    dte: int
    call_delta: Decimal | None
    put_delta: Decimal | None
    call_iv: Decimal | None
    put_iv: Decimal | None
    skew: Decimal | None


@dataclass(slots=True, frozen=True)
class ExpectedMoveEstimate:
    """Straddle-based expected move estimate for a given window."""

    label: str
    dte: int
    expected_move: Decimal | None
    expected_move_pct: Decimal | None
    straddle_cost: Decimal | None
    call_strike: Decimal | None
    put_strike: Decimal | None
    as_of: datetime | None


def summarize_iv(
    metrics: Sequence[IVMetricSnapshot],
    high_threshold: float,
    low_threshold: float,
) -> IVSummary:
    """
    Build a primary IV summary using the preferred 30-day term with graceful fallback.

    Args:
        metrics: Collection of IV snapshots (one per term ideally)
        high_threshold: IV Rank percentile for "high" regime
        low_threshold: IV Rank percentile for "low" regime

    Returns:
        IVSummary with regime classification. May contain None values when data missing.
    """
    preferred_terms = (IVTerm.D30, IVTerm.D14, IVTerm.D7)
    lookup = {metric.term: metric for metric in metrics}

    chosen = next((lookup[term] for term in preferred_terms if term in lookup), None)

    if chosen is None and metrics:
        chosen = metrics[0]

    if chosen is None:
        return IVSummary(
            term=None,
            implied_vol=None,
            iv_rank=None,
            iv_percentile=None,
            regime=None,
            as_of=None,
        )

    regime = _resolve_regime(chosen.iv_rank, high_threshold, low_threshold)

    return IVSummary(
        term=chosen.term,
        implied_vol=chosen.implied_vol,
        iv_rank=chosen.iv_rank,
        iv_percentile=chosen.iv_percentile,
        regime=regime,
        as_of=chosen.as_of,
    )


def build_term_structure(metrics: Sequence[IVMetricSnapshot]) -> list[TermStructurePoint]:
    """
    Create a sorted term structure series for visualization/analysis.

    Args:
        metrics: Collection of IV snapshots.

    Returns:
        Sorted list of term structure points from shortest to longest term.
    """
    ordered = sorted(
        metrics,
        key=lambda metric: TERM_ORDER.index(metric.term) if metric.term in TERM_ORDER else len(TERM_ORDER),
    )
    return [
        TermStructurePoint(
            term=metric.term,
            implied_vol=metric.implied_vol,
            iv_rank=metric.iv_rank,
            iv_percentile=metric.iv_percentile,
            as_of=metric.as_of,
        )
        for metric in ordered
    ]


def compute_skew(
    contracts: Sequence[OptionContractData],
    underlying_price: Decimal | None,
    dte: int,
) -> OptionSkew | None:
    """
    Estimate vertical skew using ~25 delta call/put IVs.

    Args:
        contracts: Option chain contracts.
        underlying_price: Underlying price for sanity checks.
        dte: Days to expiration for the snapshot.

    Returns:
        OptionSkew if enough data present; otherwise None.
    """
    if not contracts or underlying_price is None or underlying_price <= 0:
        return None

    call_contract = _closest_delta_contract(contracts, target_delta=Decimal("0.25"), option_type="call")
    put_contract = _closest_delta_contract(contracts, target_delta=Decimal("-0.25"), option_type="put")

    if call_contract is None or put_contract is None:
        return None

    if call_contract.implied_vol is None or put_contract.implied_vol is None:
        return None

    skew = call_contract.implied_vol - put_contract.implied_vol

    return OptionSkew(
        dte=dte,
        call_delta=call_contract.delta,
        put_delta=put_contract.delta,
        call_iv=call_contract.implied_vol,
        put_iv=put_contract.implied_vol,
        skew=skew,
    )


def compute_expected_move(
    label: str,
    contracts: Sequence[OptionContractData],
    underlying_price: Decimal | None,
    dte: int,
    as_of: datetime | None,
) -> ExpectedMoveEstimate | None:
    """
    Calculate straddle-based expected move for a target window.

    Args:
        label: Human readable window description (e.g., \"1-7d\").
        contracts: Option chain contracts.
        underlying_price: Current underlying price.
        dte: Days to expiration represented by the chain.
        as_of: Timestamp of the option snapshot.

    Returns:
        ExpectedMoveEstimate or None when insufficient data.
    """
    if not contracts or underlying_price is None or underlying_price <= 0:
        return None

    call_contract = _closest_strike_contract(contracts, option_type="call", underlying_price=underlying_price)
    put_contract = _closest_strike_contract(contracts, option_type="put", underlying_price=underlying_price)

    if call_contract is None or put_contract is None:
        return None

    call_price = _resolve_option_price(call_contract)
    put_price = _resolve_option_price(put_contract)

    if call_price is None or put_price is None:
        return None

    straddle_cost = call_price + put_price
    if straddle_cost <= 0:
        return None

    expected_move = straddle_cost
    expected_move_pct = (expected_move / underlying_price) * Decimal(100)

    return ExpectedMoveEstimate(
        label=label,
        dte=dte,
        expected_move=expected_move,
        expected_move_pct=expected_move_pct,
        straddle_cost=straddle_cost,
        call_strike=call_contract.strike,
        put_strike=put_contract.strike,
        as_of=as_of,
    )


def _resolve_regime(
    iv_rank: Decimal | None,
    high_threshold: float,
    low_threshold: float,
) -> IVRegime | None:
    """Map IV rank into a regime using configured thresholds."""
    if iv_rank is None:
        return None

    if iv_rank > Decimal(str(high_threshold)):
        return IVRegime.HIGH
    if iv_rank >= Decimal(str(low_threshold)):
        return IVRegime.NEUTRAL
    return IVRegime.LOW


def _closest_delta_contract(
    contracts: Sequence[OptionContractData],
    target_delta: Decimal,
    option_type: str,
) -> OptionContractData | None:
    """Return contract with delta closest to the requested target."""
    candidates = [
        contract
        for contract in contracts
        if contract.option_type == option_type and contract.delta is not None
    ]
    if not candidates:
        return None

    return min(candidates, key=lambda contract: abs(contract.delta - target_delta))


def _closest_strike_contract(
    contracts: Sequence[OptionContractData],
    option_type: str,
    underlying_price: Decimal,
) -> OptionContractData | None:
    """Return contract whose strike is closest to the underlying price."""
    candidates = [
        contract
        for contract in contracts
        if contract.option_type == option_type
    ]
    if not candidates:
        return None

    return min(candidates, key=lambda contract: abs(contract.strike - underlying_price))


def _resolve_option_price(contract: OptionContractData) -> Decimal | None:
    """Resolve the most reliable option price (mark -> mid -> bid)."""
    if contract.mark is not None and contract.mark > 0:
        return contract.mark

    if contract.bid is not None and contract.ask is not None:
        mid = (contract.bid + contract.ask) / Decimal(2)
        if mid > 0:
            return mid

    if contract.ask is not None and contract.ask > 0:
        return contract.ask

    if contract.bid is not None and contract.bid > 0:
        return contract.bid

    return None


def metrics_by_term(metrics: Iterable[IVMetricSnapshot]) -> dict[IVTerm, IVMetricSnapshot]:
    """Index IV metrics by term for quick lookups."""
    return {metric.term: metric for metric in metrics}
