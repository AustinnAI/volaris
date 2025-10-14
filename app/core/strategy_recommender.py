"""
Strategy Recommendation Engine
Intelligent strategy selection combining IV regime analysis, strike selection, and trade calculations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from app.config import settings
from app.core.strike_selection import (
    IVRegime,
    OptionContractData,
    determine_iv_regime,
    get_spread_width_for_price,
    recommend_long_options,
    recommend_vertical_spreads,
)


class StrategyFamily(str, Enum):
    """Strategy family classification."""

    VERTICAL_CREDIT = "vertical_credit"
    VERTICAL_DEBIT = "vertical_debit"
    LONG_CALL = "long_call"
    LONG_PUT = "long_put"
    AUTO = "auto"


@dataclass
class StrategyObjectives:
    """Trading objectives and preferences."""

    max_risk_per_trade: Decimal | None = None  # Max $ risk per trade
    min_pop_pct: Decimal | None = None  # Minimum probability of profit %
    min_risk_reward: Decimal | None = None  # Minimum R:R ratio
    prefer_credit: bool | None = None  # Prefer credit spreads if True
    avoid_earnings: bool = False  # Avoid trades during earnings
    account_size: Decimal | None = None  # For position sizing
    bias_reason: str | None = "user_manual"  # Reason for bias (Phase 3.5)


@dataclass
class StrategyConstraints:
    """Strategy constraints and filters."""

    min_credit_pct: Decimal | None = None  # Min credit as % of spread width
    max_spread_width: int | None = None  # Max spread width in points
    iv_regime_override: str | None = None  # Force specific IV regime
    min_open_interest: int | None = None  # Min OI for liquidity
    min_volume: int | None = None  # Min daily volume
    min_mark_price: Decimal | None = None  # Min mark price


@dataclass
class ScoringWeights:
    """Configurable weights for composite scoring."""

    pop_weight: Decimal = Decimal("0.30")  # Probability of profit
    rr_weight: Decimal = Decimal("0.30")  # Risk/reward ratio
    credit_weight: Decimal = Decimal("0.25")  # Credit quality (for credits)
    liquidity_weight: Decimal = Decimal("0.10")  # Liquidity score
    width_efficiency_weight: Decimal = Decimal("0.05")  # Optimal width


@dataclass
class StrategyRecommendation:
    """A ranked strategy recommendation with reasoning."""

    rank: int
    strategy_family: StrategyFamily
    option_type: str  # "call" or "put"
    position: str  # "itm", "atm", "otm"

    # Strike details
    strike: Decimal | None = None  # For long options
    long_strike: Decimal | None = None  # For spreads
    short_strike: Decimal | None = None  # For spreads

    # Pricing
    premium: Decimal | None = None  # For long options
    long_premium: Decimal | None = None  # For spreads
    short_premium: Decimal | None = None  # For spreads
    net_premium: Decimal | None = None  # Net debit/credit
    is_credit: bool | None = None
    net_credit: Decimal | None = None
    net_debit: Decimal | None = None

    # Spread details
    width_points: Decimal | None = None
    width_dollars: Decimal | None = None

    # Risk metrics
    breakeven: Decimal = Decimal(0)
    max_profit: Decimal | None = None
    max_loss: Decimal = Decimal(0)
    risk_reward_ratio: Decimal | None = None

    # Probabilities
    pop_proxy: Decimal | None = None  # Delta-based POP

    # Greeks
    delta: Decimal | None = None
    long_delta: Decimal | None = None
    short_delta: Decimal | None = None

    # Position sizing
    recommended_contracts: int | None = None
    position_size_dollars: Decimal | None = None

    # Scoring
    composite_score: Decimal = Decimal(0)

    # Liquidity
    avg_open_interest: int | None = None
    avg_volume: int | None = None

    # Reasoning
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class StrategyRecommendationResult:
    """Complete recommendation result."""

    underlying_symbol: str
    underlying_price: Decimal
    chosen_strategy_family: StrategyFamily
    iv_rank: Decimal | None
    iv_regime: str | None
    dte: int
    expected_move_pct: Decimal | None
    data_timestamp: datetime

    # Recommendations
    recommendations: list[StrategyRecommendation]

    # Configuration used
    config_used: dict[str, Any]

    # Warnings
    warnings: list[str]


def select_strategy_family(
    iv_regime: IVRegime | None,
    bias: str,
    objectives: StrategyObjectives | None = None,
) -> tuple[StrategyFamily, str, str]:
    """
    Select optimal strategy family based on IV regime and bias.

    Args:
        iv_regime: Current IV regime
        bias: Directional bias ("bullish", "bearish", "neutral")
        objectives: Trading objectives (optional)

    Returns:
        (strategy_family, option_type, reasoning)
    """
    # Check for explicit preference
    if objectives and objectives.prefer_credit is not None:
        if objectives.prefer_credit:
            # Force credit spreads
            if bias == "bullish":
                return (
                    StrategyFamily.VERTICAL_CREDIT,
                    "put",
                    "Explicit preference for credit spreads (bull put)",
                )
            elif bias == "bearish":
                return (
                    StrategyFamily.VERTICAL_CREDIT,
                    "call",
                    "Explicit preference for credit spreads (bear call)",
                )
            else:
                return (
                    StrategyFamily.VERTICAL_CREDIT,
                    "call",
                    "Explicit preference for credit spreads",
                )
        else:
            # Force debit spreads or long options
            if bias == "bullish":
                return (
                    StrategyFamily.VERTICAL_DEBIT,
                    "call",
                    "Explicit preference for debit spreads (bull call)",
                )
            elif bias == "bearish":
                return (
                    StrategyFamily.VERTICAL_DEBIT,
                    "put",
                    "Explicit preference for debit spreads (bear put)",
                )

    # IV-based selection
    if iv_regime == IVRegime.HIGH:
        # High IV → Sell premium (credit spreads)
        if bias == "bullish":
            return (
                StrategyFamily.VERTICAL_CREDIT,
                "put",
                f"High IV ({iv_regime.value}) regime favors selling premium - bull put credit spread",
            )
        elif bias == "bearish":
            return (
                StrategyFamily.VERTICAL_CREDIT,
                "call",
                f"High IV ({iv_regime.value}) regime favors selling premium - bear call credit spread",
            )
        else:  # neutral
            return (
                StrategyFamily.VERTICAL_CREDIT,
                "call",
                f"High IV ({iv_regime.value}) regime favors selling premium - credit spread",
            )

    elif iv_regime == IVRegime.LOW:
        # Low IV → Buy premium (long options for leverage)
        if bias == "bullish":
            return (
                StrategyFamily.LONG_CALL,
                "call",
                f"Low IV ({iv_regime.value}) regime favors buying cheap premium - long call",
            )
        elif bias == "bearish":
            return (
                StrategyFamily.LONG_PUT,
                "put",
                f"Low IV ({iv_regime.value}) regime favors buying cheap premium - long put",
            )
        else:  # neutral
            # Neutral with low IV → use debit spread for defined risk
            return (
                StrategyFamily.VERTICAL_DEBIT,
                "call",
                f"Low IV ({iv_regime.value}) with neutral bias - defined risk debit spread",
            )

    else:  # NEUTRAL or None
        # Neutral IV → Use debit spreads for balanced defined risk
        if bias == "bullish":
            return (
                StrategyFamily.VERTICAL_DEBIT,
                "call",
                "Neutral IV regime - balanced bull call debit spread",
            )
        elif bias == "bearish":
            return (
                StrategyFamily.VERTICAL_DEBIT,
                "put",
                "Neutral IV regime - balanced bear put debit spread",
            )
        else:  # neutral bias
            return (
                StrategyFamily.VERTICAL_DEBIT,
                "call",
                "Neutral IV and bias - balanced vertical debit spread",
            )


def apply_dte_preferences(
    strategy_family: StrategyFamily,
    option_type: str,
    dte: int,
    account_size: Decimal | None,
    bias: str,
    reasoning: str,
) -> tuple[StrategyFamily, str, str]:
    """
    Apply DTE-based strategy preferences for capital efficiency.

    Phase 3.4 ICT Integration:
    - 0-7 DTE: Prioritize credit spreads (capital efficient, high theta decay)
    - 14-45 DTE: Prefer spreads over naked options
    - Account size consideration: <$25k heavily weights credit spreads

    Args:
        strategy_family: Initial strategy selection
        option_type: "call" or "put"
        dte: Days to expiration
        account_size: Account size for capital efficiency check
        bias: Directional bias
        reasoning: Current reasoning string

    Returns:
        (adjusted_strategy_family, option_type, updated_reasoning)
    """
    # Determine account size tier
    account_tier = "large"  # Default if not specified
    if account_size:
        if account_size < Decimal("10000"):
            account_tier = "small"
        elif account_size < Decimal("25000"):
            account_tier = "medium"

    # 0-7 DTE: Heavy credit spread preference for capital efficiency
    if dte <= 7:
        # Override long options to credit spreads for small/medium accounts
        if strategy_family in (StrategyFamily.LONG_CALL, StrategyFamily.LONG_PUT):
            if account_tier in ("small", "medium"):
                # Convert to credit spread
                if bias == "bullish":
                    new_family = StrategyFamily.VERTICAL_CREDIT
                    new_type = "put"
                    new_reasoning = (
                        f"0-7 DTE + {account_tier} account: Credit spread prioritized (capital efficient, "
                        f"faster theta decay, defined risk). Bull put spread recommended. {reasoning}"
                    )
                elif bias == "bearish":
                    new_family = StrategyFamily.VERTICAL_CREDIT
                    new_type = "call"
                    new_reasoning = (
                        f"0-7 DTE + {account_tier} account: Credit spread prioritized (capital efficient, "
                        f"faster theta decay, defined risk). Bear call spread recommended. {reasoning}"
                    )
                else:  # neutral
                    new_family = StrategyFamily.VERTICAL_CREDIT
                    new_type = "call"
                    new_reasoning = f"0-7 DTE + {account_tier} account: Credit spread prioritized for capital efficiency. {reasoning}"
                return new_family, new_type, new_reasoning
            else:
                # Large account: allow long options but add context
                updated_reasoning = (
                    f"0-7 DTE: Long option suitable for fast directional execution "
                    f"(adequate buying power). {reasoning}"
                )
                return strategy_family, option_type, updated_reasoning

        # If already credit spread, enhance reasoning
        elif strategy_family == StrategyFamily.VERTICAL_CREDIT:
            updated_reasoning = f"0-7 DTE: Credit spread optimal (capital efficient, high theta decay, defined risk). {reasoning}"
            return strategy_family, option_type, updated_reasoning

        # If debit spread, add DTE context
        elif strategy_family == StrategyFamily.VERTICAL_DEBIT:
            updated_reasoning = (
                f"0-7 DTE: Debit spread for defined risk directional play. {reasoning}"
            )
            return strategy_family, option_type, updated_reasoning

    # 14-45 DTE: Prefer spreads over naked, but allow long options for large accounts
    elif 14 <= dte <= 45:
        # Long options: only for large accounts, add warning for small accounts
        if strategy_family in (StrategyFamily.LONG_CALL, StrategyFamily.LONG_PUT):
            if account_tier in ("small", "medium"):
                # Convert to debit spread for defined risk
                if bias == "bullish":
                    new_family = StrategyFamily.VERTICAL_DEBIT
                    new_type = "call"
                    new_reasoning = (
                        f"14-45 DTE + {account_tier} account: Debit spread prioritized over long option "
                        f"(defined risk, less IV crush impact, lower capital). {reasoning}"
                    )
                elif bias == "bearish":
                    new_family = StrategyFamily.VERTICAL_DEBIT
                    new_type = "put"
                    new_reasoning = (
                        f"14-45 DTE + {account_tier} account: Debit spread prioritized over long option "
                        f"(defined risk, less IV crush impact, lower capital). {reasoning}"
                    )
                else:
                    new_family = StrategyFamily.VERTICAL_DEBIT
                    new_type = "call"
                    new_reasoning = f"14-45 DTE + {account_tier} account: Debit spread for defined risk. {reasoning}"
                return new_family, new_type, new_reasoning
            else:
                # Large account: allow but add context
                updated_reasoning = (
                    f"14-45 DTE: Long option viable for large account (adequate buying power, "
                    f"expect significant move). {reasoning}"
                )
                return strategy_family, option_type, updated_reasoning

        # Spreads in this DTE range: enhance reasoning
        elif strategy_family == StrategyFamily.VERTICAL_CREDIT:
            updated_reasoning = f"14-45 DTE: Credit spread well-suited (neutral/range setup, less IV crush impact). {reasoning}"
            return strategy_family, option_type, updated_reasoning
        elif strategy_family == StrategyFamily.VERTICAL_DEBIT:
            updated_reasoning = (
                f"14-45 DTE: Debit spread for directional play with defined risk. {reasoning}"
            )
            return strategy_family, option_type, updated_reasoning

    # Other DTE ranges: minimal adjustment, just add DTE context
    else:
        if dte > 45:
            updated_reasoning = f"{dte} DTE: Longer-dated position. {reasoning}"
        else:
            updated_reasoning = f"{dte} DTE: {reasoning}"
        return strategy_family, option_type, updated_reasoning

    # No change needed
    return strategy_family, option_type, reasoning


def get_bias_context_reasoning(
    bias_reason: str | None, bias: str, strategy_family: StrategyFamily
) -> str:
    """
    Generate reasoning context based on bias_reason (Phase 3.5).

    Foundation for Phase 5 automated sweep detection - provides context
    for why a particular bias was chosen.

    Args:
        bias_reason: Reason for bias (ssl_sweep, bsl_sweep, fvg_retest, structure_shift, user_manual)
        bias: Directional bias (bullish, bearish, neutral)
        strategy_family: Selected strategy family

    Returns:
        Context string explaining the setup
    """
    if not bias_reason or bias_reason == "user_manual":
        return ""  # No additional context for manual bias

    # ICT setup context
    if bias_reason == "ssl_sweep":
        if bias == "bullish":
            return (
                "ICT Setup: SSL swept (sell-side liquidity taken) → Bullish reversal expected. "
                "Price grabbed liquidity below swing low, now targeting opposite BSL (buy-side). "
            )
        else:
            return "Note: SSL sweep typically indicates bullish bias, but bearish bias selected. "

    elif bias_reason == "bsl_sweep":
        if bias == "bearish":
            return (
                "ICT Setup: BSL swept (buy-side liquidity taken) → Bearish reversal expected. "
                "Price grabbed liquidity above swing high, now targeting opposite SSL (sell-side). "
            )
        else:
            return "Note: BSL sweep typically indicates bearish bias, but bullish bias selected. "

    elif bias_reason == "fvg_retest":
        return (
            f"ICT Setup: FVG retest (Fair Value Gap) detected → {bias.capitalize()} continuation expected. "
            "Price returning to imbalance zone for potential continuation move. "
        )

    elif bias_reason == "structure_shift":
        return (
            f"ICT Setup: Market Structure Shift (MSS) confirmed → {bias.capitalize()} trend change. "
            "Higher highs/lows pattern established, displacement validated. "
        )

    return ""  # Unknown bias_reason


def calculate_composite_score(
    recommendation: StrategyRecommendation,
    weights: ScoringWeights,
    strategy_family: StrategyFamily,
) -> Decimal:
    """
    Calculate composite score for ranking recommendations.

    Scoring formula (0-100 scale):
    - POP proxy (30%): Higher probability = better
    - Risk/Reward (30%): Higher R:R = better
    - Credit quality (25%): Higher credit % = better (for credits only)
    - Liquidity (10%): Higher OI/volume = better
    - Width efficiency (5%): Optimal width = better

    Args:
        recommendation: Strategy recommendation to score
        weights: Scoring weights
        strategy_family: Strategy family for context

    Returns:
        Composite score (0-100)
    """
    score = Decimal(0)

    # POP proxy score (0-30 points)
    if recommendation.pop_proxy is not None:
        pop_normalized = min(recommendation.pop_proxy / Decimal(100), Decimal(1))
        score += pop_normalized * weights.pop_weight * Decimal(100)

    # Risk/Reward score (0-30 points)
    if recommendation.risk_reward_ratio is not None:
        # Normalize R:R (cap at 3:1 for scoring)
        rr_normalized = min(recommendation.risk_reward_ratio / Decimal(3), Decimal(1))
        score += rr_normalized * weights.rr_weight * Decimal(100)

    # Credit quality score (0-25 points) - for credit spreads only
    if strategy_family == StrategyFamily.VERTICAL_CREDIT and recommendation.is_credit:
        if recommendation.width_dollars and recommendation.width_dollars > 0:
            credit_pct = (
                abs(recommendation.net_premium or 0) / recommendation.width_dollars
            ) * Decimal(100)
            # Normalize: 25% credit = 0.5, 50% credit = 1.0
            credit_normalized = min(credit_pct / Decimal(50), Decimal(1))
            score += credit_normalized * weights.credit_weight * Decimal(100)
    else:
        # For debit spreads, reward cost efficiency
        if recommendation.max_profit and recommendation.max_loss and recommendation.max_loss > 0:
            cost_efficiency = recommendation.max_profit / recommendation.max_loss
            cost_normalized = min(cost_efficiency / Decimal(3), Decimal(1))
            score += cost_normalized * weights.credit_weight * Decimal(100)

    # Liquidity score (0-10 points)
    if recommendation.avg_open_interest is not None:
        # Normalize: 100 OI = 0.5, 500+ OI = 1.0
        oi_normalized = min(Decimal(recommendation.avg_open_interest) / Decimal(500), Decimal(1))
        score += oi_normalized * weights.liquidity_weight * Decimal(100)

    # Width efficiency score (0-5 points)
    # Prefer ATM for balance
    if recommendation.position == "atm":
        score += weights.width_efficiency_weight * Decimal(100)
    elif recommendation.position == "otm":
        score += weights.width_efficiency_weight * Decimal(50)

    return min(score, Decimal(100))


def apply_constraints(
    candidate: StrategyRecommendation,
    constraints: StrategyConstraints | None,
    objectives: StrategyObjectives | None,
) -> tuple[bool, list[str]]:
    """
    Check if recommendation meets all constraints.

    Args:
        candidate: Recommendation to validate
        constraints: Strategy constraints
        objectives: Trading objectives

    Returns:
        (passes, warnings) tuple
    """
    warnings = []

    if not constraints and not objectives:
        return True, warnings

    # Check objectives
    if objectives:
        # Max risk constraint
        if objectives.max_risk_per_trade is not None:
            if candidate.max_loss > objectives.max_risk_per_trade:
                warnings.append(
                    f"Max loss ${candidate.max_loss} exceeds limit ${objectives.max_risk_per_trade}"
                )
                return False, warnings

        # Min POP constraint
        if objectives.min_pop_pct is not None and candidate.pop_proxy is not None:
            if candidate.pop_proxy < objectives.min_pop_pct:
                warnings.append(
                    f"POP {candidate.pop_proxy:.1f}% below minimum {objectives.min_pop_pct}%"
                )
                return False, warnings

        # Min R:R constraint
        if objectives.min_risk_reward is not None and candidate.risk_reward_ratio is not None:
            if candidate.risk_reward_ratio < objectives.min_risk_reward:
                warnings.append(
                    f"R:R {candidate.risk_reward_ratio:.2f} below minimum {objectives.min_risk_reward}"
                )
                return False, warnings

    # Check constraints
    if constraints:
        # Min credit for credit spreads
        if constraints.min_credit_pct is not None and candidate.is_credit:
            if candidate.width_dollars and candidate.width_dollars > 0:
                credit_pct = (abs(candidate.net_premium or 0) / candidate.width_dollars) * Decimal(
                    100
                )
                if credit_pct < constraints.min_credit_pct:
                    warnings.append(
                        f"Credit {credit_pct:.1f}% below minimum {constraints.min_credit_pct}%"
                    )
                    return False, warnings

        # Liquidity constraints
        if constraints.min_open_interest is not None:
            if (
                candidate.avg_open_interest is not None
                and candidate.avg_open_interest < constraints.min_open_interest
            ):
                warnings.append(
                    f"Open interest {candidate.avg_open_interest} below minimum {constraints.min_open_interest}"
                )
                return False, warnings

        if constraints.min_volume is not None:
            if candidate.avg_volume is not None and candidate.avg_volume < constraints.min_volume:
                warnings.append(
                    f"Volume {candidate.avg_volume} below minimum {constraints.min_volume}"
                )
                return False, warnings

    return True, warnings


def build_reasoning(
    recommendation: StrategyRecommendation,
    strategy_family: StrategyFamily,
    iv_regime: IVRegime | None,
    bias: str,
    strategy_selection_reason: str,
) -> list[str]:
    """
    Build clear reasoning bullets for why this recommendation was selected.

    Args:
        recommendation: The recommendation
        strategy_family: Strategy family chosen
        iv_regime: IV regime
        bias: Directional bias
        strategy_selection_reason: Reason for strategy selection

    Returns:
        List of reasoning bullets
    """
    reasons = []

    # Strategy selection reason
    reasons.append(strategy_selection_reason)

    # Position context
    position_map = {"itm": "In-the-money", "atm": "At-the-money", "otm": "Out-of-the-money"}
    reasons.append(
        f"{position_map.get(recommendation.position, recommendation.position)} {recommendation.option_type}"
    )

    # Risk/reward context
    if recommendation.risk_reward_ratio is not None:
        if recommendation.risk_reward_ratio >= Decimal("1.5"):
            reasons.append(f"Attractive R:R of {recommendation.risk_reward_ratio:.2f}:1")
        else:
            reasons.append(f"R:R {recommendation.risk_reward_ratio:.2f}:1")

    # POP context
    if recommendation.pop_proxy is not None:
        if recommendation.pop_proxy >= Decimal("60"):
            reasons.append(f"High probability setup (~{recommendation.pop_proxy:.0f}% POP)")
        elif recommendation.pop_proxy >= Decimal("40"):
            reasons.append(f"Moderate probability (~{recommendation.pop_proxy:.0f}% POP)")
        else:
            reasons.append(
                f"Lower probability, higher reward (~{recommendation.pop_proxy:.0f}% POP)"
            )

    # Credit quality for credit spreads
    if strategy_family == StrategyFamily.VERTICAL_CREDIT and recommendation.is_credit:
        if recommendation.width_dollars and recommendation.width_dollars > 0:
            credit_pct = (
                abs(recommendation.net_premium or 0) / recommendation.width_dollars
            ) * Decimal(100)
            if credit_pct >= Decimal("30"):
                reasons.append(f"Strong credit collection ({credit_pct:.0f}% of width)")
            else:
                reasons.append(f"Credit: {credit_pct:.0f}% of spread width")

    # Width efficiency
    if recommendation.width_points is not None:
        reasons.append(
            f"${recommendation.width_points:.0f} spread width for {recommendation.position.upper()}"
        )

    # Liquidity
    if recommendation.avg_open_interest is not None and recommendation.avg_open_interest >= 100:
        reasons.append(f"Good liquidity (OI: {recommendation.avg_open_interest})")

    return reasons


def recommend_strategies(
    contracts: list[OptionContractData],
    underlying_symbol: str,
    underlying_price: Decimal,
    bias: str,
    dte: int,
    iv_rank: Decimal | None = None,
    target_move_pct: Decimal | None = None,
    objectives: StrategyObjectives | None = None,
    constraints: StrategyConstraints | None = None,
    scoring_weights: ScoringWeights | None = None,
    data_timestamp: datetime | None = None,
) -> StrategyRecommendationResult:
    """
    Generate ranked strategy recommendations.

    Args:
        contracts: Available option contracts
        underlying_symbol: Ticker symbol
        underlying_price: Current underlying price
        bias: Directional bias
        dte: Days to expiration
        iv_rank: IV percentile (0-100)
        target_move_pct: Expected move as % of price
        objectives: Trading objectives
        constraints: Strategy constraints
        scoring_weights: Scoring weights (uses defaults if None)
        data_timestamp: Data timestamp

    Returns:
        StrategyRecommendationResult with ranked recommendations
    """
    warnings = []

    # Use default weights if not provided
    if scoring_weights is None:
        scoring_weights = ScoringWeights()

    # Determine IV regime
    iv_regime_override = constraints.iv_regime_override if constraints else None
    if iv_regime_override:
        iv_regime = IVRegime(iv_regime_override)
        warnings.append(f"Using overridden IV regime: {iv_regime.value}")
    else:
        iv_regime = determine_iv_regime(iv_rank)

    # Select strategy family
    strategy_family, option_type, strategy_reason = select_strategy_family(
        iv_regime, bias, objectives
    )

    # Apply DTE preferences (Phase 3.4: Capital efficiency)
    account_size = objectives.account_size if objectives else None
    strategy_family, option_type, strategy_reason = apply_dte_preferences(
        strategy_family, option_type, dte, account_size, bias, strategy_reason
    )

    # Add bias context (Phase 3.5: ICT setup context)
    bias_reason = objectives.bias_reason if objectives else "user_manual"
    bias_context = get_bias_context_reasoning(bias_reason, bias, strategy_family)
    if bias_context:
        strategy_reason = bias_context + strategy_reason

    # Get spread width
    max_width = constraints.max_spread_width if constraints else None
    spread_width = get_spread_width_for_price(underlying_price, max_width=max_width)

    # Generate candidates based on strategy family
    recommendations = []

    if strategy_family in (StrategyFamily.VERTICAL_CREDIT, StrategyFamily.VERTICAL_DEBIT):
        # Get spread candidates
        min_credit = constraints.min_credit_pct if constraints else None
        spread_candidates = recommend_vertical_spreads(
            contracts,
            underlying_price,
            option_type,
            bias,
            spread_width,
            min_credit_pct=min_credit,
            iv_regime=iv_regime,
            apply_liquidity_filter=True,
        )

        # Convert to recommendations
        for candidate in spread_candidates:
            rec = StrategyRecommendation(
                rank=0,  # Will be set after scoring
                strategy_family=strategy_family,
                option_type=option_type,
                position=candidate.position.value,
                long_strike=candidate.long_strike,
                short_strike=candidate.short_strike,
                long_premium=candidate.long_premium,
                short_premium=candidate.short_premium,
                net_premium=candidate.net_premium,
                is_credit=candidate.is_credit,
                net_credit=candidate.net_credit,
                net_debit=candidate.net_debit,
                width_points=candidate.width_points,
                width_dollars=candidate.width_dollars,
                breakeven=candidate.breakeven,
                max_profit=candidate.max_profit,
                max_loss=candidate.max_loss,
                risk_reward_ratio=candidate.risk_reward_ratio,
                pop_proxy=candidate.pop_proxy,
                long_delta=candidate.long_delta,
                short_delta=candidate.short_delta,
            )

            # Calculate avg liquidity (simple average of both legs)
            if candidate.position:
                # Placeholder - would need actual contract OI/volume
                rec.avg_open_interest = 100
                rec.avg_volume = 50

            # Position sizing if account size provided
            if objectives and objectives.account_size:
                risk_pct = Decimal("2.0")  # Default 2% risk
                max_risk = objectives.account_size * (risk_pct / Decimal(100))
                contracts_count = int(max_risk / rec.max_loss) if rec.max_loss > 0 else 1
                rec.recommended_contracts = max(1, contracts_count)
                rec.position_size_dollars = rec.max_loss * Decimal(rec.recommended_contracts)

            recommendations.append(rec)

    elif strategy_family in (StrategyFamily.LONG_CALL, StrategyFamily.LONG_PUT):
        # Get long option candidates
        long_candidates = recommend_long_options(
            contracts,
            underlying_price,
            option_type,
        )

        # Convert to recommendations
        for candidate in long_candidates:
            rec = StrategyRecommendation(
                rank=0,
                strategy_family=strategy_family,
                option_type=option_type,
                position=candidate.position.value,
                strike=candidate.strike,
                premium=candidate.premium,
                breakeven=candidate.breakeven,
                max_profit=candidate.max_profit,
                max_loss=candidate.max_loss,
                risk_reward_ratio=(
                    candidate.max_profit / candidate.max_loss
                    if candidate.max_profit and candidate.max_loss > 0
                    else None
                ),
                pop_proxy=candidate.pop_proxy,
                delta=candidate.delta,
            )

            # Position sizing if account size provided
            if objectives and objectives.account_size:
                risk_pct = Decimal("2.0")
                max_risk = objectives.account_size * (risk_pct / Decimal(100))
                contracts_count = int(max_risk / rec.max_loss) if rec.max_loss > 0 else 1
                rec.recommended_contracts = max(1, contracts_count)
                rec.position_size_dollars = rec.max_loss * Decimal(rec.recommended_contracts)

            recommendations.append(rec)

    # Filter by constraints
    filtered_recommendations = []
    rejected_count = 0
    for rec in recommendations:
        passes, constraint_warnings = apply_constraints(rec, constraints, objectives)
        if passes:
            filtered_recommendations.append(rec)
        else:
            # Don't include failed candidates in final results
            rejected_count += 1

    if rejected_count > 0:
        warnings.append(f"{rejected_count} candidate(s) rejected due to constraint violations")

    # Score and rank
    for rec in filtered_recommendations:
        rec.composite_score = calculate_composite_score(rec, scoring_weights, strategy_family)
        rec.reasons = build_reasoning(rec, strategy_family, iv_regime, bias, strategy_reason)

    # Sort by score (descending)
    filtered_recommendations.sort(key=lambda r: r.composite_score, reverse=True)

    # Assign ranks
    for i, rec in enumerate(filtered_recommendations):
        rec.rank = i + 1

    # Take top 2-3
    top_recommendations = filtered_recommendations[:3]

    if not top_recommendations:
        warnings.append(f"No candidates met constraints for {strategy_family.value}")

    # Build config used
    config_used = {
        "iv_high_threshold": float(settings.IV_HIGH_THRESHOLD),
        "iv_low_threshold": float(settings.IV_LOW_THRESHOLD),
        "min_credit_pct": (
            float(constraints.min_credit_pct)
            if constraints and constraints.min_credit_pct
            else float(settings.MIN_CREDIT_PCT * 100)
        ),
        "spread_width": spread_width,
        "scoring_weights": {
            "pop": float(scoring_weights.pop_weight),
            "rr": float(scoring_weights.rr_weight),
            "credit": float(scoring_weights.credit_weight),
            "liquidity": float(scoring_weights.liquidity_weight),
            "width_efficiency": float(scoring_weights.width_efficiency_weight),
        },
    }

    return StrategyRecommendationResult(
        underlying_symbol=underlying_symbol,
        underlying_price=underlying_price,
        chosen_strategy_family=strategy_family,
        iv_rank=iv_rank,
        iv_regime=iv_regime.value if iv_regime else None,
        dte=dte,
        expected_move_pct=target_move_pct,
        data_timestamp=data_timestamp or datetime.utcnow(),
        recommendations=top_recommendations,
        config_used=config_used,
        warnings=warnings,
    )
