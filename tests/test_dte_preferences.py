"""
Tests for Phase 3.4 DTE-based strategy preferences.
"""
import pytest
from decimal import Decimal

from app.core.strategy_recommender import (
    StrategyFamily,
    apply_dte_preferences,
)


class TestDTEPreferences:
    """Test DTE-based strategy selection logic."""

    def test_0_7_dte_small_account_converts_long_to_credit(self):
        """0-7 DTE + small account should convert long options to credit spreads."""
        strategy_family = StrategyFamily.LONG_CALL
        option_type = "call"
        dte = 5
        account_size = Decimal("8000")  # Small account
        bias = "bullish"
        reasoning = "Low IV favors buying premium"

        new_family, new_type, new_reasoning = apply_dte_preferences(
            strategy_family, option_type, dte, account_size, bias, reasoning
        )

        assert new_family == StrategyFamily.VERTICAL_CREDIT
        assert new_type == "put"  # Bull put spread
        assert "0-7 DTE" in new_reasoning
        assert "small account" in new_reasoning
        assert "Credit spread prioritized" in new_reasoning

    def test_0_7_dte_medium_account_converts_long_to_credit(self):
        """0-7 DTE + medium account should convert long options to credit spreads."""
        strategy_family = StrategyFamily.LONG_PUT
        option_type = "put"
        dte = 3
        account_size = Decimal("15000")  # Medium account
        bias = "bearish"
        reasoning = "Expecting downturn"

        new_family, new_type, new_reasoning = apply_dte_preferences(
            strategy_family, option_type, dte, account_size, bias, reasoning
        )

        assert new_family == StrategyFamily.VERTICAL_CREDIT
        assert new_type == "call"  # Bear call spread
        assert "0-7 DTE" in new_reasoning
        assert "medium account" in new_reasoning
        assert "Bear call spread recommended" in new_reasoning

    def test_0_7_dte_large_account_allows_long_options(self):
        """0-7 DTE + large account should allow long options with context."""
        strategy_family = StrategyFamily.LONG_CALL
        option_type = "call"
        dte = 7
        account_size = Decimal("50000")  # Large account
        bias = "bullish"
        reasoning = "SSL sweep detected"

        new_family, new_type, new_reasoning = apply_dte_preferences(
            strategy_family, option_type, dte, account_size, bias, reasoning
        )

        assert new_family == StrategyFamily.LONG_CALL  # Unchanged
        assert new_type == "call"
        assert "0-7 DTE" in new_reasoning
        assert "fast directional execution" in new_reasoning
        assert "adequate buying power" in new_reasoning

    def test_0_7_dte_credit_spread_enhanced_reasoning(self):
        """0-7 DTE with credit spread should enhance reasoning."""
        strategy_family = StrategyFamily.VERTICAL_CREDIT
        option_type = "put"
        dte = 5
        account_size = Decimal("20000")
        bias = "bullish"
        reasoning = "High IV regime"

        new_family, new_type, new_reasoning = apply_dte_preferences(
            strategy_family, option_type, dte, account_size, bias, reasoning
        )

        assert new_family == StrategyFamily.VERTICAL_CREDIT  # Unchanged
        assert new_type == "put"
        assert "0-7 DTE" in new_reasoning
        assert "Credit spread optimal" in new_reasoning
        assert "capital efficient" in new_reasoning

    def test_14_45_dte_small_account_converts_long_to_debit(self):
        """14-45 DTE + small account should convert long options to debit spreads."""
        strategy_family = StrategyFamily.LONG_CALL
        option_type = "call"
        dte = 30
        account_size = Decimal("9000")  # Small account
        bias = "bullish"
        reasoning = "Expecting bullish move"

        new_family, new_type, new_reasoning = apply_dte_preferences(
            strategy_family, option_type, dte, account_size, bias, reasoning
        )

        assert new_family == StrategyFamily.VERTICAL_DEBIT
        assert new_type == "call"  # Bull call debit spread
        assert "14-45 DTE" in new_reasoning
        assert "small account" in new_reasoning
        assert "Debit spread prioritized" in new_reasoning
        assert "defined risk" in new_reasoning

    def test_14_45_dte_large_account_allows_long_options(self):
        """14-45 DTE + large account should allow long options."""
        strategy_family = StrategyFamily.LONG_PUT
        option_type = "put"
        dte = 30
        account_size = Decimal("40000")  # Large account
        bias = "bearish"
        reasoning = "Bearish MSS detected"

        new_family, new_type, new_reasoning = apply_dte_preferences(
            strategy_family, option_type, dte, account_size, bias, reasoning
        )

        assert new_family == StrategyFamily.LONG_PUT  # Unchanged
        assert new_type == "put"
        assert "14-45 DTE" in new_reasoning
        assert "large account" in new_reasoning
        assert "expect significant move" in new_reasoning

    def test_14_45_dte_credit_spread_context(self):
        """14-45 DTE with credit spread should add appropriate context."""
        strategy_family = StrategyFamily.VERTICAL_CREDIT
        option_type = "call"
        dte = 45
        account_size = Decimal("20000")
        bias = "bearish"
        reasoning = "High IV"

        new_family, new_type, new_reasoning = apply_dte_preferences(
            strategy_family, option_type, dte, account_size, bias, reasoning
        )

        assert new_family == StrategyFamily.VERTICAL_CREDIT
        assert "14-45 DTE" in new_reasoning
        assert "less IV crush impact" in new_reasoning

    def test_no_account_size_defaults_to_large(self):
        """No account size should default to large account behavior."""
        strategy_family = StrategyFamily.LONG_CALL
        option_type = "call"
        dte = 5
        account_size = None  # No account size provided
        bias = "bullish"
        reasoning = "Test"

        new_family, new_type, new_reasoning = apply_dte_preferences(
            strategy_family, option_type, dte, account_size, bias, reasoning
        )

        # Should allow long options (large account behavior)
        assert new_family == StrategyFamily.LONG_CALL
        assert "adequate buying power" in new_reasoning

    def test_greater_than_45_dte_adds_context(self):
        """DTE > 45 should add longer-dated context."""
        strategy_family = StrategyFamily.VERTICAL_DEBIT
        option_type = "call"
        dte = 60
        account_size = Decimal("25000")
        bias = "bullish"
        reasoning = "Long-term bullish"

        new_family, new_type, new_reasoning = apply_dte_preferences(
            strategy_family, option_type, dte, account_size, bias, reasoning
        )

        assert new_family == StrategyFamily.VERTICAL_DEBIT  # Unchanged
        assert "60 DTE" in new_reasoning
        assert "Longer-dated position" in new_reasoning

    def test_8_13_dte_minimal_adjustment(self):
        """DTE 8-13 (between ranges) should have minimal adjustment."""
        strategy_family = StrategyFamily.VERTICAL_CREDIT
        option_type = "put"
        dte = 10
        account_size = Decimal("15000")
        bias = "bullish"
        reasoning = "Test"

        new_family, new_type, new_reasoning = apply_dte_preferences(
            strategy_family, option_type, dte, account_size, bias, reasoning
        )

        assert new_family == StrategyFamily.VERTICAL_CREDIT
        assert "10 DTE" in new_reasoning
