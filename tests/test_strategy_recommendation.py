"""
Unit tests for strategy recommendation engine.
"""

import pytest
from decimal import Decimal
from datetime import datetime

from app.core.strategy_recommender import (
    select_strategy_family,
    calculate_composite_score,
    apply_constraints,
    build_reasoning,
    recommend_strategies,
    StrategyFamily,
    StrategyObjectives,
    StrategyConstraints,
    ScoringWeights,
    StrategyRecommendation,
)
from app.core.strike_selection import (
    IVRegime,
    OptionContractData,
)


@pytest.fixture
def sample_contracts():
    """Create sample option contracts for testing."""
    contracts = []

    # Call chain around $450 with realistic pricing
    call_prices = {
        440: Decimal("12.50"),
        445: Decimal("9.00"),
        450: Decimal("6.00"),
        455: Decimal("3.50"),
        460: Decimal("1.75"),
    }
    call_deltas = {
        440: Decimal("0.75"),
        445: Decimal("0.65"),
        450: Decimal("0.50"),
        455: Decimal("0.35"),
        460: Decimal("0.20"),
    }

    for strike in [440, 445, 450, 455, 460]:
        contracts.append(
            OptionContractData(
                strike=Decimal(str(strike)),
                option_type="call",
                bid=call_prices[strike] - Decimal("0.25"),
                ask=call_prices[strike] + Decimal("0.25"),
                mark=call_prices[strike],
                delta=call_deltas[strike],
                implied_vol=Decimal("0.20"),
                volume=100,
                open_interest=500,
            )
        )

    # Put chain around $450 with realistic pricing
    put_prices = {
        440: Decimal("1.75"),
        445: Decimal("3.50"),
        450: Decimal("6.00"),
        455: Decimal("9.00"),
        460: Decimal("12.50"),
    }
    put_deltas = {
        440: Decimal("-0.20"),
        445: Decimal("-0.35"),
        450: Decimal("-0.50"),
        455: Decimal("-0.65"),
        460: Decimal("-0.75"),
    }

    for strike in [440, 445, 450, 455, 460]:
        contracts.append(
            OptionContractData(
                strike=Decimal(str(strike)),
                option_type="put",
                bid=put_prices[strike] - Decimal("0.25"),
                ask=put_prices[strike] + Decimal("0.25"),
                mark=put_prices[strike],
                delta=put_deltas[strike],
                implied_vol=Decimal("0.20"),
                volume=100,
                open_interest=500,
            )
        )

    return contracts


class TestStrategySelection:
    """Test strategy family selection logic."""

    def test_high_iv_bullish_selects_bull_put_credit(self):
        """High IV + bullish should select bull put credit spread."""
        family, option_type, reason = select_strategy_family(IVRegime.HIGH, "bullish")
        assert family == StrategyFamily.VERTICAL_CREDIT
        assert option_type == "put"
        assert "bull put credit" in reason.lower()

    def test_high_iv_bearish_selects_bear_call_credit(self):
        """High IV + bearish should select bear call credit spread."""
        family, option_type, reason = select_strategy_family(IVRegime.HIGH, "bearish")
        assert family == StrategyFamily.VERTICAL_CREDIT
        assert option_type == "call"
        assert "bear call credit" in reason.lower()

    def test_low_iv_bullish_selects_long_call(self):
        """Low IV + bullish should select long call."""
        family, option_type, reason = select_strategy_family(IVRegime.LOW, "bullish")
        assert family == StrategyFamily.LONG_CALL
        assert option_type == "call"
        assert "long call" in reason.lower()

    def test_low_iv_bearish_selects_long_put(self):
        """Low IV + bearish should select long put."""
        family, option_type, reason = select_strategy_family(IVRegime.LOW, "bearish")
        assert family == StrategyFamily.LONG_PUT
        assert option_type == "put"
        assert "long put" in reason.lower()

    def test_neutral_iv_bullish_selects_bull_call_debit(self):
        """Neutral IV + bullish should select bull call debit spread."""
        family, option_type, reason = select_strategy_family(IVRegime.NEUTRAL, "bullish")
        assert family == StrategyFamily.VERTICAL_DEBIT
        assert option_type == "call"
        assert "bull call" in reason.lower()

    def test_neutral_iv_bearish_selects_bear_put_debit(self):
        """Neutral IV + bearish should select bear put debit spread."""
        family, option_type, reason = select_strategy_family(IVRegime.NEUTRAL, "bearish")
        assert family == StrategyFamily.VERTICAL_DEBIT
        assert option_type == "put"
        assert "bear put" in reason.lower()

    def test_prefer_credit_overrides_iv_regime(self):
        """Explicit prefer_credit should override IV regime."""
        objectives = StrategyObjectives(prefer_credit=True)
        family, option_type, reason = select_strategy_family(
            IVRegime.LOW, "bullish", objectives  # Would normally select long options
        )
        assert family == StrategyFamily.VERTICAL_CREDIT
        assert option_type == "put"
        assert "credit" in reason.lower()

    def test_prefer_debit_overrides_iv_regime(self):
        """Explicit prefer_debit should override IV regime."""
        objectives = StrategyObjectives(prefer_credit=False)
        family, option_type, reason = select_strategy_family(
            IVRegime.HIGH, "bullish", objectives  # Would normally select credit spreads
        )
        assert family == StrategyFamily.VERTICAL_DEBIT
        assert option_type == "call"
        assert "debit" in reason.lower()


