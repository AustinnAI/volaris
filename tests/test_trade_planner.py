"""
Unit tests for trade planner calculation engine.
"""

from decimal import Decimal

from app.core.trade_planner import (
    TradeBias,
    calculate_long_option,
    calculate_position_size,
    calculate_vertical_spread,
)


class TestVerticalSpread:
    """Test vertical spread calculations."""

    def test_bull_call_spread_debit(self):
        """Test bull call spread (debit) calculation."""
        result = calculate_vertical_spread(
            underlying_symbol="SPY",
            underlying_price=Decimal("450.00"),
            long_strike=Decimal("445.00"),
            short_strike=Decimal("450.00"),
            long_premium=Decimal("7.50"),
            short_premium=Decimal("3.00"),
            option_type="call",
            bias=TradeBias.BULLISH,
            contracts=1,
            dte=30,
        )

        # Verify strategy type
        assert result.strategy_type == "vertical_debit"
        assert result.bias == "bullish"
        assert result.underlying_symbol == "SPY"

        # Verify risk metrics
        # Net debit = (7.50 - 3.00) * 1 * 100 = 450
        assert result.net_premium == Decimal("450.00")
        assert result.max_loss == Decimal("450.00")

        # Max profit = spread width - debit = (450 - 445) * 100 - 450 = 50
        assert result.max_profit == Decimal("50.00")

        # Risk/reward
        assert result.risk_reward_ratio == Decimal("50.00") / Decimal("450.00")

        # Breakeven = long_strike + net_debit_per_contract = 445 + 4.50 = 449.50
        assert len(result.breakeven_prices) == 1
        assert result.breakeven_prices[0] == Decimal("449.50")

        # Position sizing (no account size provided, uses requested contracts)
        assert result.recommended_contracts == 1
        assert result.position_size_dollars == Decimal("450.00")

        # Credit spreads only
        assert result.net_credit is None

    def test_bull_call_spread_with_position_sizing(self):
        """Test bull call spread with risk-based position sizing."""
        result = calculate_vertical_spread(
            underlying_symbol="SPY",
            underlying_price=Decimal("450.00"),
            long_strike=Decimal("445.00"),
            short_strike=Decimal("450.00"),
            long_premium=Decimal("7.50"),
            short_premium=Decimal("3.00"),
            option_type="call",
            bias=TradeBias.BULLISH,
            contracts=1,
            dte=30,
            account_size=Decimal("25000.00"),
            risk_percentage=Decimal("2.0"),
        )

        # Max loss per contract = 450
        # Account risk = 25000 * 0.02 = 500
        # Recommended contracts = 500 / 450 = 1.11 -> 1
        assert result.recommended_contracts == 1
        assert result.position_size_dollars == Decimal("450.00")

    def test_bull_put_spread_credit(self):
        """Test bull put spread (credit) calculation."""
        result = calculate_vertical_spread(
            underlying_symbol="SPY",
            underlying_price=Decimal("450.00"),
            long_strike=Decimal("440.00"),
            short_strike=Decimal("445.00"),
            long_premium=Decimal("2.00"),
            short_premium=Decimal("5.00"),
            option_type="put",
            bias=TradeBias.BULLISH,
            contracts=1,
            dte=30,
        )

        # Verify strategy type
        assert result.strategy_type == "vertical_credit"

        # Net credit = (2.00 - 5.00) * 1 * 100 = -300 (credit received)
        assert result.net_premium == Decimal("-300.00")
        assert result.net_credit == Decimal("300.00")

        # Max profit = credit received = 300
        assert result.max_profit == Decimal("300.00")

        # Max loss = spread width - credit = (445 - 440) * 100 - 300 = 200
        assert result.max_loss == Decimal("200.00")

        # position_size_dollars should be max_loss (risk), not credit
        assert result.position_size_dollars == Decimal("200.00")

        # Breakeven = short_strike - net_credit_per_contract = 445 - 3.00 = 442.00
        assert result.breakeven_prices[0] == Decimal("442.00")

    def test_vertical_spread_with_deltas(self):
        """Test vertical spread with delta-based probability."""
        result = calculate_vertical_spread(
            underlying_symbol="SPY",
            underlying_price=Decimal("450.00"),
            long_strike=Decimal("445.00"),
            short_strike=Decimal("450.00"),
            long_premium=Decimal("7.50"),
            short_premium=Decimal("3.00"),
            option_type="call",
            bias=TradeBias.BULLISH,
            contracts=1,
            dte=30,
            long_delta=Decimal("0.60"),
            short_delta=Decimal("0.40"),
        )

        # Net delta = (0.60 - 0.40) * 1 = 0.20
        assert result.total_delta == Decimal("0.20")

        # Win probability for debit spread = abs(net_delta) * 100 = 20%
        assert result.win_probability == Decimal("20.00")


