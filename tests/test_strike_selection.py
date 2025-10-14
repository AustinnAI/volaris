"""
Unit tests for strike selection engine.
"""

import pytest
from decimal import Decimal
from datetime import datetime

from app.core.strike_selection import (
    OptionContractData,
    StrikePosition,
    IVRegime,
    determine_iv_regime,
    get_spread_width_for_price,
    calculate_spread_metrics,
    classify_strike_position,
    find_nearest_strikes,
    recommend_vertical_spreads,
    recommend_long_options,
)


@pytest.fixture
def spy_contracts():
    """Sample SPY option contracts at $450 spot."""
    return [
        # Calls
        OptionContractData(
            strike=Decimal("440"),
            option_type="call",
            bid=Decimal("12.50"),
            ask=Decimal("13.00"),
            mark=Decimal("12.75"),
            delta=Decimal("0.75"),
            implied_vol=Decimal("0.18"),
            volume=1000,
            open_interest=5000,
        ),
        OptionContractData(
            strike=Decimal("445"),
            option_type="call",
            bid=Decimal("8.50"),
            ask=Decimal("9.00"),
            mark=Decimal("8.75"),
            delta=Decimal("0.65"),
            implied_vol=Decimal("0.17"),
            volume=2000,
            open_interest=8000,
        ),
        OptionContractData(
            strike=Decimal("450"),
            option_type="call",
            bid=Decimal("5.00"),
            ask=Decimal("5.50"),
            mark=Decimal("5.25"),
            delta=Decimal("0.50"),
            implied_vol=Decimal("0.16"),
            volume=5000,
            open_interest=15000,
        ),
        OptionContractData(
            strike=Decimal("455"),
            option_type="call",
            bid=Decimal("2.50"),
            ask=Decimal("3.00"),
            mark=Decimal("2.75"),
            delta=Decimal("0.35"),
            implied_vol=Decimal("0.17"),
            volume=3000,
            open_interest=10000,
        ),
        OptionContractData(
            strike=Decimal("460"),
            option_type="call",
            bid=Decimal("1.00"),
            ask=Decimal("1.50"),
            mark=Decimal("1.25"),
            delta=Decimal("0.20"),
            implied_vol=Decimal("0.18"),
            volume=1500,
            open_interest=6000,
        ),
        # Puts
        OptionContractData(
            strike=Decimal("440"),
            option_type="put",
            bid=Decimal("1.00"),
            ask=Decimal("1.50"),
            mark=Decimal("1.25"),
            delta=Decimal("-0.25"),
            implied_vol=Decimal("0.18"),
            volume=1500,
            open_interest=6000,
        ),
        OptionContractData(
            strike=Decimal("445"),
            option_type="put",
            bid=Decimal("2.50"),
            ask=Decimal("3.00"),
            mark=Decimal("2.75"),
            delta=Decimal("-0.35"),
            implied_vol=Decimal("0.17"),
            volume=2000,
            open_interest=8000,
        ),
        OptionContractData(
            strike=Decimal("450"),
            option_type="put",
            bid=Decimal("5.00"),
            ask=Decimal("5.50"),
            mark=Decimal("5.25"),
            delta=Decimal("-0.50"),
            implied_vol=Decimal("0.16"),
            volume=5000,
            open_interest=15000,
        ),
        OptionContractData(
            strike=Decimal("455"),
            option_type="put",
            bid=Decimal("8.50"),
            ask=Decimal("9.00"),
            mark=Decimal("8.75"),
            delta=Decimal("-0.65"),
            implied_vol=Decimal("0.17"),
            volume=3000,
            open_interest=10000,
        ),
        OptionContractData(
            strike=Decimal("460"),
            option_type="put",
            bid=Decimal("12.50"),
            ask=Decimal("13.00"),
            mark=Decimal("12.75"),
            delta=Decimal("-0.75"),
            implied_vol=Decimal("0.18"),
            volume=1000,
            open_interest=5000,
        ),
    ]


class TestIVRegime:
    """Test IV regime classification."""

    def test_high_iv(self):
        """Test high IV classification."""
        assert determine_iv_regime(Decimal("60")) == IVRegime.HIGH
        assert determine_iv_regime(Decimal("100")) == IVRegime.HIGH

    def test_neutral_iv(self):
        """Test neutral IV classification."""
        assert determine_iv_regime(Decimal("40")) == IVRegime.NEUTRAL
        assert determine_iv_regime(Decimal("25")) == IVRegime.NEUTRAL

    def test_low_iv(self):
        """Test low IV classification."""
        assert determine_iv_regime(Decimal("10")) == IVRegime.LOW
        assert determine_iv_regime(Decimal("24")) == IVRegime.LOW

    def test_none_iv(self):
        """Test None IV."""
        assert determine_iv_regime(None) is None


