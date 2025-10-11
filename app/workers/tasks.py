"""Data ingestion tasks for scheduled jobs."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.models import (
    DataProvider,
    IVMetric,
    IVTerm,
    OptionChainSnapshot,
    OptionContract,
    OptionType,
    PriceBar,
    Ticker,
    Timeframe,
)
from app.services.provider_manager import DataType, provider_manager
from app.utils.logger import app_logger
from app.workers.utils import (
    normalize_option_contracts,
    normalize_price_points,
    parse_date,
    to_decimal,
)


TIMEFRAME_TO_PROVIDER_ARGS = {
    Timeframe.ONE_MINUTE: {"frequency": 1, "timeframe": "1Min"},
    Timeframe.FIVE_MINUTE: {"frequency": 5, "timeframe": "5Min"},
    Timeframe.DAILY: {"frequency": None, "timeframe": "1Day"},
}

IV_TERM_WINDOWS = {
    IVTerm.D7: (0, 7),
    IVTerm.D14: (8, 14),
    IVTerm.D30: (15, 30),
    IVTerm.D60: (31, 60),
    IVTerm.D90: (61, 90),
}


def _provider_enum_from_object(provider: object) -> DataProvider:
    name = getattr(provider, "provider_name", "") or ""
    slug = str(name).lower()
    try:
        return DataProvider(slug)
    except ValueError:
        app_logger.debug("Unknown provider name, defaulting to Schwab", extra={"name": slug})
        return DataProvider.SCHWAB


async def get_active_tickers(session: AsyncSession) -> List[Ticker]:
    """Fetch active tickers to drive periodic jobs."""

    result = await session.execute(select(Ticker).where(Ticker.is_active.is_(True)))
    return list(result.scalars().all())


async def fetch_realtime_prices(
    session: AsyncSession,
    symbols: Optional[Sequence[str]] = None,
    timeframe: Timeframe = Timeframe.ONE_MINUTE,
    provider: Optional[object] = None,
    lookback_minutes: int = 5,
) -> int:
    """Ingest recent intraday bars from the configured provider."""

    tickers = await _resolve_tickers(session, symbols)
    if not tickers:
        app_logger.info("No active tickers available for real-time sync")
        return 0

    provider = provider or provider_manager.get_provider(DataType.REALTIME_MINUTE)
    if provider is None:
        app_logger.warning("No provider available for real-time minute data")
        return 0

    added = 0
    provider_enum = _provider_enum_from_object(provider)
    provider_kwargs = TIMEFRAME_TO_PROVIDER_ARGS.get(timeframe, {})

    frequency = provider_kwargs.get("frequency") or 1
    limit = max(int(lookback_minutes / frequency), 1)

    for ticker in tickers:
        try:
            response = await _fetch_price_payload(provider, ticker.symbol, timeframe, limit)
            for candle in normalize_price_points(response):
                if await _upsert_price_bar(session, ticker, timeframe, candle, provider_enum):
                    added += 1
        except Exception as exc:  # pylint: disable=broad-except
            app_logger.error(
                "Realtime price sync failed",
                extra={"symbol": ticker.symbol, "error": str(exc)},
            )

    await session.commit()
    return added


async def backfill_historical_prices(
    session: AsyncSession,
    symbols: Optional[Sequence[str]] = None,
    timeframe: Timeframe = Timeframe.DAILY,
    start: Optional[date] = None,
    end: Optional[date] = None,
    provider: Optional[object] = None,
) -> int:
    """Backfill historical prices using Databento/Alpaca providers."""

    tickers = await _resolve_tickers(session, symbols)
    if not tickers:
        return 0

    provider = provider or provider_manager.get_provider(DataType.HISTORICAL)
    if provider is None:
        app_logger.warning("No provider available for historical backfills")
        return 0

    start = start or (date.today() - timedelta(days=settings.HISTORICAL_BACKFILL_LOOKBACK_DAYS))
    end = end or date.today()
    provider_enum = _provider_enum_from_object(provider)
    added = 0

    for ticker in tickers:
        try:
            response = await _fetch_historical_payload(provider, ticker.symbol, timeframe, start, end)
            for candle in normalize_price_points(response):
                if await _upsert_price_bar(session, ticker, timeframe, candle, provider_enum):
                    added += 1
        except Exception as exc:  # pylint: disable=broad-except
            app_logger.error(
                "Historical price backfill failed",
                extra={
                    "symbol": ticker.symbol,
                    "error": str(exc),
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                },
            )

    await session.commit()
    return added


async def sync_eod_prices(
    session: AsyncSession,
    symbols: Optional[Sequence[str]] = None,
    provider: Optional[object] = None,
) -> int:
    """Sync end-of-day prices using Tiingo."""

    tickers = await _resolve_tickers(session, symbols)
    if not tickers:
        return 0

    provider = provider or provider_manager.get_provider(DataType.EOD)
    if provider is None:
        app_logger.warning("No provider available for EOD data")
        return 0

    provider_enum = _provider_enum_from_object(provider)
    added = 0

    for ticker in tickers:
        try:
            response = await provider.get_eod_prices(ticker.symbol)
            for candle in normalize_price_points(response):
                if await _upsert_price_bar(session, ticker, Timeframe.DAILY, candle, provider_enum):
                    added += 1
        except Exception as exc:  # pylint: disable=broad-except
            app_logger.error(
                "EOD price sync failed",
                extra={"symbol": ticker.symbol, "error": str(exc)},
            )

    await session.commit()
    return added


async def fetch_option_chains(
    session: AsyncSession,
    symbols: Optional[Sequence[str]] = None,
    provider: Optional[object] = None,
    strike_count: int = 10,
) -> int:
    """Pull option-chain snapshots and persist contracts."""

    tickers = await _resolve_tickers(session, symbols)
    if not tickers:
        return 0

    provider = provider or provider_manager.get_provider(DataType.OPTIONS)
    if provider is None:
        app_logger.warning("No provider available for option chains")
        return 0

    provider_enum = _provider_enum_from_object(provider)
    snapshots_created = 0

    now = datetime.now(timezone.utc)

    for ticker in tickers:
        try:
            response = await provider.get_option_chain(
                ticker.symbol,
                contract_type="ALL",
                strike_count=strike_count,
                include_quotes=True,
            )
        except Exception as exc:  # pylint: disable=broad-except
            app_logger.error(
                "Option chain request failed",
                extra={"symbol": ticker.symbol, "error": str(exc)},
            )
            continue

        contracts = normalize_option_contracts(response)
        if not contracts:
            continue

        expiration = _first_contract_expiration(contracts)
        if expiration is None:
            app_logger.debug("Option chain missing expiration", extra={"symbol": ticker.symbol})
            continue

        snapshot = OptionChainSnapshot(
            ticker_id=ticker.id,
            as_of=now,
            expiration=expiration,
            dte=_compute_dte(now.date(), expiration),
            underlying_price=to_decimal(response.get("underlyingPrice") if isinstance(response, dict) else None),
            data_provider=provider_enum,
        )
        session.add(snapshot)
        await session.flush()

        for contract in contracts:
            option_type = OptionType.CALL if "call" in contract["option_type"] else OptionType.PUT
            expiration_date = parse_date(contract.get("expiration")) or expiration
            session.add(
                OptionContract(
                    snapshot_id=snapshot.id,
                    option_type=option_type,
                    strike=contract["strike"],
                    bid=contract.get("bid"),
                    ask=contract.get("ask"),
                    last=contract.get("last"),
                    mark=contract.get("mark"),
                    volume=contract.get("volume"),
                    open_interest=contract.get("open_interest"),
                    implied_vol=contract.get("implied_vol"),
                    delta=contract.get("delta"),
                    gamma=contract.get("gamma"),
                    theta=contract.get("theta"),
                    vega=contract.get("vega"),
                    rho=contract.get("rho"),
                    created_at=now,
                    updated_at=now,
                )
            )
        snapshots_created += 1

    await session.commit()
    return snapshots_created


async def compute_iv_metrics(
    session: AsyncSession,
    symbols: Optional[Sequence[str]] = None,
) -> int:
    """Derive IV/IVR metrics from the latest option-chain snapshots."""

    tickers = await _resolve_tickers(session, symbols)
    if not tickers:
        return 0

    metrics_created = 0

    for ticker in tickers:
        snapshot = await session.scalar(
            select(OptionChainSnapshot)
            .where(OptionChainSnapshot.ticker_id == ticker.id)
            .order_by(OptionChainSnapshot.as_of.desc())
            .options(selectinload(OptionChainSnapshot.contracts))
        )
        if snapshot is None or not snapshot.contracts:
            continue

        iv_by_term = _group_contracts_by_term(snapshot)
        for term, vols in iv_by_term.items():
            if not vols:
                continue
            avg_iv = decimal_mean(vols)
            rank, percentile = await _calculate_iv_rank(session, ticker.id, term, avg_iv)
            metric = IVMetric(
                ticker_id=ticker.id,
                as_of=snapshot.as_of,
                term=term,
                implied_vol=avg_iv,
                iv_rank=rank,
                iv_percentile=percentile,
                data_provider=snapshot.data_provider,
            )
            await _upsert_iv_metric(session, metric)
            metrics_created += 1

    await session.commit()
    return metrics_created


async def _resolve_tickers(session: AsyncSession, symbols: Optional[Sequence[str]]) -> List[Ticker]:
    if symbols:
        result = await session.execute(select(Ticker).where(Ticker.symbol.in_(symbols)))
        return list(result.scalars().all())
    return await get_active_tickers(session)


async def _fetch_price_payload(provider: object, symbol: str, timeframe: Timeframe, limit: int):
    if hasattr(provider, "get_price_history"):
        kwargs = {
            "symbol": symbol,
            "period_type": "day",
            "period": 1,
            "frequency_type": "minute",
            "frequency": TIMEFRAME_TO_PROVIDER_ARGS.get(timeframe, {}).get("frequency", 1),
        }
        return await provider.get_price_history(**kwargs)

    if hasattr(provider, "get_bars"):
        timeframe_label = TIMEFRAME_TO_PROVIDER_ARGS.get(timeframe, {}).get("timeframe", "1Min")
        return await provider.get_bars(symbol, timeframe=timeframe_label, limit=limit)

    raise AttributeError("Provider does not support price history retrieval")


async def _fetch_historical_payload(
    provider: object,
    symbol: str,
    timeframe: Timeframe,
    start: date,
    end: date,
):
    if hasattr(provider, "get_ohlcv_bars"):
        return await provider.get_ohlcv_bars(symbol, start=start, end=end, timeframe=timeframe.value)

    if hasattr(provider, "get_bars"):
        timeframe_label = TIMEFRAME_TO_PROVIDER_ARGS.get(timeframe, {}).get("timeframe", "1Day")
        # Alpaca expects ISO8601 datetimes
        start_dt = datetime.combine(start, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(end, datetime.min.time()).replace(tzinfo=timezone.utc)
        return await provider.get_bars(
            symbol,
            timeframe=timeframe_label,
            start=start_dt,
            end=end_dt,
            limit=10_000,
        )

    raise AttributeError("Provider does not support historical data retrieval")


async def _upsert_price_bar(
    session: AsyncSession,
    ticker: Ticker,
    timeframe: Timeframe,
    candle: dict,
    provider: DataProvider,
) -> bool:
    timestamp = candle["timestamp"]
    existing = await session.scalar(
        select(PriceBar).where(
            PriceBar.ticker_id == ticker.id,
            PriceBar.timestamp == timestamp,
            PriceBar.timeframe == timeframe,
        )
    )

    if existing:
        existing.open = candle["open"]
        existing.high = candle["high"]
        existing.low = candle["low"]
        existing.close = candle["close"]
        existing.volume = candle.get("volume")
        existing.data_provider = provider
        return False

    session.add(
        PriceBar(
            ticker_id=ticker.id,
            timestamp=timestamp,
            timeframe=timeframe,
            open=candle["open"],
            high=candle["high"],
            low=candle["low"],
            close=candle["close"],
            volume=candle.get("volume"),
            data_provider=provider,
        )
    )
    return True


def _compute_dte(today: date, expiration: date) -> int:
    return max((expiration - today).days, 0)


def _first_contract_expiration(contracts: Iterable[dict]) -> Optional[date]:
    for contract in contracts:
        parsed = parse_date(contract.get("expiration"))
        if parsed:
            return parsed
    return None


def _group_contracts_by_term(snapshot: OptionChainSnapshot) -> dict[IVTerm, List[Decimal]]:
    grouped: dict[IVTerm, List[Decimal]] = defaultdict(list)

    for contract in snapshot.contracts:
        if contract.implied_vol is None:
            continue
        dte = snapshot.dte or 0
        for term, (min_days, max_days) in IV_TERM_WINDOWS.items():
            if min_days <= dte <= max_days:
                grouped[term].append(Decimal(contract.implied_vol))
                break

    return grouped


async def _calculate_iv_rank(
    session: AsyncSession,
    ticker_id: int,
    term: IVTerm,
    current_iv: Decimal,
) -> tuple[Optional[Decimal], Optional[Decimal]]:
    """Compute IV rank and percentile based on historical metrics."""

    # Fetch historical metrics excluding the current observation so far.
    history = await session.execute(
        select(IVMetric.implied_vol)
        .where(IVMetric.ticker_id == ticker_id, IVMetric.term == term, IVMetric.implied_vol.is_not(None))
    )
    historical_vals = [row[0] for row in history.fetchall() if row[0] is not None]
    if not historical_vals:
        return None, None

    high = max(historical_vals)
    low = min(historical_vals)
    if high == low:
        rank = Decimal("0")
    else:
        rank = (current_iv - low) / (high - low) * Decimal(100)

    less_equal = sum(1 for val in historical_vals if val <= current_iv)
    percentile = Decimal(less_equal) / Decimal(len(historical_vals)) * Decimal(100)
    return rank.quantize(Decimal("0.01")), percentile.quantize(Decimal("0.01"))


async def _upsert_iv_metric(session: AsyncSession, metric: IVMetric) -> None:
    existing = await session.scalar(
        select(IVMetric).where(
            IVMetric.ticker_id == metric.ticker_id,
            IVMetric.as_of == metric.as_of,
            IVMetric.term == metric.term,
        )
    )
    if existing:
        existing.implied_vol = metric.implied_vol
        existing.iv_rank = metric.iv_rank
        existing.iv_percentile = metric.iv_percentile
        existing.data_provider = metric.data_provider
    else:
        session.add(metric)


def decimal_mean(values: Iterable[Decimal]) -> Decimal:
    """Mean helper that returns a Decimal rounded to 1e-6."""

    dec_values = [Decimal(v) for v in values]
    if not dec_values:
        return Decimal("0")
    avg = sum(dec_values) / Decimal(len(dec_values))
    return avg.quantize(Decimal("0.000001"))
