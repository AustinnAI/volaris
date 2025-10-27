"""
Options Flow API Endpoints (Phase 3).

Provides endpoints for detecting and querying unusual options activity.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.flow_service import FlowService
from app.utils.logger import app_logger

# EST timezone
EST = ZoneInfo("America/New_York")

router = APIRouter(prefix="/flow", tags=["options-flow"])


class UnusualTradeResponse(BaseModel):
    """Response model for a single unusual trade."""

    contract_symbol: str
    option_type: str
    strike: float
    expiration: str
    last_price: float
    volume: int
    open_interest: int
    volume_oi_ratio: float
    premium: float
    anomaly_score: float
    flags: list[str]
    detected_at: str


class FlowResponse(BaseModel):
    """Response model for flow detection."""

    symbol: str
    detected_count: int
    unusual_trades: list[UnusualTradeResponse]
    min_score: float
    detection_time: str
    provider: str  # Which provider was used (Schwab, AlphaVantage, YFinance)


@router.get("/{symbol}", response_model=FlowResponse)
async def get_unusual_flow(
    symbol: str,
    min_score: float = Query(default=0.7, ge=0.0, le=1.0),
    force_refresh: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> FlowResponse:
    """
    Detect unusual options activity for a ticker.

    Args:
        symbol: Ticker symbol (e.g., SPY, AAPL).
        min_score: Minimum anomaly score (0-1) to return.
        force_refresh: If True, fetch fresh data. If False, use cached data from last 1 hour.

    Returns:
        FlowResponse with detected unusual trades sorted by anomaly score.
    """
    try:
        flow_service = FlowService()

        provider_name = None

        if force_refresh:
            # Detect and store new unusual activity
            app_logger.info(f"Force refresh: detecting unusual activity for {symbol}")
            flow_records, provider_name = await flow_service.detect_and_store_unusual_activity(
                db, symbol, min_score=min_score
            )
        else:
            # Try to get recent cached data (last 1 hour)
            app_logger.info(f"Checking cached unusual activity for {symbol}")
            flow_records = await flow_service.get_recent_unusual_activity(
                db, symbol, hours=1, min_score=min_score
            )

            # If no cached data, fetch fresh
            if not flow_records:
                app_logger.info(f"No cached data, detecting fresh activity for {symbol}")
                flow_records, provider_name = await flow_service.detect_and_store_unusual_activity(
                    db, symbol, min_score=min_score
                )
            else:
                provider_name = "cached"

        # Convert to response format
        unusual_trades = []
        for record in flow_records:
            # Parse flags from JSON string
            import json

            flags = json.loads(record.flags) if record.flags else []

            # Convert detected_at to EST with readable format
            detected_at_est = record.detected_at.astimezone(EST).strftime(
                "%b %d, %Y %I:%M:%S %p EST"
            )

            unusual_trades.append(
                UnusualTradeResponse(
                    contract_symbol=record.contract_symbol,
                    option_type=record.option_type,
                    strike=float(record.strike),
                    expiration=record.expiration.isoformat(),
                    last_price=float(record.last_price),
                    volume=record.volume,
                    open_interest=record.open_interest,
                    volume_oi_ratio=float(record.volume_oi_ratio),
                    premium=float(record.premium),
                    anomaly_score=float(record.anomaly_score),
                    flags=flags,
                    detected_at=detected_at_est,
                )
            )

        # Current time in EST with readable format
        detection_time_est = datetime.now(EST).strftime("%b %d, %Y %I:%M:%S %p EST")

        return FlowResponse(
            symbol=symbol.upper(),
            detected_count=len(unusual_trades),
            unusual_trades=unusual_trades,
            min_score=min_score,
            detection_time=detection_time_est,
            provider=provider_name or "unknown",
        )

    except ValueError as e:
        app_logger.error(f"Flow detection failed for {symbol}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        app_logger.error(f"Unexpected error detecting flow for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{symbol}/history", response_model=FlowResponse)
async def get_flow_history(
    symbol: str,
    hours: int = Query(default=24, ge=1, le=168),
    min_score: float = Query(default=0.7, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> FlowResponse:
    """
    Get historical unusual activity from database.

    Args:
        symbol: Ticker symbol (e.g., SPY, AAPL).
        hours: Lookback period in hours (1-168).
        min_score: Minimum anomaly score filter.
        limit: Maximum results to return.

    Returns:
        FlowResponse with historical unusual trades.
    """
    try:
        flow_service = FlowService()
        flow_records = await flow_service.get_recent_unusual_activity(
            db, symbol, hours=hours, min_score=min_score, limit=limit
        )

        # Convert to response format
        unusual_trades = []
        for record in flow_records:
            import json

            flags = json.loads(record.flags) if record.flags else []

            # Convert detected_at to EST with readable format
            detected_at_est = record.detected_at.astimezone(EST).strftime(
                "%b %d, %Y %I:%M:%S %p EST"
            )

            unusual_trades.append(
                UnusualTradeResponse(
                    contract_symbol=record.contract_symbol,
                    option_type=record.option_type,
                    strike=float(record.strike),
                    expiration=record.expiration.isoformat(),
                    last_price=float(record.last_price),
                    volume=record.volume,
                    open_interest=record.open_interest,
                    volume_oi_ratio=float(record.volume_oi_ratio),
                    premium=float(record.premium),
                    anomaly_score=float(record.anomaly_score),
                    flags=flags,
                    detected_at=detected_at_est,
                )
            )

        # Current time in EST with readable format
        detection_time_est = datetime.now(EST).strftime("%b %d, %Y %I:%M:%S %p EST")

        return FlowResponse(
            symbol=symbol.upper(),
            detected_count=len(unusual_trades),
            unusual_trades=unusual_trades,
            min_score=min_score,
            detection_time=detection_time_est,
            provider="database",  # History endpoint always queries from database
        )

    except Exception as e:
        app_logger.error(f"Failed to get flow history for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
