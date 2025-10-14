"""
Configuration Management
Centralized configuration using Pydantic settings with environment variable support.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Uses .env file for local development.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    ENVIRONMENT: str = Field(
        default="development", description="Environment: development, staging, production"
    )
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # API Configuration
    API_V1_PREFIX: str = Field(default="/api/v1", description="API version 1 prefix")
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins",
    )

    # Database - PostgreSQL (Neon/Supabase)
    DATABASE_URL: str = Field(
        ..., description="PostgreSQL connection string (postgresql://user:pass@host:port/db)"
    )
    DB_POOL_SIZE: int = Field(default=5, description="Database connection pool size")
    DB_MAX_OVERFLOW: int = Field(default=10, description="Max overflow connections")
    DB_ECHO: bool = Field(default=False, description="Echo SQL queries (debug)")

    # Redis Cache (Upstash)
    UPSTASH_REDIS_REST_URL: str = Field(..., description="Upstash Redis REST URL")
    UPSTASH_REDIS_REST_TOKEN: str = Field(..., description="Upstash Redis REST token")
    REDIS_TTL_DEFAULT: int = Field(default=300, description="Default Redis TTL in seconds")

    # Sentry Monitoring
    SENTRY_DSN: str | None = Field(default=None, description="Sentry DSN for error tracking")

    # API Keys - Market Data Providers (Phase 1.2)
    # Schwab API (Primary real-time 1m/5m)
    SCHWAB_APP_KEY: str | None = Field(default=None, description="Schwab API app key")
    SCHWAB_SECRET_KEY: str | None = Field(default=None, description="Schwab API secret key")
    SCHWAB_REDIRECT_URI: str | None = Field(
        default="https://volaris.onrender.com/auth/schwab/callback",  # Placeholder - update when deployed
        description="Schwab OAuth redirect URI",
    )
    SCHWAB_API_BASE: str = Field(
        default="https://api.schwabapi.com", description="Schwab API base URL"
    )
    SCHWAB_REFRESH_TOKEN: str | None = Field(default=None, description="Schwab OAuth refresh token")

    # Tiingo (EOD data)
    TIINGO_API_KEY: str | None = Field(default=None, description="Tiingo API key")
    TIINGO_API_BASE: str = Field(
        default="https://api.tiingo.com", description="Tiingo API base URL"
    )

    # Alpaca (Minute delayed historical)
    ALPACA_API_KEY: str | None = Field(default=None, description="Alpaca API key ID")
    ALPACA_API_SECRET: str | None = Field(default=None, description="Alpaca API secret key")
    ALPACA_API_BASE: str = Field(
        default="https://paper-api.alpaca.markets", description="Alpaca API base URL"
    )

    # Databento (Historical backfills)
    DATABENTO_API_KEY: str | None = Field(default=None, description="Databento API key")
    DATABENTO_API_BASE: str = Field(
        default="https://hist.databento.com", description="Databento API base URL"
    )

    # Finnhub (Fundamentals & news)
    FINNHUB_API_KEY: str | None = Field(default=None, description="Finnhub API key")
    FINNHUB_WEBHOOK_SECRET: str | None = Field(default=None, description="Finnhub webhook secret")
    FINNHUB_API_BASE: str = Field(
        default="https://finnhub.io/api/v1", description="Finnhub API base URL"
    )

    # Discord Integration (Phase 8)
    DISCORD_BOT_TOKEN: str | None = Field(default=None, description="Discord bot token")
    DISCORD_WEBHOOK_URL: str | None = Field(
        default=None, description="Discord webhook URL for alerts"
    )
    DISCORD_SERVER_ID: str | None = Field(default=None, description="Discord server/guild ID")
    DISCORD_GUILD_ID: str | None = Field(
        default=None,
        description="Discord guild ID for command registration (fallback to SERVER_ID)",
    )
    DISCORD_BOT_ENABLED: bool = Field(default=False, description="Enable Discord bot")
    API_BASE_URL: str = Field(
        default="http://localhost:8000", description="API base URL for Discord bot"
    )
    PRICE_ALERT_POLL_SECONDS: int = Field(
        default=60, description="Polling cadence (seconds) for Discord price alerts"
    )
    PRICE_STREAM_POLL_SECONDS: int = Field(
        default=60, description="Polling cadence (seconds) for Discord price streams"
    )
    PRICE_STREAM_DEFAULT_INTERVAL_SECONDS: int = Field(
        default=900, description="Default interval for recurring price streams (seconds)"
    )
    PRICE_STREAM_MIN_INTERVAL_SECONDS: int = Field(
        default=300, description="Minimum allowed interval for price streams (seconds)"
    )
    PRICE_STREAM_MAX_INTERVAL_SECONDS: int = Field(
        default=7200, description="Maximum allowed interval for price streams (seconds)"
    )
    REALTIME_SYNC_BATCH_SIZE: int = Field(
        default=25, ge=1, description="Number of tickers to process per realtime price batch"
    )
    SENTIMENT_CACHE_SECONDS: int = Field(
        default=600, description="Cache TTL for sentiment responses (seconds)"
    )
    TOP_MOVERS_LIMIT: int = Field(
        default=5, description="Number of gainers/losers to display in top command"
    )
    DISCORD_DEFAULT_CHANNEL_ID: str | None = Field(
        default=None, description="Default Discord channel for scheduled digests"
    )
    POLYGON_API_KEY: str | None = Field(
        default=None, description="Polygon.io API key for market data"
    )
    POLYGON_API_BASE: str = Field(
        default="https://api.polygon.io", description="Polygon API base URL"
    )
    MARKETSTACK_API_KEY: str | None = Field(
        default=None, description="Marketstack API key for EOD fallback"
    )
    MARKETSTACK_API_BASE: str = Field(
        default="http://api.marketstack.com/v1", description="Marketstack API base URL"
    )

    @property
    def discord_guild_id_resolved(self) -> str | None:
        """Get Discord guild ID, preferring DISCORD_GUILD_ID, falling back to DISCORD_SERVER_ID."""
        return self.DISCORD_GUILD_ID or self.DISCORD_SERVER_ID

    # Trading Configuration
    DEFAULT_ACCOUNT_SIZE: float = Field(
        default=25000.0, description="Default account size for risk calculations"
    )
    MAX_RISK_PERCENTAGE: float = Field(
        default=10.0, description="Max risk per trade as % of account"
    )
    PDT_THRESHOLD: int = Field(default=25000, description="Pattern Day Trader threshold")

    # Strike Selection Configuration (Phase 3.2)
    # IV Regime Thresholds
    IV_HIGH_THRESHOLD: float = Field(
        default=50.0, description="IV percentile threshold for 'high' regime"
    )
    IV_LOW_THRESHOLD: float = Field(
        default=25.0, description="IV percentile threshold for 'low' regime"
    )

    # Credit Spread Thresholds
    MIN_CREDIT_PCT: float = Field(
        default=0.25, description="Minimum credit as % of spread width (default 25%)"
    )

    # Strike Classification
    ATM_THRESHOLD_PCT: float = Field(
        default=2.0, description="ATM classification threshold as % of underlying price"
    )

    # Liquidity Filters
    MIN_OPEN_INTEREST: int = Field(
        default=10, description="Minimum open interest for tradeable contracts"
    )
    MIN_VOLUME: int = Field(default=5, description="Minimum daily volume for tradeable contracts")
    MIN_MARK_PRICE: float = Field(
        default=0.01, description="Minimum mark price to avoid stale contracts"
    )

    # Spread Width Limits (in points)
    SPREAD_WIDTH_LOW_PRICE_MIN: int = Field(
        default=2, description="Min spread width for stocks < $100"
    )
    SPREAD_WIDTH_LOW_PRICE_MAX: int = Field(
        default=5, description="Max spread width for stocks < $100"
    )
    SPREAD_WIDTH_MID_PRICE: int = Field(default=5, description="Spread width for stocks $100-$300")
    SPREAD_WIDTH_HIGH_PRICE_MIN: int = Field(
        default=5, description="Min spread width for stocks > $300"
    )
    SPREAD_WIDTH_HIGH_PRICE_MAX: int = Field(
        default=10, description="Max spread width for stocks > $300"
    )
    SPREAD_WIDTH_TOLERANCE_PCT: float = Field(
        default=0.20, description="Tolerance for short leg width (±20%)"
    )

    # Bid-Ask Spread Quality
    MAX_BID_ASK_SPREAD_PCT: float = Field(
        default=0.15, description="Max bid-ask spread as % of mark (15%)"
    )

    # Strategy Recommendation Scoring Weights
    SCORING_WEIGHT_POP: float = Field(default=0.30, description="POP weight in composite score")
    SCORING_WEIGHT_RR: float = Field(default=0.30, description="R:R weight in composite score")
    SCORING_WEIGHT_CREDIT: float = Field(default=0.25, description="Credit quality weight")
    SCORING_WEIGHT_LIQUIDITY: float = Field(default=0.10, description="Liquidity weight")
    SCORING_WEIGHT_WIDTH: float = Field(default=0.05, description="Width efficiency weight")

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable rate limiting")
    RATE_LIMIT_REQUESTS: int = Field(default=100, description="Max requests per window")
    RATE_LIMIT_WINDOW: int = Field(default=60, description="Rate limit window in seconds")

    # Scheduler
    SCHEDULER_ENABLED: bool = Field(
        default=False,
        description="Enable background APScheduler jobs",
    )
    SCHEDULER_TIMEZONE: str = Field(
        default="UTC",
        description="Timezone for APScheduler jobs",
    )
    REALTIME_JOB_INTERVAL_SECONDS: int = Field(
        default=120,
        description="Interval for price sync job (2 min for memory optimization)",
    )
    FIVE_MINUTE_JOB_INTERVAL_SECONDS: int = Field(
        default=300,
        description="[DEPRECATED] 5-minute job removed for memory optimization",
    )
    OPTION_CHAIN_JOB_INTERVAL_MINUTES: int = Field(
        default=30,
        description="Interval for option chain refresh (30 min for memory optimization)",
    )
    IV_METRICS_JOB_INTERVAL_MINUTES: int = Field(
        default=60,
        description="Interval for IV metric calculation (60 min for memory optimization)",
    )
    EOD_SYNC_CRON_HOUR: int = Field(
        default=22,
        description="Hour (24h) for daily Tiingo EOD sync",
    )
    EOD_SYNC_CRON_MINUTE: int = Field(
        default=15,
        description="Minute for daily Tiingo EOD sync",
    )
    HISTORICAL_BACKFILL_CRON_HOUR: int = Field(
        default=3,
        description="Hour (24h) for historical backfill job",
    )
    HISTORICAL_BACKFILL_LOOKBACK_DAYS: int = Field(
        default=30,
        description="Lookback window (days) for historical backfill",
    )
    SP500_REFRESH_CRON_DAY: str = Field(
        default="mon",
        description="Day of week for S&P 500 constituent refresh (cron expression, e.g., mon)",
    )
    SP500_REFRESH_CRON_HOUR: int = Field(
        default=6, description="Hour (24h) for S&P 500 refresh job"
    )
    SP500_REFRESH_CRON_MINUTE: int = Field(default=0, description="Minute for S&P 500 refresh job")

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value"""
        allowed = {"development", "staging", "production", "testing"}
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}")
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level"""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}")
        return v_upper

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.ENVIRONMENT == "development"


# Global settings instance
settings = Settings()
