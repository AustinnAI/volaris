"""
Options Flow API Endpoints (Phase 3).

Provides endpoints for detecting and querying unusual options activity.
"""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import FlowSubscription, Ticker
from app.services.flow_service import FlowService
from app.utils.logger import app_logger

# EST timezone
EST = ZoneInfo("America/New_York")

router = APIRouter(prefix="/flow", tags=["options-flow"])


# NOTE: Route order matters! More specific routes (like /scan) must come before
# catch-all routes (like /{symbol}) to avoid incorrect matching.


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


class SubscriptionResponse(BaseModel):
    """Response model for a single subscription."""

    symbol: str
    min_score: float
    channel_id: str
    created_at: str


class SubscriptionsListResponse(BaseModel):
    """Response model for listing user subscriptions."""

    user_id: str
    subscription_count: int
    subscriptions: list[SubscriptionResponse]


class BatchScanResult(BaseModel):
    """Result for a single ticker in batch scan."""

    symbol: str
    detected_count: int
    top_score: float | None
    unusual_trades: list[UnusualTradeResponse]
    provider: str
    subscribers: list[dict]  # List of {user_id, channel_id, min_score}


class BatchScanResponse(BaseModel):
    """Response model for batch flow scan."""

    scanned_count: int
    detected_tickers: int
    results: list[BatchScanResult]
    scan_time: str


# -------------------------------------------------------------------------
# SPECIFIC ROUTES (must come before catch-all /{symbol} route)
# -------------------------------------------------------------------------


