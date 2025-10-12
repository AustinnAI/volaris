"""
Pydantic schemas for strike selection API.
"""

from decimal import Decimal
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class StrikeRecommendationRequest(BaseModel):
    """Request model for strike recommendations."""

    underlying_symbol: str = Field(..., description="Ticker symbol")
    bias: str = Field(..., description="Directional bias: 'bullish', 'bearish', or 'neutral'")
    strategy_type: str = Field(
        ...,
        description="Strategy type: 'vertical_spread', 'long_call', 'long_put', or 'auto'"
    )
    target_dte: int = Field(..., description="Target days to expiration", ge=1, le=365)
    dte_tolerance: int = Field(
        default=3,
        description="DTE tolerance window in days",
        ge=0,
        le=10
    )
    target_move_pct: Optional[Decimal] = Field(
        default=None,
        description="Expected move as % of current price",
        ge=0,
        le=100
    )
    min_credit_pct: Decimal = Field(
        default=Decimal("25.0"),
        description="Minimum credit as % of spread width for credit spreads",
        ge=0,
        le=100
    )
    max_spread_width: int = Field(
        default=10,
        description="Maximum spread width in dollars",
        ge=1,
        le=50
    )
    iv_regime_override: Optional[str] = Field(
        default=None,
        description="Override IV regime: 'high', 'neutral', or 'low'"
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
    def validate_iv_regime(cls, v: Optional[str]) -> Optional[str]:
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
    net_credit: Optional[Decimal]  # Positive credit received (credit spreads only)
    net_debit: Optional[Decimal]  # Positive debit paid (debit spreads only)
    width_points: Decimal  # Spread width in strike points
    width_dollars: Decimal  # Spread width in dollars (width_points × 100)
    spread_width: Decimal  # DEPRECATED: Use width_dollars instead
    breakeven: Decimal
    max_profit: Decimal
    max_loss: Decimal
    risk_reward_ratio: Decimal
    pop_proxy: Optional[Decimal]
    long_delta: Optional[Decimal]
    short_delta: Optional[Decimal]
    quality_score: Optional[Decimal]  # Composite ranking score
    notes: List[str]


class LongOptionCandidateResponse(BaseModel):
    """Response model for a long option candidate."""

    position: str  # "itm", "atm", "otm"
    strike: Decimal
    premium: Decimal
    breakeven: Decimal
    max_loss: Decimal
    max_profit: Optional[Decimal]  # None for calls
    delta: Optional[Decimal]
    pop_proxy: Optional[Decimal]
    notes: List[str]


class StrikeRecommendationResponse(BaseModel):
    """Response model for strike recommendations."""

    underlying_symbol: str
    underlying_price: Decimal
    strategy_type: str
    bias: str
    dte: int
    iv_rank: Optional[Decimal]
    iv_regime: Optional[str]
    spread_candidates: Optional[List[SpreadCandidateResponse]]
    long_option_candidates: Optional[List[LongOptionCandidateResponse]]
    data_timestamp: datetime
    warnings: List[str]

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z",
        }
