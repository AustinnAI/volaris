"""APScheduler factory for background jobs."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.db.models import Timeframe
from app.utils.logger import app_logger
from app.utils.memory_profiler import get_memory_usage
from app.workers.jobs import (
    iv_metric_job,
    option_chain_refresh_job,
    realtime_prices_job,
    refresh_sp500_job,
)


def _log_job_memory(event):
    """Log memory usage after each job execution."""
    if event.exception:
        return  # Job failed, memory info not useful

    memory = get_memory_usage()
    app_logger.info(
        "job_completed",
        extra={
            "job_id": event.job_id,
            "memory_mb": memory["rss_mb"],
            "memory_percent": memory["percent"],
        },
    )


def create_scheduler() -> AsyncIOScheduler:
    """Configure the AsyncIO scheduler with recurring jobs."""

    scheduler = AsyncIOScheduler(timezone=settings.SCHEDULER_TIMEZONE)

    # Add listener to log memory usage after each job
    scheduler.add_listener(_log_job_memory, mask=1 | 2)  # JOB_EXECUTED | JOB_ERROR

    scheduler.add_job(
        realtime_prices_job,
        trigger="interval",
        seconds=settings.REALTIME_JOB_INTERVAL_SECONDS,
        kwargs={"timeframe": Timeframe.ONE_MINUTE},
        id="prices_1m",
        max_instances=1,
        misfire_grace_time=30,  # Skip if job is 30s late
    )

    # REMOVED: prices_5m job (redundant with prices_1m)
    # 5-minute data can be downsampled from 1-minute data when needed
    # Memory savings: ~35%

    # REMOVED: eod_sync job (only needed for Phase 4+ backtesting)
    # Re-enable when implementing historical analysis features
    # Memory savings: ~20%

    # REMOVED: historical_backfill job (one-time setup)
    # Run manually when needed: python -m app.workers.jobs historical_backfill
    # Memory savings: ~15%

    scheduler.add_job(
        option_chain_refresh_job,
        trigger="interval",
        minutes=settings.OPTION_CHAIN_JOB_INTERVAL_MINUTES,
        id="options_refresh",
        max_instances=1,
        misfire_grace_time=120,  # Skip if job is 2 min late
    )

    scheduler.add_job(
        iv_metric_job,
        trigger="interval",
        minutes=settings.IV_METRICS_JOB_INTERVAL_MINUTES,
        id="iv_metrics",
        max_instances=1,
        misfire_grace_time=120,  # Skip if job is 2 min late
    )

    scheduler.add_job(
        refresh_sp500_job,
        trigger=CronTrigger(
            day_of_week=settings.SP500_REFRESH_CRON_DAY,
            hour=settings.SP500_REFRESH_CRON_HOUR,
            minute=settings.SP500_REFRESH_CRON_MINUTE,
        ),
        id="sp500_refresh",
        max_instances=1,
        misfire_grace_time=600,
    )

    app_logger.info("APScheduler configured with background jobs")
    return scheduler
