"""
Market Data API Endpoints
Provides quick market data access for Discord commands.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Ticker, PriceBar, Timeframe, OptionContract, IVMetric, OptionChainSnapshot
from app.services.schwab import SchwabClient
from app.services.finnhub import FinnhubClient
from app.services.market_insights import fetch_sentiment, get_top_movers
from app.services.index_service import (
    get_index_constituents_symbols,
    refresh_index_constituents,
    SP500_SYMBOL,
)
from app.services.exceptions import DataNotFoundError
from app.config import settings
from app.workers.tasks import (
    fetch_realtime_prices,
    fetch_option_chains,
    compute_iv_metrics,
)

router = APIRouter(prefix="/market", tags=["market-data"])


def _extract_schwab_quote(payload: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    """
    Normalize Schwab quote payloads into a flat quote dict.

    The Schwab Market Data API can return several shapes:
    - {"symbol": "...", "quote": {...}}
    - {"quotes": {"AAPL": {"quote": {...}}}}
    - {"quotes": {"AAPL": {...}}}

    Args:
        payload: Raw response from SchwabClient.get_quote
        symbol: Requested symbol (used to disambiguate keyed responses)

    Returns:
        The innermost quote dict if present; empty dict otherwise.
    """
    if not payload:
        return {}

    symbol_key = symbol.upper()

    direct_quote = payload.get("quote")
    if isinstance(direct_quote, dict):
        return direct_quote

    quotes_container = payload.get("quotes")
    if isinstance(quotes_container, dict):
        candidate = quotes_container.get(symbol_key)
        if isinstance(candidate, dict):
            nested_quote = candidate.get("quote")
            if isinstance(nested_quote, dict):
                return nested_quote
            return candidate

    keyed_entry = payload.get(symbol_key)
    if isinstance(keyed_entry, dict):
        nested_quote = keyed_entry.get("quote")
        if isinstance(nested_quote, dict):
            return nested_quote
        return keyed_entry

    return {}


def _extract_finnhub_earnings(payload: Any, symbol: str) -> Optional[Dict[str, Any]]:
    """
    Extract the next earnings record for a symbol from a Finnhub payload.

    Args:
        payload: Raw response from FinnhubClient.get_earnings_calendar.
        symbol: Requested ticker symbol.

    Returns:
        Matching earnings record or None.
    """
    symbol_upper = symbol.upper()
    records: list[Dict[str, Any]] = []

    if isinstance(payload, dict):
        candidates = payload.get("earningsCalendar") or payload.get("earnings")
        if isinstance(candidates, list):
            records = [item for item in candidates if isinstance(item, dict)]
    elif isinstance(payload, list):
        records = [item for item in payload if isinstance(item, dict)]

    if not records:
        return None

    for record in records:
        record_symbol = str(record.get("symbol") or symbol_upper).upper()
        if record.get("date") and record_symbol == symbol_upper:
            return record

    for record in records:
        if record.get("date"):
            return record

    return None


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
    # Strategy: Get most recent bar (any timeframe) + most recent daily bar for previous close

    # Get most recent intraday bar (1m preferred, fallback to 5m) for current price
    stmt_latest = (
        select(PriceBar)
        .join(Ticker)
        .where(Ticker.symbol == symbol)
        .where(PriceBar.timeframe.in_([Timeframe.ONE_MINUTE, Timeframe.FIVE_MINUTE]))
        .order_by(desc(PriceBar.timestamp))
        .limit(1)
    )
    result_latest = await db.execute(stmt_latest)
    latest_bar = result_latest.scalar_one_or_none()

    # Get most recent DAILY bar for previous close
    stmt_daily = (
        select(PriceBar)
        .join(Ticker)
        .where(Ticker.symbol == symbol)
        .where(PriceBar.timeframe == Timeframe.DAILY)
        .order_by(desc(PriceBar.timestamp))
        .limit(1)
    )
    result_daily = await db.execute(stmt_daily)
    daily_bar = result_daily.scalar_one_or_none()

    def _is_stale(bar_timestamp: datetime, grace_minutes: int = 15) -> bool:
        """Return True when cached bar data is older than the allowed freshness window."""
        if bar_timestamp.tzinfo is None:
            ts = bar_timestamp.replace(tzinfo=timezone.utc)
        else:
            ts = bar_timestamp
        return datetime.now(ts.tzinfo or timezone.utc) - ts > timedelta(minutes=grace_minutes)

    if latest_bar and daily_bar and not _is_stale(latest_bar.timestamp):
        # Use most recent bar for current price, daily bar for previous close
        current_price = float(latest_bar.close)
        previous_close = float(daily_bar.close)
        change = current_price - previous_close
        change_pct = (change / previous_close * 100) if previous_close else 0

        return {
            "symbol": symbol,
            "price": current_price,
            "previous_close": previous_close,
            "change": change,
            "change_pct": change_pct,
            "volume": latest_bar.volume or 0,
        }

    # Fallback: Fetch from Schwab API
    try:
        schwab = SchwabClient()
        quote_data = await schwab.get_quote(symbol)

        quote = _extract_schwab_quote(quote_data, symbol)
        if not quote:
            raise HTTPException(status_code=502, detail="Malformed Schwab quote payload")

        current_price = quote.get("lastPrice") or quote.get("mark") or quote.get("closePrice") or 0
        previous_close = quote.get("previousClose") or quote.get("closePrice") or current_price
        change = current_price - previous_close
        change_pct = (change / previous_close * 100) if previous_close else 0

        return {
            "symbol": symbol,
            "price": current_price,
            "previous_close": previous_close,
            "change": change,
            "change_pct": change_pct,
            "volume": quote.get("totalVolume") or quote.get("realTimeVolume") or 0,
        }
    except HTTPException:
        raise
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
        .join(Ticker)
        .where(Ticker.symbol == symbol)
        .order_by(desc(IVMetric.as_of))
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
            "current_iv": float(iv_metric.implied_vol) if iv_metric.implied_vol else 0,
            "iv_rank": float(iv_metric.iv_rank) if iv_metric.iv_rank else 0,
            "iv_percentile": float(iv_metric.iv_percentile) if iv_metric.iv_percentile else 0,
            "regime": regime,
        }

    # No IV data in database
    raise HTTPException(
        status_code=404,
        detail=f"No IV data available for {symbol}. Enable scheduler to populate data.",
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
        schwab = SchwabClient()
        quote_data = await schwab.get_quote(symbol)

        quote = _extract_schwab_quote(quote_data, symbol)
        if not quote:
            raise HTTPException(status_code=502, detail="Malformed Schwab quote payload")

        # DEBUG: Log raw Schwab response
        import logging

        logger = logging.getLogger("volaris.market_data")
        logger.info(f"Schwab raw quote for {symbol}: {quote}")

        # Extract price fields from Schwab's quote structure (see Schwab API docs)
        last_price = quote.get("lastPrice") or 0
        mark_price = quote.get("mark") or 0
        close_price = quote.get("closePrice") or 0

        # Use lastPrice during market hours, closePrice after market close
        current_price = last_price or mark_price or close_price or 0

        # Schwab provides netChange and netPercentChange directly in the quote object
        net_change = quote.get("netChange")
        net_change_pct = quote.get("netPercentChange")

        # Calculate previous close: previousClose = closePrice - netChange
        # (Schwab doesn't include previousClose field, but we can derive it)
        if net_change is not None and close_price:
            previous_close = close_price - net_change
        else:
            previous_close = 0

        # Use Schwab's provided percent change if available, otherwise calculate
        if net_change_pct is not None:
            change_pct = float(net_change_pct)
        elif previous_close and previous_close > 0:
            change_pct = (current_price - previous_close) / previous_close * 100
        else:
            change_pct = 0.0

        return {
            "symbol": symbol,
            "price": current_price,
            "bid": quote.get("bidPrice") or 0,
            "ask": quote.get("askPrice") or 0,
            "volume": quote.get("totalVolume") or quote.get("realTimeVolume") or 0,
            "avg_volume": quote.get("averageVolume")
            or quote.get("avgVolume")
            or quote.get("totalVolume")
            or 0,
            "change_pct": change_pct,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch quote: {str(e)}")


@router.get("/sentiment/{symbol}")
async def get_sentiment(symbol: str, db: AsyncSession = Depends(get_db)):
    symbol_upper = symbol.upper()

    sp500_symbols = await get_index_constituents_symbols(db)
    if not sp500_symbols:
        try:
            sp500_symbols = set(await refresh_index_constituents(db))
        except DataNotFoundError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:  # pylint: disable=broad-except
            raise HTTPException(
                status_code=500, detail=f"Failed to refresh S&P 500 list: {str(exc)}"
            ) from exc

    if symbol_upper not in sp500_symbols:
        raise HTTPException(status_code=400, detail="Symbol must be part of the S&P 500 list")

    try:
        sentiment = await fetch_sentiment(symbol_upper)
    except DataNotFoundError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch sentiment: {str(exc)}"
        ) from exc

    return sentiment


@router.get("/top")
async def get_top_movers_endpoint(
    limit: int = Query(default=settings.TOP_MOVERS_LIMIT, ge=1, le=25),
    db: AsyncSession = Depends(get_db),
):
    sp500_symbols = await get_index_constituents_symbols(db)
    if not sp500_symbols:
        try:
            sp500_symbols = set(await refresh_index_constituents(db))
        except DataNotFoundError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:  # pylint: disable=broad-except
            raise HTTPException(
                status_code=500, detail=f"Failed to refresh S&P 500 list: {str(exc)}"
            ) from exc

    try:
        movers = await get_top_movers(limit=limit, sp500_symbols=sp500_symbols)
    except DataNotFoundError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch top movers: {str(exc)}"
        ) from exc

    return {
        "index": SP500_SYMBOL,
        "limit": limit,
        "gainers": movers.get("gainers", []),
        "losers": movers.get("losers", []),
    }


@router.get("/sp500")
async def get_sp500_constituents(db: AsyncSession = Depends(get_db)):
    symbols = await get_index_constituents_symbols(db)
    if not symbols:
        try:
            symbols = set(await refresh_index_constituents(db))
        except DataNotFoundError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:  # pylint: disable=broad-except
            raise HTTPException(
                status_code=500, detail=f"Failed to refresh S&P 500 list: {str(exc)}"
            ) from exc
    return {
        "index": SP500_SYMBOL,
        "symbols": sorted(symbols),
    }


@router.post("/refresh/price/{symbol}", status_code=202)
async def refresh_price(symbol: str, db: AsyncSession = Depends(get_db)) -> Dict[str, int]:
    symbol_upper = symbol.upper()
    inserted = await fetch_realtime_prices(db, symbols=[symbol_upper])
    return {"inserted": inserted}


@router.post("/refresh/options/{symbol}", status_code=202)
async def refresh_option_chain(symbol: str, db: AsyncSession = Depends(get_db)) -> Dict[str, int]:
    symbol_upper = symbol.upper()
    snapshots = await fetch_option_chains(db, symbols=[symbol_upper])
    return {"snapshots": snapshots}


@router.post("/refresh/iv/{symbol}", status_code=202)
async def refresh_iv_metrics(symbol: str, db: AsyncSession = Depends(get_db)) -> Dict[str, int]:
    symbol_upper = symbol.upper()
    metrics = await compute_iv_metrics(db, symbols=[symbol_upper])
    return {"metrics": metrics}


@router.get("/delta/{symbol}/{strike}/{option_type}/{dte}")
async def get_delta(
    symbol: str, strike: float, option_type: str, dte: int, db: AsyncSession = Depends(get_db)
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
        .join(OptionChainSnapshot)
        .join(Ticker)
        .where(Ticker.symbol == symbol)
        .where(OptionContract.option_type == option_type)
        .where(OptionContract.strike == strike)
        .where(OptionChainSnapshot.expiration >= expiration_target.date() - timedelta(days=3))
        .where(OptionChainSnapshot.expiration <= expiration_target.date() + timedelta(days=3))
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
        detail=f"No option data for {symbol} ${strike} {option_type} ~{dte}DTE. Enable scheduler to populate data.",
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
        finnhub = FinnhubClient()
        earnings_payload = await finnhub.get_earnings_calendar(symbol=symbol)

        record = _extract_finnhub_earnings(earnings_payload, symbol)
        if not record:
            raise HTTPException(status_code=404, detail=f"No upcoming earnings data for {symbol}")

        earnings_date_raw = record.get("date")
        if not earnings_date_raw:
            raise HTTPException(status_code=404, detail=f"No upcoming earnings data for {symbol}")

        try:
            earnings_date = datetime.fromisoformat(earnings_date_raw).date()
        except ValueError:
            from datetime import datetime as dt

            earnings_date = dt.strptime(earnings_date_raw, "%Y-%m-%d").date()

        today = date.today()
        days_until = (earnings_date - today).days

        response: Dict[str, Any] = {
            "symbol": symbol,
            "earnings_date": earnings_date.isoformat(),
            "days_until": days_until,
        }

        for key in ("hour", "epsEstimate", "epsActual", "revenueEstimate", "revenueActual"):
            if record.get(key) is not None:
                response[key] = record[key]

        return response

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
        select(func.max(PriceBar.high).label("high_52w"), func.min(PriceBar.low).label("low_52w"))
        .join(Ticker)
        .where(Ticker.symbol == symbol)
        .where(PriceBar.timeframe == Timeframe.DAILY)
        .where(PriceBar.timestamp >= one_year_ago)
    )
    result = await db.execute(stmt)
    range_data = result.one_or_none()

    # Get current price
    stmt_current = (
        select(PriceBar)
        .join(Ticker)
        .where(Ticker.symbol == symbol)
        .where(PriceBar.timeframe == Timeframe.DAILY)
        .order_by(desc(PriceBar.timestamp))
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
        detail=f"No 52-week range data for {symbol}. Enable scheduler to populate data.",
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
        select(PriceBar)
        .join(Ticker)
        .where(Ticker.symbol == symbol)
        .where(PriceBar.timeframe == Timeframe.DAILY)
        .order_by(desc(PriceBar.timestamp))
        .limit(1)
    )
    result_current = await db.execute(stmt_current)
    current = result_current.scalar_one_or_none()

    # Get 30-day average volume
    thirty_days_ago = datetime.now() - timedelta(days=30)

    stmt_avg = (
        select(func.avg(PriceBar.volume).label("avg_volume"))
        .join(Ticker)
        .where(Ticker.symbol == symbol)
        .where(PriceBar.timeframe == Timeframe.DAILY)
        .where(PriceBar.timestamp >= thirty_days_ago)
        .where(PriceBar.volume.isnot(None))
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
        status_code=404, detail=f"No volume data for {symbol}. Enable scheduler to populate data."
    )
