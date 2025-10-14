"""
Pydantic schemas for price alert management.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.db.models import PriceAlertDirection


class PriceAlertCreateRequest(BaseModel):
    """Payload for creating a new price alert."""

    symbol: str = Field(..., description="Ticker symbol (e.g., SPY)")
    target_price: Decimal = Field(..., gt=0, description="Target price that triggers the alert")
    direction: PriceAlertDirection = Field(
        ..., description="Trigger direction: above (price ≥ target) or below (price ≤ target)"
    )
    channel_id: str = Field(..., description="Discord channel ID to notify when the alert fires")
    created_by: str | None = Field(
        default=None,
        description="Discord user ID that created the alert (optional metadata)",
    )


class PriceAlertResponse(BaseModel):
    """Serialized price alert record."""

    id: int
    symbol: str
    target_price: Decimal
    direction: PriceAlertDirection
    channel_id: str
    created_by: str | None
    created_at: datetime


class PriceAlertListResponse(BaseModel):
    """Response containing all active alerts."""

    alerts: list[PriceAlertResponse]


class PriceAlertTriggered(BaseModel):
    """Alert that just fired and should be announced."""

    id: int
    symbol: str
    target_price: Decimal
    direction: PriceAlertDirection
    current_price: Decimal
    channel_id: str
    created_by: str | None


class PriceAlertEvaluateResponse(BaseModel):
    """Result of evaluating alerts for trigger conditions."""

    triggered: list[PriceAlertTriggered]
