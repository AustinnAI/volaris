"""APScheduler factory for background jobs."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.db.models import Timeframe
from app.utils.logger import app_logger
from app.workers.jobs import (
    eod_sync_job,
    historical_backfill_job,
    iv_metric_job,
    option_chain_refresh_job,
    realtime_prices_job,
)


def create_scheduler() -> AsyncIOScheduler:
    """Configure the AsyncIO scheduler with recurring jobs."""

    scheduler = AsyncIOScheduler(timezone=settings.SCHEDULER_TIMEZONE)

    scheduler.add_job(
        realtime_prices_job,
        trigger="interval",
        seconds=settings.REALTIME_JOB_INTERVAL_SECONDS,
        kwargs={"timeframe": Timeframe.ONE_MINUTE},
        id="prices_1m",
        max_instances=1,
    )

    scheduler.add_job(
        realtime_prices_job,
        trigger="interval",
        seconds=settings.FIVE_MINUTE_JOB_INTERVAL_SECONDS,
        kwargs={"timeframe": Timeframe.FIVE_MINUTE},
        id="prices_5m",
        max_instances=1,
    )

    scheduler.add_job(
        eod_sync_job,
        trigger=CronTrigger(
            hour=settings.EOD_SYNC_CRON_HOUR,
            minute=settings.EOD_SYNC_CRON_MINUTE,
        ),
        id="eod_sync",
        max_instances=1,
    )

    scheduler.add_job(
        historical_backfill_job,
        trigger=CronTrigger(hour=settings.HISTORICAL_BACKFILL_CRON_HOUR, minute=0),
        id="historical_backfill",
        max_instances=1,
    )

    scheduler.add_job(
        option_chain_refresh_job,
        trigger="interval",
        minutes=settings.OPTION_CHAIN_JOB_INTERVAL_MINUTES,
        id="options_refresh",
        max_instances=1,
    )

    scheduler.add_job(
        iv_metric_job,
        trigger="interval",
        minutes=settings.IV_METRICS_JOB_INTERVAL_MINUTES,
        id="iv_metrics",
        max_instances=1,
    )

    app_logger.info("APScheduler configured with background jobs")
    return scheduler