class TestLongOption:
    """Test long option calculations."""

    def test_long_call(self):
        """Test long call calculation."""
        result = calculate_long_option(
            underlying_symbol="AAPL",
            underlying_price=Decimal("175.00"),
            strike=Decimal("180.00"),
            premium=Decimal("3.50"),
            option_type="call",
            bias=TradeBias.BULLISH,
            contracts=2,
            dte=45,
        )

        # Verify strategy type
        assert result.strategy_type == "long_call"
        assert result.bias == "bullish"

        # Net premium = 3.50 * 2 * 100 = 700
        assert result.net_premium == Decimal("700.00")

        # Max loss = premium paid
        assert result.max_loss == Decimal("700.00")

        # Max profit = None (unlimited for calls)
        assert result.max_profit is None
        assert result.risk_reward_ratio is None

        # Breakeven = strike + premium = 180 + 3.50 = 183.50
        assert result.breakeven_prices[0] == Decimal("183.50")

        # Position sizing
        assert result.recommended_contracts == 2
        assert result.position_size_dollars == Decimal("700.00")

        # No credit for long options
        assert result.net_credit is None

    def test_long_put(self):
        """Test long put calculation."""
        result = calculate_long_option(
            underlying_symbol="SPY",
            underlying_price=Decimal("450.00"),
            strike=Decimal("445.00"),
            premium=Decimal("5.00"),
            option_type="put",
            bias=TradeBias.BEARISH,
            contracts=1,
            dte=30,
        )

        # Verify strategy type
        assert result.strategy_type == "long_put"
        assert result.bias == "bearish"

        # Net premium = 5.00 * 1 * 100 = 500
        assert result.net_premium == Decimal("500.00")

        # Max loss = premium paid
        assert result.max_loss == Decimal("500.00")

        # Max profit = (strike - premium) * 100 * contracts = (445 - 5) * 100 * 1 = 44000
        assert result.max_profit == Decimal("44000.00")

        # Risk/reward = 44000 / 500 = 88
        assert result.risk_reward_ratio == Decimal("88.00")

        # Breakeven = strike - premium = 445 - 5.00 = 440.00
        assert result.breakeven_prices[0] == Decimal("440.00")

    def test_long_option_with_delta(self):
        """Test long option with delta-based probability."""
        result = calculate_long_option(
            underlying_symbol="AAPL",
            underlying_price=Decimal("175.00"),
            strike=Decimal("180.00"),
            premium=Decimal("3.50"),
            option_type="call",
            bias=TradeBias.BULLISH,
            contracts=1,
            dte=45,
            delta=Decimal("0.35"),
        )

        # Total delta = 0.35 * 1 = 0.35
        assert result.total_delta == Decimal("0.35")

        # Win probability = abs(delta) * 100 = 35%
        assert result.win_probability == Decimal("35.00")

    def test_long_put_with_position_sizing(self):
        """Test long put with risk-based position sizing."""
        result = calculate_long_option(
            underlying_symbol="SPY",
            underlying_price=Decimal("450.00"),
            strike=Decimal("445.00"),
            premium=Decimal("5.00"),
            option_type="put",
            bias=TradeBias.BEARISH,
            contracts=1,
            dte=30,
            account_size=Decimal("25000.00"),
            risk_percentage=Decimal("2.0"),
        )

        # Max loss per contract = 500
        # Account risk = 25000 * 0.02 = 500
        # Recommended contracts = 500 / 500 = 1
        assert result.recommended_contracts == 1
        assert result.position_size_dollars == Decimal("500.00")


