"""
Rate Limiting Utility
Token bucket implementation for API rate limiting.
"""

import time
from collections import defaultdict

from app.config import settings


class RateLimiter:
    """
    Token bucket rate limiter for API calls.
    Prevents exceeding API rate limits across different providers.
    """

    def __init__(self):
        self.buckets: dict[str, tuple[int, float]] = defaultdict(
            lambda: (settings.RATE_LIMIT_REQUESTS, time.time())
        )
        self.max_requests = settings.RATE_LIMIT_REQUESTS
        self.window_seconds = settings.RATE_LIMIT_WINDOW

    def is_allowed(self, key: str) -> bool:
        """
        Check if request is allowed under rate limit.

        Args:
            key: Rate limit key (e.g., "schwab", "tiingo", "user_123")

        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        if not settings.RATE_LIMIT_ENABLED:
            return True

        current_time = time.time()
        tokens, last_update = self.buckets[key]

        # Refill tokens based on elapsed time
        elapsed = current_time - last_update
        refill_rate = self.max_requests / self.window_seconds
        tokens = min(self.max_requests, tokens + (elapsed * refill_rate))

        # Check if we have tokens available
        if tokens >= 1:
            self.buckets[key] = (tokens - 1, current_time)
            return True
        else:
            self.buckets[key] = (tokens, current_time)
            return False

    def get_wait_time(self, key: str) -> float:
        """
        Get wait time in seconds until next request is allowed.

        Args:
            key: Rate limit key

        Returns:
            Wait time in seconds (0 if immediately allowed)
        """
        if not settings.RATE_LIMIT_ENABLED:
            return 0.0

        tokens, last_update = self.buckets[key]
        if tokens >= 1:
            return 0.0

        # Calculate time needed to refill 1 token
        refill_rate = self.max_requests / self.window_seconds
        time_per_token = 1.0 / refill_rate
        tokens_needed = 1.0 - tokens

        return tokens_needed * time_per_token

    def reset(self, key: str) -> None:
        """
        Reset rate limit for a specific key.

        Args:
            key: Rate limit key to reset
        """
        self.buckets[key] = (self.max_requests, time.time())


# Global rate limiter instance
rate_limiter = RateLimiter()
