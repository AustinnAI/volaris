"""
Pydantic schemas for strategy recommendation API.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator


class StrategyObjectivesRequest(BaseModel):
    """Trading objectives."""

    max_risk_per_trade: Decimal | None = Field(
        default=None, description="Maximum risk per trade in dollars", ge=0
    )
    min_pop_pct: Decimal | None = Field(
        default=None, description="Minimum probability of profit %", ge=0, le=100
    )
    min_risk_reward: Decimal | None = Field(
        default=None, description="Minimum risk/reward ratio", ge=0
    )
    prefer_credit: bool | None = Field(
        default=None, description="Prefer credit spreads if True, debit if False, auto if None"
    )
    avoid_earnings: bool = Field(default=False, description="Avoid trades during earnings window")
    account_size: Decimal | None = Field(
        default=None, description="Account size for position sizing", ge=0
    )
    bias_reason: str | None = Field(
        default="user_manual",
        description="Reason for bias: 'ssl_sweep', 'bsl_sweep', 'fvg_retest', 'structure_shift', 'user_manual'",
    )

    @field_validator("bias_reason")
    @classmethod
    def validate_bias_reason(cls, v: str | None) -> str | None:
        """Validate bias_reason is one of the allowed values."""
        if v is None:
            return "user_manual"
        allowed_values = {"ssl_sweep", "bsl_sweep", "fvg_retest", "structure_shift", "user_manual"}
        if v.lower() not in allowed_values:
            raise ValueError(f"bias_reason must be one of: {', '.join(allowed_values)}")
        return v.lower()


class StrategyConstraintsRequest(BaseModel):
    """Strategy constraints."""

    min_credit_pct: Decimal | None = Field(
        default=None, description="Minimum credit as % of spread width", ge=0, le=100
    )
    max_spread_width: int | None = Field(
        default=None, description="Maximum spread width in points", ge=1, le=50
    )
    iv_regime_override: str | None = Field(
        default=None, description="Override IV regime: 'high', 'neutral', or 'low'"
    )
    min_open_interest: int | None = Field(default=None, description="Minimum open interest", ge=0)
    min_volume: int | None = Field(default=None, description="Minimum daily volume", ge=0)
    min_mark_price: Decimal | None = Field(default=None, description="Minimum mark price", ge=0)

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


class StrategyRecommendationRequest(BaseModel):
    """Request model for strategy recommendations."""

    underlying_symbol: str = Field(..., description="Ticker symbol")
    bias: str = Field(..., description="Directional bias: 'bullish', 'bearish', or 'neutral'")
    target_dte: int = Field(..., description="Target days to expiration", ge=1, le=365)
    dte_tolerance: int = Field(default=3, description="DTE tolerance window in days", ge=0, le=10)
    target_move_pct: Decimal | None = Field(
        default=None, description="Expected move as % of current price", ge=0, le=100
    )
    objectives: StrategyObjectivesRequest | None = Field(
        default=None, description="Trading objectives and preferences"
    )
    constraints: StrategyConstraintsRequest | None = Field(
        default=None, description="Strategy constraints and filters"
    )

    @field_validator("bias")
    @classmethod
    def validate_bias(cls, v: str) -> str:
        """Validate bias."""
        allowed = {"bullish", "bearish", "neutral"}
        if v.lower() not in allowed:
            raise ValueError(f"bias must be one of {allowed}")
        return v.lower()


class StrategyRecommendationResponse(BaseModel):
    """Individual strategy recommendation."""

    rank: int = Field(..., description="Ranking (1=best)")
    strategy_family: str = Field(..., description="Strategy family")
    option_type: str = Field(..., description="'call' or 'put'")
    position: str = Field(..., description="'itm', 'atm', or 'otm'")

    # Strike details
    strike: Decimal | None = Field(default=None, description="Strike for long options")
    long_strike: Decimal | None = Field(default=None, description="Long strike for spreads")
    short_strike: Decimal | None = Field(default=None, description="Short strike for spreads")

    # Pricing
    premium: Decimal | None = Field(default=None, description="Premium for long options")
    long_premium: Decimal | None = Field(default=None, description="Long premium for spreads")
    short_premium: Decimal | None = Field(default=None, description="Short premium for spreads")
    net_premium: Decimal | None = Field(default=None, description="Net debit/credit")
    is_credit: bool | None = Field(default=None, description="True if credit spread")
    net_credit: Decimal | None = Field(default=None, description="Credit received")
    net_debit: Decimal | None = Field(default=None, description="Debit paid")

    # Spread details
    width_points: Decimal | None = Field(default=None, description="Spread width in points")
    width_dollars: Decimal | None = Field(default=None, description="Spread width in dollars")

    # Risk metrics
    breakeven: Decimal = Field(..., description="Breakeven price")
    max_profit: Decimal | None = Field(..., description="Maximum profit (None=unlimited)")
    max_loss: Decimal = Field(..., description="Maximum loss")
    risk_reward_ratio: Decimal | None = Field(default=None, description="Risk/reward ratio")

    # Probabilities
    pop_proxy: Decimal | None = Field(default=None, description="Probability of profit proxy %")

    # Greeks
    delta: Decimal | None = Field(default=None, description="Delta for long options")
    long_delta: Decimal | None = Field(default=None, description="Long delta for spreads")
    short_delta: Decimal | None = Field(default=None, description="Short delta for spreads")

    # Position sizing
    recommended_contracts: int | None = Field(
        default=None, description="Recommended contract count"
    )
    position_size_dollars: Decimal | None = Field(
        default=None, description="Position size in dollars"
    )

    # Scoring
    composite_score: Decimal = Field(..., description="Composite ranking score (0-100)")

    # Liquidity
    avg_open_interest: int | None = Field(default=None, description="Average open interest")
    avg_volume: int | None = Field(default=None, description="Average volume")

    # Reasoning
    reasons: list[str] = Field(default_factory=list, description="Reasoning bullets")
    warnings: list[str] = Field(default_factory=list, description="Warning messages")


class StrategyRecommendationResultResponse(BaseModel):
    """Complete recommendation result."""

    underlying_symbol: str = Field(..., description="Ticker symbol")
    underlying_price: Decimal = Field(..., description="Current underlying price")
    chosen_strategy_family: str = Field(..., description="Selected strategy family")
    iv_rank: Decimal | None = Field(default=None, description="IV rank percentile")
    iv_regime: str | None = Field(default=None, description="IV regime classification")
    dte: int = Field(..., description="Days to expiration")
    expected_move_pct: Decimal | None = Field(default=None, description="Expected move %")
    data_timestamp: datetime = Field(..., description="Data timestamp")

    # Recommendations
    recommendations: list[StrategyRecommendationResponse] = Field(
        ..., description="Ranked recommendations (top 2-3)"
    )

    # Configuration
    config_used: dict[str, Any] = Field(..., description="Configuration used")

    # Warnings
    warnings: list[str] = Field(default_factory=list, description="System warnings")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z",
        }
