"""
Flow Service Layer for unusual options activity detection.

Handles business logic for fetching, storing, and querying unusual
options activity detected by flow providers.
"""

import json
from datetime import datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OptionFlow, Ticker
from app.services.flow.provider_manager import FlowProviderManager
from app.utils.logger import app_logger


class FlowService:
    """Service for managing options flow detection and storage."""

    def __init__(self):
        """Initialize flow service with provider manager."""
        self.provider_manager = FlowProviderManager()

    async def detect_and_store_unusual_activity(
        self,
        db: AsyncSession,
        symbol: str,
        min_score: float = 0.7,
        lookback_minutes: int = 60,
    ) -> list[OptionFlow]:
        """
        Detect unusual activity and store in database.

        Args:
            db: Database session.
            symbol: Ticker symbol (e.g., SPY, AAPL).
            min_score: Minimum anomaly score threshold.
            lookback_minutes: Lookback period (not used by yfinance).

        Returns:
            List of OptionFlow records created.

        Raises:
            ValueError: If ticker not found or providers fail.
        """
        # Get ticker from database
        ticker = await self._get_or_create_ticker(db, symbol)

        # Detect unusual activity
        unusual_trades = await self.provider_manager.get_unusual_activity(
            symbol, min_score, lookback_minutes
        )

        if not unusual_trades:
            app_logger.info(f"No unusual activity detected for {symbol}")
            return []

        # Store in database
        flow_records = []
        for trade in unusual_trades:
            flow = OptionFlow(
                ticker_id=ticker.id,
                contract_symbol=trade["contract_symbol"],
                option_type=trade["option_type"],
                strike=trade["strike"],
                expiration=trade["expiration"].date(),
                last_price=trade["last_price"],
                volume=trade["volume"],
                open_interest=trade["open_interest"],
                volume_oi_ratio=trade["volume_oi_ratio"],
                premium=trade["premium"],
                anomaly_score=trade["anomaly_score"],
                flags=json.dumps(trade["flags"]),  # Store as JSON string
                detected_at=trade["detected_at"],
            )
            db.add(flow)
            flow_records.append(flow)

        await db.commit()
        app_logger.info(f"Stored {len(flow_records)} unusual trades for {symbol}")
        return flow_records

    async def get_recent_unusual_activity(
        self,
        db: AsyncSession,
        symbol: str,
        hours: int = 24,
        min_score: float = 0.7,
        limit: int = 50,
    ) -> list[OptionFlow]:
        """
        Query recent unusual activity from database.

        Args:
            db: Database session.
            symbol: Ticker symbol (e.g., SPY, AAPL).
            hours: Lookback period in hours.
            min_score: Minimum anomaly score filter.
            limit: Maximum results to return.

        Returns:
            List of OptionFlow records sorted by anomaly_score descending.
        """
        # Get ticker
        ticker_stmt = select(Ticker).where(Ticker.symbol == symbol.upper())
        result = await db.execute(ticker_stmt)
        ticker = result.scalar_one_or_none()

        if not ticker:
            return []

        # Query flow records
        cutoff = datetime.now() - timedelta(hours=hours)
        stmt = (
            select(OptionFlow)
            .where(
                OptionFlow.ticker_id == ticker.id,
                OptionFlow.detected_at >= cutoff,
                OptionFlow.anomaly_score >= min_score,
            )
            .order_by(desc(OptionFlow.anomaly_score))
            .limit(limit)
        )

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _get_or_create_ticker(self, db: AsyncSession, symbol: str) -> Ticker:
        """Get ticker from database or create if doesn't exist."""
        stmt = select(Ticker).where(Ticker.symbol == symbol.upper())
        result = await db.execute(stmt)
        ticker = result.scalar_one_or_none()

        if not ticker:
            ticker = Ticker(symbol=symbol.upper(), is_active=True)
            db.add(ticker)
            await db.flush()

        return ticker