class TestCompositeScoring:
    """Test composite scoring system."""

    def test_high_score_for_good_metrics(self):
        """Recommendation with good metrics should score high."""
        rec = StrategyRecommendation(
            rank=1,
            strategy_family=StrategyFamily.VERTICAL_DEBIT,
            option_type="call",
            position="atm",
            breakeven=Decimal("450"),
            max_profit=Decimal("350"),
            max_loss=Decimal("150"),
            risk_reward_ratio=Decimal("2.33"),
            pop_proxy=Decimal("65"),
            avg_open_interest=500,
            composite_score=Decimal(0),
        )

        score = calculate_composite_score(rec, ScoringWeights(), StrategyFamily.VERTICAL_DEBIT)

        # Should score well (high POP, good R:R, ATM, good liquidity)
        assert score > Decimal("70")

    def test_low_score_for_poor_metrics(self):
        """Recommendation with poor metrics should score low."""
        rec = StrategyRecommendation(
            rank=1,
            strategy_family=StrategyFamily.VERTICAL_DEBIT,
            option_type="call",
            position="itm",
            breakeven=Decimal("450"),
            max_profit=Decimal("100"),
            max_loss=Decimal("400"),
            risk_reward_ratio=Decimal("0.25"),
            pop_proxy=Decimal("20"),
            avg_open_interest=10,
            composite_score=Decimal(0),
        )

        score = calculate_composite_score(rec, ScoringWeights(), StrategyFamily.VERTICAL_DEBIT)

        # Should score poorly (low POP, poor R:R, ITM, low liquidity)
        assert score < Decimal("40")

    def test_credit_quality_scoring(self):
        """Credit spreads should score based on credit quality."""
        rec = StrategyRecommendation(
            rank=1,
            strategy_family=StrategyFamily.VERTICAL_CREDIT,
            option_type="put",
            position="atm",
            net_premium=Decimal("-200"),  # $2.00 credit
            is_credit=True,
            width_dollars=Decimal("500"),  # $5 wide
            breakeven=Decimal("445"),
            max_profit=Decimal("200"),
            max_loss=Decimal("300"),
            risk_reward_ratio=Decimal("0.67"),
            pop_proxy=Decimal("70"),
            avg_open_interest=500,
            composite_score=Decimal(0),
        )

        score = calculate_composite_score(rec, ScoringWeights(), StrategyFamily.VERTICAL_CREDIT)

        # 40% credit ($2/$5) should contribute to score
        # With high POP (70%), decent R:R, ATM position, and good liquidity
        assert score > Decimal("50")


