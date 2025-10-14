"""
Trade Planning & Strategy Calculation Engine
Provides core calculations for vertical spreads and long options.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class StrategyType(str, Enum):
    """Supported strategy types for calculation."""

    VERTICAL_DEBIT = "vertical_debit"
    VERTICAL_CREDIT = "vertical_credit"
    LONG_CALL = "long_call"
    LONG_PUT = "long_put"


class TradeBias(str, Enum):
    """Directional bias."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class LegInput:
    """Represents a single option leg."""

    strike: Decimal
    premium: Decimal
    option_type: str  # "call" or "put"
    position: str  # "long" or "short"
    contracts: int = 1


@dataclass
class StrategyCalculationResult:
    """Output of strategy calculation."""

    strategy_type: str
    bias: str
    underlying_symbol: str
    underlying_price: Decimal

    # Position structure
    legs: list[dict]

    # Risk metrics
    max_profit: Optional[Decimal]  # None for unlimited (long calls)
    max_loss: Decimal
    breakeven_prices: list[Decimal]
    risk_reward_ratio: Optional[Decimal]  # None if max_profit is unlimited

    # Probability proxy (delta-based)
    win_probability: Optional[Decimal]

    # Position sizing (risk-based recommendations)
    recommended_contracts: int  # Based on account size & risk %
    position_size_dollars: Decimal  # Dollar risk (max_loss * recommended_contracts)

    # Metadata
    net_premium: Decimal  # debit (positive) or credit (negative)
    net_credit: Optional[Decimal]  # For credit spreads, the credit received
    dte: Optional[int]
    total_delta: Optional[Decimal]

    assumptions: dict


def calculate_vertical_spread(
    underlying_symbol: str,
    underlying_price: Decimal,
    long_strike: Decimal,
    short_strike: Decimal,
    long_premium: Decimal,
    short_premium: Decimal,
    option_type: str,  # "call" or "put"
    bias: TradeBias,
    contracts: int = 1,
    dte: Optional[int] = None,
    long_delta: Optional[Decimal] = None,
    short_delta: Optional[Decimal] = None,
    account_size: Optional[Decimal] = None,
    risk_percentage: Decimal = Decimal("2.0"),
) -> StrategyCalculationResult:
    """
    Calculate risk/reward for a vertical spread (debit or credit).

    Args:
        underlying_symbol: Ticker symbol
        underlying_price: Current spot price
        long_strike: Strike of the long option
        short_strike: Strike of the short option
        long_premium: Premium paid for long option
        short_premium: Premium received for short option
        option_type: "call" or "put"
        bias: Directional bias
        contracts: Number of contracts (default 1)
        dte: Days to expiration
        long_delta: Delta of the long option (optional, for probability proxy)
        short_delta: Delta of the short option (optional)

    Returns:
        StrategyCalculationResult with all computed metrics
    """
    net_premium = (long_premium - short_premium) * Decimal(contracts) * Decimal(100)
    spread_width = abs(long_strike - short_strike) * Decimal(contracts) * Decimal(100)

    # Determine if debit or credit spread
    is_debit = net_premium > 0
    strategy_type = StrategyType.VERTICAL_DEBIT if is_debit else StrategyType.VERTICAL_CREDIT

    # Risk/Reward calculation
    if is_debit:
        # Debit spread: loss = premium paid, profit = spread_width - premium
        max_loss = net_premium
        max_profit = spread_width - net_premium
    else:
        # Credit spread: profit = premium received, loss = spread_width - premium
        max_profit = abs(net_premium)
        max_loss = spread_width - abs(net_premium)

    # Risk/reward ratio
    risk_reward_ratio = max_profit / max_loss if max_loss != 0 else Decimal(0)

    # Breakeven calculation
    if option_type == "call":
        if is_debit:
            # Bull call spread: BE = long_strike + net_debit_per_contract
            breakeven = long_strike + (net_premium / (Decimal(contracts) * Decimal(100)))
        else:
            # Bear call spread: BE = short_strike + net_credit_per_contract
            breakeven = short_strike + (abs(net_premium) / (Decimal(contracts) * Decimal(100)))
    else:  # put
        if is_debit:
            # Bear put spread: BE = long_strike - net_debit_per_contract
            breakeven = long_strike - (net_premium / (Decimal(contracts) * Decimal(100)))
        else:
            # Bull put spread: BE = short_strike - net_credit_per_contract
            breakeven = short_strike - (abs(net_premium) / (Decimal(contracts) * Decimal(100)))

    breakeven_prices = [breakeven]

    # Win probability proxy using delta
    win_probability = None
    total_delta = None
    if long_delta is not None and short_delta is not None:
        # Net delta approximates probability of profit
        total_delta = (long_delta - short_delta) * Decimal(contracts)
        # Rough probability: for debit spreads, higher abs(delta) = higher win chance
        # For credit spreads, we use (1 - abs(net_delta)) as proxy
        if is_debit:
            win_probability = abs(total_delta) * Decimal(100)  # Convert to percentage
        else:
            win_probability = (Decimal(1) - abs(total_delta)) * Decimal(100)

    # Calculate risk-based position sizing
    if account_size is not None:
        # Calculate recommended contracts based on risk management
        max_loss_per_contract = max_loss / Decimal(contracts)
        recommended_contracts = calculate_position_size(
            max_loss=max_loss_per_contract,
            account_size=account_size,
            risk_percentage=risk_percentage,
        )
        position_dollars = max_loss_per_contract * Decimal(recommended_contracts)
    else:
        # Use the requested contracts if no account size provided
        recommended_contracts = contracts
        position_dollars = max_loss

    # Build leg structure
    legs = [
        {
            "strike": float(long_strike),
            "premium": float(long_premium),
            "option_type": option_type,
            "position": "long",
            "contracts": contracts,
        },
        {
            "strike": float(short_strike),
            "premium": float(short_premium),
            "option_type": option_type,
            "position": "short",
            "contracts": contracts,
        },
    ]

    return StrategyCalculationResult(
        strategy_type=strategy_type.value,
        bias=bias.value,
        underlying_symbol=underlying_symbol,
        underlying_price=underlying_price,
        legs=legs,
        max_profit=max_profit,
        max_loss=max_loss,
        breakeven_prices=breakeven_prices,
        risk_reward_ratio=risk_reward_ratio,
        win_probability=win_probability,
        recommended_contracts=recommended_contracts,
        position_size_dollars=position_dollars,
        net_premium=net_premium,
        net_credit=abs(net_premium) if not is_debit else None,
        dte=dte,
        total_delta=total_delta,
        assumptions={
            "spread_width": float(spread_width),
            "is_debit_spread": is_debit,
            "multiplier": 100,
            "max_loss_per_contract": float(max_loss / Decimal(contracts)),
        },
    )