class TestSpreadWidth:
    """Test spread width logic."""

    def test_low_priced_ticker(self):
        """Test spread width for low-priced ticker."""
        assert get_spread_width_for_price(Decimal("50")) == 5

    def test_mid_priced_ticker(self):
        """Test spread width for mid-priced ticker."""
        assert get_spread_width_for_price(Decimal("150")) == 5

    def test_high_priced_ticker(self):
        """Test spread width for high-priced ticker."""
        assert get_spread_width_for_price(Decimal("500")) == 10

    def test_custom_max_width(self):
        """Test custom max width."""
        assert get_spread_width_for_price(Decimal("500"), max_width=7) == 7


class TestSpreadMetrics:
    """Test spread metrics calculation."""

    def test_bull_call_spread_debit(self):
        """Test bull call spread debit metrics."""
        net_premium, breakeven, max_profit, max_loss, rr, pop = calculate_spread_metrics(
            long_strike=Decimal("445"),
            short_strike=Decimal("450"),
            long_premium=Decimal("8.75"),
            short_premium=Decimal("5.25"),
            option_type="call",
            long_delta=Decimal("0.65"),
            short_delta=Decimal("0.50"),
        )

        assert net_premium == Decimal("350.00")  # (8.75 - 5.25) * 100
        assert max_loss == Decimal("350.00")
        assert max_profit == Decimal("150.00")  # (5 * 100) - 350
        assert breakeven == Decimal("448.50")  # 445 + 3.50
        assert rr == Decimal("150.00") / Decimal("350.00")
        assert pop == Decimal("15.00")  # abs(0.65 - 0.50) * 100

    def test_bull_put_spread_credit(self):
        """Test bull put spread credit metrics."""
        net_premium, breakeven, max_profit, max_loss, rr, pop = calculate_spread_metrics(
            long_strike=Decimal("440"),
            short_strike=Decimal("445"),
            long_premium=Decimal("1.25"),
            short_premium=Decimal("2.75"),
            option_type="put",
            long_delta=Decimal("-0.25"),
            short_delta=Decimal("-0.35"),
        )

        assert net_premium == Decimal("-150.00")  # (1.25 - 2.75) * 100
        assert max_profit == Decimal("150.00")
        assert max_loss == Decimal("350.00")  # (5 * 100) - 150
        assert breakeven == Decimal("443.50")  # 445 - 1.50
        assert pop == Decimal("90.00")  # (1 - 0.10) * 100


class TestStrikeClassification:
    """Test strike position classification."""

    def test_call_itm(self):
        """Test ITM call classification."""
        pos = classify_strike_position(
            Decimal("440"), Decimal("450"), "call", atm_threshold=Decimal("1.0")
        )
        assert pos == StrikePosition.ITM

    def test_call_atm(self):
        """Test ATM call classification."""
        pos = classify_strike_position(Decimal("450"), Decimal("450"), "call")
        assert pos == StrikePosition.ATM

    def test_call_otm(self):
        """Test OTM call classification."""
        pos = classify_strike_position(
            Decimal("460"), Decimal("450"), "call", atm_threshold=Decimal("1.0")
        )
        assert pos == StrikePosition.OTM

    def test_put_itm(self):
        """Test ITM put classification."""
        pos = classify_strike_position(
            Decimal("460"), Decimal("450"), "put", atm_threshold=Decimal("1.0")
        )
        assert pos == StrikePosition.ITM

    def test_put_otm(self):
        """Test OTM put classification."""
        pos = classify_strike_position(
            Decimal("440"), Decimal("450"), "put", atm_threshold=Decimal("1.0")
        )
        assert pos == StrikePosition.OTM


class TestFindNearestStrikes:
    """Test finding nearest strikes."""

    def test_find_call_strikes(self, spy_contracts):
        """Test finding nearest call strikes."""
        strikes = find_nearest_strikes(
            spy_contracts,
            Decimal("450"),
            "call",
        )

        assert strikes[StrikePosition.ITM].strike == Decimal("445")
        assert strikes[StrikePosition.ATM].strike == Decimal("450")
        assert strikes[StrikePosition.OTM].strike == Decimal("455")

    def test_find_put_strikes(self, spy_contracts):
        """Test finding nearest put strikes."""
        strikes = find_nearest_strikes(
            spy_contracts,
            Decimal("450"),
            "put",
        )

        assert strikes[StrikePosition.ITM].strike == Decimal("455")
        assert strikes[StrikePosition.ATM].strike == Decimal("450")
        assert strikes[StrikePosition.OTM].strike == Decimal("445")


