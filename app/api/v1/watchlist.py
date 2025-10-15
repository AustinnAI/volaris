"""
Watchlist API endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.security import require_bearer_token
from app.api.v1.schemas.watchlist import WatchlistResponse, WatchlistUpdateRequest
from app.db.database import get_db
from app.services.watchlist import WatchlistService, WatchlistValidationError

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("", response_model=WatchlistResponse)
async def get_watchlist(db: AsyncSession = Depends(get_db)) -> WatchlistResponse:
    """Return the current server watchlist."""
    symbols = await WatchlistService.get_symbols(db)
    return WatchlistResponse(symbols=symbols)


@router.post("", response_model=WatchlistResponse, status_code=status.HTTP_200_OK)
async def set_watchlist(
    request: Request,
    payload: WatchlistUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> WatchlistResponse:
    """Update the server watchlist."""
    require_bearer_token(request)
    try:
        symbols = await WatchlistService.set_symbols(db, payload.symbols)
    except WatchlistValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return WatchlistResponse(symbols=symbols)
