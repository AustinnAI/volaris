"""
Volatility API Endpoints
Expose IV summaries, term structure, expected move, and skew analytics.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.volatility import (
    ExpectedMoveResponse,
    IVSummaryResponse,
    TermStructureResponse,
    VolatilityOverviewResponse,
)
from app.db.database import get_db
from app.services.exceptions import DataNotFoundError
from app.services.volatility_service import VolatilityService

router = APIRouter(prefix="/vol", tags=["volatility"])


@router.get("/iv/{symbol}", response_model=IVSummaryResponse)
async def get_iv_summary(symbol: str, db: AsyncSession = Depends(get_db)) -> IVSummaryResponse:
    """
    Return primary IV metrics (current IV, IV Rank/Percentile, regime) for the symbol.
    """
    try:
        snapshot = await VolatilityService.get_snapshot(db, symbol)
    except DataNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return IVSummaryResponse.from_snapshot(snapshot)


@router.get("/term/{symbol}", response_model=TermStructureResponse)
async def get_term_structure(symbol: str, db: AsyncSession = Depends(get_db)) -> TermStructureResponse:
    """
    Return IV term structure across configured horizons (7-90d).
    """
    try:
        snapshot = await VolatilityService.get_snapshot(db, symbol)
    except DataNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TermStructureResponse.from_snapshot(snapshot)


@router.get("/expected-move/{symbol}", response_model=ExpectedMoveResponse)
async def get_expected_move(symbol: str, db: AsyncSession = Depends(get_db)) -> ExpectedMoveResponse:
    """
    Return expected move estimates (1-7d and 14-45d) derived from ATM straddles.
    """
    try:
        snapshot = await VolatilityService.get_snapshot(db, symbol)
    except DataNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ExpectedMoveResponse.from_snapshot(snapshot)


@router.get("/overview/{symbol}", response_model=VolatilityOverviewResponse)
async def get_volatility_overview(
    symbol: str,
    db: AsyncSession = Depends(get_db),
) -> VolatilityOverviewResponse:
    """
    Return composite volatility overview covering IV summary, term structure, skew, and expected moves.
    """
    try:
        snapshot = await VolatilityService.get_snapshot(db, symbol)
    except DataNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return VolatilityOverviewResponse.from_snapshot(snapshot)

