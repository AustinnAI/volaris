"""
Configuration Management
Centralized configuration using Pydantic settings with environment variable support.
"""

from typing import List, Optional
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
    ENVIRONMENT: str = Field(default="development", description="Environment: development, staging, production")
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # API Configuration
    API_V1_PREFIX: str = Field(default="/api/v1", description="API version 1 prefix")
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins"
    )

    # Database - PostgreSQL (Neon/Supabase)
    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL connection string (postgresql://user:pass@host:port/db)"
    )
    DB_POOL_SIZE: int = Field(default=5, description="Database connection pool size")
    DB_MAX_OVERFLOW: int = Field(default=10, description="Max overflow connections")
    DB_ECHO: bool = Field(default=False, description="Echo SQL queries (debug)")

    # Redis Cache (Upstash)
    UPSTASH_REDIS_REST_URL: str = Field(
        ...,
        description="Upstash Redis REST URL"
    )
    UPSTASH_REDIS_REST_TOKEN: str = Field(
        ...,
        description="Upstash Redis REST token"
    )
    REDIS_TTL_DEFAULT: int = Field(default=300, description="Default Redis TTL in seconds")

    # Sentry Monitoring
    SENTRY_DSN: Optional[str] = Field(default=None, description="Sentry DSN for error tracking")

    # API Keys - Market Data Providers (Phase 1.2)
    # Schwab API (Primary real-time 1m/5m)
    SCHWAB_APP_KEY: Optional[str] = Field(default=None, description="Schwab API app key")
    SCHWAB_SECRET_KEY: Optional[str] = Field(default=None, description="Schwab API secret key")
    SCHWAB_REDIRECT_URI: Optional[str] = Field(
        default="https://volaris.onrender.com/auth/schwab/callback",  # Placeholder - update when deployed
        description="Schwab OAuth redirect URI"
    )
    SCHWAB_API_BASE: str = Field(
        default="https://api.schwabapi.com",
        description="Schwab API base URL"
    )
    SCHWAB_REFRESH_TOKEN: Optional[str] = Field(default=None, description="Schwab OAuth refresh token")

    # Tiingo (EOD data)
    TIINGO_API_KEY: Optional[str] = Field(default=None, description="Tiingo API key")
    TIINGO_API_BASE: str = Field(
        default="https://api.tiingo.com",
        description="Tiingo API base URL"
    )

    # Alpaca (Minute delayed historical)
    ALPACA_API_KEY: Optional[str] = Field(default=None, description="Alpaca API key ID")
    ALPACA_API_SECRET: Optional[str] = Field(default=None, description="Alpaca API secret key")
    ALPACA_API_BASE: str = Field(
        default="https://paper-api.alpaca.markets",
        description="Alpaca API base URL"
    )

    # Databento (Historical backfills)
    DATABENTO_API_KEY: Optional[str] = Field(default=None, description="Databento API key")
    DATABENTO_API_BASE: str = Field(
        default="https://hist.databento.com",
        description="Databento API base URL"
    )

    # Finnhub (Fundamentals & news)
    FINNHUB_API_KEY: Optional[str] = Field(default=None, description="Finnhub API key")
    FINNHUB_WEBHOOK_SECRET: Optional[str] = Field(default=None, description="Finnhub webhook secret")
    FINNHUB_API_BASE: str = Field(
        default="https://finnhub.io/api/v1",
        description="Finnhub API base URL"
    )

    # Discord Integration (Phase 8)
    DISCORD_BOT_TOKEN: Optional[str] = Field(default=None, description="Discord bot token")
    DISCORD_WEBHOOK_URL: Optional[str] = Field(default=None, description="Discord webhook URL for alerts")
    DISCORD_SERVER_ID: Optional[str] = Field(default=None, description="Discord server ID")

    # Trading Configuration
    DEFAULT_ACCOUNT_SIZE: float = Field(default=25000.0, description="Default account size for risk calculations")
    MAX_RISK_PERCENTAGE: float = Field(default=10.0, description="Max risk per trade as % of account")
    PDT_THRESHOLD: int = Field(default=25000, description="Pattern Day Trader threshold")

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
        default=60,
        description="Interval for 1-minute price sync job",
    )
    FIVE_MINUTE_JOB_INTERVAL_SECONDS: int = Field(
        default=300,
        description="Interval for 5-minute price sync job",
    )
    OPTION_CHAIN_JOB_INTERVAL_MINUTES: int = Field(
        default=15,
        description="Interval for option chain refresh job",
    )
    IV_METRICS_JOB_INTERVAL_MINUTES: int = Field(
        default=30,
        description="Interval for IV metric calculation job",
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

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value"""
        allowed = {"development", "staging", "production"}
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
