"""
Strike Selection Engine
Recommends optimal strikes and widths for vertical spreads and long options.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from datetime import datetime

from app.config import settings


class StrikePosition(str, Enum):
    """Strike position relative to underlying."""
    ITM = "itm"  # In the money
    ATM = "atm"  # At the money
    OTM = "otm"  # Out of the money


class IVRegime(str, Enum):
    """Implied volatility regime classification."""
    HIGH = "high"      # IV Rank > 50
    NEUTRAL = "neutral"  # IV Rank 25-50
    LOW = "low"       # IV Rank < 25


@dataclass
class OptionContractData:
    """Data for a single option contract from database."""
    strike: Decimal
    option_type: str  # "call" or "put"
    bid: Optional[Decimal]
    ask: Optional[Decimal]
    mark: Optional[Decimal]
    delta: Optional[Decimal]
    implied_vol: Optional[Decimal]
    volume: Optional[int]
    open_interest: Optional[int]


@dataclass
class SpreadCandidate:
    """A candidate vertical spread recommendation."""
    position: StrikePosition
    long_strike: Decimal
    short_strike: Decimal
    long_premium: Decimal
    short_premium: Decimal
    net_premium: Decimal  # Negative for credits, positive for debits
    is_credit: bool  # True if credit spread
    net_credit: Optional[Decimal]  # Positive credit received (credit spreads only)
    net_debit: Optional[Decimal]  # Positive debit paid (debit spreads only)
    width_points: Decimal  # Spread width in strike points
    width_dollars: Decimal  # Spread width in dollars (width_points × 100)
    spread_width: Decimal  # DEPRECATED: Use width_dollars
    breakeven: Decimal
    max_profit: Decimal
    max_loss: Decimal
    risk_reward_ratio: Decimal
    pop_proxy: Optional[Decimal]  # Delta-based probability
    long_delta: Optional[Decimal]
    short_delta: Optional[Decimal]
    quality_score: Optional[Decimal] = None  # Composite ranking score
    notes: List[str] = field(default_factory=list)


@dataclass
class LongOptionCandidate:
    """A candidate long option recommendation."""
    position: StrikePosition
    strike: Decimal
    premium: Decimal
    breakeven: Decimal
    max_loss: Decimal
    max_profit: Optional[Decimal]  # None for calls
    delta: Optional[Decimal]
    pop_proxy: Optional[Decimal]
    notes: List[str]


@dataclass
class StrikeRecommendation:
    """Complete recommendation result."""
    underlying_symbol: str
    underlying_price: Decimal
    strategy_type: str
    bias: str
    dte: int
    iv_rank: Optional[Decimal]
    iv_regime: Optional[str]
    candidates: List[SpreadCandidate | LongOptionCandidate]
    data_timestamp: datetime
    warnings: List[str]


def determine_iv_regime(iv_rank: Optional[Decimal]) -> Optional[IVRegime]:
    """
    Classify IV regime based on IV Rank using configurable thresholds.

    Args:
        iv_rank: IV Rank as percentage (0-100)

    Returns:
        IVRegime classification or None if iv_rank is None
    """
    if iv_rank is None:
        return None

    if iv_rank > settings.IV_HIGH_THRESHOLD:
        return IVRegime.HIGH
    elif iv_rank >= settings.IV_LOW_THRESHOLD:
        return IVRegime.NEUTRAL
    else:
        return IVRegime.LOW


def get_spread_width_for_price(
    underlying_price: Decimal,
    min_width: Optional[int] = None,
    max_width: Optional[int] = None,
) -> int:
    """
    Determine appropriate spread width based on underlying price using config settings.

    Args:
        underlying_price: Current price of underlying
        min_width: Minimum spread width override (uses config if None)
        max_width: Maximum spread width override (uses config if None)

    Returns:
        Recommended spread width in points

    Logic:
        - Low-priced (< $100): 2-5 wide
        - Mid-priced ($100-300): 5 wide
        - High-priced (> $300): 5-10 wide
    """
    if underlying_price < Decimal("100"):
        default_width = settings.SPREAD_WIDTH_LOW_PRICE_MAX
        if max_width is not None:
            return min(default_width, max_width)
        return default_width
    elif underlying_price < Decimal("300"):
        return settings.SPREAD_WIDTH_MID_PRICE
    else:
        default_width = settings.SPREAD_WIDTH_HIGH_PRICE_MAX
        if max_width is not None:
            return min(default_width, max_width)
        return default_width


def calculate_spread_metrics(
    long_strike: Decimal,
    short_strike: Decimal,
    long_premium: Decimal,
    short_premium: Decimal,
    option_type: str,
    long_delta: Optional[Decimal] = None,
    short_delta: Optional[Decimal] = None,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Optional[Decimal]]:
    """
    Calculate key metrics for a vertical spread.

    Returns:
        (net_premium, breakeven, max_profit, max_loss, risk_reward, pop_proxy)
    """
    net_premium = (long_premium - short_premium) * Decimal(100)
    spread_width = abs(long_strike - short_strike) * Decimal(100)

    is_debit = net_premium > 0

    if is_debit:
        max_loss = net_premium
        max_profit = spread_width - net_premium
    else:
        max_profit = abs(net_premium)
        max_loss = spread_width - abs(net_premium)

    risk_reward = max_profit / max_loss if max_loss > 0 else Decimal(0)

    # Breakeven calculation
    if option_type == "call":
        if is_debit:
            breakeven = long_strike + (net_premium / Decimal(100))
        else:
            breakeven = short_strike + (abs(net_premium) / Decimal(100))
    else:  # put
        if is_debit:
            breakeven = long_strike - (net_premium / Decimal(100))
        else:
            breakeven = short_strike - (abs(net_premium) / Decimal(100))

    # POP proxy from deltas
    pop_proxy = None
    if long_delta is not None and short_delta is not None:
        net_delta = abs(long_delta - short_delta)
        if is_debit:
            pop_proxy = net_delta * Decimal(100)
        else:
            pop_proxy = (Decimal(1) - net_delta) * Decimal(100)

    return net_premium, breakeven, max_profit, max_loss, risk_reward, pop_proxy


def passes_liquidity_filter(
    contract: OptionContractData,
    min_open_interest: Optional[int] = None,
    min_volume: Optional[int] = None,
    min_mark: Optional[Decimal] = None,
) -> tuple[bool, List[str]]:
    """
    Check if a contract passes liquidity filters.

    Args:
        contract: Option contract to check
        min_open_interest: Minimum open interest (uses config if None)
        min_volume: Minimum volume (uses config if None)
        min_mark: Minimum mark price (uses config if None)

    Returns:
        (passes, warnings) tuple
    """
    warnings = []

    # Use config defaults if not specified
    if min_open_interest is None:
        min_open_interest = settings.MIN_OPEN_INTEREST
    if min_volume is None:
        min_volume = settings.MIN_VOLUME
    if min_mark is None:
        min_mark = Decimal(str(settings.MIN_MARK_PRICE))

    # Check mark price
    if contract.mark is None or contract.mark < min_mark:
        warnings.append(f"Mark ${contract.mark or 0:.2f} < ${min_mark}")
        return False, warnings

    # Check open interest
    if contract.open_interest is not None and contract.open_interest < min_open_interest:
        warnings.append(f"OI {contract.open_interest} < {min_open_interest}")
        return False, warnings

    # Check volume
    if contract.volume is not None and contract.volume < min_volume:
        warnings.append(f"Volume {contract.volume} < {min_volume}")
        return False, warnings

    return True, warnings


def calculate_quality_score(
    candidate: SpreadCandidate,
    iv_regime: Optional[IVRegime] = None,
) -> Decimal:
    """
    Calculate composite quality score for ranking spread candidates.

    Args:
        candidate: Spread candidate to score
        iv_regime: Current IV regime (affects weighting)

    Returns:
        Quality score (higher is better, 0-100 scale)

    Scoring factors:
        - Risk/reward ratio (weight: 40%)
        - POP proxy (weight: 30%)
        - Credit % of width for credits (weight: 20%)
        - ATM preference (weight: 10%)
    """
    score = Decimal(0)

    # Risk/reward (40 points max, normalize to 0-10 scale)
    rr_score = min(candidate.risk_reward_ratio * Decimal(4), Decimal(10))
    score += rr_score * Decimal(4)

    # POP proxy (30 points max)
    if candidate.pop_proxy is not None:
        score += (candidate.pop_proxy / Decimal(100)) * Decimal(30)

    # Credit quality (20 points max) - for credit spreads only
    if candidate.is_credit and candidate.width_dollars > 0:
        credit_pct = (abs(candidate.net_premium) / candidate.width_dollars) * Decimal(100)
        credit_score = min(credit_pct / Decimal(5), Decimal(10))  # Normalize 0-50% to 0-10
        score += credit_score * Decimal(2)
    else:
        # For debit spreads, reward lower cost relative to max profit
        if candidate.max_profit > 0:
            cost_efficiency = (candidate.max_profit / candidate.max_loss) / Decimal(5)
            score += min(cost_efficiency, Decimal(1)) * Decimal(20)

    # Position preference (10 points max) - prefer ATM
    if candidate.position == StrikePosition.ATM:
        score += Decimal(10)
    elif candidate.position == StrikePosition.OTM:
        score += Decimal(5)
    # ITM gets 0

    return min(score, Decimal(100))


def classify_strike_position(
    strike: Decimal,
    underlying_price: Decimal,
    option_type: str,
    atm_threshold: Optional[Decimal] = None,
) -> StrikePosition:
    """
    Classify a strike as ITM, ATM, or OTM.

    Args:
        strike: Option strike price
        underlying_price: Current underlying price
        option_type: "call" or "put"
        atm_threshold: Distance (%) from spot to consider ATM (uses config if None)

    Returns:
        StrikePosition classification
    """
    if atm_threshold is None:
        atm_threshold = Decimal(str(settings.ATM_THRESHOLD_PCT))

    pct_diff = abs((strike - underlying_price) / underlying_price) * Decimal(100)

    if pct_diff <= atm_threshold:
        return StrikePosition.ATM

    if option_type == "call":
        return StrikePosition.ITM if strike < underlying_price else StrikePosition.OTM
    else:  # put
        return StrikePosition.ITM if strike > underlying_price else StrikePosition.OTM


def find_nearest_strikes(
    contracts: List[OptionContractData],
    underlying_price: Decimal,
    option_type: str,
    positions: List[StrikePosition] = [StrikePosition.ITM, StrikePosition.ATM, StrikePosition.OTM],
) -> dict[StrikePosition, Optional[OptionContractData]]:
    """
    Find the nearest strikes for each requested position.

    Args:
        contracts: List of available option contracts
        underlying_price: Current underlying price
        option_type: "call" or "put"
        positions: List of positions to find

    Returns:
        Dict mapping position to nearest contract
    """
    result = {pos: None for pos in positions}

    # Filter by option type
    filtered = [c for c in contracts if c.option_type == option_type]

    if not filtered:
        return result

    # Sort by strike
    sorted_contracts = sorted(filtered, key=lambda c: c.strike)

    # Find ATM
    atm_contract = min(sorted_contracts, key=lambda c: abs(c.strike - underlying_price))
    if StrikePosition.ATM in positions:
        result[StrikePosition.ATM] = atm_contract

    # Find ITM
    if StrikePosition.ITM in positions:
        if option_type == "call":
            itm_contracts = [c for c in sorted_contracts if c.strike < underlying_price]
            if itm_contracts:
                result[StrikePosition.ITM] = max(itm_contracts, key=lambda c: c.strike)
        else:  # put
            itm_contracts = [c for c in sorted_contracts if c.strike > underlying_price]
            if itm_contracts:
                result[StrikePosition.ITM] = min(itm_contracts, key=lambda c: c.strike)

    # Find OTM
    if StrikePosition.OTM in positions:
        if option_type == "call":
            otm_contracts = [c for c in sorted_contracts if c.strike > underlying_price]
            if otm_contracts:
                result[StrikePosition.OTM] = min(otm_contracts, key=lambda c: c.strike)
        else:  # put
            otm_contracts = [c for c in sorted_contracts if c.strike < underlying_price]
            if otm_contracts:
                result[StrikePosition.OTM] = max(otm_contracts, key=lambda c: c.strike)

    return result


def recommend_vertical_spreads(
    contracts: List[OptionContractData],
    underlying_price: Decimal,
    option_type: str,
    bias: str,
    target_width: int,
    min_credit_pct: Optional[Decimal] = None,
    iv_regime: Optional[IVRegime] = None,
    apply_liquidity_filter: bool = True,
) -> List[SpreadCandidate]:
    """
    Recommend vertical spread candidates (ITM, ATM, OTM) with liquidity filtering and ranking.

    Args:
        contracts: Available option contracts
        underlying_price: Current underlying price
        option_type: "call" or "put"
        bias: "bullish", "bearish", or "neutral"
        target_width: Desired spread width in points
        min_credit_pct: Minimum credit as % of spread width (uses config if None)
        iv_regime: Current IV regime (for quality scoring)
        apply_liquidity_filter: Whether to apply liquidity filters

    Returns:
        List of spread candidates, sorted by quality score (best first)
    """
    if min_credit_pct is None:
        min_credit_pct = Decimal(str(settings.MIN_CREDIT_PCT * 100))  # Convert to percentage

    candidates = []
    positions = [StrikePosition.ITM, StrikePosition.ATM, StrikePosition.OTM]

    # Determine if debit or credit based on bias and option type
    is_debit_strategy = (
        (bias == "bullish" and option_type == "call") or
        (bias == "bearish" and option_type == "put")
    )

    for position in positions:
        # Find anchor strike based on position
        anchor_contracts = find_nearest_strikes(contracts, underlying_price, option_type, [position])
        anchor_contract = anchor_contracts.get(position)

        if not anchor_contract or not anchor_contract.mark:
            continue

        # Apply liquidity filter to anchor
        if apply_liquidity_filter:
            passes, warnings = passes_liquidity_filter(anchor_contract)
            if not passes:
                continue

        # Determine leg orientation based on strategy type
        if is_debit_strategy:
            # DEBIT: Buy nearer strike, sell farther strike
            # Bull call: Long 445, Short 450 → pay net debit
            # Bear put: Long 450, Short 445 → pay net debit
            if option_type == "call":
                target_other_strike = anchor_contract.strike + Decimal(target_width)
            else:  # put
                target_other_strike = anchor_contract.strike - Decimal(target_width)

            # For debit spreads: anchor is long, other is short
            long_strike_to_use = anchor_contract.strike
            long_premium_to_use = anchor_contract.mark
            long_delta_to_use = anchor_contract.delta

        else:
            # CREDIT: Sell nearer strike, buy farther strike
            # Bull put: Short 445, Long 440 → receive net credit
            # Bear call: Short 450, Long 455 → receive net credit
            if option_type == "call":
                target_other_strike = anchor_contract.strike + Decimal(target_width)
            else:  # put
                target_other_strike = anchor_contract.strike - Decimal(target_width)

            # For credit spreads: anchor is short, other is long
            # We'll swap after finding the other contract

        # Find the other strike
        eligible_contracts = [c for c in contracts if c.option_type == option_type and c.mark is not None]
        if apply_liquidity_filter:
            eligible_contracts = [c for c in eligible_contracts if passes_liquidity_filter(c)[0]]

        if not eligible_contracts:
            continue

        other_contract = min(
            eligible_contracts,
            key=lambda c: abs(c.strike - target_other_strike),
            default=None
        )

        if not other_contract or not other_contract.mark:
            continue

        # Check if strike distance is reasonable (within 20% of target width)
        actual_width = abs(other_contract.strike - anchor_contract.strike)
        if abs(actual_width - Decimal(target_width)) > Decimal(target_width) * Decimal("0.2"):
            continue  # Skip if strike spacing is too different from target

        # Assign long/short based on strategy type
        if is_debit_strategy:
            long_contract = anchor_contract
            short_contract = other_contract
        else:
            # For credit spreads, reverse the roles
            long_contract = other_contract
            short_contract = anchor_contract

        # Calculate metrics
        net_premium, breakeven, max_profit, max_loss, rr, pop = calculate_spread_metrics(
            long_contract.strike,
            short_contract.strike,
            long_contract.mark,
            short_contract.mark,
            option_type,
            long_contract.delta,
            short_contract.delta,
        )

        # Validation and notes
        notes = []
        is_credit = net_premium < 0
        width_points = abs(long_contract.strike - short_contract.strike)
        width_dollars = width_points * Decimal(100)

        # Calculate net_credit and net_debit for clarity
        net_credit = abs(net_premium) if is_credit else None
        net_debit = net_premium if not is_credit else None

        if is_credit:
            credit_pct = (abs(net_premium) / width_dollars) * Decimal(100)
            if credit_pct < min_credit_pct:
                notes.append(f"Credit {credit_pct:.1f}% < minimum {min_credit_pct}%")
                # Skip candidates that don't meet credit threshold
                continue

        # Add position context
        notes.append(f"{position.value.upper()} spread")

        if pop is not None:
            notes.append(f"~{pop:.0f}% POP")

        candidate = SpreadCandidate(
            position=position,
            long_strike=long_contract.strike,
            short_strike=short_contract.strike,
            long_premium=long_contract.mark,
            short_premium=short_contract.mark,
            net_premium=net_premium,
            is_credit=is_credit,
            net_credit=net_credit,
            net_debit=net_debit,
            width_points=width_points,
            width_dollars=width_dollars,
            spread_width=width_dollars,  # DEPRECATED
            breakeven=breakeven,
            max_profit=max_profit,
            max_loss=max_loss,
            risk_reward_ratio=rr,
            pop_proxy=pop,
            long_delta=long_contract.delta,
            short_delta=short_contract.delta,
            notes=notes,
        )

        # Calculate quality score
        candidate.quality_score = calculate_quality_score(candidate, iv_regime)

        candidates.append(candidate)

    # Sort by quality score (best first)
    candidates.sort(key=lambda c: c.quality_score or Decimal(0), reverse=True)

    return candidates


def recommend_long_options(
    contracts: List[OptionContractData],
    underlying_price: Decimal,
    option_type: str,
) -> List[LongOptionCandidate]:
    """
    Recommend long option candidates (ITM, ATM, OTM).

    Args:
        contracts: Available option contracts
        underlying_price: Current underlying price
        option_type: "call" or "put"

    Returns:
        List of long option candidates
    """
    candidates = []
    positions = [StrikePosition.ITM, StrikePosition.ATM, StrikePosition.OTM]

    strike_map = find_nearest_strikes(contracts, underlying_price, option_type, positions)

    for position, contract in strike_map.items():
        if not contract or not contract.mark:
            continue

        # Calculate metrics
        max_loss = contract.mark * Decimal(100)

        if option_type == "call":
            max_profit = None  # Unlimited
            breakeven = contract.strike + contract.mark
        else:  # put
            max_profit = (contract.strike - contract.mark) * Decimal(100)
            breakeven = contract.strike - contract.mark

        pop = contract.delta * Decimal(100) if contract.delta else None

        notes = [f"{position.value.upper()} {option_type}"]
        if pop:
            notes.append(f"~{pop:.0f}% POP")

        candidate = LongOptionCandidate(
            position=position,
            strike=contract.strike,
            premium=contract.mark,
            breakeven=breakeven,
            max_loss=max_loss,
            max_profit=max_profit,
            delta=contract.delta,
            pop_proxy=pop,
            notes=notes,
        )

        candidates.append(candidate)

    return candidates
