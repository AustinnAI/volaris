"""Market hours utilities for NYSE/NASDAQ trading hours."""

from datetime import UTC, datetime, time

import pytz

from app.config import settings


def is_market_hours(dt: datetime | None = None) -> bool:
    """
    Check if given datetime falls within regular market hours (9:30 AM - 4:00 PM ET).

    Args:
        dt: Datetime to check (UTC). Defaults to current UTC time.

    Returns:
        True if within market hours (Mon-Fri 9:30 AM - 4:00 PM ET), False otherwise.

    Example:
        >>> # Check current time
        >>> if is_market_hours():
        ...     print("Market is open")
        >>> # Check specific time
        >>> dt = datetime(2025, 11, 5, 14, 30, tzinfo=UTC)  # 9:30 AM ET
        >>> is_market_hours(dt)
        True
    """
    if dt is None:
        dt = datetime.now(UTC)

    # Ensure UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    elif dt.tzinfo != UTC:
        dt = dt.astimezone(UTC)

    # Convert to market timezone
    market_tz = pytz.timezone(settings.MARKET_TZ)
    dt_market = dt.astimezone(market_tz)

    # Check if weekday (0=Mon, 6=Sun)
    if dt_market.weekday() >= 5:  # Saturday or Sunday
        return False

    # Market hours: 9:30 AM - 4:00 PM ET
    market_open = time(9, 30)
    market_close = time(16, 0)

    current_time = dt_market.time()
    return market_open <= current_time < market_close
