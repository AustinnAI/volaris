"""Async job wrappers executed by APScheduler."""

from __future__ import annotations

from datetime import date

from app.db.database import async_session_maker
from app.db.models import Timeframe
from app.utils.logger import app_logger
from app.workers import tasks


async def realtime_prices_job(timeframe: Timeframe = Timeframe.ONE_MINUTE) -> None:
    async with async_session_maker() as session:
        try:
            inserted = await tasks.fetch_realtime_prices(session, timeframe=timeframe)
            app_logger.debug(
                "Realtime prices job complete",
                extra={"timeframe": timeframe.value, "inserted": inserted},
            )
        except Exception as exc:  # pylint: disable=broad-except
            app_logger.error("Realtime job failed", extra={"error": str(exc)})


async def historical_backfill_job() -> None:
    async with async_session_maker() as session:
        try:
            inserted = await tasks.backfill_historical_prices(session)
            app_logger.info("Historical backfill complete", extra={"inserted": inserted})
        except Exception as exc:  # pylint: disable=broad-except
            app_logger.error("Historical backfill failed", extra={"error": str(exc)})


async def eod_sync_job() -> None:
    async with async_session_maker() as session:
        try:
            inserted = await tasks.sync_eod_prices(session)
            app_logger.info("EOD sync complete", extra={"records": inserted})
        except Exception as exc:  # pylint: disable=broad-except
            app_logger.error("EOD sync failed", extra={"error": str(exc)})


async def option_chain_refresh_job() -> None:
    async with async_session_maker() as session:
        try:
            snapshots = await tasks.fetch_option_chains(session)
            app_logger.info("Option chain refresh complete", extra={"snapshots": snapshots})
        except Exception as exc:  # pylint: disable=broad-except
            app_logger.error("Option chain refresh failed", extra={"error": str(exc)})


async def iv_metric_job() -> None:
    async with async_session_maker() as session:
        try:
            metrics = await tasks.compute_iv_metrics(session)
            app_logger.debug("IV metric job complete", extra={"metrics": metrics})
        except Exception as exc:  # pylint: disable=broad-except
            app_logger.error("IV metric job failed", extra={"error": str(exc)})