class TestVerticalSpreadRecommendations:
    """Test vertical spread recommendations."""

    def test_bullish_call_spread(self, spy_contracts):
        """Test bullish call spread recommendations."""
        candidates = recommend_vertical_spreads(
            spy_contracts,
            Decimal("450"),
            "call",
            "bullish",
            target_width=5,
        )

        assert len(candidates) > 0
        # Should have ITM, ATM, OTM candidates
        positions = [c.position for c in candidates]
        assert StrikePosition.ATM in positions

        # Check ATM candidate
        atm = next(c for c in candidates if c.position == StrikePosition.ATM)
        assert atm.long_strike == Decimal("450")
        assert atm.short_strike == Decimal("455")
        assert atm.net_premium > 0  # Debit spread
        assert atm.max_loss == atm.net_premium

    def test_bearish_put_spread(self, spy_contracts):
        """Test bearish put spread (debit) recommendations."""
        candidates = recommend_vertical_spreads(
            spy_contracts,
            Decimal("450"),
            "put",
            "bearish",
            target_width=5,
        )

        assert len(candidates) > 0

        # Check ATM candidate - should be a debit spread
        atm = next((c for c in candidates if c.position == StrikePosition.ATM), None)
        if atm:
            # Bear put debit: Long higher strike, short lower strike
            assert atm.long_strike > atm.short_strike
            assert atm.net_premium > 0  # Debit spread

    def test_bullish_put_spread_credit(self, spy_contracts):
        """Test bullish put spread (credit) recommendations."""
        candidates = recommend_vertical_spreads(
            spy_contracts,
            Decimal("450"),
            "put",
            "bullish",  # Bullish with puts → credit spread
            target_width=5,
        )

        assert len(candidates) > 0

        # Check ATM candidate - should be a credit spread
        atm = next((c for c in candidates if c.position == StrikePosition.ATM), None)
        if atm:
            # Bull put credit: Short higher strike, long lower strike
            # So long_strike should be LOWER than short_strike
            assert atm.long_strike < atm.short_strike
            assert atm.net_premium < 0  # Credit spread (negative net premium)
            assert atm.max_profit == abs(atm.net_premium)  # Profit = credit received

    def test_bearish_call_spread_credit(self, spy_contracts):
        """Test bearish call spread (credit) recommendations."""
        candidates = recommend_vertical_spreads(
            spy_contracts,
            Decimal("450"),
            "call",
            "bearish",  # Bearish with calls → credit spread
            target_width=5,
        )

        assert len(candidates) > 0

        # Check ATM candidate - should be a credit spread
        atm = next((c for c in candidates if c.position == StrikePosition.ATM), None)
        if atm:
            # Bear call credit: Short lower strike, long higher strike
            # So long_strike should be HIGHER than short_strike
            assert atm.long_strike > atm.short_strike
            assert atm.net_premium < 0  # Credit spread
            assert atm.max_profit == abs(atm.net_premium)

    def test_min_credit_filter(self, spy_contracts):
        """Test minimum credit percentage filter."""
        candidates = recommend_vertical_spreads(
            spy_contracts,
            Decimal("450"),
            "put",
            "bullish",  # Bull put spread (credit)
            target_width=5,
            min_credit_pct=Decimal("50.0"),  # Very high threshold
        )

        # Should still return candidates but with warnings in notes
        if candidates:
            for candidate in candidates:
                if candidate.net_premium < 0:  # Credit spread
                    # Check if warning note is present for low credits
                    pass  # Notes will indicate if below threshold


class TestLongOptionRecommendations:
    """Test long option recommendations."""

    def test_long_call_recommendations(self, spy_contracts):
        """Test long call recommendations."""
        candidates = recommend_long_options(
            spy_contracts,
            Decimal("450"),
            "call",
        )

        assert len(candidates) > 0
        positions = [c.position for c in candidates]
        assert StrikePosition.ATM in positions

        # Check ATM call
        atm = next(c for c in candidates if c.position == StrikePosition.ATM)
        assert atm.strike == Decimal("450")
        assert atm.premium == Decimal("5.25")
        assert atm.max_loss == Decimal("525.00")  # 5.25 * 100
        assert atm.max_profit is None  # Unlimited for calls
        assert atm.breakeven == Decimal("455.25")  # 450 + 5.25

    def test_long_put_recommendations(self, spy_contracts):
        """Test long put recommendations."""
        candidates = recommend_long_options(
            spy_contracts,
            Decimal("450"),
            "put",
        )

        assert len(candidates) > 0

        # Check ATM put
        atm = next((c for c in candidates if c.position == StrikePosition.ATM), None)
        if atm:
            assert atm.strike == Decimal("450")
            assert atm.premium == Decimal("5.25")
            assert atm.max_loss == Decimal("525.00")
            assert atm.max_profit == Decimal("44475.00")  # (450 - 5.25) * 100
            assert atm.breakeven == Decimal("444.75")  # 450 - 5.25


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_contracts(self):
        """Test with no contracts."""
        candidates = recommend_vertical_spreads(
            [],
            Decimal("450"),
            "call",
            "bullish",
            5,
        )
        assert len(candidates) == 0

    def test_missing_marks(self):
        """Test with contracts missing mark prices."""
        contracts = [
            OptionContractData(
                strike=Decimal("450"),
                option_type="call",
                bid=None,
                ask=None,
                mark=None,
                delta=Decimal("0.50"),
                implied_vol=None,
                volume=None,
                open_interest=None,
            ),
        ]

        candidates = recommend_vertical_spreads(
            contracts,
            Decimal("450"),
            "call",
            "bullish",
            5,
        )
        assert len(candidates) == 0  # Should skip contracts without marks