def calculate_long_option(
    underlying_symbol: str,
    underlying_price: Decimal,
    strike: Decimal,
    premium: Decimal,
    option_type: str,  # "call" or "put"
    bias: TradeBias,
    contracts: int = 1,
    dte: Optional[int] = None,
    delta: Optional[Decimal] = None,
    account_size: Optional[Decimal] = None,
    risk_percentage: Decimal = Decimal("2.0"),
) -> StrategyCalculationResult:
    """
    Calculate risk/reward for a long call or long put.

    Args:
        underlying_symbol: Ticker symbol
        underlying_price: Current spot price
        strike: Strike price of the option
        premium: Premium paid per contract
        option_type: "call" or "put"
        bias: Directional bias (bullish for call, bearish for put)
        contracts: Number of contracts (default 1)
        dte: Days to expiration
        delta: Delta of the option (optional, for probability proxy)
        account_size: Total account size for position sizing (optional)
        risk_percentage: Risk percentage for position sizing (default 2%)

    Returns:
        StrategyCalculationResult with all computed metrics
    """
    net_premium = premium * Decimal(contracts) * Decimal(100)

    strategy_type = StrategyType.LONG_CALL if option_type == "call" else StrategyType.LONG_PUT

    # Risk/Reward calculation
    max_loss = net_premium  # Limited to premium paid

    # Max profit calculation
    if option_type == "call":
        # Calls have theoretically unlimited profit potential
        max_profit = None
        risk_reward_ratio = None
    else:
        # Puts: max profit = (strike - premium) * 100 * contracts
        # (max profit occurs if stock goes to $0)
        max_profit = (strike - premium) * Decimal(100) * Decimal(contracts)
        risk_reward_ratio = max_profit / max_loss if max_loss != 0 else Decimal(0)

    # Breakeven calculation
    if option_type == "call":
        breakeven = strike + premium
    else:
        breakeven = strike - premium

    breakeven_prices = [breakeven]

    # Win probability proxy using delta
    win_probability = None
    if delta is not None:
        # For long options, abs(delta) is a rough probability proxy
        win_probability = abs(delta) * Decimal(100)  # Convert to percentage

    # Calculate risk-based position sizing
    if account_size is not None:
        # Calculate recommended contracts based on risk management
        max_loss_per_contract = max_loss / Decimal(contracts)
        recommended_contracts = calculate_position_size(
            max_loss=max_loss_per_contract,
            account_size=account_size,
            risk_percentage=risk_percentage,
        )
        position_dollars = max_loss_per_contract * Decimal(recommended_contracts)
    else:
        # Use the requested contracts if no account size provided
        recommended_contracts = contracts
        position_dollars = max_loss

    # Build leg structure
    legs = [
        {
            "strike": float(strike),
            "premium": float(premium),
            "option_type": option_type,
            "position": "long",
            "contracts": contracts,
        },
    ]

    return StrategyCalculationResult(
        strategy_type=strategy_type.value,
        bias=bias.value,
        underlying_symbol=underlying_symbol,
        underlying_price=underlying_price,
        legs=legs,
        max_profit=max_profit,
        max_loss=max_loss,
        breakeven_prices=breakeven_prices,
        risk_reward_ratio=risk_reward_ratio,
        win_probability=win_probability,
        recommended_contracts=recommended_contracts,
        position_size_dollars=position_dollars,
        net_premium=net_premium,
        net_credit=None,
        dte=dte,
        total_delta=delta * Decimal(contracts) if delta else None,
        assumptions={
            "max_profit_note": "Unlimited for calls, (strike - premium) * 100 * contracts for puts",
            "multiplier": 100,
            "max_loss_per_contract": float(max_loss / Decimal(contracts)),
        },
    )


def calculate_position_size(
    max_loss: Decimal,
    account_size: Decimal,
    risk_percentage: Decimal = Decimal("2.0"),
) -> int:
    """
    Calculate position size in contracts based on risk management rules.

    Args:
        max_loss: Maximum loss per contract (in dollars)
        account_size: Total account size
        risk_percentage: Maximum risk as % of account (default 2%)

    Returns:
        Number of contracts to trade
    """
    max_risk_dollars = account_size * (risk_percentage / Decimal(100))

    if max_loss <= 0:
        return 0

    # Calculate contracts based on risk
    contracts = int(max_risk_dollars / max_loss)

    # Minimum 1 contract if within risk tolerance
    return max(1, contracts) if contracts > 0 else 0
