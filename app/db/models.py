"""SQLAlchemy ORM models for the Volaris platform."""

from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class TimestampMixin:
    """Adds created/updated timestamps to inheriting models."""

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


class Timeframe(str, enum.Enum):
    """Supported OHLC aggregation windows."""

    ONE_MINUTE = "1m"
    FIVE_MINUTE = "5m"
    DAILY = "1d"


class DataProvider(str, enum.Enum):
    """Enumerates known market data providers."""

    SCHWAB = "schwab"
    ALPACA = "alpaca"
    TIINGO = "tiingo"
    DATABENTO = "databento"
    FINNHUB = "finnhub"


class OptionType(str, enum.Enum):
    """Option contract side."""

    CALL = "call"
    PUT = "put"


class StrategyType(str, enum.Enum):
    """Trade plan strategy classification."""

    VERTICAL_DEBIT = "vertical_debit"
    VERTICAL_CREDIT = "vertical_credit"
    LONG_OPTION = "long_option"
    SHORT_OPTION = "short_option"
    IRON_CONDOR = "iron_condor"
    CUSTOM = "custom"


class TradeBias(str, enum.Enum):
    """Directional bias for a trade plan."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class TradePlanStatus(str, enum.Enum):
    """Lifecycle state of a trade plan."""

    DRAFT = "draft"
    ACTIVE = "active"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class TradeExecutionType(str, enum.Enum):
    """Execution event type."""

    ENTRY = "entry"
    EXIT = "exit"
    ADJUSTMENT = "adjustment"


class JournalSentiment(str, enum.Enum):
    """Optional sentiment tagging for journal entries."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class NewsSentimentLabel(str, enum.Enum):
    """Sentiment classification for news articles."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class MarketLevelType(str, enum.Enum):
    """Market-structure level classification."""

    SWING_HIGH = "swing_high"
    SWING_LOW = "swing_low"
    FAIR_VALUE_GAP = "fair_value_gap"
    VWAP = "vwap"
    EMA_200_TOUCH = "ema_200_touch"
    LIQUIDITY_ZONE = "liquidity_zone"


class IVTerm(str, enum.Enum):
    """Supported horizons for implied-volatility metrics."""

    D7 = "7d"
    D14 = "14d"
    D30 = "30d"
    D60 = "60d"
    D90 = "90d"


def enum_column(enum_cls: type[enum.Enum], *, length: int) -> SqlEnum:
    """Factory for string-based Enum columns that persist enum names."""

    return SqlEnum(enum_cls, native_enum=False, length=length)


class PriceAlertDirection(str, enum.Enum):
    """Directional trigger for price alerts."""

    ABOVE = "above"
    BELOW = "below"


class Ticker(TimestampMixin, Base):
    """Represents a tradeable underlying security."""

    __tablename__ = "tickers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    exchange: Mapped[str | None] = mapped_column(String(64))
    sector: Mapped[str | None] = mapped_column(String(128))
    industry: Mapped[str | None] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)

    price_bars: Mapped[list[PriceBar]] = relationship("PriceBar", back_populates="ticker")  # type: ignore[name-defined]
    watchlist_items: Mapped[list[WatchlistItem]] = relationship("WatchlistItem", back_populates="ticker")  # type: ignore[name-defined]
    option_snapshots: Mapped[list[OptionChainSnapshot]] = relationship("OptionChainSnapshot", back_populates="ticker")  # type: ignore[name-defined]
    iv_metrics: Mapped[list[IVMetric]] = relationship("IVMetric", back_populates="ticker")  # type: ignore[name-defined]
    market_levels: Mapped[list[MarketStructureLevel]] = relationship("MarketStructureLevel", back_populates="ticker")  # type: ignore[name-defined]
    trade_plans: Mapped[list[TradePlan]] = relationship("TradePlan", back_populates="ticker")  # type: ignore[name-defined]
    price_alerts: Mapped[list[PriceAlert]] = relationship(
        "PriceAlert",
        back_populates="ticker",
        cascade="all, delete-orphan",
    )
    price_streams: Mapped[list[PriceStream]] = relationship(
        "PriceStream",
        back_populates="ticker",
        cascade="all, delete-orphan",
    )
    index_memberships: Mapped[list[IndexConstituent]] = relationship(
        "IndexConstituent",
        back_populates="ticker",
        cascade="all, delete-orphan",
    )
    news_articles: Mapped[list[NewsArticle]] = relationship(
        "NewsArticle",
        back_populates="ticker",
        cascade="all, delete-orphan",
    )


class Watchlist(TimestampMixin, Base):
    """Named collection of tickers to monitor."""

    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)

    items: Mapped[list[WatchlistItem]] = relationship("WatchlistItem", back_populates="watchlist", cascade="all, delete-orphan")  # type: ignore[name-defined]


class WatchlistItem(TimestampMixin, Base):
    """Links a ticker to a watchlist with optional ordering metadata."""

    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    watchlist_id: Mapped[int] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False
    )
    ticker_id: Mapped[int] = mapped_column(
        ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rank: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)

    watchlist: Mapped[Watchlist] = relationship("Watchlist", back_populates="items")
    ticker: Mapped[Ticker] = relationship("Ticker", back_populates="watchlist_items")

    __table_args__ = (UniqueConstraint("watchlist_id", "ticker_id", name="uq_watchlist_ticker"),)


class PriceBar(TimestampMixin, Base):
    """Stores aggregated OHLCV data for a ticker and timeframe."""

    __tablename__ = "price_bars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker_id: Mapped[int] = mapped_column(
        ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timeframe: Mapped[Timeframe] = mapped_column(enum_column(Timeframe, length=16), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    data_provider: Mapped[DataProvider] = mapped_column(
        enum_column(DataProvider, length=32), nullable=False
    )

    ticker: Mapped[Ticker] = relationship("Ticker", back_populates="price_bars")

    __table_args__ = (
        UniqueConstraint(
            "ticker_id", "timestamp", "timeframe", name="uq_price_bars_ticker_ts_frame"
        ),
        Index("ix_price_bars_ticker_timestamp", "ticker_id", "timestamp"),
    )


class OptionChainSnapshot(TimestampMixin, Base):
    """Captures an option chain pull for a ticker and expiration."""

    __tablename__ = "option_chain_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker_id: Mapped[int] = mapped_column(
        ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    expiration: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    dte: Mapped[int] = mapped_column(Integer, nullable=False)
    underlying_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    data_provider: Mapped[DataProvider] = mapped_column(
        enum_column(DataProvider, length=32), nullable=False
    )

    ticker: Mapped[Ticker] = relationship("Ticker", back_populates="option_snapshots")
    contracts: Mapped[list[OptionContract]] = relationship("OptionContract", back_populates="snapshot", cascade="all, delete-orphan")  # type: ignore[name-defined]

    __table_args__ = (
        Index("ix_option_chain_snapshot_ticker_expiration", "ticker_id", "expiration"),
    )


class OptionContract(TimestampMixin, Base):
    """Represents greeks and pricing for a single option contract."""

    __tablename__ = "option_contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("option_chain_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    option_type: Mapped[OptionType] = mapped_column(
        enum_column(OptionType, length=16), nullable=False
    )
    strike: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    bid: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    ask: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    last: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    mark: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    open_interest: Mapped[int | None] = mapped_column(BigInteger)
    implied_vol: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    delta: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    gamma: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    theta: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    vega: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    rho: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))

    snapshot: Mapped[OptionChainSnapshot] = relationship(
        "OptionChainSnapshot", back_populates="contracts"
    )

    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "option_type", "strike", name="uq_option_contract_snapshot_strike"
        ),
        Index("ix_option_contract_snapshot", "snapshot_id"),
    )


class IVMetric(TimestampMixin, Base):
    """Derived implied-volatility metrics per ticker."""

    __tablename__ = "iv_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker_id: Mapped[int] = mapped_column(
        ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    term: Mapped[IVTerm] = mapped_column(enum_column(IVTerm, length=16), nullable=False)
    implied_vol: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    iv_rank: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    iv_percentile: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    data_provider: Mapped[DataProvider] = mapped_column(
        SqlEnum(DataProvider, native_enum=False, length=16), nullable=False
    )

    ticker: Mapped[Ticker] = relationship("Ticker", back_populates="iv_metrics")

    __table_args__ = (
        UniqueConstraint("ticker_id", "as_of", "term", name="uq_iv_metrics_ticker_term"),
        Index("ix_iv_metrics_ticker_asof", "ticker_id", "as_of"),
    )


class MarketStructureLevel(TimestampMixin, Base):
    """Stores detected market-structure levels used by alerts."""

    __tablename__ = "market_structure_levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker_id: Mapped[int] = mapped_column(
        ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False
    )
    level_type: Mapped[MarketLevelType] = mapped_column(
        enum_column(MarketLevelType, length=64), nullable=False
    )
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    notes: Mapped[str | None] = mapped_column(Text)

    ticker: Mapped[Ticker] = relationship("Ticker", back_populates="market_levels")

    __table_args__ = (Index("ix_market_levels_ticker_type", "ticker_id", "level_type"),)


class PriceAlert(TimestampMixin, Base):
    """Server-wide price alert triggered when price crosses target."""

    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker_id: Mapped[int] = mapped_column(
        ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[PriceAlertDirection] = mapped_column(
        enum_column(PriceAlertDirection, length=16), nullable=False
    )
    target_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(64))
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    ticker: Mapped[Ticker] = relationship("Ticker", back_populates="price_alerts")

    __table_args__ = (Index("ix_price_alerts_ticker_direction", "ticker_id", "direction"),)


class PriceStream(TimestampMixin, Base):
    """Recurring price stream announcements for a channel."""

    __tablename__ = "price_streams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker_id: Mapped[int] = mapped_column(
        ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[str] = mapped_column(String(64), nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(64))
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))

    ticker: Mapped[Ticker] = relationship("Ticker", back_populates="price_streams")

    __table_args__ = (
        UniqueConstraint("ticker_id", "channel_id", name="uq_price_stream_channel"),
        Index("ix_price_streams_next_run", "next_run_at"),
    )


class IndexConstituent(TimestampMixin, Base):
    """Ticker membership for a specific market index (e.g., S&P 500)."""

    __tablename__ = "index_constituents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    index_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    ticker_id: Mapped[int] = mapped_column(
        ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False
    )
    weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))

    ticker: Mapped[Ticker] = relationship("Ticker", back_populates="index_memberships")

    __table_args__ = (
        UniqueConstraint("index_symbol", "ticker_id", name="uq_index_constituent"),
        Index("ix_index_constituents_symbol", "index_symbol"),
    )


class TradePlan(TimestampMixin, Base):
    """Represents a prepared trade idea with sizing and risk parameters."""

    __tablename__ = "trade_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker_id: Mapped[int] = mapped_column(
        ForeignKey("tickers.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[TradePlanStatus] = mapped_column(
        enum_column(TradePlanStatus, length=32),
        nullable=False,
        server_default=TradePlanStatus.DRAFT.value,
    )
    strategy: Mapped[StrategyType] = mapped_column(
        enum_column(StrategyType, length=48), nullable=False
    )
    bias: Mapped[TradeBias] = mapped_column(enum_column(TradeBias, length=16), nullable=False)
    thesis: Mapped[str | None] = mapped_column(Text)
    expiration: Mapped[date | None] = mapped_column(Date)
    dte: Mapped[int | None] = mapped_column(Integer)
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    max_loss: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    max_profit: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    risk_reward: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    position_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    tags: Mapped[str | None] = mapped_column(String(255))

    ticker: Mapped[Ticker] = relationship("Ticker", back_populates="trade_plans")
    executions: Mapped[list[TradeExecution]] = relationship("TradeExecution", back_populates="trade_plan", cascade="all, delete-orphan")  # type: ignore[name-defined]
    journal_entries: Mapped[list[TradeJournalEntry]] = relationship("TradeJournalEntry", back_populates="trade_plan", cascade="all, delete-orphan")  # type: ignore[name-defined]

    __table_args__ = (Index("ix_trade_plans_ticker_status", "ticker_id", "status"),)


class TradeExecution(TimestampMixin, Base):
    """Tracks fills and adjustments executed against a trade plan."""

    __tablename__ = "trade_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_plan_id: Mapped[int] = mapped_column(
        ForeignKey("trade_plans.id", ondelete="SET NULL"), nullable=True
    )
    execution_type: Mapped[TradeExecutionType] = mapped_column(
        enum_column(TradeExecutionType, length=32), nullable=False
    )
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fill_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    order_id: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)

    trade_plan: Mapped[TradePlan | None] = relationship("TradePlan", back_populates="executions")
    journal_entries: Mapped[list[TradeJournalEntry]] = relationship("TradeJournalEntry", back_populates="execution")  # type: ignore[name-defined]


class TradeJournalEntry(TimestampMixin, Base):
    """Narrative notes and grading tied to trade plans or executions."""

    __tablename__ = "trade_journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("trade_plans.id", ondelete="SET NULL")
    )
    execution_id: Mapped[int | None] = mapped_column(
        ForeignKey("trade_executions.id", ondelete="SET NULL")
    )
    sentiment: Mapped[JournalSentiment | None] = mapped_column(
        enum_column(JournalSentiment, length=16)
    )
    rating: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[str | None] = mapped_column(Text)

    trade_plan: Mapped[TradePlan | None] = relationship(
        "TradePlan", back_populates="journal_entries"
    )
    execution: Mapped[TradeExecution | None] = relationship(
        "TradeExecution", back_populates="journal_entries"
    )


class NewsArticle(TimestampMixin, Base):
    """Stores news articles with VADER sentiment analysis for tickers."""

    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker_id: Mapped[int] = mapped_column(
        ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False
    )
    headline: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(128))
    url: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sentiment_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    sentiment_label: Mapped[NewsSentimentLabel | None] = mapped_column(
        enum_column(NewsSentimentLabel, length=16)
    )
    sentiment_compound: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    ticker: Mapped[Ticker] = relationship("Ticker", back_populates="news_articles")

    __table_args__ = (
        Index("ix_news_articles_ticker_published", "ticker_id", "published_at"),
        Index("ix_news_articles_url", "url", unique=True),
    )
