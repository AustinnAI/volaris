"""
Pydantic models for volatility API responses.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:  # pragma: no cover
    from app.services.volatility_service import VolatilitySnapshot


class IVSummaryResponse(BaseModel):
    """Primary IV summary payload returned by /vol/iv."""

    symbol: str = Field(..., description="Ticker symbol")
    underlying_price: Decimal | None = Field(
        default=None,
        description="Latest underlying price when available",
    )
    term: str | None = Field(
        default=None,
        description="Term associated with the summary (e.g., 30d)",
    )
    implied_vol: Decimal | None = Field(
        default=None,
        description="Implied volatility for the selected term",
    )
    iv_rank: Decimal | None = Field(
        default=None,
        description="IV Rank percentile",
    )
    iv_percentile: Decimal | None = Field(
        default=None,
        description="IV percentile (percentage of observations below current)",
    )
    regime: str | None = Field(
        default=None,
        description="IV regime classification (high, neutral, low)",
    )
    as_of: datetime | None = Field(
        default=None,
        description="Timestamp of the underlying metric",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal warnings describing missing data or fallbacks",
    )

    @classmethod
    def from_snapshot(cls, snapshot: "VolatilitySnapshot") -> "IVSummaryResponse":
        """Build response model from service snapshot."""
        return cls(
            symbol=snapshot.symbol,
            underlying_price=snapshot.underlying_price,
            term=snapshot.iv_summary.term.value if snapshot.iv_summary.term else None,
            implied_vol=snapshot.iv_summary.implied_vol,
            iv_rank=snapshot.iv_summary.iv_rank,
            iv_percentile=snapshot.iv_summary.iv_percentile,
            regime=snapshot.iv_summary.regime.value if snapshot.iv_summary.regime else None,
            as_of=snapshot.iv_summary.as_of,
            warnings=snapshot.warnings,
        )


class TermStructurePointResponse(BaseModel):
    """Term structure point entry."""

    term: str = Field(..., description="Term label (e.g., 7d, 30d)")
    implied_vol: Decimal | None = Field(default=None, description="Implied volatility for the term")
    iv_rank: Decimal | None = Field(default=None, description="IV Rank for the term")
    iv_percentile: Decimal | None = Field(
        default=None,
        description="IV percentile for the term",
    )
    as_of: datetime | None = Field(
        default=None,
        description="Timestamp for the metric",
    )


class TermStructureResponse(BaseModel):
    """Term structure response payload."""

    symbol: str = Field(..., description="Ticker symbol")
    points: list[TermStructurePointResponse] = Field(
        default_factory=list,
        description="Ordered term structure points",
    )
    warnings: list[str] = Field(default_factory=list, description="Warnings emitted by service")

    @classmethod
    def from_snapshot(cls, snapshot: "VolatilitySnapshot") -> "TermStructureResponse":
        """Build response model from service snapshot."""
        return cls(
            symbol=snapshot.symbol,
            points=[
                TermStructurePointResponse(
                    term=point.term.value,
                    implied_vol=point.implied_vol,
                    iv_rank=point.iv_rank,
                    iv_percentile=point.iv_percentile,
                    as_of=point.as_of,
                )
                for point in snapshot.term_structure
            ],
            warnings=snapshot.warnings,
        )


class ExpectedMovePointResponse(BaseModel):
    """Expected move estimate entry."""

    label: str = Field(..., description="Window label (e.g., 1-7d)")
    dte: int = Field(..., description="Days to expiration represented by the estimate", ge=0)
    expected_move: Decimal | None = Field(
        default=None,
        description="Expected move in underlying units",
    )
    expected_move_pct: Decimal | None = Field(
        default=None,
        description="Expected move expressed as percentage of the underlying price",
    )
    straddle_cost: Decimal | None = Field(
        default=None,
        description="Combined premium of ATM call+put used for EM computation",
    )
    call_strike: Decimal | None = Field(
        default=None,
        description="Call strike used for the estimate",
    )
    put_strike: Decimal | None = Field(
        default=None,
        description="Put strike used for the estimate",
    )
    as_of: datetime | None = Field(
        default=None,
        description="Timestamp of the option snapshot",
    )


class ExpectedMoveResponse(BaseModel):
    """Expected move response payload."""

    symbol: str = Field(..., description="Ticker symbol")
    underlying_price: Decimal | None = Field(
        default=None,
        description="Latest underlying price",
    )
    estimates: list[ExpectedMovePointResponse] = Field(
        default_factory=list,
        description="Expected move estimates across windows",
    )
    warnings: list[str] = Field(default_factory=list, description="Warnings emitted by service")

    @classmethod
    def from_snapshot(cls, snapshot: "VolatilitySnapshot") -> "ExpectedMoveResponse":
        """Build response model from service snapshot."""
        return cls(
            symbol=snapshot.symbol,
            underlying_price=snapshot.underlying_price,
            estimates=[
                ExpectedMovePointResponse(
                    label=estimate.label,
                    dte=estimate.dte,
                    expected_move=estimate.expected_move,
                    expected_move_pct=estimate.expected_move_pct,
                    straddle_cost=estimate.straddle_cost,
                    call_strike=estimate.call_strike,
                    put_strike=estimate.put_strike,
                    as_of=estimate.as_of,
                )
                for estimate in snapshot.expected_moves
            ],
            warnings=snapshot.warnings,
        )


class VolatilityOverviewResponse(BaseModel):
    """Full volatility overview combining summary, term structure, skew, and expected moves."""

    symbol: str = Field(..., description="Ticker symbol")
    underlying_price: Decimal | None = Field(
        default=None,
        description="Latest underlying price",
    )
    iv_summary: IVSummaryResponse
    term_structure: list[TermStructurePointResponse] = Field(
        default_factory=list,
        description="Ordered term structure points",
    )
    expected_moves: list[ExpectedMovePointResponse] = Field(
        default_factory=list,
        description="Expected move estimates",
    )
    skew: dict[str, Decimal | int | None] | None = Field(
        default=None,
        description="Basic skew metrics (call/put IV and delta)",
    )
    warnings: list[str] = Field(default_factory=list, description="Warnings emitted by service")

    @classmethod
    def from_snapshot(cls, snapshot: "VolatilitySnapshot") -> "VolatilityOverviewResponse":
        """Build response model from service snapshot."""
        skew_payload = None
        if snapshot.skew:
            skew_payload = {
                "dte": snapshot.skew.dte,
                "call_delta": snapshot.skew.call_delta,
                "put_delta": snapshot.skew.put_delta,
                "call_iv": snapshot.skew.call_iv,
                "put_iv": snapshot.skew.put_iv,
                "skew": snapshot.skew.skew,
            }

        return cls(
            symbol=snapshot.symbol,
            underlying_price=snapshot.underlying_price,
            iv_summary=IVSummaryResponse.from_snapshot(snapshot),
            term_structure=[
                TermStructurePointResponse(
                    term=point.term.value,
                    implied_vol=point.implied_vol,
                    iv_rank=point.iv_rank,
                    iv_percentile=point.iv_percentile,
                    as_of=point.as_of,
                )
                for point in snapshot.term_structure
            ],
            expected_moves=[
                ExpectedMovePointResponse(
                    label=estimate.label,
                    dte=estimate.dte,
                    expected_move=estimate.expected_move,
                    expected_move_pct=estimate.expected_move_pct,
                    straddle_cost=estimate.straddle_cost,
                    call_strike=estimate.call_strike,
                    put_strike=estimate.put_strike,
                    as_of=estimate.as_of,
                )
                for estimate in snapshot.expected_moves
            ],
            skew=skew_payload,
            warnings=snapshot.warnings,
        )
