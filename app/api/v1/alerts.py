"""Price alert management endpoints."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.market_data import _extract_schwab_quote
from app.api.v1.schemas.alerts import (
    PriceAlertCreateRequest,
    PriceAlertEvaluateResponse,
    PriceAlertListResponse,
    PriceAlertResponse,
    PriceAlertTriggered,
)
from app.db.database import get_db
from app.db.models import PriceAlert, PriceAlertDirection
from app.services.exceptions import AuthenticationError
from app.services.schwab import SchwabClient
from app.services.tickers import get_or_create_ticker
from app.utils.logger import app_logger

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _should_trigger(direction: PriceAlertDirection, *, target: Decimal, current: Decimal) -> bool:
    if direction is PriceAlertDirection.ABOVE:
        return current >= target
    if direction is PriceAlertDirection.BELOW:
        return current <= target
    return False


def _serialize_alert(alert: PriceAlert) -> PriceAlertResponse:
    return PriceAlertResponse(
        id=alert.id,
        symbol=alert.ticker.symbol,
        target_price=alert.target_price,
        direction=alert.direction,
        channel_id=alert.channel_id,
        created_by=alert.created_by,
        created_at=alert.created_at,
    )


@router.post("/price", response_model=PriceAlertResponse, status_code=201)
async def create_price_alert(
    payload: PriceAlertCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> PriceAlertResponse:
    symbol = payload.symbol.upper().strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")

    ticker = await get_or_create_ticker(symbol, db)

    alert = PriceAlert(
        ticker_id=ticker.id,
        direction=payload.direction,
        target_price=payload.target_price,
        channel_id=payload.channel_id,
        created_by=payload.created_by,
    )
    db.add(alert)
    await db.flush()

    app_logger.info(
        "Price alert created",
        extra={
            "symbol": symbol,
            "direction": payload.direction.value,
            "target": str(payload.target_price),
            "channel_id": payload.channel_id,
        },
    )

    await db.refresh(alert, attribute_names=["created_at"])
    return _serialize_alert(alert)


@router.get("/price", response_model=PriceAlertListResponse)
async def list_price_alerts(db: AsyncSession = Depends(get_db)) -> PriceAlertListResponse:
    stmt = (
        select(PriceAlert)
        .options(selectinload(PriceAlert.ticker))
        .order_by(PriceAlert.created_at.desc())
    )
    result = await db.execute(stmt)
    alerts = result.scalars().all()
    return PriceAlertListResponse(alerts=[_serialize_alert(alert) for alert in alerts])


@router.delete("/price/{alert_id}", status_code=204, response_class=Response)
async def delete_price_alert(alert_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    stmt = select(PriceAlert).where(PriceAlert.id == alert_id)
    result = await db.execute(stmt)
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    await db.delete(alert)
    app_logger.info("Price alert deleted", extra={"alert_id": alert_id})
    return Response(status_code=204)


async def _fetch_prices(symbols: Iterable[str]) -> dict[str, Decimal]:
    prices: dict[str, Decimal] = {}
    if not symbols:
        return prices

    try:
        client = SchwabClient()
    except AuthenticationError as exc:
        app_logger.error(
            "Schwab authentication unavailable for price alerts",
            extra={"error": str(exc)},
        )
        return prices
    for symbol in symbols:
        try:
            raw_quote = await client.get_quote(symbol)
            quote = _extract_schwab_quote(raw_quote, symbol)
            if not quote:
                continue
            price_value = quote.get("lastPrice") or quote.get("mark") or quote.get("closePrice")
            if price_value is None:
                continue
            prices[symbol] = Decimal(str(price_value))
        except Exception as exc:  # pylint: disable=broad-except
            app_logger.error(
                "Failed to fetch quote for alert evaluation",
                extra={"symbol": symbol, "error": str(exc)},
            )
    return prices


@router.post("/price/evaluate", response_model=PriceAlertEvaluateResponse)
async def evaluate_price_alerts(db: AsyncSession = Depends(get_db)) -> PriceAlertEvaluateResponse:
    stmt = select(PriceAlert).options(selectinload(PriceAlert.ticker))
    result = await db.execute(stmt)
    alerts = result.scalars().all()
    if not alerts:
        return PriceAlertEvaluateResponse(triggered=[])

    symbol_map = defaultdict(list)
    for alert in alerts:
        symbol_map[alert.ticker.symbol].append(alert)

    prices = await _fetch_prices(symbol_map.keys())

    triggered: list[PriceAlertTriggered] = []
    now = datetime.now(UTC)

    for symbol, symbol_alerts in symbol_map.items():
        current_price = prices.get(symbol)
        if current_price is None:
            continue
        for alert in symbol_alerts:
            if _should_trigger(alert.direction, target=alert.target_price, current=current_price):
                triggered.append(
                    PriceAlertTriggered(
                        id=alert.id,
                        symbol=symbol,
                        target_price=alert.target_price,
                        direction=alert.direction,
                        current_price=current_price,
                        channel_id=alert.channel_id,
                        created_by=alert.created_by,
                    )
                )
                alert.triggered_at = now
                await db.delete(alert)

    if triggered:
        app_logger.info(
            "Price alerts triggered",
            extra={"count": len(triggered)},
        )

    return PriceAlertEvaluateResponse(triggered=triggered)
