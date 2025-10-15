"""
Pydantic models for watchlist endpoints.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field


class WatchlistResponse(BaseModel):
    """Response payload containing watchlist symbols."""

    symbols: list[str] = Field(..., description="Uppercase ticker symbols")


class WatchlistUpdateRequest(BaseModel):
    """Request body for updating the watchlist."""

    symbols: Annotated[list[str], Field(..., description="List of uppercase symbols")]


class RefreshBatchRequest(BaseModel):
    """Request for manual batch refresh override."""

    symbols: list[str] = Field(..., description="Symbols to refresh", min_length=1)
    kinds: list[str] = Field(
        default_factory=lambda: ["price", "options", "iv"],
        description="Refresh kinds for manual override",
    )
