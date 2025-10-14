"""Pytest fixtures for Discord bot testing."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest


@pytest.fixture
def mock_interaction():
    """Create a mock Discord interaction."""
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = 12345
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.guild = MagicMock()
    interaction.guild.id = 67890
    return interaction


@pytest.fixture
def mock_bot():
    """Create a mock Discord bot."""
    bot = MagicMock()
    bot.tree = MagicMock()
    bot.user = MagicMock()
    bot.user.name = "VolarisBot"

    # Mock rate limiter
    bot.check_rate_limit = MagicMock(return_value=True)
    bot.rate_limit_tracker = {}

    # Mock API client
    bot.api_client = AsyncMock()
    bot.api_client.base_url = "http://localhost:8000"

    return bot


@pytest.fixture
def mock_api_response():
    """Create a mock API response for /plan command."""
    return {
        "underlying_symbol": "SPY",
        "underlying_price": 580.50,
        "iv_regime": "neutral",
        "chosen_strategy_family": "bull_put_credit_spread",
        "recommendations": [
            {
                "rank": 1,
                "strategy_family": "bull_put_credit_spread",
                "position": "short put spread",
                "long_strike": 575.0,
                "short_strike": 580.0,
                "width_points": 5.0,
                "width_dollars": 500.0,
                "net_premium": 125.0,
                "is_credit": True,
                "max_profit": 125.0,
                "max_loss": 375.0,
                "risk_reward_ratio": 0.33,
                "pop_proxy": 70.0,
                "breakeven": 578.75,
                "composite_score": 85.5,
                "dte": 7,
                "recommended_contracts": 2,
                "position_size_dollars": 750.0,
                "reasons": [
                    "High probability credit spread",
                    "IV regime supports selling premium",
                    "Optimal risk/reward for account size",
                ],
                "warnings": [],
            }
        ],
        "warnings": [],
    }


@pytest.fixture
def sample_symbols():
    """Sample ticker symbols for testing."""
    return ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]


@pytest.fixture
async def mock_aiohttp_session():
    """Mock aiohttp session for API calls."""
    session = AsyncMock()
    response = AsyncMock()
    response.status = 200
    response.json = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    session.post = AsyncMock(return_value=response)
    session.get = AsyncMock(return_value=response)
    return session
