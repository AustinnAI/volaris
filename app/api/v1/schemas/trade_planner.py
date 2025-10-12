"""
Pydantic schemas for trade planner API.
"""

from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class VerticalSpreadRequest(BaseModel):
    """Request model for vertical spread calculation."""

    underlying_symbol: str = Field(..., description="Ticker symbol")
    underlying_price: Decimal = Field(..., description="Current spot price", gt=0)
    long_strike: Decimal = Field(..., description="Strike of the long option", gt=0)
    short_strike: Decimal = Field(..., description="Strike of the short option", gt=0)
    long_premium: Decimal = Field(..., description="Premium paid for long option", gt=0)
    short_premium: Decimal = Field(..., description="Premium received for short option", gt=0)
    option_type: str = Field(..., description="Option type: 'call' or 'put'")
    bias: str = Field(..., description="Directional bias: 'bullish', 'bearish', or 'neutral'")
    contracts: int = Field(default=1, description="Number of contracts", ge=1)
    dte: Optional[int] = Field(default=None, description="Days to expiration", ge=0)
    long_delta: Optional[Decimal] = Field(default=None, description="Delta of the long option")
    short_delta: Optional[Decimal] = Field(default=None, description="Delta of the short option")
    account_size: Optional[Decimal] = Field(default=None, description="Account size for position sizing", gt=0)
    risk_percentage: Decimal = Field(default=Decimal("2.0"), description="Risk percentage", gt=0, le=100)

    @field_validator("option_type")
    @classmethod
    def validate_option_type(cls, v: str) -> str:
        """Validate option type."""
        allowed = {"call", "put"}
        if v.lower() not in allowed:
            raise ValueError(f"option_type must be one of {allowed}")
        return v.lower()

    @field_validator("bias")
    @classmethod
    def validate_bias(cls, v: str) -> str:
        """Validate directional bias."""
        allowed = {"bullish", "bearish", "neutral"}
        if v.lower() not in allowed:
            raise ValueError(f"bias must be one of {allowed}")
        return v.lower()


class LongOptionRequest(BaseModel):
    """Request model for long option (call/put) calculation."""

    underlying_symbol: str = Field(..., description="Ticker symbol")
    underlying_price: Decimal = Field(..., description="Current spot price", gt=0)
    strike: Decimal = Field(..., description="Strike price", gt=0)
    premium: Decimal = Field(..., description="Premium paid per contract", gt=0)
    option_type: str = Field(..., description="Option type: 'call' or 'put'")
    bias: str = Field(..., description="Directional bias: 'bullish' or 'bearish'")
    contracts: int = Field(default=1, description="Number of contracts", ge=1)
    dte: Optional[int] = Field(default=None, description="Days to expiration", ge=0)
    delta: Optional[Decimal] = Field(default=None, description="Delta of the option")
    account_size: Optional[Decimal] = Field(default=None, description="Account size for position sizing", gt=0)
    risk_percentage: Decimal = Field(default=Decimal("2.0"), description="Risk percentage", gt=0, le=100)

    @field_validator("option_type")
    @classmethod
    def validate_option_type(cls, v: str) -> str:
        """Validate option type."""
        allowed = {"call", "put"}
        if v.lower() not in allowed:
            raise ValueError(f"option_type must be one of {allowed}")
        return v.lower()

    @field_validator("bias")
    @classmethod
    def validate_bias(cls, v: str) -> str:
        """Validate directional bias."""
        allowed = {"bullish", "bearish"}
        if v.lower() not in allowed:
            raise ValueError(f"bias must be one of {allowed}")
        return v.lower()


class PositionSizeRequest(BaseModel):
    """Request model for position size calculation."""

    max_loss_per_contract: Decimal = Field(..., description="Maximum loss per contract (dollars)", gt=0)
    account_size: Decimal = Field(..., description="Total account size", gt=0)
    risk_percentage: Decimal = Field(
        default=Decimal("2.0"),
        description="Max risk as % of account",
        gt=0,
        le=100
    )


class LegResponse(BaseModel):
    """Response model for a single option leg."""

    strike: float
    premium: float
    option_type: str
    position: str  # "long" or "short"
    contracts: int


class CalculationResponse(BaseModel):
    """Response model for strategy calculation."""

    strategy_type: str
    bias: str
    underlying_symbol: str
    underlying_price: Decimal

    # Position structure
    legs: List[LegResponse]

    # Risk metrics
    max_profit: Optional[Decimal]  # None for unlimited (long calls)
    max_loss: Decimal
    breakeven_prices: List[Decimal]
    risk_reward_ratio: Optional[Decimal]  # None if max_profit is unlimited

    # Probability proxy
    win_probability: Optional[Decimal]

    # Position sizing (risk-based recommendations)
    recommended_contracts: int  # Based on account size & risk %
    position_size_dollars: Decimal  # Dollar risk (max_loss * recommended_contracts)

    # Metadata
    net_premium: Decimal
    net_credit: Optional[Decimal]  # For credit spreads
    dte: Optional[int]
    total_delta: Optional[Decimal]

    assumptions: dict


class PositionSizeResponse(BaseModel):
    """Response model for position size calculation."""

    contracts: int
    max_loss_per_contract: Decimal
    account_size: Decimal
    risk_percentage: Decimal
    total_risk_dollars: Decimal
    risk_as_percent_of_account: Decimal


class StrategyCalculateRequest(BaseModel):
    """
    Unified request for strategy calculation.
    Determines strategy type from provided fields.
    """

    strategy_type: str = Field(..., description="Strategy type: 'vertical_spread', 'long_call', 'long_put'")

    # Common fields
    underlying_symbol: str
    underlying_price: Decimal

    # Vertical spread fields
    long_strike: Optional[Decimal] = None
    short_strike: Optional[Decimal] = None
    long_premium: Optional[Decimal] = None
    short_premium: Optional[Decimal] = None
    long_delta: Optional[Decimal] = None
    short_delta: Optional[Decimal] = None

    # Long option fields
    strike: Optional[Decimal] = None
    premium: Optional[Decimal] = None
    delta: Optional[Decimal] = None

    # Common
    option_type: str
    bias: str
    contracts: int = 1
    dte: Optional[int] = None

    @field_validator("strategy_type")
    @classmethod
    def validate_strategy_type(cls, v: str) -> str:
        """Validate strategy type."""
        allowed = {"vertical_spread", "long_call", "long_put"}
        if v.lower() not in allowed:
            raise ValueError(f"strategy_type must be one of {allowed}")
        return v.lower()
