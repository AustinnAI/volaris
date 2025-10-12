"""
Entry point for running Discord bot as a module: python -m app.alerts
"""
import asyncio
import logging

from app.alerts.discord_bot import run_bot

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(run_bot())
