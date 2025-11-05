"""
Utility slash commands and grouped alert/stream management.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from app.alerts.discord_bot import VolarisBot


class AlertsCog(commands.GroupCog, name="alerts", group_description="Manage server price alerts"):
    """Slash command group for managing shared price alerts."""

    def __init__(self, bot: VolarisBot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name="add", description="Create a server-wide price alert")
    @app_commands.describe(
        ticker="Ticker symbol (e.g., SPY)",
        direction="Trigger condition",
        target_price="Target price that fires the alert",
    )
    @app_commands.choices(
        direction=[
            app_commands.Choice(name="Price at or above target", value="above"),
            app_commands.Choice(name="Price at or below target", value="below"),
        ]
    )
    async def add(
        self,
        interaction: discord.Interaction,
        ticker: str,
        direction: str,
        target_price: float,
    ) -> None:
        """Create a new price alert for the server."""
        if target_price <= 0:
            await interaction.response.send_message(
                "❌ Target price must be greater than 0.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            alert = await self.bot.alerts_api.create_alert(
                symbol=ticker,
                target_price=target_price,
                direction=direction,
                channel_id=interaction.channel_id,
                created_by=interaction.user.id,
            )
        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ Failed to create alert: {exc}", ephemeral=True)
            return

        direction_text = "≥" if direction == "above" else "≤"
        embed = discord.Embed(title="✅ Price Alert Created", color=discord.Color.blue())
        embed.add_field(name="Symbol", value=alert["symbol"], inline=True)
        embed.add_field(name="Direction", value=direction.upper(), inline=True)
        embed.add_field(name="Target", value=f"${float(alert['target_price']):,.2f}", inline=True)
        embed.set_footer(text=f"Alert ID #{alert['id']} • Fires when price {direction_text} target")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @add.autocomplete("ticker")
    async def alerts_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for /alerts add ticker parameter."""
        _ = interaction
        try:
            matches = self.bot.symbol_service.matches(current)
            return [
                app_commands.Choice(name=self.bot.symbol_service.get_display_name(sym), value=sym)
                for sym in matches
            ]
        except Exception:  # pylint: disable=broad-except
            self.bot.logger.error("Autocomplete error in /alerts add", exc_info=True)
            return []

    @app_commands.command(name="remove", description="Remove a price alert by ID")
    @app_commands.describe(alert_id="Alert ID (view with /alerts list)")
    async def remove(self, interaction: discord.Interaction, alert_id: int) -> None:
        """Remove an existing server price alert."""
        await interaction.response.defer(ephemeral=True)

        try:
            await self.bot.alerts_api.delete_alert(alert_id)
        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ Unable to remove alert: {exc}", ephemeral=True)
            return

        await interaction.followup.send(f"🗑️ Removed price alert #{alert_id}", ephemeral=True)

    @app_commands.command(name="list", description="View all active price alerts")
    async def list_alerts(self, interaction: discord.Interaction) -> None:
        """List the current alerts configured for the server."""
        await interaction.response.defer(ephemeral=True)

        try:
            alerts = await self.bot.alerts_api.list_alerts()
        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ Unable to load alerts: {exc}", ephemeral=True)
            return

        if not alerts:
            await interaction.followup.send("✅ No active price alerts.", ephemeral=True)
            return

        lines: list[str] = []
        for alert in alerts[:25]:
            direction = "≥" if alert["direction"] == "above" else "≤"
            target = float(alert["target_price"])
            channel_id = alert.get("channel_id")
            creator = alert.get("created_by")
            metadata_parts = []
            if channel_id:
                metadata_parts.append(f"<#{channel_id}>")
            if creator:
                metadata_parts.append(f"by <@{creator}>")
            metadata = " • ".join(metadata_parts)
            lines.append(
                f"#{alert['id']} • {alert['symbol']} {direction} ${target:,.2f} {metadata}".strip()
            )

        if len(alerts) > 25:
            lines.append(f"… and {len(alerts) - 25} more alerts")

        embed = discord.Embed(
            title="Active Price Alerts",
            description="\n".join(lines),
            color=discord.Color.blue(),
        )
        embed.set_footer(text="Use /alerts remove <id> to delete an alert")

        await interaction.followup.send(embed=embed, ephemeral=True)


# StreamsCog moved to legacy/cogs/streams_cog.py (unused, low value for current focus)