class TestConstraints:
    """Test constraint filtering."""

    def test_max_risk_constraint(self):
        """Should reject if max_loss exceeds max_risk."""
        rec = StrategyRecommendation(
            rank=1,
            strategy_family=StrategyFamily.VERTICAL_DEBIT,
            option_type="call",
            position="atm",
            breakeven=Decimal("450"),
            max_profit=Decimal("350"),
            max_loss=Decimal("600"),  # Too high
            composite_score=Decimal(0),
        )

        objectives = StrategyObjectives(max_risk_per_trade=Decimal("500"))
        passes, warnings = apply_constraints(rec, None, objectives)

        assert not passes
        assert any("exceeds limit" in w for w in warnings)

    def test_min_pop_constraint(self):
        """Should reject if POP below minimum."""
        rec = StrategyRecommendation(
            rank=1,
            strategy_family=StrategyFamily.VERTICAL_DEBIT,
            option_type="call",
            position="atm",
            breakeven=Decimal("450"),
            max_profit=Decimal("350"),
            max_loss=Decimal("150"),
            pop_proxy=Decimal("30"),  # Too low
            composite_score=Decimal(0),
        )

        objectives = StrategyObjectives(min_pop_pct=Decimal("50"))
        passes, warnings = apply_constraints(rec, None, objectives)

        assert not passes
        assert any("POP" in w and "below minimum" in w for w in warnings)

    def test_min_credit_constraint(self):
        """Should reject credit spread if credit below minimum."""
        rec = StrategyRecommendation(
            rank=1,
            strategy_family=StrategyFamily.VERTICAL_CREDIT,
            option_type="put",
            position="atm",
            net_premium=Decimal("-100"),  # $1.00 credit
            is_credit=True,
            width_dollars=Decimal("500"),  # $5 wide = 20% credit
            breakeven=Decimal("445"),
            max_profit=Decimal("100"),
            max_loss=Decimal("400"),
            composite_score=Decimal(0),
        )

        constraints = StrategyConstraints(min_credit_pct=Decimal("25"))  # Need 25%
        passes, warnings = apply_constraints(rec, constraints, None)

        assert not passes
        assert any("Credit" in w and "below minimum" in w for w in warnings)

    def test_passes_all_constraints(self):
        """Should pass if all constraints met."""
        rec = StrategyRecommendation(
            rank=1,
            strategy_family=StrategyFamily.VERTICAL_CREDIT,
            option_type="put",
            position="atm",
            net_premium=Decimal("-150"),  # $1.50 credit
            is_credit=True,
            width_dollars=Decimal("500"),  # $5 wide = 30% credit
            breakeven=Decimal("445"),
            max_profit=Decimal("150"),
            max_loss=Decimal("350"),
            risk_reward_ratio=Decimal("0.43"),
            pop_proxy=Decimal("65"),
            avg_open_interest=200,
            avg_volume=100,
            composite_score=Decimal(0),
        )

        objectives = StrategyObjectives(
            max_risk_per_trade=Decimal("400"),
            min_pop_pct=Decimal("50"),
            min_risk_reward=Decimal("0.30"),
        )
        constraints = StrategyConstraints(
            min_credit_pct=Decimal("25"),
            min_open_interest=100,
            min_volume=50,
        )

        passes, warnings = apply_constraints(rec, constraints, objectives)

        assert passes
        assert len(warnings) == 0


class TestReasoning:
    """Test reasoning generation."""

    def test_includes_strategy_reason(self):
        """Reasoning should include strategy selection reason."""
        rec = StrategyRecommendation(
            rank=1,
            strategy_family=StrategyFamily.VERTICAL_CREDIT,
            option_type="put",
            position="atm",
            breakeven=Decimal("445"),
            max_loss=Decimal("350"),
            composite_score=Decimal(0),
        )

        strategy_reason = "High IV regime favors selling premium"
        reasons = build_reasoning(
            rec, StrategyFamily.VERTICAL_CREDIT, IVRegime.HIGH, "bullish", strategy_reason
        )

        assert strategy_reason in reasons

    def test_includes_position_context(self):
        """Reasoning should include position context."""
        rec = StrategyRecommendation(
            rank=1,
            strategy_family=StrategyFamily.VERTICAL_DEBIT,
            option_type="call",
            position="atm",
            breakeven=Decimal("450"),
            max_loss=Decimal("150"),
            composite_score=Decimal(0),
        )

        reasons = build_reasoning(
            rec,
            StrategyFamily.VERTICAL_DEBIT,
            IVRegime.NEUTRAL,
            "bullish",
            "Neutral IV - balanced debit spread",
        )

        assert any("at-the-money" in r.lower() for r in reasons)
        assert any("call" in r.lower() for r in reasons)

    def test_highlights_high_rr(self):
        """Reasoning should highlight attractive R:R."""
        rec = StrategyRecommendation(
            rank=1,
            strategy_family=StrategyFamily.VERTICAL_DEBIT,
            option_type="call",
            position="otm",
            risk_reward_ratio=Decimal("2.50"),
            breakeven=Decimal("455"),
            max_loss=Decimal("150"),
            composite_score=Decimal(0),
        )

        reasons = build_reasoning(
            rec, StrategyFamily.VERTICAL_DEBIT, IVRegime.NEUTRAL, "bullish", "Neutral IV"
        )

        assert any("Attractive R:R" in r for r in reasons)


