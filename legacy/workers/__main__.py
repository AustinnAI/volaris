"""
Standalone entry point for running the APScheduler worker.
Usage: python -m app.workers
"""

import asyncio
import signal
import sys

from app.config import settings
from app.db.database import close_db, init_db
from app.utils.logger import app_logger
from app.workers import create_scheduler


async def main():
    """Run the scheduler as a standalone service."""
    if not settings.SCHEDULER_ENABLED:
        app_logger.error("SCHEDULER_ENABLED=false in config. Set to true to run worker.")
        sys.exit(1)

    app_logger.info("Initializing background worker...")

    # Initialize database
    await init_db()

    # Create and start scheduler
    scheduler = create_scheduler()
    scheduler.start()

    app_logger.info("Background worker started. Press Ctrl+C to stop.")

    # Setup graceful shutdown
    def shutdown_handler(signum, frame):
        app_logger.info("Received shutdown signal. Stopping scheduler...")
        scheduler.shutdown(wait=True)
        asyncio.create_task(close_db())
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        app_logger.info("Keyboard interrupt. Stopping scheduler...")
        scheduler.shutdown(wait=True)
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
