"""
API Client Exceptions
Clear error taxonomy for all market data provider interactions.
"""


class APIClientError(Exception):
    """Base exception for all API client errors"""

    def __init__(self, message: str, provider: str, status_code: int | None = None):
        self.message = message
        self.provider = provider
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationError(APIClientError):
    """Authentication failed (invalid credentials, expired token, etc.)"""

    pass


class RateLimitError(APIClientError):
    """Rate limit exceeded"""

    def __init__(self, message: str, provider: str, retry_after: int | None = None, **kwargs):
        self.retry_after = retry_after
        super().__init__(message, provider, **kwargs)


class QuotaExceededError(APIClientError):
    """API quota/credits exhausted"""

    pass


class InvalidRequestError(APIClientError):
    """Invalid request parameters (4xx errors except 401, 403, 429)"""

    pass


class ProviderError(APIClientError):
    """Provider-side error (5xx errors)"""

    pass


class DataNotFoundError(APIClientError):
    """Requested data not found or unavailable"""

    pass


class NetworkError(APIClientError):
    """Network connectivity issues"""

    pass


class TimeoutError(APIClientError):
    """Request timeout"""

    pass


class ValidationError(APIClientError):
    """Response data validation failed"""

    pass
