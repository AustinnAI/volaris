"""
Calculator-style slash commands (POP, contracts, risk, DTE, delta, spread checks).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from app.alerts.discord_bot import VolarisBot


class CalculatorsCog(commands.Cog):
    """Pure calculation helpers surfaced as slash commands."""

    def __init__(self, bot: VolarisBot) -> None:
        self.bot = bot

    # -----------------------------------------------------------------------------
    # Probability of Profit
    # -----------------------------------------------------------------------------
    @app_commands.command(name="pop", description="Calculate probability of profit from delta")
    @app_commands.describe(delta="Option delta (0.0 to 1.0)")
    async def pop(self, interaction: discord.Interaction, delta: float) -> None:
        """Approximate POP for long vs short options based on Black-Scholes delta."""
        await interaction.response.defer()

        try:
            if delta < 0 or delta > 1:
                await interaction.followup.send("❌ Delta must be between 0.0 and 1.0")
                return

            pop_short = 100 - (delta * 100)
            pop_long = delta * 100

            embed = discord.Embed(
                title="📊 Probability of Profit Calculator", color=discord.Color.blue()
            )
            embed.add_field(name="Delta", value=f"{delta:.3f}", inline=True)
            embed.add_field(name="Short Option POP", value=f"**{pop_short:.1f}%**", inline=True)
            embed.add_field(name="Long Option POP", value=f"**{pop_long:.1f}%**", inline=True)
            embed.add_field(
                name="ℹ️ Explanation",
                value=(
                    f"• **Selling** an option with Δ={delta:.2f} → ~{pop_short:.0f}% chance it expires OTM (profit)\n"
                    f"• **Buying** an option with Δ={delta:.2f} → ~{pop_long:.0f}% chance it expires ITM\n"
                    "• Lower delta = Higher POP for credit strategies\n"
                    "• Common targets: Δ0.30 (70% POP), Δ0.20 (80% POP), Δ0.16 (84% POP)"
                ),
                inline=False,
            )

            await interaction.followup.send(embed=embed)

        except Exception as exc:  # pylint: disable=broad-except
            self.bot.logger.error("Error in /pop", exc_info=True)
            await interaction.followup.send(f"❌ Error: {exc}")

    # -----------------------------------------------------------------------------
    # Contracts from risk
    # -----------------------------------------------------------------------------
    @app_commands.command(
        name="contracts", description="Calculate contracts needed for target risk amount"
    )
    @app_commands.describe(
        risk="Target risk amount in dollars (e.g., 500 for $500 max risk)",
        premium="Premium per contract (for spreads: max loss per contract)",
    )
    async def contracts(
        self, interaction: discord.Interaction, risk: float, premium: float
    ) -> None:
        """Determine contract count given a risk budget and per-contract premium."""
        await interaction.response.defer()

        try:
            if risk <= 0 or premium <= 0:
                await interaction.followup.send("❌ Risk and premium must be positive numbers")
                return

            num_contracts = int(risk / premium)
            actual_risk = num_contracts * premium
            remaining = risk - actual_risk

            embed = discord.Embed(title="📐 Contract Calculator", color=discord.Color.gold())
            embed.add_field(name="Target Risk", value=f"${risk:,.2f}", inline=True)
            embed.add_field(name="Premium/Contract", value=f"${premium:.2f}", inline=True)
            embed.add_field(name="📊 Contracts", value=f"**{num_contracts}**", inline=True)
            embed.add_field(name="Actual Risk", value=f"${actual_risk:,.2f}", inline=True)
            embed.add_field(name="Remaining", value=f"${remaining:.2f}", inline=True)
            embed.add_field(name="Risk %", value=f"{(actual_risk / risk * 100):.1f}%", inline=True)

            if num_contracts == 0:
                embed.add_field(
                    name="⚠️ Warning",
                    value=f"Premium too high for target risk. Need ${premium:.2f} minimum.",
                    inline=False,
                )

            await interaction.followup.send(embed=embed)

        except Exception as exc:  # pylint: disable=broad-except
            self.bot.logger.error("Error in /contracts", exc_info=True)
            await interaction.followup.send(f"❌ Error: {exc}")

    # -----------------------------------------------------------------------------
    # Risk calculator
    # -----------------------------------------------------------------------------
    @app_commands.command(name="risk", description="Calculate total risk for number of contracts")
    @app_commands.describe(
        contracts="Number of contracts",
        premium="Premium per contract (for spreads: max loss per contract)",
    )
    async def risk_calc(
        self, interaction: discord.Interaction, contracts: int, premium: float
    ) -> None:
        """Return total risk given a contract count."""
        await interaction.response.defer()

        try:
            if contracts <= 0 or premium <= 0:
                await interaction.followup.send("❌ Contracts and premium must be positive numbers")
                return

            total_risk = contracts * premium

            embed = discord.Embed(title="💰 Risk Calculator", color=discord.Color.red())
            embed.add_field(name="Contracts", value=f"{contracts}", inline=True)
            embed.add_field(name="Premium/Contract", value=f"${premium:.2f}", inline=True)
            embed.add_field(name="Total Risk", value=f"**${total_risk:,.2f}**", inline=True)
            embed.add_field(
                name="Context",
                value="Include this amount in your portfolio risk tracker. Evaluate if it fits the day's risk budget.",
                inline=False,
            )

            await interaction.followup.send(embed=embed)

        except Exception as exc:  # pylint: disable=broad-except
            self.bot.logger.error("Error in /risk", exc_info=True)
            await interaction.followup.send(f"❌ Error: {exc}")

    # -----------------------------------------------------------------------------
    # DTE calculator
    # -----------------------------------------------------------------------------
    @app_commands.command(name="dte", description="Calculate days to expiration from date")
    @app_commands.describe(expiration_date="Expiration date (YYYY-MM-DD or MM/DD/YYYY)")
    async def dte(self, interaction: discord.Interaction, expiration_date: str) -> None:
        """Calculate days to expiration and provide ICT-flavoured guidance."""
        await interaction.response.defer()

        try:
            exp_date = None
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d"):
                try:
                    exp_date = datetime.strptime(expiration_date, fmt).date()
                    break
                except ValueError:
                    continue

            if exp_date is None:
                await interaction.followup.send(
                    "❌ Invalid date format. Use YYYY-MM-DD or MM/DD/YYYY"
                )
                return

            today = date.today()
            days_remaining = (exp_date - today).days

            if days_remaining < 0:
                color = discord.Color.greyple()
                emoji = "⏰"
                status = "Expired"
            elif days_remaining <= 7:
                color = discord.Color.red()
                emoji = "⚡"
                status = "Short-dated (0-7 DTE)"
            elif days_remaining <= 45:
                color = discord.Color.gold()
                emoji = "📅"
                status = "Medium-dated (8-45 DTE)"
            else:
                color = discord.Color.blue()
                emoji = "📆"
                status = "Long-dated (45+ DTE)"

            embed = discord.Embed(title=f"{emoji} Days to Expiration", color=color)
            embed.add_field(
                name="Expiration Date", value=exp_date.strftime("%B %d, %Y"), inline=True
            )
            embed.add_field(name="Today", value=today.strftime("%B %d, %Y"), inline=True)
            embed.add_field(name="DTE", value=f"**{days_remaining}** days", inline=True)
            embed.add_field(name="Classification", value=status, inline=False)

            if days_remaining >= 0:
                if days_remaining <= 7:
                    strategy = "Credit spreads (high theta decay, defined risk)"
                elif days_remaining <= 45:
                    strategy = "Credit/debit spreads (balance of theta and directional edge)"
                else:
                    strategy = "Longer-term strategies (less theta decay, more directional)"
                embed.add_field(name="💡 ICT Strategy", value=strategy, inline=False)

            await interaction.followup.send(embed=embed)

        except Exception as exc:  # pylint: disable=broad-except
            self.bot.logger.error("Error in /dte", exc_info=True)
            await interaction.followup.send(f"❌ Error: {exc}")

    # -----------------------------------------------------------------------------
    # Delta lookup
    # -----------------------------------------------------------------------------
    @app_commands.command(name="delta", description="Get delta for a specific option strike")
    @app_commands.describe(
        symbol="Ticker symbol (e.g., SPY)",
        strike="Strike price",
        option_type="Call or Put",
        dte="Days to expiration (approximate)",
    )
    @app_commands.choices(
        option_type=[
            app_commands.Choice(name="Call", value="call"),
            app_commands.Choice(name="Put", value="put"),
        ]
    )
    async def delta(
        self,
        interaction: discord.Interaction,
        symbol: str,
        strike: float,
        option_type: str,
        dte: int,
    ) -> None:
        """Fetch delta from the market API and add qualitative guidance."""
        await interaction.response.defer()

        try:
            symbol_clean = symbol.upper().strip()
            url = f"{self.bot.api_client.base_url}/api/v1/market/delta/{symbol_clean}/{strike}/{option_type}/{dte}"

            async with aiohttp.ClientSession(timeout=self.bot.api_client.timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        await interaction.followup.send(f"❌ API error: {error_text}")
                        return
                    data = await response.json()

            delta_value = data.get("delta", 0.0)
            pop = 100 - abs(delta_value) * 100

            embed = discord.Embed(
                title=f"📐 {symbol_clean} ${strike:.0f} {option_type.upper()} Delta",
                color=discord.Color.blue(),
            )
            embed.add_field(name="Strike", value=f"${strike:.2f}", inline=True)
            embed.add_field(name="Type", value=option_type.upper(), inline=True)
            embed.add_field(name="DTE", value=f"{dte} days", inline=True)
            embed.add_field(name="Delta", value=f"**{delta_value:.3f}**", inline=True)
            embed.add_field(name="POP (Short)", value=f"~{pop:.0f}%", inline=True)

            if abs(delta_value) >= 0.7:
                context = "Deep ITM (high directional risk)"
            elif abs(delta_value) >= 0.5:
                context = "ATM (balanced risk/reward)"
            elif abs(delta_value) >= 0.3:
                context = "OTM (good for credit spreads)"
            else:
                context = "Far OTM (low premium, high POP)"

            embed.add_field(name="Classification", value=context, inline=False)
            embed.set_footer(text=f"{symbol_clean} • Delta approximation")

            await interaction.followup.send(embed=embed)

        except Exception as exc:  # pylint: disable=broad-except
            self.bot.logger.error("Error in /delta", exc_info=True)
            await interaction.followup.send(f"❌ Error: {exc}")

    @delta.autocomplete("symbol")
    async def delta_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete hook for /delta."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [
            app_commands.Choice(name=self.bot.symbol_service.get_display_name(sym), value=sym)
            for sym in matches
        ]

    # -----------------------------------------------------------------------------
    # Spread width guidance
    # -----------------------------------------------------------------------------
    @app_commands.command(
        name="spread", description="Validate if spread width is appropriate for a stock"
    )
    @app_commands.describe(
        symbol="Ticker symbol (e.g., SPY)",
        width="Spread width in points (e.g., 5 for a 5-point spread)",
    )
    async def spread(self, interaction: discord.Interaction, symbol: str, width: int) -> None:
        """Validate spread width based on the underlying price tier."""
        await interaction.response.defer()

        try:
            symbol_clean = symbol.upper().strip()
            url = f"{self.bot.api_client.base_url}/api/v1/market/price/{symbol_clean}"

            async with aiohttp.ClientSession(timeout=self.bot.api_client.timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        await interaction.followup.send(f"❌ API error: {error_text}")
                        return
                    data = await response.json()

            price = data.get("price", 0.0)

            if price < 100:
                min_width, max_width = 2, 5
                price_tier = "Low-priced (<$100)"
            elif price < 300:
                min_width, max_width = 5, 10
                price_tier = "Mid-priced ($100-$300)"
            else:
                min_width, max_width = 5, 15
                price_tier = "High-priced (>$300)"

            is_valid = min_width <= width <= max_width

            if is_valid:
                color = discord.Color.green()
                emoji = "✅"
                verdict = "Optimal width"
            elif width < min_width:
                color = discord.Color.orange()
                emoji = "⚠️"
                verdict = "Too narrow (low credit)"
            else:
                color = discord.Color.red()
                emoji = "❌"
                verdict = "Too wide (high risk)"

            embed = discord.Embed(
                title=f"{emoji} {symbol_clean} Spread Width Validator", color=color
            )
            embed.add_field(name="Current Price", value=f"${price:.2f}", inline=True)
            embed.add_field(name="Your Width", value=f"**{width} points**", inline=True)
            embed.add_field(name="Verdict", value=verdict, inline=True)
            embed.add_field(name="Price Tier", value=price_tier, inline=True)
            embed.add_field(
                name="Recommended Range", value=f"{min_width}-{max_width} points", inline=True
            )

            if is_valid:
                explanation = (
                    f"✅ {width}-point spread is optimal for {symbol_clean} (${price:.0f}). "
                    "Good balance of credit and risk."
                )
            elif width < min_width:
                explanation = (
                    f"⚠️ Width too narrow. Consider widening to at least {min_width} points "
                    "to collect sufficient credit."
                )
            else:
                explanation = f"❌ Width too wide. Consider narrowing to {max_width} points to stay within risk tolerance."
            embed.add_field(name="Explanation", value=explanation, inline=False)

            await interaction.followup.send(embed=embed)

        except Exception as exc:  # pylint: disable=broad-except
            self.bot.logger.error("Error in /spread", exc_info=True)
            await interaction.followup.send(f"❌ Error: {exc}")

    @spread.autocomplete("symbol")
    async def spread_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete hook for /spread."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [
            app_commands.Choice(name=self.bot.symbol_service.get_display_name(sym), value=sym)
            for sym in matches
        ]


async def setup(bot: VolarisBot) -> None:
    """Register the calculators cog."""
    await bot.add_cog(CalculatorsCog(bot))
