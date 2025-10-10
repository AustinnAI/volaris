"""
Database Models
SQLAlchemy ORM models for the Volaris platform.
Models will be added in Phase 2.1
"""

from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# TODO: Phase 2.1 - Add models:
# - Ticker (watchlist)
# - OHLCData (minute, 5-min, daily)
# - OptionsChain
# - IVMetrics
# - MarketStructure (swing highs/lows, FVG, VWAP)
# - TradePlan
# - TradeExecution
# - TradeJournal
