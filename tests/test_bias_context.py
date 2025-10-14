"""
Tests for Phase 3.5 Bias Context Enhancement.
"""

import pytest

from app.core.strategy_recommender import (
    StrategyFamily,
    get_bias_context_reasoning,
)


class TestBiasContextReasoning:
    """Test bias context reasoning generation."""

    def test_ssl_sweep_bullish(self):
        """SSL sweep with bullish bias should explain the ICT setup."""
        bias_reason = "ssl_sweep"
        bias = "bullish"
        strategy_family = StrategyFamily.VERTICAL_CREDIT

        context = get_bias_context_reasoning(bias_reason, bias, strategy_family)

        assert "SSL swept" in context
        assert "sell-side liquidity taken" in context
        assert "Bullish reversal expected" in context
        assert "BSL" in context  # Targeting opposite liquidity

    def test_ssl_sweep_bearish_mismatch(self):
        """SSL sweep with bearish bias should note the mismatch."""
        bias_reason = "ssl_sweep"
        bias = "bearish"
        strategy_family = StrategyFamily.VERTICAL_CREDIT

        context = get_bias_context_reasoning(bias_reason, bias, strategy_family)

        assert "SSL sweep typically indicates bullish bias" in context
        assert "bearish bias selected" in context

    def test_bsl_sweep_bearish(self):
        """BSL sweep with bearish bias should explain the ICT setup."""
        bias_reason = "bsl_sweep"
        bias = "bearish"
        strategy_family = StrategyFamily.VERTICAL_CREDIT

        context = get_bias_context_reasoning(bias_reason, bias, strategy_family)

        assert "BSL swept" in context
        assert "buy-side liquidity taken" in context
        assert "Bearish reversal expected" in context
        assert "SSL" in context  # Targeting opposite liquidity

    def test_bsl_sweep_bullish_mismatch(self):
        """BSL sweep with bullish bias should note the mismatch."""
        bias_reason = "bsl_sweep"
        bias = "bullish"
        strategy_family = StrategyFamily.VERTICAL_DEBIT

        context = get_bias_context_reasoning(bias_reason, bias, strategy_family)

        assert "BSL sweep typically indicates bearish bias" in context
        assert "bullish bias selected" in context

    def test_fvg_retest_bullish(self):
        """FVG retest should explain continuation setup."""
        bias_reason = "fvg_retest"
        bias = "bullish"
        strategy_family = StrategyFamily.VERTICAL_DEBIT

        context = get_bias_context_reasoning(bias_reason, bias, strategy_family)

        assert "FVG retest" in context
        assert "Fair Value Gap" in context
        assert "Bullish continuation expected" in context
        assert "imbalance zone" in context

    def test_fvg_retest_bearish(self):
        """FVG retest with bearish bias."""
        bias_reason = "fvg_retest"
        bias = "bearish"
        strategy_family = StrategyFamily.LONG_PUT

        context = get_bias_context_reasoning(bias_reason, bias, strategy_family)

        assert "FVG retest" in context
        assert "Bearish continuation expected" in context

    def test_structure_shift_bullish(self):
        """Structure shift should explain MSS confirmation."""
        bias_reason = "structure_shift"
        bias = "bullish"
        strategy_family = StrategyFamily.VERTICAL_DEBIT

        context = get_bias_context_reasoning(bias_reason, bias, strategy_family)

        assert "Market Structure Shift" in context
        assert "MSS" in context
        assert "Bullish trend change" in context
        assert "Higher highs/lows" in context
        assert "displacement validated" in context

    def test_structure_shift_bearish(self):
        """Structure shift with bearish bias."""
        bias_reason = "structure_shift"
        bias = "bearish"
        strategy_family = StrategyFamily.LONG_PUT

        context = get_bias_context_reasoning(bias_reason, bias, strategy_family)

        assert "Market Structure Shift" in context
        assert "Bearish trend change" in context

    def test_user_manual_returns_empty(self):
        """User manual bias should return empty context."""
        bias_reason = "user_manual"
        bias = "bullish"
        strategy_family = StrategyFamily.VERTICAL_CREDIT

        context = get_bias_context_reasoning(bias_reason, bias, strategy_family)

        assert context == ""

    def test_none_bias_reason_returns_empty(self):
        """None bias_reason should return empty context."""
        bias_reason = None
        bias = "bearish"
        strategy_family = StrategyFamily.LONG_PUT

        context = get_bias_context_reasoning(bias_reason, bias, strategy_family)

        assert context == ""

    def test_unknown_bias_reason_returns_empty(self):
        """Unknown bias_reason should return empty context."""
        bias_reason = "unknown_setup"
        bias = "neutral"
        strategy_family = StrategyFamily.VERTICAL_CREDIT

        context = get_bias_context_reasoning(bias_reason, bias, strategy_family)

        assert context == ""
