"""
Strategy planning and sizing slash commands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from app.alerts.helpers import MoreCandidatesView, create_recommendation_embed
from app.config import settings

if TYPE_CHECKING:
    from app.alerts.discord_bot import VolarisBot


class StrategyCog(commands.Cog):
    """Commands that power the trade planner experience."""

    def __init__(self, bot: VolarisBot) -> None:
        self.bot = bot

    async def _refresh_trade_context(self, symbol: str) -> None:
        if settings.SCHEDULER_ENABLED:
            return
        try:
            await self.bot.market_api.refresh_price(symbol)
            await self.bot.market_api.refresh_option_chain(symbol)
            await self.bot.market_api.refresh_iv_metrics(symbol)
        except aiohttp.ClientError as exc:
            self.bot.logger.warning(
                "Trade context refresh failed", extra={"symbol": symbol, "error": str(exc)}
            )
        except Exception:  # pylint: disable=broad-except
            self.bot.logger.exception(
                "Unexpected trade context refresh failure", extra={"symbol": symbol}
            )

    async def _refresh_price_only(self, symbol: str) -> None:
        if settings.SCHEDULER_ENABLED:
            return
        try:
            await self.bot.market_api.refresh_price(symbol)
        except aiohttp.ClientError as exc:
            self.bot.logger.warning(
                "Price refresh failed", extra={"symbol": symbol, "error": str(exc)}
            )
        except Exception:  # pylint: disable=broad-except
            self.bot.logger.exception("Unexpected price refresh failure", extra={"symbol": symbol})

    # =============================================================================
    # /plan
    # =============================================================================
    @app_commands.command(name="plan", description="Get options strategy recommendations")
    @app_commands.describe(
        ticker="Ticker symbol (e.g., SPY, AAPL)",
        bias="Market bias",
        dte="Days to expiration",
        mode="Strategy preference (auto selects based on IV)",
        max_risk="Maximum risk per trade in dollars (optional)",
        account_size="Account size for position sizing (optional)",
        bias_reason="ICT setup context (optional, advanced)",
    )
    @app_commands.choices(
        bias=[
            app_commands.Choice(name="Bullish", value="bullish"),
            app_commands.Choice(name="Bearish", value="bearish"),
            app_commands.Choice(name="Neutral", value="neutral"),
        ],
        mode=[
            app_commands.Choice(name="Auto (IV-based)", value="auto"),
            app_commands.Choice(name="Force Credit", value="credit"),
            app_commands.Choice(name="Force Debit", value="debit"),
        ],
        bias_reason=[
            app_commands.Choice(name="Manual (default)", value="user_manual"),
            app_commands.Choice(name="SSL Sweep", value="ssl_sweep"),
            app_commands.Choice(name="BSL Sweep", value="bsl_sweep"),
            app_commands.Choice(name="FVG Retest", value="fvg_retest"),
            app_commands.Choice(name="Structure Shift", value="structure_shift"),
        ],
    )
    async def plan(
        self,
        interaction: discord.Interaction,
        ticker: str,
        bias: str,
        dte: int,
        mode: str = "auto",
        max_risk: float | None = None,
        account_size: float | None = None,
        bias_reason: str | None = None,
    ) -> None:
        """Call the Volaris strategy engine and render the top candidates."""
        if dte < 1 or dte > 365:
            await interaction.response.send_message(
                f"❌ Invalid DTE: {dte}. Must be between 1 and 365 days.",
                ephemeral=True,
            )
            return

        if not self.bot.check_rate_limit(interaction.user.id):
            await interaction.response.send_message(
                "⚠️ Rate limit: Please wait before requesting another recommendation.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        symbol_clean = ticker.upper().strip()
        await self._refresh_price_only(symbol_clean)

        symbol_clean = ticker.upper().strip()
        await self._refresh_trade_context(symbol_clean)

        try:
            result = await self.bot.api_client.recommend_strategy(
                symbol=symbol_clean,
                bias=bias,
                dte=dte,
                mode=mode,
                max_risk=max_risk,
                account_size=account_size,
                bias_reason=bias_reason,
            )
        except ValueError as exc:
            await interaction.followup.send(f"❌ {exc}")
            return
        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ API error: {exc}")
            return
        except Exception as exc:  # pylint: disable=broad-except
            self.bot.logger.error("Unexpected error in /plan", exc_info=True)
            await interaction.followup.send(f"❌ Unexpected error: {exc}")
            return

        recommendations = result.get("recommendations", [])
        if not recommendations:
            warnings = ", ".join(result.get("warnings", ["No data available"]))
            await interaction.followup.send(
                f"❌ No recommendations found for {symbol_clean}.\nWarnings: {warnings}"
            )
            return

        embed = create_recommendation_embed(
            recommendations[0],
            result["underlying_symbol"],
            float(result["underlying_price"]),
            result.get("iv_regime"),
            result["chosen_strategy_family"],
        )

        system_warnings = result.get("warnings", [])
        if system_warnings:
            warning_text = "\n".join(f"• {warning}" for warning in system_warnings[:2])
            embed.add_field(name="ℹ️ System Info", value=warning_text, inline=False)

        view: MoreCandidatesView | None = None
        if len(recommendations) > 1:
            view = MoreCandidatesView(
                recommendations,
                result["underlying_symbol"],
                float(result["underlying_price"]),
                result.get("iv_regime"),
                result["chosen_strategy_family"],
            )

        await interaction.followup.send(embed=embed, view=view)

    @plan.autocomplete("ticker")
    async def plan_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for the /plan ticker argument."""
        _ = interaction  # Unused, but keeps signature consistent.
        matches = self.bot.symbol_service.matches(current)
        return [
            app_commands.Choice(name=self.bot.symbol_service.get_display_name(sym), value=sym)
            for sym in matches
        ]

    # =============================================================================
    # /calc
    # =============================================================================
    @app_commands.command(name="calc", description="Calculate P/L for a specific strategy")
    @app_commands.describe(
        strategy="Strategy type",
        ticker="Ticker symbol",
        strikes=(
            "Strike prices: '540' for single, or 'first/second' for spreads:\n"
            "• Debit spreads: long/short (buy first, e.g., '445/450')\n"
            "• Credit spreads: short/long (sell first, e.g., '450/445')"
        ),
        dte="Days to expiration",
        premium="Net premium (optional - auto-fetches from API if omitted)",
        underlying_price="Current stock price (optional - auto-fetches if omitted)",
    )
    @app_commands.choices(
        strategy=[
            app_commands.Choice(name="Bull Call Spread (Debit)", value="bull_call_spread"),
            app_commands.Choice(name="Bear Put Spread (Debit)", value="bear_put_spread"),
            app_commands.Choice(name="Bull Put Spread (Credit)", value="bull_put_spread"),
            app_commands.Choice(name="Bear Call Spread (Credit)", value="bear_call_spread"),
            app_commands.Choice(name="Long Call", value="long_call"),
            app_commands.Choice(name="Long Put", value="long_put"),
        ]
    )
    async def calc(
        self,
        interaction: discord.Interaction,
        strategy: str,
        ticker: str,
        strikes: str,
        dte: int,
        premium: float | None = None,
        underlying_price: float | None = None,
    ) -> None:
        """Call the calculator endpoint and render payoff metrics."""
        if dte < 1 or dte > 365:
            await interaction.response.send_message(
                f"❌ Invalid DTE: {dte}. Must be between 1 and 365 days.", ephemeral=True
            )
            return

        await interaction.response.defer()

        symbol_clean = ticker.upper().strip()

        try:
            is_spread = strategy in {
                "bull_call_spread",
                "bear_put_spread",
                "bull_put_spread",
                "bear_call_spread",
            }

            long_strike: float | None = None
            short_strike: float | None = None
            single_strike: float | None = None
            option_type: str | None = None
            is_credit = False

            if is_spread:
                if "/" not in strikes:
                    await interaction.followup.send(
                        "❌ Spread requires two strikes in format 'long/short' (e.g., '445/450')"
                    )
                    return

                strike_parts = strikes.split("/")
                if len(strike_parts) != 2:
                    await interaction.followup.send(
                        "❌ Invalid format. Use 'long/short' (e.g., '445/450')"
                    )
                    return

                first_strike = float(strike_parts[0])
                second_strike = float(strike_parts[1])

                if strategy == "bull_call_spread":
                    if first_strike >= second_strike:
                        await interaction.followup.send(
                            "❌ Bull Call Spread: Format is 'lower/higher' (e.g., '445/450')\n"
                            f"You entered: {first_strike}/{second_strike}"
                        )
                        return
                    long_strike = first_strike
                    short_strike = second_strike
                    option_type = "call"
                    is_credit = False
                elif strategy == "bear_put_spread":
                    if first_strike <= second_strike:
                        await interaction.followup.send(
                            "❌ Bear Put Spread: Format is 'higher/lower' (e.g., '450/445')\n"
                            f"You entered: {first_strike}/{second_strike}"
                        )
                        return
                    long_strike = first_strike
                    short_strike = second_strike
                    option_type = "put"
                    is_credit = False
                elif strategy == "bull_put_spread":
                    if first_strike <= second_strike:
                        await interaction.followup.send(
                            "❌ Bull Put Spread: Format is 'higher/lower' (e.g., '450/445')\n"
                            f"You entered: {first_strike}/{second_strike}"
                        )
                        return
                    short_strike = first_strike
                    long_strike = second_strike
                    option_type = "put"
                    is_credit = True
                elif strategy == "bear_call_spread":
                    if first_strike >= second_strike:
                        await interaction.followup.send(
                            "❌ Bear Call Spread: Format is 'lower/higher' (e.g., '445/450')\n"
                            f"You entered: {first_strike}/{second_strike}"
                        )
                        return
                    short_strike = first_strike
                    long_strike = second_strike
                    option_type = "call"
                    is_credit = True
            else:
                single_strike = float(strikes)
                option_type = "call" if strategy == "long_call" else "put"

            # Map strategy to API format and determine bias
            if is_spread:
                api_strategy_type = "vertical_spread"
                # Determine bias from strategy name
                if strategy in ("bull_call_spread", "bull_put_spread"):
                    bias = "bullish"
                else:  # bear_put_spread, bear_call_spread
                    bias = "bearish"
            else:
                # Long options
                api_strategy_type = "long_call" if strategy == "long_call" else "long_put"
                bias = "bullish" if strategy == "long_call" else "bearish"

            # Build payload based on strategy type
            if is_spread:
                # For spreads, estimate individual premiums from net premium
                if premium is not None:
                    # Calculate spread width to estimate individual premiums
                    spread_width = abs(float(long_strike) - float(short_strike))
                    net_premium_abs = abs(premium)

                    # Estimate individual premiums based on typical ratios
                    # Credit spread: short_prem = net_credit + (spread_width * 0.4)
                    # Debit spread: long_prem = net_debit + (spread_width * 0.4)
                    if is_credit:
                        short_premium_val = net_premium_abs + (spread_width * 0.4)
                        long_premium_val = short_premium_val - net_premium_abs
                    else:
                        long_premium_val = net_premium_abs + (spread_width * 0.4)
                        short_premium_val = long_premium_val - net_premium_abs
                else:
                    # Premium not provided - will error, user must provide it
                    long_premium_val = None
                    short_premium_val = None

                payload: dict[str, float | str | int | None] = {
                    "strategy_type": api_strategy_type,
                    "underlying_symbol": symbol_clean,
                    "underlying_price": underlying_price,
                    "long_strike": long_strike,
                    "short_strike": short_strike,
                    "long_premium": long_premium_val,
                    "short_premium": short_premium_val,
                    "option_type": option_type,
                    "bias": bias,
                    "contracts": 1,
                    "dte": dte,
                }
            else:
                # Long option
                payload: dict[str, float | str | int | None] = {
                    "strategy_type": api_strategy_type,
                    "underlying_symbol": symbol_clean,
                    "underlying_price": underlying_price,
                    "strike": single_strike,
                    "premium": premium,
                    "option_type": option_type,
                    "bias": bias,
                    "contracts": 1,
                    "dte": dte,
                }

            url = f"{self.bot.api_client.base_url}/api/v1/trade-planner/calculate"
            async with aiohttp.ClientSession(timeout=self.bot.api_client.timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        await interaction.followup.send(f"❌ API error: {error_text}")
                        return
                    result = await response.json()

            strategy_name = {
                "bull_call_spread": "Bull Call Spread (Debit)",
                "bear_put_spread": "Bear Put Spread (Debit)",
                "bull_put_spread": "Bull Put Spread (Credit)",
                "bear_call_spread": "Bear Call Spread (Credit)",
                "long_call": "Long Call",
                "long_put": "Long Put",
            }

            embed = discord.Embed(
                title=f"📊 {strategy_name[strategy]} - {symbol_clean}",
                color=discord.Color.green() if is_spread and is_credit else discord.Color.blue(),
            )

            if is_spread and long_strike is not None and short_strike is not None:
                embed.add_field(
                    name="Strikes",
                    value=f"Long: ${long_strike:.2f}\nShort: ${short_strike:.2f}",
                    inline=True,
                )
                if is_credit:
                    embed.add_field(
                        name="💰 Credit",
                        value=f"**${abs(float(result['net_premium'])):.2f}**",
                        inline=True,
                    )
                else:
                    embed.add_field(
                        name="💸 Debit",
                        value=f"**${float(result['net_premium']):.2f}**",
                        inline=True,
                    )
            elif single_strike is not None:
                embed.add_field(name="Strike", value=f"${single_strike:.2f}", inline=True)
                embed.add_field(
                    name="💸 Premium", value=f"**${float(result['premium']):.2f}**", inline=True
                )

            embed.add_field(
                name="📈 Max Profit",
                value=f"${float(result.get('max_profit', 0)):.2f}",
                inline=True,
            )
            embed.add_field(
                name="📉 Max Loss", value=f"${float(result['max_loss']):.2f}", inline=True
            )
            embed.add_field(
                name="⚖️ R:R",
                value=f"{float(result.get('risk_reward_ratio', 0)):.2f}:1",
                inline=True,
            )
            # API returns breakeven_prices as a list
            breakeven_prices = result.get("breakeven_prices", [])
            breakeven_display = f"${float(breakeven_prices[0]):.2f}" if breakeven_prices else "N/A"
            embed.add_field(name="🎯 Breakeven", value=breakeven_display, inline=True)

            if result.get("pop_proxy"):
                embed.add_field(
                    name="📊 POP", value=f"{float(result['pop_proxy']):.0f}%", inline=True
                )

            if is_spread:
                ict_context = {
                    "bull_call_spread": "Best after SSL sweep + bullish displacement",
                    "bear_put_spread": "Best after BSL sweep + bearish displacement",
                    "bull_put_spread": "Profit if price stays above short strike (bullish/neutral)",
                    "bear_call_spread": "Profit if price stays below short strike (bearish/neutral)",
                }
                embed.add_field(name="💡 ICT Context", value=ict_context[strategy], inline=False)

            await interaction.followup.send(embed=embed)

        except ValueError as exc:
            await interaction.followup.send(f"❌ Invalid input: {exc}")
        except Exception as exc:  # pylint: disable=broad-except
            self.bot.logger.error("Error in /calc", exc_info=True)
            await interaction.followup.send(f"❌ Error: {exc}")

    @calc.autocomplete("ticker")
    async def calc_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for the /calc ticker argument."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [
            app_commands.Choice(name=self.bot.symbol_service.get_display_name(sym), value=sym)
            for sym in matches
        ]

    # =============================================================================
    # /size
    # =============================================================================
    @app_commands.command(name="size", description="Calculate position sizing")
    @app_commands.describe(
        account_size="Your account value",
        max_risk_pct="Max risk as % of account (e.g., 2 for 2%)",
        strategy_cost="Cost per contract (premium or max loss)",
    )
    async def size(
        self,
        interaction: discord.Interaction,
        account_size: float,
        max_risk_pct: float,
        strategy_cost: float,
    ) -> None:
        """Return contract sizing guidance based on risk parameters."""
        await interaction.response.defer()

        try:
            max_risk_dollars = account_size * (max_risk_pct / 100)
            recommended_contracts = int(max_risk_dollars / strategy_cost)
            total_position_size = recommended_contracts * strategy_cost
            actual_risk_pct = (total_position_size / account_size) * 100 if account_size else 0

            embed = discord.Embed(
                title="📐 Position Sizing Recommendation",
                color=discord.Color.green(),
            )

            embed.add_field(name="Account Size", value=f"${account_size:,.2f}", inline=True)
            embed.add_field(name="Max Risk %", value=f"{max_risk_pct:.1f}%", inline=True)
            embed.add_field(name="Max Risk $", value=f"${max_risk_dollars:,.2f}", inline=True)
            embed.add_field(name="Cost/Contract", value=f"${strategy_cost:.2f}", inline=True)
            embed.add_field(name="✅ Contracts", value=f"**{recommended_contracts}**", inline=True)
            embed.add_field(
                name="Total Position", value=f"${total_position_size:,.2f}", inline=True
            )
            embed.add_field(name="Actual Risk %", value=f"{actual_risk_pct:.2f}%", inline=True)
            embed.add_field(name="Max Loss", value=f"${total_position_size:,.2f}", inline=True)

            if recommended_contracts == 0:
                embed.add_field(
                    name="⚠️ Warning",
                    value=(
                        "Strategy cost exceeds risk limit. Consider reducing position size or using spreads."
                    ),
                    inline=False,
                )

            await interaction.followup.send(embed=embed)

        except Exception as exc:  # pylint: disable=broad-except
            self.bot.logger.error("Error in /size", exc_info=True)
            await interaction.followup.send(f"❌ Error: {exc}")

    # =============================================================================
    # /breakeven
    # =============================================================================
    @app_commands.command(name="breakeven", description="Calculate breakeven price")
    @app_commands.describe(
        strategy="Strategy type",
        strikes=(
            "Strike prices: '540' for single, or 'first/second' for spreads:\n"
            "• Debit spreads: long/short (buy first, e.g., '445/450')\n"
            "• Credit spreads: short/long (sell first, e.g., '450/445')"
        ),
        cost="Premium paid or received (positive for debit, negative for credit)",
    )
    @app_commands.choices(
        strategy=[
            app_commands.Choice(name="Bull Call Spread", value="bull_call"),
            app_commands.Choice(name="Bear Put Spread", value="bear_put"),
            app_commands.Choice(name="Bull Put Spread (Credit)", value="bull_put"),
            app_commands.Choice(name="Bear Call Spread (Credit)", value="bear_call"),
            app_commands.Choice(name="Long Call", value="long_call"),
            app_commands.Choice(name="Long Put", value="long_put"),
        ]
    )
    async def breakeven(
        self,
        interaction: discord.Interaction,
        strategy: str,
        strikes: str,
        cost: float,
    ) -> None:
        """Return breakeven levels for spreads or long options."""
        await interaction.response.defer()

        try:
            if "/" in strikes:
                strike_parts = strikes.split("/")
                if len(strike_parts) != 2:
                    await interaction.followup.send(
                        "❌ Invalid strikes format. Use '540/545' for spreads."
                    )
                    return
                first_strike = float(strike_parts[0])
                second_strike = float(strike_parts[1])

                # Parse strikes based on strategy type (same logic as /calc)
                if strategy == "bull_call":
                    # Bull call: lower/higher (e.g., '445/450')
                    if first_strike >= second_strike:
                        await interaction.followup.send(
                            f"❌ Bull Call Spread: Format is 'lower/higher' (e.g., '445/450')\n"
                            f"You entered: {first_strike}/{second_strike}"
                        )
                        return
                    long_strike = first_strike
                    short_strike = second_strike
                    breakeven = long_strike + abs(cost)
                elif strategy == "bear_put":
                    # Bear put: higher/lower (e.g., '450/445')
                    if first_strike <= second_strike:
                        await interaction.followup.send(
                            f"❌ Bear Put Spread: Format is 'higher/lower' (e.g., '450/445')\n"
                            f"You entered: {first_strike}/{second_strike}"
                        )
                        return
                    long_strike = first_strike
                    short_strike = second_strike
                    breakeven = long_strike - abs(cost)
                elif strategy == "bull_put":
                    # Bull put credit: higher/lower (e.g., '450/445')
                    if first_strike <= second_strike:
                        await interaction.followup.send(
                            f"❌ Bull Put Spread: Format is 'higher/lower' (e.g., '450/445')\n"
                            f"You entered: {first_strike}/{second_strike}"
                        )
                        return
                    short_strike = first_strike
                    long_strike = second_strike
                    breakeven = short_strike - abs(cost)
                else:  # bear_call
                    # Bear call credit: lower/higher (e.g., '445/450')
                    if first_strike >= second_strike:
                        await interaction.followup.send(
                            f"❌ Bear Call Spread: Format is 'lower/higher' (e.g., '445/450')\n"
                            f"You entered: {first_strike}/{second_strike}"
                        )
                        return
                    short_strike = first_strike
                    long_strike = second_strike
                    breakeven = short_strike + abs(cost)
            else:
                strike = float(strikes)
                breakeven = strike + abs(cost) if strategy == "long_call" else strike - abs(cost)

            embed = discord.Embed(
                title=f"⚖️ Breakeven Calculator - {strategy.replace('_', ' ').title()}",
                color=discord.Color.gold(),
            )

            if "/" in strikes:
                embed.add_field(
                    name="Strikes", value=f"{long_strike:.2f}/{short_strike:.2f}", inline=True
                )
            else:
                embed.add_field(name="Strike", value=f"${strike:.2f}", inline=True)

            embed.add_field(name="Cost", value=f"${abs(cost):.2f}", inline=True)
            embed.add_field(name="✅ Breakeven", value=f"**${breakeven:.2f}**", inline=True)

            if "/" in strikes:
                if strategy in ("bull_call", "bear_put"):
                    embed.add_field(
                        name="Explanation",
                        value=f"Debit spread: Needs ${abs(cost):.2f} move beyond long strike to breakeven",
                        inline=False,
                    )
                else:
                    embed.add_field(
                        name="Explanation",
                        value=f"Credit spread: Profit if price stays beyond ${breakeven:.2f}",
                        inline=False,
                    )

            await interaction.followup.send(embed=embed)

        except ValueError as exc:
            await interaction.followup.send(f"❌ Invalid input: {exc}")
        except Exception as exc:  # pylint: disable=broad-except
            self.bot.logger.error("Error in /breakeven", exc_info=True)
            await interaction.followup.send(f"❌ Error: {exc}")


async def setup(bot: VolarisBot) -> None:
    """Add the strategy cog to the bot."""
    await bot.add_cog(StrategyCog(bot))
