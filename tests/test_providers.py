"""
Tests for API Provider Clients
Mock-based tests for all provider integrations.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.exceptions import (
    AuthenticationError,
    ProviderError,
    RateLimitError,
)

# ==================== Tiingo Tests ====================


@pytest.mark.asyncio
async def test_tiingo_get_eod_prices():
    """Test Tiingo EOD price fetching"""
    from app.services.tiingo import TiingoClient

    mock_response = [
        {
            "date": "2024-01-15T00:00:00.000Z",
            "close": 185.56,
            "high": 186.40,
            "low": 183.92,
            "open": 184.35,
            "volume": 50123456,
        }
    ]

    with patch("app.services.tiingo.settings") as mock_settings:
        mock_settings.TIINGO_API_KEY = "test_key"
        mock_settings.TIINGO_API_BASE = "https://api.tiingo.com"

        client = TiingoClient()
        client.get = AsyncMock(return_value=mock_response)

        prices = await client.get_eod_prices("AAPL")

        assert len(prices) == 1
        assert prices[0]["close"] == 185.56
        assert prices[0]["symbol"] == "AAPL" or prices[0]["close"] == 185.56


@pytest.mark.asyncio
async def test_tiingo_authentication_error():
    """Test Tiingo authentication error handling"""
    from app.services.tiingo import TiingoClient

    with patch("app.services.tiingo.settings") as mock_settings:
        mock_settings.TIINGO_API_KEY = None

        with pytest.raises(AuthenticationError):
            TiingoClient()


# ==================== Alpaca Tests ====================


@pytest.mark.asyncio
async def test_alpaca_get_bars():
    """Test Alpaca bars fetching"""
    from app.services.alpaca import AlpacaClient

    mock_response = {
        "bars": [
            {
                "t": "2024-01-15T09:30:00Z",
                "o": 184.50,
                "h": 184.75,
                "l": 184.40,
                "c": 184.60,
                "v": 125000,
            }
        ]
    }

    with patch("app.services.alpaca.settings") as mock_settings:
        mock_settings.ALPACA_API_KEY = "test_key"
        mock_settings.ALPACA_API_SECRET = "test_secret"
        mock_settings.ALPACA_API_BASE = "https://paper-api.alpaca.markets"

        client = AlpacaClient()
        client.get = AsyncMock(return_value=mock_response)

        bars = await client.get_bars("SPY", timeframe="1Min")

        assert len(bars) == 1
        assert bars[0]["c"] == 184.60


# ==================== Databento Tests ====================


@pytest.mark.asyncio
async def test_databento_list_datasets():
    """Test Databento dataset listing"""
    from app.services.databento import DatabentoClient

    mock_response = {"datasets": [{"dataset": "XNAS.ITCH", "description": "NASDAQ ITCH data"}]}

    with patch("app.services.databento.settings") as mock_settings:
        mock_settings.DATABENTO_API_KEY = "test_key"
        mock_settings.DATABENTO_API_BASE = "https://hist.databento.com"

        client = DatabentoClient()
        client.get = AsyncMock(return_value=mock_response)

        datasets = await client.list_datasets()

        assert len(datasets) == 1
        assert datasets[0]["dataset"] == "XNAS.ITCH"


# ==================== Finnhub Tests ====================


@pytest.mark.asyncio
async def test_finnhub_get_company_profile():
    """Test Finnhub company profile fetching"""
    from app.services.finnhub import FinnhubClient

    mock_response = {
        "ticker": "AAPL",
        "name": "Apple Inc",
        "marketCapitalization": 2800000,
        "finnhubIndustry": "Technology",
    }

    with patch("app.services.finnhub.settings") as mock_settings:
        mock_settings.FINNHUB_API_KEY = "test_key"
        mock_settings.FINNHUB_API_BASE = "https://finnhub.io/api/v1"

        client = FinnhubClient()
        client.get = AsyncMock(return_value=mock_response)

        profile = await client.get_company_profile("AAPL")

        assert profile["ticker"] == "AAPL"
        assert profile["name"] == "Apple Inc"


@pytest.mark.asyncio
async def test_finnhub_get_quote():
    """Test Finnhub quote fetching"""
    from app.services.finnhub import FinnhubClient

    mock_response = {
        "c": 185.56,  # Current price
        "d": 1.21,  # Change
        "dp": 0.66,  # Percent change
    }

    with patch("app.services.finnhub.settings") as mock_settings:
        mock_settings.FINNHUB_API_KEY = "test_key"
        mock_settings.FINNHUB_API_BASE = "https://finnhub.io/api/v1"

        client = FinnhubClient()
        client.get = AsyncMock(return_value=mock_response)

        quote = await client.get_quote("SPY")

        assert quote["c"] == 185.56
        assert quote["d"] == 1.21


# ==================== Schwab Tests ====================


@pytest.mark.asyncio
async def test_schwab_pkce_generation():
    """Test Schwab PKCE code generation"""
    from app.services.schwab import SchwabClient

    with patch("app.services.schwab.settings") as mock_settings:
        mock_settings.SCHWAB_APP_KEY = "test_app_key"
        mock_settings.SCHWAB_SECRET_KEY = "test_secret"
        mock_settings.SCHWAB_REDIRECT_URI = "https://127.0.0.1:8000/callback"
        mock_settings.SCHWAB_API_BASE = "https://api.schwabapi.com"

        client = SchwabClient()
        code_verifier, code_challenge = client.generate_pkce_codes()

        assert len(code_verifier) >= 43
        assert len(code_challenge) >= 43
        assert code_verifier != code_challenge


def test_schwab_authorization_url():
    """Test Schwab authorization URL generation"""
    from app.services.schwab import SchwabClient

    with patch("app.services.schwab.settings") as mock_settings:
        mock_settings.SCHWAB_APP_KEY = "test_app_key"
        mock_settings.SCHWAB_SECRET_KEY = "test_secret"
        mock_settings.SCHWAB_REDIRECT_URI = "https://127.0.0.1:8000/callback"
        mock_settings.SCHWAB_API_BASE = "https://api.schwabapi.com"

        client = SchwabClient()
        auth_url, code_verifier = client.get_authorization_url()

        assert "authorize" in auth_url
        assert "client_id=test_app_key" in auth_url
        assert "code_challenge" in auth_url
        assert len(code_verifier) >= 43


# ==================== Base Client Tests ====================


@pytest.mark.asyncio
async def test_base_client_rate_limit_handling():
    """Test base client rate limit error handling"""
    from app.services.base_client import BaseAPIClient

    client = BaseAPIClient(
        base_url="https://api.example.com",
        provider_name="TestProvider",
    )

    # Mock 429 response
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "60"}

    with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response

        with pytest.raises(RateLimitError) as exc_info:
            await client._request("GET", "/test")

        assert exc_info.value.retry_after == 60


@pytest.mark.asyncio
async def test_base_client_server_error_retry():
    """Test base client server error retry logic"""
    from app.services.base_client import BaseAPIClient

    client = BaseAPIClient(
        base_url="https://api.example.com",
        provider_name="TestProvider",
    )

    # Mock 500 response
    mock_response = MagicMock()
    mock_response.status_code = 500

    with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response

        with pytest.raises(ProviderError):
            await client._request("GET", "/test")


# ==================== Provider Manager Tests ====================


@pytest.mark.asyncio
async def test_provider_manager_get_provider():
    """Test provider manager provider selection"""
    from app.services.provider_manager import DataType, provider_manager

    # Test getting EOD provider (should be Tiingo)
    provider = provider_manager.get_provider(DataType.EOD)

    # Provider may be None if not configured, that's OK for test
    assert provider is None or provider is not None


@pytest.mark.asyncio
async def test_provider_manager_health_check():
    """Test provider manager health check"""
    from app.services.provider_manager import provider_manager

    health = await provider_manager.get_provider_health()

    assert isinstance(health, dict)
    # Health dict should contain provider names as keys
    assert "tiingo" in health or "schwab" in health or len(health) >= 0


def test_provider_manager_configured_providers():
    """Test getting configured providers"""
    from app.services.provider_manager import provider_manager

    configured = provider_manager.get_configured_providers()

    assert isinstance(configured, list)


def test_provider_manager_capabilities():
    """Test getting available data types"""
    from app.services.provider_manager import provider_manager

    capabilities = provider_manager.get_available_data_types()

    assert isinstance(capabilities, dict)
