"""
Discord Command Handlers (Placeholder for Phase 8)
Provides bridge functions to integrate trade planner with Discord commands.
"""

from decimal import Decimal
from typing import Optional

from app.core.trade_planner import (
    calculate_vertical_spread,
    calculate_long_option,
    calculate_position_size,
    TradeBias,
    StrategyCalculationResult,
)


async def handle_plan_vertical_spread(
    underlying_symbol: str,
    underlying_price: Decimal,
    long_strike: Decimal,
    short_strike: Decimal,
    long_premium: Decimal,
    short_premium: Decimal,
    option_type: str,
    bias: str,
    contracts: int = 1,
    dte: Optional[int] = None,
) -> StrategyCalculationResult:
    """
    Handle /plan command for vertical spreads from Discord.

    This function serves as a bridge between Discord slash commands
    and the core calculation engine. In Phase 8, this will be wired
    to Discord bot slash command handlers.

    Args:
        underlying_symbol: Ticker symbol
        underlying_price: Current spot price
        long_strike: Strike of the long option
        short_strike: Strike of the short option
        long_premium: Premium paid for long option
        short_premium: Premium received for short option
        option_type: "call" or "put"
        bias: Directional bias ("bullish", "bearish", "neutral")
        contracts: Number of contracts
        dte: Days to expiration

    Returns:
        StrategyCalculationResult with all metrics

    Example Discord command (Phase 8):
        /plan vertical SPY 450 445/450 call 7.50/3.00 bullish 30
    """
    result = calculate_vertical_spread(
        underlying_symbol=underlying_symbol.upper(),
        underlying_price=underlying_price,
        long_strike=long_strike,
        short_strike=short_strike,
        long_premium=long_premium,
        short_premium=short_premium,
        option_type=option_type.lower(),
        bias=TradeBias(bias.lower()),
        contracts=contracts,
        dte=dte,
    )

    return result


async def handle_plan_long_option(
    underlying_symbol: str,
    underlying_price: Decimal,
    strike: Decimal,
    premium: Decimal,
    option_type: str,
    bias: str,
    contracts: int = 1,
    dte: Optional[int] = None,
) -> StrategyCalculationResult:
    """
    Handle /plan command for long options (calls/puts) from Discord.

    This function serves as a bridge between Discord slash commands
    and the core calculation engine. In Phase 8, this will be wired
    to Discord bot slash command handlers.

    Args:
        underlying_symbol: Ticker symbol
        underlying_price: Current spot price
        strike: Strike price
        premium: Premium paid per contract
        option_type: "call" or "put"
        bias: Directional bias ("bullish" or "bearish")
        contracts: Number of contracts
        dte: Days to expiration

    Returns:
        StrategyCalculationResult with all metrics

    Example Discord command (Phase 8):
        /plan long AAPL 175 180 call 3.50 bullish 45
    """
    result = calculate_long_option(
        underlying_symbol=underlying_symbol.upper(),
        underlying_price=underlying_price,
        strike=strike,
        premium=premium,
        option_type=option_type.lower(),
        bias=TradeBias(bias.lower()),
        contracts=contracts,
        dte=dte,
    )

    return result


def format_calculation_for_discord(result: StrategyCalculationResult) -> str:
    """
    Format calculation result as a Discord embed-friendly string.

    This will be used in Phase 8 to generate Discord embeds for trade plans.

    Args:
        result: Calculation result from trade planner

    Returns:
        Formatted string for Discord display

    Example output:
        **Strategy:** Bull Call Spread (Vertical Debit)
        **Ticker:** SPY @ $450.00
        **Bias:** Bullish

        **Position:**
        • Long 445 Call @ $7.50 (1 contract)
        • Short 450 Call @ $3.00 (1 contract)

        **Risk/Reward:**
        • Max Profit: $50.00
        • Max Loss: $450.00
        • Breakeven: $449.50
        • R:R Ratio: 0.11

        **Position Size:** 1 contract ($450 at risk)
        **Win Probability:** ~20% (delta-based estimate)
    """
    lines = []

    # Header
    strategy_name = result.strategy_type.replace("_", " ").title()
    lines.append(f"**Strategy:** {strategy_name}")
    lines.append(f"**Ticker:** {result.underlying_symbol} @ ${result.underlying_price}")
    lines.append(f"**Bias:** {result.bias.title()}")
    lines.append("")

    # Position structure
    lines.append("**Position:**")
    for leg in result.legs:
        position = leg["position"].title()
        strike = leg["strike"]
        premium = leg["premium"]
        opt_type = leg["option_type"].title()
        contracts = leg["contracts"]
        lines.append(
            f"• {position} {strike} {opt_type} @ ${premium} ({contracts} contract{'s' if contracts > 1 else ''})"
        )
    lines.append("")

    # Risk/Reward metrics
    lines.append("**Risk/Reward:**")
    lines.append(f"• Max Profit: ${result.max_profit:.2f}")
    lines.append(f"• Max Loss: ${result.max_loss:.2f}")

    breakevens = ", ".join([f"${be:.2f}" for be in result.breakeven_prices])
    lines.append(f"• Breakeven: {breakevens}")
    lines.append(f"• R:R Ratio: {result.risk_reward_ratio:.2f}")
    lines.append("")

    # Position sizing & probability
    lines.append(
        f"**Position Size:** {result.position_size_contracts} contract{'s' if result.position_size_contracts > 1 else ''} (${result.position_size_dollars:.2f} at risk)"
    )

    if result.win_probability:
        lines.append(f"**Win Probability:** ~{result.win_probability:.0f}% (delta-based estimate)")

    if result.dte:
        lines.append(f"**DTE:** {result.dte} days")

    return "\n".join(lines)


# TODO: Phase 8 integration points
# 1. Wire handle_plan_vertical_spread to Discord /plan vertical command
# 2. Wire handle_plan_long_option to Discord /plan long command
# 3. Use format_calculation_for_discord to generate Discord embeds
# 4. Add interactive buttons for "Save to DB" and "Adjust Position"
# 5. Implement /size command using calculate_position_size
