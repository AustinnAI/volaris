"""
Pydantic schemas for strike selection API.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class StrikeRecommendationRequest(BaseModel):
    """Request model for strike recommendations."""

    underlying_symbol: str = Field(..., description="Ticker symbol")
    bias: str = Field(..., description="Directional bias: 'bullish', 'bearish', or 'neutral'")
    strategy_type: str = Field(
        ..., description="Strategy type: 'vertical_spread', 'long_call', 'long_put', or 'auto'"
    )
    target_dte: int = Field(..., description="Target days to expiration", ge=1, le=365)
    dte_tolerance: int = Field(default=3, description="DTE tolerance window in days", ge=0, le=10)
    target_move_pct: Decimal | None = Field(
        default=None, description="Expected move as % of current price", ge=0, le=100
    )
    min_credit_pct: Decimal = Field(
        default=Decimal("25.0"),
        description="Minimum credit as % of spread width for credit spreads",
        ge=0,
        le=100,
    )
    max_spread_width: int = Field(
        default=10, description="Maximum spread width in dollars", ge=1, le=50
    )
    iv_regime_override: str | None = Field(
        default=None, description="Override IV regime: 'high', 'neutral', or 'low'"
    )

    @field_validator("bias")
    @classmethod
    def validate_bias(cls, v: str) -> str:
        """Validate bias."""
        allowed = {"bullish", "bearish", "neutral"}
        if v.lower() not in allowed:
            raise ValueError(f"bias must be one of {allowed}")
        return v.lower()

    @field_validator("strategy_type")
    @classmethod
    def validate_strategy_type(cls, v: str) -> str:
        """Validate strategy type."""
        allowed = {"vertical_spread", "long_call", "long_put", "auto"}
        if v.lower() not in allowed:
            raise ValueError(f"strategy_type must be one of {allowed}")
        return v.lower()

    @field_validator("iv_regime_override")
    @classmethod
    def validate_iv_regime(cls, v: str | None) -> str | None:
        """Validate IV regime override."""
        if v is None:
            return None
        allowed = {"high", "neutral", "low"}
        if v.lower() not in allowed:
            raise ValueError(f"iv_regime_override must be one of {allowed}")
        return v.lower()


class SpreadCandidateResponse(BaseModel):
    """Response model for a vertical spread candidate."""

    position: str  # "itm", "atm", "otm"
    long_strike: Decimal
    short_strike: Decimal
    long_premium: Decimal
    short_premium: Decimal
    net_premium: Decimal  # Negative for credits, positive for debits
    is_credit: bool  # True if credit spread, False if debit spread
    net_credit: Decimal | None  # Positive credit received (credit spreads only)
    net_debit: Decimal | None  # Positive debit paid (debit spreads only)
    width_points: Decimal  # Spread width in strike points
    width_dollars: Decimal  # Spread width in dollars (width_points × 100)
    spread_width: Decimal  # DEPRECATED: Use width_dollars instead
    breakeven: Decimal
    max_profit: Decimal
    max_loss: Decimal
    risk_reward_ratio: Decimal
    pop_proxy: Decimal | None
    long_delta: Decimal | None
    short_delta: Decimal | None
    quality_score: Decimal | None  # Composite ranking score
    notes: list[str]


class LongOptionCandidateResponse(BaseModel):
    """Response model for a long option candidate."""

    position: str  # "itm", "atm", "otm"
    strike: Decimal
    premium: Decimal
    breakeven: Decimal
    max_loss: Decimal
    max_profit: Decimal | None  # None for calls
    delta: Decimal | None
    pop_proxy: Decimal | None
    notes: list[str]


class StrikeRecommendationResponse(BaseModel):
    """Response model for strike recommendations."""

    underlying_symbol: str
    underlying_price: Decimal
    strategy_type: str
    bias: str
    dte: int
    iv_rank: Decimal | None
    iv_regime: str | None
    spread_candidates: list[SpreadCandidateResponse] | None
    long_option_candidates: list[LongOptionCandidateResponse] | None
    data_timestamp: datetime
    warnings: list[str]

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z",
        }
