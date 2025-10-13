"""
Market Data API Endpoints
Provides quick market data access for Discord commands.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Ticker, PriceData, Timeframe, OptionContract, IVMetric
from app.services.schwab import SchwabClient
from app.services.finnhub import FinnhubClient
from app.config import settings

router = APIRouter(prefix="/market", tags=["market-data"])


@router.get("/price/{symbol}")
async def get_price(symbol: str, db: AsyncSession = Depends(get_db)):
    """
    Get current price and daily change for a symbol.

    Returns:
        - price: Current price
        - previous_close: Yesterday's close
        - change: Price change ($)
        - change_pct: Price change (%)
        - volume: Today's volume
    """
    symbol = symbol.upper()

    # Try to get latest price from database
    stmt = (
        select(PriceData)
        .where(PriceData.symbol == symbol)
        .where(PriceData.timeframe == Timeframe.DAILY)
        .order_by(desc(PriceData.timestamp))
        .limit(2)
    )
    result = await db.execute(stmt)
    prices = result.scalars().all()

    if len(prices) >= 2:
        latest = prices[0]
        previous = prices[1]

        return {
            "symbol": symbol,
            "price": float(latest.close),
            "previous_close": float(previous.close),
            "change": float(latest.close - previous.close),
            "change_pct": float((latest.close - previous.close) / previous.close * 100),
            "volume": latest.volume or 0,
        }

    # Fallback: Fetch from Schwab API
    try:
        schwab = SchwabClient(
            app_key=settings.SCHWAB_APP_KEY,
            secret_key=settings.SCHWAB_SECRET_KEY,
            refresh_token=settings.SCHWAB_REFRESH_TOKEN
        )
        quote_data = await schwab.get_quote(symbol)

        current_price = quote_data.get("lastPrice", 0)
        previous_close = quote_data.get("previousClose", current_price)
        change = current_price - previous_close
        change_pct = (change / previous_close * 100) if previous_close else 0

        return {
            "symbol": symbol,
            "price": current_price,
            "previous_close": previous_close,
            "change": change,
            "change_pct": change_pct,
            "volume": quote_data.get("totalVolume", 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch price: {str(e)}")


@router.get("/iv/{symbol}")
async def get_iv(symbol: str, db: AsyncSession = Depends(get_db)):
    """
    Get IV metrics for a symbol.

    Returns:
        - current_iv: Current implied volatility (%)
        - iv_rank: IV rank (% of days in past year IV was lower)
        - iv_percentile: IV percentile
        - regime: high/low/neutral
    """
    symbol = symbol.upper()

    # Get latest IV metric from database
    stmt = (
        select(IVMetric)
        .where(IVMetric.symbol == symbol)
        .order_by(desc(IVMetric.timestamp))
        .limit(1)
    )
    result = await db.execute(stmt)
    iv_metric = result.scalar_one_or_none()

    if iv_metric:
        # Determine regime
        if iv_metric.iv_rank >= settings.IV_HIGH_THRESHOLD:
            regime = "high"
        elif iv_metric.iv_rank <= settings.IV_LOW_THRESHOLD:
            regime = "low"
        else:
            regime = "neutral"

        return {
            "symbol": symbol,
            "current_iv": float(iv_metric.current_iv),
            "iv_rank": float(iv_metric.iv_rank),
            "iv_percentile": float(iv_metric.iv_percentile),
            "regime": regime,
        }

    # No IV data in database
    raise HTTPException(
        status_code=404,
        detail=f"No IV data available for {symbol}. Enable scheduler to populate data."
    )


@router.get("/quote/{symbol}")
async def get_quote(symbol: str):
    """
    Get full quote with bid/ask/volume.

    Returns:
        - price: Last price
        - bid: Bid price
        - ask: Ask price
        - volume: Today's volume
        - avg_volume: 30-day average volume
        - change_pct: Daily % change
    """
    symbol = symbol.upper()

    try:
        schwab = SchwabClient(
            app_key=settings.SCHWAB_APP_KEY,
            secret_key=settings.SCHWAB_SECRET_KEY,
            refresh_token=settings.SCHWAB_REFRESH_TOKEN
        )
        quote_data = await schwab.get_quote(symbol)

        current_price = quote_data.get("lastPrice", 0)
        previous_close = quote_data.get("previousClose", current_price)
        change_pct = ((current_price - previous_close) / previous_close * 100) if previous_close else 0

        return {
            "symbol": symbol,
            "price": current_price,
            "bid": quote_data.get("bidPrice", 0),
            "ask": quote_data.get("askPrice", 0),
            "volume": quote_data.get("totalVolume", 0),
            "avg_volume": quote_data.get("avgVolume", quote_data.get("totalVolume", 0)),
            "change_pct": change_pct,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch quote: {str(e)}")


@router.get("/delta/{symbol}/{strike}/{option_type}/{dte}")
async def get_delta(
    symbol: str,
    strike: float,
    option_type: str,
    dte: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get delta for a specific option strike.

    Returns:
        - delta: Option delta (approximation from database)
        - strike: Strike price
        - option_type: call or put
        - dte: Days to expiration
    """
    symbol = symbol.upper()
    option_type = option_type.lower()

    # Find option contract close to requested strike and DTE
    expiration_target = datetime.now() + timedelta(days=dte)

    stmt = (
        select(OptionContract)
        .where(OptionContract.symbol == symbol)
        .where(OptionContract.option_type == option_type)
        .where(OptionContract.strike == strike)
        .where(OptionContract.expiration >= expiration_target - timedelta(days=3))
        .where(OptionContract.expiration <= expiration_target + timedelta(days=3))
        .limit(1)
    )
    result = await db.execute(stmt)
    contract = result.scalar_one_or_none()

    if contract and contract.delta:
        return {
            "symbol": symbol,
            "strike": strike,
            "option_type": option_type,
            "dte": dte,
            "delta": float(contract.delta),
        }

    # Fallback: Approximate delta based on moneyness
    # This is a rough approximation; real delta requires Black-Scholes
    # For now, return error asking for real data
    raise HTTPException(
        status_code=404,
        detail=f"No option data for {symbol} ${strike} {option_type} ~{dte}DTE. Enable scheduler to populate data."
    )