class UtilitiesCog(commands.Cog):
    """Single commands for health checks and help messaging."""

    def __init__(self, bot: VolarisBot) -> None:
        self.bot = bot

    @app_commands.command(name="check", description="Check bot and API health")
    async def check(self, interaction: discord.Interaction) -> None:
        """Call the Volaris /health endpoint and surface system status."""
        await interaction.response.defer()

        try:
            start_time = time.time()
            url = f"{self.bot.api_client.base_url}/health"
            async with aiohttp.ClientSession(timeout=self.bot.api_client.timeout) as session:
                async with session.get(url) as response:
                    health_data = await response.json() if response.status == 200 else {}
                    api_status = (
                        "✅ Healthy" if response.status == 200 else f"❌ Error ({response.status})"
                    )

            response_time = (time.time() - start_time) * 1000

            embed = discord.Embed(
                title="🏥 System Health Check",
                color=discord.Color.green() if response_time < 500 else discord.Color.orange(),
            )
            embed.add_field(name="Bot Status", value="✅ Online", inline=True)
            embed.add_field(name="API Status", value=api_status, inline=True)
            embed.add_field(name="Response Time", value=f"{response_time:.0f}ms", inline=True)

            if health_data:
                embed.add_field(
                    name="Database", value=health_data.get("database", "Unknown"), inline=True
                )
                embed.add_field(
                    name="Redis", value=health_data.get("redis", "Unknown"), inline=True
                )
                version = health_data.get("version")
                if version:
                    embed.add_field(name="Version", value=version, inline=True)

            embed.set_footer(text=f"API: {self.bot.api_client.base_url}")
            await interaction.followup.send(embed=embed)

        except Exception as exc:  # pylint: disable=broad-except
            self.bot.logger.error("Error in /check", exc_info=True)
            embed = discord.Embed(title="🏥 System Health Check", color=discord.Color.red())
            embed.add_field(name="Bot Status", value="✅ Online", inline=True)
            embed.add_field(name="API Status", value=f"❌ Error: {exc}", inline=False)
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="help", description="Show all available commands and usage")
    async def help(self, interaction: discord.Interaction) -> None:
        """Send a comprehensive command reference embed."""
        embed = discord.Embed(
            title="📚 Volaris Bot Commands",
            description="Track unusual options activity and sentiment for SPY/QQQ/large-caps",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="🔥 Options Flow (Core Feature)",
            value=(
                "**`/flow <ticker>`** - Find unusual options activity (smart money)\n"
                "**`/flow-subscribe <ticker>`** - Get alerts every 10 min during market hours\n"
                "**`/flow-subscriptions`** - View your active alert subscriptions\n"
                "**`/flow-unsubscribe <ticker>`** - Stop receiving alerts\n"
                "_Shows: Block trades, volume spikes, high vol/OI ratios_"
            ),
            inline=False,
        )

        embed.add_field(
            name="📰 News & Sentiment",
            value=(
                "**`/news <ticker>`** - Recent headlines with sentiment (auto-fetches if needed)\n"
                "**`/news-sentiment <ticker>`** - Aggregated bullish/bearish score\n"
                "**`/refresh-news <ticker>`** - Manually refresh articles from Finnhub\n"
                "_Sources: Yahoo Finance, CNBC, Seeking Alpha, Reuters (via Finnhub)_"
            ),
            inline=False,
        )

        embed.add_field(
            name="📈 Market Data",
            value=(
                "**`/price <ticker>`** - Current price + % change\n"
                "**`/iv <ticker>`** - IV rank/percentile (options pricing)\n"
                "**`/volume <ticker>`** - Volume vs 30-day avg\n"
                "**`/range <ticker>`** - 52-week high/low position"
            ),
            inline=False,
        )

        embed.add_field(
            name="🔔 Price Alerts",
            value=(
                "**`/alerts add <ticker> <direction> <price>`** - Get notified at price\n"
                "**`/alerts list`** - View all alerts\n"
                "**`/alerts remove <id>`** - Delete alert\n"
                "_Example: `/alerts add SPY above 600`_"
            ),
            inline=False,
        )

        embed.add_field(
            name="📋 Watchlist & Utils",
            value=(
                "**`/watchlist get`** - View server watchlist\n"
                "**`/watchlist set <symbols>`** - Update watchlist\n"
                "**`/check`** - Bot health status\n"
                "**`/help`** - Show this message"
            ),
            inline=False,
        )

        embed.add_field(
            name="🚀 Recommended Workflow",
            value=(
                "1. Subscribe: `/flow-subscribe SPY`\n"
                "2. Check sentiment: `/news-sentiment SPY`\n"
                "3. Read headlines: `/news SPY`\n"
                "4. Confirm flow: `/flow SPY` (manual check)\n"
                "5. Set target: `/alerts add SPY above 600`\n"
                "6. Get automated flow alerts in #trading every 10 min"
            ),
            inline=False,
        )

        embed.set_footer(
            text="Volaris V1 • 19 Commands • Automated flow alerts every 10 min during market hours"
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: VolarisBot) -> None:
    """Register utility cogs."""
    await bot.add_cog(AlertsCog(bot))
    # StreamsCog removed - see legacy/cogs/streams_cog.py
    await bot.add_cog(UtilitiesCog(bot))
