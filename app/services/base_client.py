"""
Base API Client
Shared functionality for all market data provider clients.
Includes retry logic with exponential backoff and error handling.
"""

from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.services.exceptions import (
    NetworkError,
    ProviderError,
    RateLimitError,
    TimeoutError,
)
from app.utils.logger import app_logger


class BaseAPIClient:
    """
    Base class for all API clients.
    Provides HTTP methods with retry logic and standardized error handling.
    """

    def __init__(
        self,
        base_url: str,
        provider_name: str,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.provider_name = provider_name
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((NetworkError, ProviderError)),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            headers: Request headers
            params: Query parameters
            json: JSON body
            data: Form data

        Returns:
            Response data as dict

        Raises:
            Various APIClientError subclasses
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            app_logger.debug(
                f"{self.provider_name} API request: {method} {url}",
                extra={"params": params},
            )

            response = await self.client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json,
                data=data,
            )

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitError(
                    "Rate limit exceeded",
                    provider=self.provider_name,
                    retry_after=retry_after,
                    status_code=429,
                )

            # Handle server errors (retry)
            if 500 <= response.status_code < 600:
                raise ProviderError(
                    f"Provider error: {response.status_code}",
                    provider=self.provider_name,
                    status_code=response.status_code,
                )

            # Raise for other HTTP errors
            response.raise_for_status()

            # Parse JSON response
            return response.json()

        except httpx.TimeoutException as e:
            app_logger.error(f"{self.provider_name} request timeout: {url}")
            raise TimeoutError(
                f"Request timeout after {self.timeout}s",
                provider=self.provider_name,
            ) from e

        except httpx.NetworkError as e:
            app_logger.error(f"{self.provider_name} network error: {url}")
            raise NetworkError(f"Network error: {str(e)}", provider=self.provider_name) from e

        except httpx.HTTPStatusError as e:
            # Already handled 429 and 5xx above
            # This catches 4xx errors
            from app.services.exceptions import (
                AuthenticationError,
                InvalidRequestError,
            )

            if e.response.status_code == 401:
                raise AuthenticationError(
                    "Authentication failed",
                    provider=self.provider_name,
                    status_code=401,
                ) from e
            elif e.response.status_code == 403:
                raise AuthenticationError(
                    "Access forbidden",
                    provider=self.provider_name,
                    status_code=403,
                ) from e
            else:
                raise InvalidRequestError(
                    f"Invalid request: {e.response.status_code}",
                    provider=self.provider_name,
                    status_code=e.response.status_code,
                ) from e

    async def get(
        self,
        endpoint: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """GET request"""
        return await self._request("GET", endpoint, headers=headers, params=params)

    async def post(
        self,
        endpoint: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """POST request"""
        return await self._request(
            "POST", endpoint, headers=headers, params=params, json=json, data=data
        )

    async def health_check(self) -> bool:
        """
        Check if provider API is reachable.
        Override in subclasses for provider-specific health checks.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Default: just check base URL is reachable
            await self.client.get(self.base_url, timeout=5.0)
            return True
        except Exception as e:
            app_logger.warning(f"{self.provider_name} health check failed: {str(e)}")
            return False
