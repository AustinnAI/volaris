"""
Embed builders shared across Discord cogs.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import discord


def create_recommendation_embed(
    recommendation: dict[str, Any],
    symbol: str,
    underlying_price: float,
    iv_regime: str | None,
    chosen_strategy: str,
) -> discord.Embed:
    """Return a rich embed for a strategy recommendation."""
    rank = recommendation["rank"]
    strategy = recommendation["strategy_family"]
    position = recommendation["position"].upper()

    title = f"#{rank} {strategy.replace('_', ' ').title()} - {symbol} @ ${underlying_price:.2f}"
    color = discord.Color.green() if "credit" in strategy else discord.Color.blue()
    if "long" in strategy:
        color = discord.Color.gold()

    embed = discord.Embed(
        title=title,
        description=f"**IV Regime:** {iv_regime or 'N/A'} | **DTE:** {recommendation.get('dte', 'N/A')}",
        color=color,
    )

    if recommendation.get("long_strike"):
        long_strike = float(recommendation["long_strike"])
        short_strike = float(recommendation["short_strike"])
        embed.add_field(
            name="📊 Strikes",
            value=f"Long: **${long_strike:.2f}**\nShort: **${short_strike:.2f}**",
            inline=True,
        )
    elif recommendation.get("strike"):
        strike = float(recommendation["strike"])
        embed.add_field(
            name="📊 Strike",
            value=f"**${strike:.2f}** {position}",
            inline=True,
        )

    if recommendation.get("width_points"):
        width_pts = float(recommendation["width_points"])
        width_dollars = float(recommendation["width_dollars"])
        embed.add_field(
            name="📏 Width",
            value=f"**${width_pts:.0f}** pts (${width_dollars:.0f})",
            inline=True,
        )

    net_premium = float(recommendation.get("net_premium", 0))
    is_credit = recommendation.get("is_credit", False)

    if is_credit:
        net_credit = abs(net_premium)
        embed.add_field(name="💰 Credit", value=f"**${net_credit:.2f}**", inline=True)
    else:
        net_debit = net_premium
        embed.add_field(name="💸 Debit", value=f"**${net_debit:.2f}**", inline=True)

    max_profit = recommendation.get("max_profit")
    max_loss = float(recommendation.get("max_loss", 0))

    profit_str = f"${max_profit:.2f}" if max_profit else "Unlimited ♾️"
    embed.add_field(name="📈 Max Profit", value=f"**{profit_str}**", inline=True)
    embed.add_field(name="📉 Max Loss", value=f"**${max_loss:.2f}**", inline=True)

    rr = recommendation.get("risk_reward_ratio")
    if rr:
        embed.add_field(name="⚖️ R:R", value=f"**{float(rr):.2f}:1**", inline=True)

    pop = recommendation.get("pop_proxy")
    if pop:
        embed.add_field(name="🎯 POP", value=f"**{float(pop):.0f}%**", inline=True)

    rec_contracts = recommendation.get("recommended_contracts")
    pos_size = recommendation.get("position_size_dollars")
    if rec_contracts:
        size_text = f"**{rec_contracts}** contracts"
        if pos_size:
            size_text += f"\n(${float(pos_size):.2f} risk)"
        embed.add_field(name="📦 Size", value=size_text, inline=True)

    breakeven = float(recommendation.get("breakeven", 0))
    if breakeven > 0:
        embed.add_field(name="🎲 Breakeven", value=f"**${breakeven:.2f}**", inline=True)

    score = recommendation.get("composite_score")
    if score:
        embed.add_field(name="⭐ Score", value=f"**{float(score):.1f}/100**", inline=True)

    reasons: Iterable[str] = recommendation.get("reasons", [])
    if reasons:
        reason_text = "\n".join(f"• {reason}" for reason in list(reasons)[:4])
        if reason_text:
            embed.add_field(name="💡 Why This Trade", value=reason_text, inline=False)

    warnings: Iterable[str] = recommendation.get("warnings", [])
    if warnings:
        warning_text = "\n".join(f"⚠️ {warning}" for warning in list(warnings)[:2])
        if warning_text:
            embed.add_field(name="⚠️ Warnings", value=warning_text, inline=False)

    embed.set_footer(text=f"Volaris Strategy Planner • Rank #{rank}")
    return embed


def build_top_movers_embed(data: dict[str, Any], title: str = "Top Movers") -> discord.Embed:
    """Build an embed summarising S&P 500 top gainers and losers."""
    gainers = data.get("gainers", [])
    losers = data.get("losers", [])
    limit = data.get("limit") or len(gainers)

    def _format(entries: list[dict[str, Any]]) -> str:
        if not entries:
            return "No data"
        lines: list[str] = []
        for entry in entries:
            symbol = entry.get("symbol", "")
            price = entry.get("price")
            percent = entry.get("percent")
            change = entry.get("change")
            price_str = f"${price:,.2f}" if price is not None else "—"
            change_str = f"{change:+.2f}" if change is not None else "—"
            percent_str = f"{percent:+.2f}%" if percent is not None else "—"
            lines.append(f"**{symbol}** {price_str} ({percent_str}) {change_str}")
        return "\n".join(lines)

    embed = discord.Embed(title=title, color=discord.Color.blue(), timestamp=discord.utils.utcnow())
    embed.add_field(name=f"Top Gainers (n={limit})", value=_format(gainers), inline=False)
    embed.add_field(name=f"Top Losers (n={limit})", value=_format(losers), inline=False)
    embed.set_footer(text="Data sourced from Tiingo and Finnhub caches")
    return embed


def build_expected_move_embed(data: dict[str, Any]) -> discord.Embed:
    """Build an embed summarising expected move estimates."""
    symbol = data.get("symbol", "Unknown")
    underlying_price = data.get("underlying_price")
    price_text = f"${float(underlying_price):,.2f}" if underlying_price is not None else "N/A"

    embed = discord.Embed(
        title=f"{symbol} Expected Move",
        description=f"Underlying Price: **{price_text}**",
        color=discord.Color.orange(),
        timestamp=discord.utils.utcnow(),
    )

    estimates = data.get("estimates") or []
    if not estimates:
        embed.add_field(name="Estimates", value="No expected move data available.", inline=False)
    else:
        for estimate in estimates:
            label = estimate.get("label", "Window")
            em_value = estimate.get("expected_move")
            em_pct = estimate.get("expected_move_pct")
            straddle_cost = estimate.get("straddle_cost")
            call_strike = estimate.get("call_strike")
            put_strike = estimate.get("put_strike")
            dte = estimate.get("dte")

            move_text = "—"
            if em_value is not None:
                move_text = f"${float(em_value):.2f}"
            if em_pct is not None:
                move_text += f" ({float(em_pct):.1f}%)"

            strikes_text = ""
            if call_strike is not None and put_strike is not None:
                strikes_text = f"\nATM Strikes: C {float(call_strike):.2f} / P {float(put_strike):.2f}"

            straddle_text = ""
            if straddle_cost is not None:
                straddle_text = f"\nStraddle Cost: ${float(straddle_cost):.2f}"

            dte_text = f"\nDTE: {int(dte)}" if dte is not None else ""

            field_value = f"Expected Move: **{move_text}**{strikes_text}{straddle_text}{dte_text}"
            embed.add_field(name=label, value=field_value, inline=False)

    warnings = data.get("warnings") or []
    if warnings:
        warning_text = "\n".join(f"⚠️ {warning}" for warning in warnings[:3])
        embed.add_field(name="Warnings", value=warning_text, inline=False)

    embed.set_footer(text="Powered by Volaris Volatility Module")
    return embed