class TestEndToEndRecommendations:
    """Test end-to-end recommendation generation."""

    def test_high_iv_bullish_recommends_credit_spreads(self, sample_contracts):
        """High IV + bullish should recommend bull put credit spreads."""
        result = recommend_strategies(
            contracts=sample_contracts,
            underlying_symbol="SPY",
            underlying_price=Decimal("450"),
            bias="bullish",
            dte=30,
            iv_rank=Decimal("75"),  # High IV
        )

        assert result.chosen_strategy_family == StrategyFamily.VERTICAL_CREDIT
        assert result.iv_regime == "high"
        assert len(result.recommendations) > 0

        # Check first recommendation
        top_rec = result.recommendations[0]
        assert top_rec.option_type == "put"
        assert top_rec.is_credit is True
        assert top_rec.rank == 1

    def test_low_iv_bearish_recommends_long_puts(self, sample_contracts):
        """Low IV + bearish should recommend long puts."""
        result = recommend_strategies(
            contracts=sample_contracts,
            underlying_symbol="SPY",
            underlying_price=Decimal("450"),
            bias="bearish",
            dte=30,
            iv_rank=Decimal("15"),  # Low IV
        )

        assert result.chosen_strategy_family == StrategyFamily.LONG_PUT
        assert result.iv_regime == "low"
        assert len(result.recommendations) > 0

        top_rec = result.recommendations[0]
        assert top_rec.option_type == "put"
        assert top_rec.strike is not None

    def test_recommendations_are_ranked(self, sample_contracts):
        """Recommendations should be ranked by score."""
        result = recommend_strategies(
            contracts=sample_contracts,
            underlying_symbol="SPY",
            underlying_price=Decimal("450"),
            bias="bullish",
            dte=30,
            iv_rank=Decimal("45"),  # Neutral IV
        )

        assert len(result.recommendations) > 1

        # Check ranks are sequential
        for i, rec in enumerate(result.recommendations):
            assert rec.rank == i + 1

        # Check scores are descending
        for i in range(len(result.recommendations) - 1):
            assert (
                result.recommendations[i].composite_score
                >= result.recommendations[i + 1].composite_score
            )

    def test_constraints_filter_candidates(self, sample_contracts):
        """Constraints should filter out non-compliant candidates."""
        objectives = StrategyObjectives(
            max_risk_per_trade=Decimal("500"),  # Restrictive but achievable
        )

        result = recommend_strategies(
            contracts=sample_contracts,
            underlying_symbol="SPY",
            underlying_price=Decimal("450"),
            bias="bullish",
            dte=30,
            iv_rank=Decimal("45"),
            objectives=objectives,
        )

        # All recommendations should respect max risk
        for rec in result.recommendations:
            assert rec.max_loss <= Decimal("500")

        # Should have rejected some candidates
        assert any("rejected" in w.lower() for w in result.warnings)

    def test_position_sizing_with_account_size(self, sample_contracts):
        """Should calculate position sizing with account size."""
        objectives = StrategyObjectives(
            account_size=Decimal("25000"),
        )

        result = recommend_strategies(
            contracts=sample_contracts,
            underlying_symbol="SPY",
            underlying_price=Decimal("450"),
            bias="bullish",
            dte=30,
            iv_rank=Decimal("45"),
            objectives=objectives,
        )

        # Should have position sizing
        for rec in result.recommendations:
            assert rec.recommended_contracts is not None
            assert rec.recommended_contracts > 0
            assert rec.position_size_dollars is not None

    def test_iv_regime_override(self, sample_contracts):
        """IV regime override should force strategy selection."""
        constraints = StrategyConstraints(iv_regime_override="high")  # Force high IV treatment

        result = recommend_strategies(
            contracts=sample_contracts,
            underlying_symbol="SPY",
            underlying_price=Decimal("450"),
            bias="bullish",
            dte=30,
            iv_rank=Decimal("15"),  # Actually low IV
            constraints=constraints,
        )

        # Should treat as high IV (credit spreads)
        assert result.iv_regime == "high"
        assert result.chosen_strategy_family == StrategyFamily.VERTICAL_CREDIT
        assert any("overridden" in w.lower() for w in result.warnings)

    def test_reasoning_bullets_present(self, sample_contracts):
        """All recommendations should have reasoning bullets."""
        result = recommend_strategies(
            contracts=sample_contracts,
            underlying_symbol="SPY",
            underlying_price=Decimal("450"),
            bias="bullish",
            dte=30,
            iv_rank=Decimal("45"),
        )

        for rec in result.recommendations:
            assert len(rec.reasons) > 0
            # Should have IV justification
            assert any(
                "iv" in r.lower() or "regime" in r.lower() or "neutral" in r.lower()
                for r in rec.reasons
            )
