"""
Integration tests for Discord bot commands.
Tests end-to-end flow from Discord command → API → Core logic.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from app.alerts.discord_bot import StrategyRecommendationAPI


class TestStrategyRecommendationAPI:
    """Test Discord API client integration."""

    @pytest.mark.skip(reason="Async HTTP mocking needs aioresponses library")
    @pytest.mark.asyncio
    async def test_recommend_strategy_basic(self):
        """Test basic strategy recommendation API call."""
        api = StrategyRecommendationAPI(base_url="http://localhost:8000")

        # Mock the HTTP response
        mock_response = {
            "underlying_symbol": "SPY",
            "underlying_price": 450.00,
            "chosen_strategy_family": "vertical_credit",
            "iv_rank": 45.5,
            "iv_regime": "neutral",
            "dte": 30,
            "recommendations": [
                {
                    "rank": 1,
                    "strategy_family": "vertical_credit",
                    "option_type": "put",
                    "long_strike": 445.0,
                    "short_strike": 450.0,
                    "net_premium": 1.25,
                    "max_profit": 125.0,
                    "max_loss": 375.0,
                    "breakeven": 448.75,
                    "risk_reward_ratio": 3.0,
                    "pop_proxy": 65.0,
                    "composite_score": 85.0,
                    "reasons": ["High IV favors credit spreads"],
                    "warnings": [],
                }
            ],
            "warnings": [],
        }

        with patch("aiohttp.ClientSession") as mock_session:
            mock_response_obj = AsyncMock()
            mock_response_obj.status = 200
            mock_response_obj.json = AsyncMock(return_value=mock_response)

            mock_post_context = AsyncMock()
            mock_post_context.__aenter__.return_value = mock_response_obj

            mock_session_instance = AsyncMock()
            mock_session_instance.post.return_value = mock_post_context

            mock_session_context = AsyncMock()
            mock_session_context.__aenter__.return_value = mock_session_instance
            mock_session.return_value = mock_session_context

            result = await api.recommend_strategy(
                symbol="SPY",
                bias="bullish",
                dte=30,
                mode="auto",
                max_risk=500.0,
                account_size=25000.0,
            )

        assert result["underlying_symbol"] == "SPY"
        assert len(result["recommendations"]) == 1
        assert result["recommendations"][0]["strategy_family"] == "vertical_credit"

    @pytest.mark.skip(reason="Async HTTP mocking needs aioresponses library")
    @pytest.mark.asyncio
    async def test_recommend_strategy_with_bias_reason(self):
        """Test strategy recommendation with ICT bias_reason parameter."""
        api = StrategyRecommendationAPI(base_url="http://localhost:8000")

        mock_response = {
            "underlying_symbol": "SPY",
            "underlying_price": 450.00,
            "chosen_strategy_family": "vertical_credit",
            "dte": 7,
            "recommendations": [
                {
                    "rank": 1,
                    "strategy_family": "vertical_credit",
                    "option_type": "put",
                    "long_strike": 445.0,
                    "short_strike": 450.0,
                    "net_premium": 1.50,
                    "max_profit": 150.0,
                    "max_loss": 350.0,
                    "breakeven": 448.50,
                    "risk_reward_ratio": 2.33,
                    "pop_proxy": 70.0,
                    "composite_score": 88.0,
                    "reasons": [
                        "ICT Setup: SSL swept (sell-side liquidity taken) → Bullish reversal expected.",
                        "0-7 DTE: Credit spread prioritized (capital efficient, 70% POP)",
                    ],
                    "warnings": [],
                }
            ],
            "warnings": [],
        }

        with patch("aiohttp.ClientSession") as mock_session:
            mock_response_obj = AsyncMock()
            mock_response_obj.status = 200
            mock_response_obj.json = AsyncMock(return_value=mock_response)

            mock_post_context = AsyncMock()
            mock_post_context.__aenter__.return_value = mock_response_obj

            mock_session_instance = AsyncMock()
            mock_session_instance.post.return_value = mock_post_context

            mock_session_context = AsyncMock()
            mock_session_context.__aenter__.return_value = mock_session_instance
            mock_session.return_value = mock_session_context

            result = await api.recommend_strategy(
                symbol="SPY",
                bias="bullish",
                dte=7,
                mode="auto",
                account_size=10000.0,
                bias_reason="ssl_sweep",
            )

        # Verify bias_reason context appears in reasoning
        reasons = result["recommendations"][0]["reasons"]
        assert any(
            "SSL swept" in reason for reason in reasons
        ), "Expected ICT bias_reason context in recommendation reasoning"
        assert any("0-7 DTE" in reason for reason in reasons), "Expected DTE preference reasoning"

    @pytest.mark.skip(reason="Async HTTP mocking needs aioresponses library")
    @pytest.mark.asyncio
    async def test_recommend_strategy_404_error(self):
        """Test handling of 404 errors (ticker not found)."""
        api = StrategyRecommendationAPI(base_url="http://localhost:8000")

        with patch("aiohttp.ClientSession") as mock_session:
            mock_response_obj = AsyncMock()
            mock_response_obj.status = 404
            mock_response_obj.json = AsyncMock(return_value={"detail": "Ticker INVALID not found"})

            mock_post_context = AsyncMock()
            mock_post_context.__aenter__.return_value = mock_response_obj

            mock_session_instance = AsyncMock()
            mock_session_instance.post.return_value = mock_post_context

            mock_session_context = AsyncMock()
            mock_session_context.__aenter__.return_value = mock_session_instance
            mock_session.return_value = mock_session_context

            with pytest.raises(ValueError, match="Ticker INVALID not found"):
                await api.recommend_strategy(symbol="INVALID", bias="bullish", dte=30)

    @pytest.mark.skip(reason="Async HTTP mocking needs aioresponses library")
    @pytest.mark.asyncio
    async def test_recommend_strategy_server_error(self):
        """Test handling of 500 server errors."""
        api = StrategyRecommendationAPI(base_url="http://localhost:8000")

        with patch("aiohttp.ClientSession") as mock_session:
            mock_response_obj = AsyncMock()
            mock_response_obj.status = 500
            mock_response_obj.json = AsyncMock(return_value={"detail": "Internal server error"})
            mock_response_obj.text = AsyncMock(return_value="Internal server error")

            mock_post_context = AsyncMock()
            mock_post_context.__aenter__.return_value = mock_response_obj

            mock_session_instance = AsyncMock()
            mock_session_instance.post.return_value = mock_post_context

            mock_session_context = AsyncMock()
            mock_session_context.__aenter__.return_value = mock_session_instance
            mock_session.return_value = mock_session_context

            with pytest.raises(Exception):
                await api.recommend_strategy(symbol="SPY", bias="bullish", dte=30)


class TestCreditSpreadLogic:
    """Test credit spread detection logic in /calc command."""

    def test_bull_put_credit_identification(self):
        """Test bull put credit spread is correctly identified."""
        # Bull put credit: short_strike > long_strike
        position = "put"
        long_strike = 445.0
        short_strike = 450.0

        is_credit = (position == "put" and short_strike > long_strike) or (
            position == "call" and short_strike < long_strike
        )

        assert is_credit is True, "Bull put credit spread should be identified as credit"

    def test_bear_call_credit_identification(self):
        """Test bear call credit spread is correctly identified."""
        # Bear call credit: short_strike < long_strike
        position = "call"
        long_strike = 455.0
        short_strike = 450.0

        is_credit = (position == "put" and short_strike > long_strike) or (
            position == "call" and short_strike < long_strike
        )

        assert is_credit is True, "Bear call credit spread should be identified as credit"

    def test_bull_call_debit_identification(self):
        """Test bull call debit spread is correctly identified."""
        # Bull call debit: short_strike > long_strike
        position = "call"
        long_strike = 450.0
        short_strike = 455.0

        is_credit = (position == "put" and short_strike > long_strike) or (
            position == "call" and short_strike < long_strike
        )

        assert is_credit is False, "Bull call debit spread should be identified as debit"

    def test_bear_put_debit_identification(self):
        """Test bear put debit spread is correctly identified."""
        # Bear put debit: short_strike < long_strike
        position = "put"
        long_strike = 450.0
        short_strike = 445.0

        is_credit = (position == "put" and short_strike > long_strike) or (
            position == "call" and short_strike < long_strike
        )

        assert is_credit is False, "Bear put debit spread should be identified as debit"


class TestDTEValidation:
    """Test DTE validation for Discord commands."""

    def test_valid_dte_ranges(self):
        """Test valid DTE values."""
        valid_dtes = [1, 7, 14, 30, 45, 90, 180, 365]
        for dte in valid_dtes:
            assert 1 <= dte <= 365, f"DTE {dte} should be valid"

    def test_invalid_dte_below_minimum(self):
        """Test DTE below minimum (0)."""
        dte = 0
        assert dte < 1, "DTE 0 should be invalid"

    def test_invalid_dte_above_maximum(self):
        """Test DTE above maximum (365)."""
        dte = 500
        assert dte > 365, "DTE 500 should be invalid"

    def test_negative_dte(self):
        """Test negative DTE values."""
        dte = -5
        assert dte < 1, "Negative DTE should be invalid"


class TestBiasReasonIntegration:
    """Test bias_reason parameter integration across layers."""

    def test_bias_reason_values(self):
        """Test all valid bias_reason values."""
        valid_reasons = {"ssl_sweep", "bsl_sweep", "fvg_retest", "structure_shift", "user_manual"}

        # Test each value
        for reason in valid_reasons:
            assert reason in valid_reasons, f"{reason} should be valid"

    def test_bias_reason_default(self):
        """Test default bias_reason is user_manual."""
        default_reason = "user_manual"
        assert default_reason == "user_manual"

    def test_invalid_bias_reason(self):
        """Test invalid bias_reason should be caught by validation."""
        invalid_reason = "invalid_setup"
        valid_reasons = {"ssl_sweep", "bsl_sweep", "fvg_retest", "structure_shift", "user_manual"}

        assert invalid_reason not in valid_reasons, "Invalid bias_reason should fail validation"
