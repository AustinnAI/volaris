"""
LLM Client Service.

Provider-agnostic interface for calling LLM APIs with retries, timeouts,
and circuit breaker logic.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.config import settings
from app.utils.logger import app_logger


class LLMError(Exception):
    """Base exception for LLM client errors."""

    pass


class LLMTimeoutError(LLMError):
    """LLM request timed out."""

    pass


class LLMRateLimitError(LLMError):
    """LLM provider rate limit exceeded."""

    pass


class LLMInvalidResponseError(LLMError):
    """LLM returned invalid or unparseable response."""

    pass


class BaseLLMClient(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, api_key: str, timeout: int = 12):
        """
        Initialize LLM client.

        Args:
            api_key: Provider API key.
            timeout: Request timeout in seconds.
        """
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = 3
        self.retry_delays = [1, 2, 4]  # Exponential backoff

    @abstractmethod
    async def _call_api(
        self, prompt: str, model: str, max_tokens: int, temperature: float
    ) -> dict[str, Any]:
        """
        Call provider-specific API.

        Args:
            prompt: User prompt.
            model: Model identifier.
            max_tokens: Max tokens in response.
            temperature: Sampling temperature.

        Returns:
            Parsed JSON response from LLM.

        Raises:
            LLMError: On API failure.
        """
        pass

    async def summarize(
        self, prompt: str, model: str, max_tokens: int = 800, temperature: float = 0.2
    ) -> dict[str, Any]:
        """
        Generate summary with retry logic.

        Args:
            prompt: Grounded prompt with article context.
            model: Model name.
            max_tokens: Max response tokens.
            temperature: Sampling temperature.

        Returns:
            Parsed JSON summary (validated against schema later).

        Raises:
            LLMError: If all retries fail or timeout occurs.
        """
        for attempt in range(self.max_retries):
            try:
                app_logger.info(
                    f"LLM API call attempt {attempt + 1}/{self.max_retries}",
                    extra={
                        "provider": self.__class__.__name__,
                        "model": model,
                        "max_tokens": max_tokens,
                    },
                )

                result = await self._call_api(prompt, model, max_tokens, temperature)

                app_logger.info(
                    "LLM API call succeeded",
                    extra={"provider": self.__class__.__name__, "model": model},
                )

                return result

            except httpx.TimeoutException as e:
                app_logger.warning(
                    f"LLM timeout on attempt {attempt + 1}",
                    extra={"provider": self.__class__.__name__, "error": str(e)},
                )
                if attempt == self.max_retries - 1:
                    raise LLMTimeoutError(
                        f"LLM request timed out after {self.max_retries} attempts"
                    )
                await asyncio.sleep(self.retry_delays[attempt])

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    app_logger.warning(
                        f"LLM rate limit on attempt {attempt + 1}",
                        extra={"provider": self.__class__.__name__},
                    )
                    if attempt == self.max_retries - 1:
                        raise LLMRateLimitError("LLM provider rate limit exceeded")
                    await asyncio.sleep(self.retry_delays[attempt])
                elif e.response.status_code >= 500:
                    app_logger.error(
                        f"LLM server error on attempt {attempt + 1}",
                        extra={
                            "provider": self.__class__.__name__,
                            "status": e.response.status_code,
                        },
                    )
                    if attempt == self.max_retries - 1:
                        raise LLMError(f"LLM server error: {e.response.status_code}")
                    await asyncio.sleep(self.retry_delays[attempt])
                else:
                    # Client error (4xx) - don't retry
                    app_logger.error(
                        "LLM client error",
                        extra={
                            "provider": self.__class__.__name__,
                            "status": e.response.status_code,
                            "error": str(e),
                        },
                    )
                    raise LLMError(f"LLM client error: {e.response.status_code}")

            except Exception as e:
                app_logger.error(
                    "Unexpected LLM error",
                    extra={"provider": self.__class__.__name__, "error": str(e)},
                    exc_info=True,
                )
                if attempt == self.max_retries - 1:
                    raise LLMError(f"Unexpected LLM error: {str(e)}")
                await asyncio.sleep(self.retry_delays[attempt])

        raise LLMError("Max retries exceeded")


class OpenAIClient(BaseLLMClient):
    """OpenAI API client."""

    def __init__(self, api_key: str, timeout: int = 12):
        super().__init__(api_key, timeout)
        self.base_url = "https://api.openai.com/v1"

    async def _call_api(
        self, prompt: str, model: str, max_tokens: int, temperature: float
    ) -> dict[str, Any]:
        """
        Call OpenAI Chat Completions API with JSON mode.

        Args:
            prompt: System + user prompt.
            model: OpenAI model (e.g., gpt-4o-mini).
            max_tokens: Max completion tokens.
            temperature: Sampling temperature.

        Returns:
            Parsed JSON response.

        Raises:
            LLMError: On API or parsing failure.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a financial analyst providing concise market intelligence summaries. Always respond with valid JSON matching the specified schema.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},  # Force JSON mode
                },
            )

            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                app_logger.error(
                    "Failed to parse OpenAI JSON response",
                    extra={"content": content, "error": str(e)},
                )
                raise LLMInvalidResponseError(f"Invalid JSON from OpenAI: {str(e)}")


def get_llm_client() -> BaseLLMClient | None:
    """
    Factory function to get configured LLM client.

    Returns:
        LLM client instance, or None if LLM disabled or API key missing.
    """
    if not settings.LLM_ENABLED:
        app_logger.debug("LLM disabled via LLM_ENABLED=false")
        return None

    if not settings.LLM_API_KEY:
        app_logger.warning("LLM enabled but LLM_API_KEY not set")
        return None

    provider = settings.LLM_PROVIDER.lower()

    if provider == "openai":
        return OpenAIClient(settings.LLM_API_KEY, settings.LLM_TIMEOUT_SECONDS)
    else:
        app_logger.error(f"Unsupported LLM provider: {provider}")
        return None
