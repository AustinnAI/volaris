"""Price stream management endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.market_data import _extract_schwab_quote
from app.api.v1.schemas.streams import (
    PriceStreamCreateRequest,
    PriceStreamDispatch,
    PriceStreamEvaluateResponse,
    PriceStreamListResponse,
    PriceStreamResponse,
)
from app.config import settings
from app.db.database import get_db
from app.db.models import PriceStream
from app.services.schwab import SchwabClient
from app.services.tickers import get_or_create_ticker
from app.utils.logger import app_logger

router = APIRouter(prefix="/streams", tags=["streams"])


def _serialize_stream(stream: PriceStream) -> PriceStreamResponse:
    return PriceStreamResponse(
        id=stream.id,
        symbol=stream.ticker.symbol,
        channel_id=stream.channel_id,
        interval_seconds=stream.interval_seconds,
        next_run_at=stream.next_run_at,
        created_by=stream.created_by,
        created_at=stream.created_at,
    )


@router.get("/price", response_model=PriceStreamListResponse)
async def list_price_streams(db: AsyncSession = Depends(get_db)) -> PriceStreamListResponse:
    stmt = (
        select(PriceStream)
        .options(selectinload(PriceStream.ticker))
        .order_by(PriceStream.created_at.desc())
    )
    result = await db.execute(stmt)
    streams = result.scalars().all()
    return PriceStreamListResponse(streams=[_serialize_stream(stream) for stream in streams])


@router.post("/price", response_model=PriceStreamResponse, status_code=201)
async def create_or_update_price_stream(
    payload: PriceStreamCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> PriceStreamResponse:
    symbol = payload.symbol.upper().strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")

    min_interval = settings.PRICE_STREAM_MIN_INTERVAL_SECONDS
    max_interval = settings.PRICE_STREAM_MAX_INTERVAL_SECONDS
    interval = payload.interval_seconds or settings.PRICE_STREAM_DEFAULT_INTERVAL_SECONDS
    if interval < min_interval or interval > max_interval:
        raise HTTPException(
            status_code=400,
            detail=f"Interval must be between {min_interval} and {max_interval} seconds",
        )

    ticker = await get_or_create_ticker(symbol, db)

    stmt = (
        select(PriceStream)
        .where(PriceStream.ticker_id == ticker.id)
        .where(PriceStream.channel_id == payload.channel_id)
    )
    result = await db.execute(stmt)
    stream = result.scalar_one_or_none()

    now = datetime.now(UTC)

    if stream:
        stream.interval_seconds = interval
        stream.next_run_at = now
        stream.created_by = payload.created_by or stream.created_by
    else:
        stream = PriceStream(
            ticker_id=ticker.id,
            channel_id=payload.channel_id,
            interval_seconds=interval,
            next_run_at=now,
            created_by=payload.created_by,
        )
        db.add(stream)
        await db.flush()

    await db.refresh(stream)
    return _serialize_stream(stream)


@router.delete("/price/{stream_id}", status_code=204, response_class=Response)
async def delete_price_stream(stream_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    stmt = select(PriceStream).where(PriceStream.id == stream_id)
    result = await db.execute(stmt)
    stream = result.scalar_one_or_none()
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")

    await db.delete(stream)
    return Response(status_code=204)


@router.post("/price/evaluate", response_model=PriceStreamEvaluateResponse)
async def evaluate_price_streams(db: AsyncSession = Depends(get_db)) -> PriceStreamEvaluateResponse:
    now = datetime.now(UTC)
    stmt = (
        select(PriceStream)
        .options(selectinload(PriceStream.ticker))
        .where(PriceStream.next_run_at <= now)
    )
    result = await db.execute(stmt)
    streams = list(result.scalars().all())
    if not streams:
        return PriceStreamEvaluateResponse(streams=[])

    client = SchwabClient()
    payloads: list[PriceStreamDispatch] = []

    for stream in streams:
        symbol = stream.ticker.symbol
        try:
            raw_quote = await client.get_quote(symbol)
            quote = _extract_schwab_quote(raw_quote, symbol)
            if not quote:
                continue
            current_price = float(
                quote.get("lastPrice") or quote.get("mark") or quote.get("closePrice") or 0.0
            )
            prev_close = float(
                quote.get("previousClose") or quote.get("closePrice") or current_price
            )
            change = current_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0.0

            payloads.append(
                PriceStreamDispatch(
                    id=stream.id,
                    symbol=symbol,
                    channel_id=stream.channel_id,
                    interval_seconds=stream.interval_seconds,
                    price=current_price,
                    previous_close=prev_close,
                    change=change,
                    change_percent=change_pct,
                    timestamp=now,
                )
            )

            stream.last_price = Decimal(str(current_price))
            stream.next_run_at = now + timedelta(seconds=stream.interval_seconds)
        except Exception as exc:  # pylint: disable=broad-except
            app_logger.error(
                "Failed to evaluate price stream",
                extra={"symbol": symbol, "channel": stream.channel_id, "error": str(exc)},
            )
            continue

    return PriceStreamEvaluateResponse(streams=payloads)
