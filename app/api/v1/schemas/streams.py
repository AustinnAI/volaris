"""Pydantic schemas for price streams."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PriceStreamCreateRequest(BaseModel):
    symbol: str = Field(..., description="Ticker symbol (e.g., SPY)")
    interval_seconds: Optional[int] = Field(
        default=None,
        description="Interval in seconds between updates (defaults to config)",
    )
    channel_id: str = Field(..., description="Discord channel ID receiving the updates")
    created_by: Optional[str] = Field(
        default=None,
        description="Discord user ID that created the stream",
    )


class PriceStreamResponse(BaseModel):
    id: int
    symbol: str
    channel_id: str
    interval_seconds: int
    next_run_at: datetime
    created_by: Optional[str]
    created_at: datetime


class PriceStreamListResponse(BaseModel):
    streams: List[PriceStreamResponse]


class PriceStreamDispatch(BaseModel):
    id: int
    symbol: str
    channel_id: str
    interval_seconds: int
    price: float
    previous_close: float
    change: float
    change_percent: float
    timestamp: datetime


class PriceStreamEvaluateResponse(BaseModel):
    streams: List[PriceStreamDispatch]
