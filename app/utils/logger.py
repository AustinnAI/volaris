"""
Logging Configuration
Structured logging with Sentry integration for error tracking.
"""

import logging
import sys
from typing import Any, Dict
from app.config import settings


def setup_logging() -> logging.Logger:
    """
    Configure application logging with structured output.
    Integrates with Sentry for error tracking in production.

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("volaris")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler with formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL))

    # Format: timestamp - level - module - message
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    # Log startup info
    logger.info(f"Logging initialized - Level: {settings.LOG_LEVEL}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    if settings.SENTRY_DSN:
        logger.info("Sentry monitoring enabled")

    return logger


def log_api_call(
    logger: logging.Logger,
    provider: str,
    endpoint: str,
    status_code: int,
    response_time: float,
    error: str = None,
) -> None:
    """
    Log API call details for monitoring and debugging.

    Args:
        logger: Logger instance
        provider: API provider name (e.g., "Schwab", "Tiingo")
        endpoint: API endpoint called
        status_code: HTTP status code
        response_time: Response time in seconds
        error: Error message if call failed
    """
    log_data = {
        "provider": provider,
        "endpoint": endpoint,
        "status_code": status_code,
        "response_time_ms": round(response_time * 1000, 2),
    }

    if error:
        log_data["error"] = error
        logger.error(f"API call failed: {log_data}")
    else:
        logger.info(f"API call successful: {log_data}")


# Global logger instance
app_logger = setup_logging()