class TestPositionSize:
    """Test position sizing calculations."""

    def test_position_size_basic(self):
        """Test basic position size calculation."""
        contracts = calculate_position_size(
            max_loss=Decimal("450.00"),
            account_size=Decimal("25000.00"),
            risk_percentage=Decimal("2.0"),
        )

        # Max risk = 25000 * 0.02 = 500
        # Contracts = 500 / 450 = 1.11 -> 1
        assert contracts == 1

    def test_position_size_multiple_contracts(self):
        """Test position size with multiple contracts."""
        contracts = calculate_position_size(
            max_loss=Decimal("200.00"),
            account_size=Decimal("50000.00"),
            risk_percentage=Decimal("2.0"),
        )

        # Max risk = 50000 * 0.02 = 1000
        # Contracts = 1000 / 200 = 5
        assert contracts == 5

    def test_position_size_high_risk_percentage(self):
        """Test position size with higher risk tolerance."""
        contracts = calculate_position_size(
            max_loss=Decimal("300.00"),
            account_size=Decimal("10000.00"),
            risk_percentage=Decimal("5.0"),
        )

        # Max risk = 10000 * 0.05 = 500
        # Contracts = 500 / 300 = 1.66 -> 1
        assert contracts == 1

    def test_position_size_exceeds_account(self):
        """Test position size when max loss exceeds account risk tolerance."""
        contracts = calculate_position_size(
            max_loss=Decimal("1000.00"),
            account_size=Decimal("5000.00"),
            risk_percentage=Decimal("2.0"),
        )

        # Max risk = 5000 * 0.02 = 100
        # Contracts = 100 / 1000 = 0.1 -> 0 (can't trade)
        assert contracts == 0


class TestEdgeCases:
    """Test edge cases and validation."""

    def test_wide_spread_debit(self):
        """Test wide spread with significant width."""
        result = calculate_vertical_spread(
            underlying_symbol="SPY",
            underlying_price=Decimal("450.00"),
            long_strike=Decimal("440.00"),
            short_strike=Decimal("460.00"),
            long_premium=Decimal("15.00"),
            short_premium=Decimal("5.00"),
            option_type="call",
            bias=TradeBias.BULLISH,
            contracts=1,
            dte=60,
        )

        # Net debit = (15.00 - 5.00) * 1 * 100 = 1000
        assert result.net_premium == Decimal("1000.00")
        assert result.max_loss == Decimal("1000.00")

        # Spread width = (460 - 440) * 100 = 2000
        # Max profit = 2000 - 1000 = 1000
        assert result.max_profit == Decimal("1000.00")

    def test_narrow_spread_credit(self):
        """Test narrow spread with tight strikes."""
        result = calculate_vertical_spread(
            underlying_symbol="SPY",
            underlying_price=Decimal("450.00"),
            long_strike=Decimal("449.00"),
            short_strike=Decimal("450.00"),
            long_premium=Decimal("1.00"),
            short_premium=Decimal("1.50"),
            option_type="call",
            bias=TradeBias.BEARISH,
            contracts=1,
            dte=7,
        )

        # Net credit = (1.00 - 1.50) * 1 * 100 = -50
        assert result.net_premium == Decimal("-50.00")
        assert result.net_credit == Decimal("50.00")

        # Max profit = credit = 50
        assert result.max_profit == Decimal("50.00")

        # Spread width = (450 - 449) * 100 = 100
        # Max loss = 100 - 50 = 50
        assert result.max_loss == Decimal("50.00")

        # position_size_dollars = max_loss (risk)
        assert result.position_size_dollars == Decimal("50.00")

    def test_multiple_contracts(self):
        """Test calculations scale correctly with multiple contracts."""
        result = calculate_vertical_spread(
            underlying_symbol="SPY",
            underlying_price=Decimal("450.00"),
            long_strike=Decimal("445.00"),
            short_strike=Decimal("450.00"),
            long_premium=Decimal("7.50"),
            short_premium=Decimal("3.00"),
            option_type="call",
            bias=TradeBias.BULLISH,
            contracts=5,
            dte=30,
        )

        # Net debit = (7.50 - 3.00) * 5 * 100 = 2250
        assert result.net_premium == Decimal("2250.00")
        assert result.max_loss == Decimal("2250.00")

        # Max profit = (5 * 100 * 5) - 2250 = 250
        assert result.max_profit == Decimal("250.00")

        assert result.recommended_contracts == 5