@router.get("/scan", response_model=BatchScanResponse)
async def batch_scan_subscribed_tickers(
    min_score: float = Query(default=0.75, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
) -> BatchScanResponse:
    """
    Batch scan all tickers with active subscriptions for unusual flow.

    This endpoint is called by GitHub Actions workflow to detect unusual activity
    and notify subscribed users via Discord webhooks.

    Args:
        min_score: Global minimum anomaly score (can be overridden per subscription).

    Returns:
        BatchScanResponse with detected unusual activity and subscriber lists.
    """
    try:
        # Get all tickers with active subscriptions
        stmt = (
            select(Ticker, FlowSubscription)
            .join(FlowSubscription, FlowSubscription.ticker_id == Ticker.id)
            .where(FlowSubscription.is_active)
            .order_by(Ticker.symbol)
        )
        result = await db.execute(stmt)
        rows = result.all()

        # Group subscriptions by ticker
        ticker_subs = {}
        for ticker, sub in rows:
            if ticker.symbol not in ticker_subs:
                ticker_subs[ticker.symbol] = {"ticker": ticker, "subscribers": []}

            ticker_subs[ticker.symbol]["subscribers"].append(
                {
                    "user_id": sub.user_id,
                    "channel_id": sub.channel_id,
                    "min_score": float(sub.min_score),
                }
            )

        # Scan each ticker for unusual flow
        flow_service = FlowService()
        results = []
        detected_tickers = 0

        for symbol, data in ticker_subs.items():
            try:
                # Use lowest min_score from all subscribers for this ticker
                ticker_min_score = min(
                    [sub["min_score"] for sub in data["subscribers"]],
                    default=min_score,
                )

                # Detect unusual activity (with 1hr cache)
                flow_records = await flow_service.get_recent_unusual_activity(
                    db, symbol, hours=1, min_score=ticker_min_score
                )

                # If no cached data, fetch fresh
                if not flow_records:
                    flow_records, provider_name = (
                        await flow_service.detect_and_store_unusual_activity(
                            db, symbol, min_score=ticker_min_score
                        )
                    )
                else:
                    provider_name = "cached"

                # Convert to response format
                unusual_trades = []
                top_score = None

                for record in flow_records:
                    import json

                    flags = json.loads(record.flags) if record.flags else []
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

                    if top_score is None or float(record.anomaly_score) > top_score:
                        top_score = float(record.anomaly_score)

                if unusual_trades:
                    detected_tickers += 1

                results.append(
                    BatchScanResult(
                        symbol=symbol,
                        detected_count=len(unusual_trades),
                        top_score=top_score,
                        unusual_trades=unusual_trades,
                        provider=provider_name,
                        subscribers=data["subscribers"],
                    )
                )

            except Exception as ticker_error:
                app_logger.error(f"Failed to scan {symbol} in batch: {ticker_error}", exc_info=True)
                # Continue with next ticker
                continue

        scan_time_est = datetime.now(EST).strftime("%b %d, %Y %I:%M:%S %p EST")

        return BatchScanResponse(
            scanned_count=len(ticker_subs),
            detected_tickers=detected_tickers,
            results=results,
            scan_time=scan_time_est,
        )

    except Exception as e:
        app_logger.error(f"Batch flow scan failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Batch scan failed")


# -------------------------------------------------------------------------
# CATCH-ALL ROUTES (must come after specific routes)
# -------------------------------------------------------------------------


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


# -------------------------------------------------------------------------
# Subscription Management (Phase 3.2 - Automated Alerts)
# -------------------------------------------------------------------------


class SubscribeRequest(BaseModel):
    """Request model for flow subscription."""

    user_id: str = Field(..., description="Discord user ID")
    symbol: str = Field(..., description="Ticker symbol")
    channel_id: str = Field(..., description="Discord channel ID for alerts")
    min_score: float = Field(default=0.75, ge=0.0, le=1.0, description="Min anomaly score")


class UnsubscribeRequest(BaseModel):
    """Request model for unsubscribing."""

    user_id: str = Field(..., description="Discord user ID")
    symbol: str = Field(..., description="Ticker symbol")


class UpdateSubscriptionRequest(BaseModel):
    """Request model for updating subscription settings."""

    user_id: str = Field(..., description="Discord user ID")
    symbol: str = Field(..., description="Ticker symbol")
    min_score: float = Field(..., ge=0.0, le=1.0, description="New min anomaly score")


@router.post("/subscribe")
async def subscribe_to_flow(
    request: SubscribeRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Subscribe a user to unusual flow alerts for a ticker.

    Args:
        request: Subscription details (user_id, symbol, channel_id, min_score).

    Returns:
        Success message.
    """
    try:
        # Get or create ticker
        stmt = select(Ticker).where(Ticker.symbol == request.symbol.upper())
        result = await db.execute(stmt)
        ticker = result.scalar_one_or_none()

        if not ticker:
            # Create ticker if it doesn't exist
            ticker = Ticker(symbol=request.symbol.upper(), is_active=True)
            db.add(ticker)
            await db.flush()

        # Check for existing subscription
        stmt = select(FlowSubscription).where(
            FlowSubscription.user_id == request.user_id,
            FlowSubscription.ticker_id == ticker.id,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Already subscribed to {request.symbol} flow alerts",
            )

        # Create subscription
        subscription = FlowSubscription(
            user_id=request.user_id,
            ticker_id=ticker.id,
            channel_id=request.channel_id,
            min_score=Decimal(str(request.min_score)),
            is_active=True,
        )
        db.add(subscription)
        await db.commit()

        app_logger.info(
            f"User {request.user_id} subscribed to {request.symbol} flow alerts (min_score={request.min_score})"
        )

        return {
            "message": f"Successfully subscribed to {request.symbol} flow alerts",
            "symbol": request.symbol.upper(),
            "min_score": request.min_score,
        }

    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Failed to create flow subscription: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create subscription")


@router.post("/unsubscribe")
async def unsubscribe_from_flow(
    request: UnsubscribeRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Unsubscribe a user from flow alerts for a ticker.

    Args:
        request: Unsubscribe details (user_id, symbol).

    Returns:
        Success message.
    """
    try:
        # Find ticker
        stmt = select(Ticker).where(Ticker.symbol == request.symbol.upper())
        result = await db.execute(stmt)
        ticker = result.scalar_one_or_none()

        if not ticker:
            raise HTTPException(status_code=404, detail=f"Ticker {request.symbol} not found")

        # Find and delete subscription
        stmt = select(FlowSubscription).where(
            FlowSubscription.user_id == request.user_id,
            FlowSubscription.ticker_id == ticker.id,
        )
        result = await db.execute(stmt)
        subscription = result.scalar_one_or_none()

        if not subscription:
            raise HTTPException(
                status_code=404,
                detail=f"No active subscription found for {request.symbol}",
            )

        await db.delete(subscription)
        await db.commit()

        app_logger.info(f"User {request.user_id} unsubscribed from {request.symbol} flow alerts")

        return {
            "message": f"Successfully unsubscribed from {request.symbol} flow alerts",
            "symbol": request.symbol.upper(),
        }

    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Failed to delete flow subscription: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete subscription")


@router.put("/update")
async def update_flow_subscription(
    request: UpdateSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Update an existing flow subscription's settings.

    Args:
        request: Update details (user_id, symbol, min_score).

    Returns:
        Success message with updated settings.
    """
    try:
        # Find ticker
        stmt = select(Ticker).where(Ticker.symbol == request.symbol.upper())
        result = await db.execute(stmt)
        ticker = result.scalar_one_or_none()

        if not ticker:
            raise HTTPException(status_code=404, detail=f"Ticker {request.symbol} not found")

        # Find subscription
        stmt = select(FlowSubscription).where(
            FlowSubscription.user_id == request.user_id,
            FlowSubscription.ticker_id == ticker.id,
        )
        result = await db.execute(stmt)
        subscription = result.scalar_one_or_none()

        if not subscription:
            raise HTTPException(
                status_code=404,
                detail=f"No active subscription found for {request.symbol}",
            )

        # Update min_score
        old_score = float(subscription.min_score)
        subscription.min_score = Decimal(str(request.min_score))
        await db.commit()

        app_logger.info(
            f"User {request.user_id} updated {request.symbol} flow subscription: "
            f"min_score {old_score:.2f} → {request.min_score:.2f}"
        )

        return {
            "message": f"Successfully updated {request.symbol} flow alert settings",
            "symbol": request.symbol.upper(),
            "old_min_score": old_score,
            "new_min_score": request.min_score,
        }

    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Failed to update flow subscription: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update subscription")


@router.get("/subscriptions/{user_id}", response_model=SubscriptionsListResponse)
async def get_user_subscriptions(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> SubscriptionsListResponse:
    """
    Get all flow subscriptions for a user.

    Args:
        user_id: Discord user ID.

    Returns:
        List of user's active subscriptions.
    """
    try:
        stmt = (
            select(FlowSubscription, Ticker)
            .join(Ticker, FlowSubscription.ticker_id == Ticker.id)
            .where(FlowSubscription.user_id == user_id, FlowSubscription.is_active)
            .order_by(Ticker.symbol)
        )
        result = await db.execute(stmt)
        rows = result.all()

        subscriptions = []
        for sub, ticker in rows:
            # Format created_at in EST
            created_at_est = sub.created_at.astimezone(EST).strftime("%b %d, %Y")

            subscriptions.append(
                SubscriptionResponse(
                    symbol=ticker.symbol,
                    min_score=float(sub.min_score),
                    channel_id=sub.channel_id,
                    created_at=created_at_est,
                )
            )

        return SubscriptionsListResponse(
            user_id=user_id,
            subscription_count=len(subscriptions),
            subscriptions=subscriptions,
        )

    except Exception as e:
        app_logger.error(f"Failed to fetch subscriptions for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch subscriptions")