@router.get("/earnings/{symbol}")
async def get_earnings(symbol: str):
    """
    Get next earnings date for a symbol.

    Returns:
        - symbol: Ticker symbol
        - earnings_date: Next earnings date (ISO format)
        - days_until: Days until earnings
    """
    symbol = symbol.upper()

    try:
        finnhub = FinnhubClient(api_key=settings.FINNHUB_API_KEY)
        earnings_data = await finnhub.get_earnings_calendar(symbol)

        if earnings_data and len(earnings_data) > 0:
            next_earnings = earnings_data[0]
            earnings_date_str = next_earnings.get("date")

            if earnings_date_str:
                earnings_date = datetime.fromisoformat(earnings_date_str)
                days_until = (earnings_date.date() - datetime.now().date()).days

                return {
                    "symbol": symbol,
                    "earnings_date": earnings_date.isoformat(),
                    "days_until": days_until,
                }

        raise HTTPException(status_code=404, detail=f"No upcoming earnings data for {symbol}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch earnings: {str(e)}")


@router.get("/range/{symbol}")
async def get_range(symbol: str, db: AsyncSession = Depends(get_db)):
    """
    Get 52-week high/low range.

    Returns:
        - current_price: Current price
        - high_52w: 52-week high
        - low_52w: 52-week low
        - position_pct: Position in range (0-100%)
    """
    symbol = symbol.upper()

    # Get price data from last 52 weeks
    one_year_ago = datetime.now() - timedelta(days=365)

    stmt = (
        select(
            func.max(PriceData.high).label("high_52w"),
            func.min(PriceData.low).label("low_52w")
        )
        .where(PriceData.symbol == symbol)
        .where(PriceData.timeframe == Timeframe.DAILY)
        .where(PriceData.timestamp >= one_year_ago)
    )
    result = await db.execute(stmt)
    range_data = result.one_or_none()

    # Get current price
    stmt_current = (
        select(PriceData)
        .where(PriceData.symbol == symbol)
        .where(PriceData.timeframe == Timeframe.DAILY)
        .order_by(desc(PriceData.timestamp))
        .limit(1)
    )
    result_current = await db.execute(stmt_current)
    current = result_current.scalar_one_or_none()

    if range_data and current:
        high_52w = float(range_data.high_52w) if range_data.high_52w else float(current.close)
        low_52w = float(range_data.low_52w) if range_data.low_52w else float(current.close)
        current_price = float(current.close)

        range_size = high_52w - low_52w
        position_pct = ((current_price - low_52w) / range_size * 100) if range_size > 0 else 50

        return {
            "symbol": symbol,
            "current_price": current_price,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "position_pct": position_pct,
        }

    raise HTTPException(
        status_code=404,
        detail=f"No 52-week range data for {symbol}. Enable scheduler to populate data."
    )


@router.get("/volume/{symbol}")
async def get_volume(symbol: str, db: AsyncSession = Depends(get_db)):
    """
    Get volume comparison vs 30-day average.

    Returns:
        - current_volume: Today's volume
        - avg_volume_30d: 30-day average volume
        - volume_ratio: Current / Average
    """
    symbol = symbol.upper()

    # Get current day volume
    stmt_current = (
        select(PriceData)
        .where(PriceData.symbol == symbol)
        .where(PriceData.timeframe == Timeframe.DAILY)
        .order_by(desc(PriceData.timestamp))
        .limit(1)
    )
    result_current = await db.execute(stmt_current)
    current = result_current.scalar_one_or_none()

    # Get 30-day average volume
    thirty_days_ago = datetime.now() - timedelta(days=30)

    stmt_avg = (
        select(func.avg(PriceData.volume).label("avg_volume"))
        .where(PriceData.symbol == symbol)
        .where(PriceData.timeframe == Timeframe.DAILY)
        .where(PriceData.timestamp >= thirty_days_ago)
        .where(PriceData.volume.isnot(None))
    )
    result_avg = await db.execute(stmt_avg)
    avg_data = result_avg.one_or_none()

    if current and avg_data:
        current_volume = current.volume or 0
        avg_volume = float(avg_data.avg_volume) if avg_data.avg_volume else current_volume
        volume_ratio = (current_volume / avg_volume) if avg_volume > 0 else 1

        return {
            "symbol": symbol,
            "current_volume": current_volume,
            "avg_volume_30d": int(avg_volume),
            "volume_ratio": volume_ratio,
        }

    raise HTTPException(
        status_code=404,
        detail=f"No volume data for {symbol}. Enable scheduler to populate data."
    )
