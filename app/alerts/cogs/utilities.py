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
        symbol="Ticker symbol (e.g., SPY)",
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
        symbol: str,
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
                symbol=symbol,
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

    @add.autocomplete("symbol")
    async def alerts_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for /alerts add symbol parameter."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [
            app_commands.Choice(name=self.bot.symbol_service.get_display_name(sym), value=sym)
            for sym in matches
        ]

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


class StreamsCog(
    commands.GroupCog, name="streams", group_description="Manage recurring price streams"
):
    """Slash command group for scheduled price stream management."""

    def __init__(self, bot: VolarisBot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name="add", description="Start a recurring price update")
    @app_commands.describe(symbol="Ticker symbol (e.g., SPY)", interval="Update cadence in minutes")
    @app_commands.choices(
        interval=[
            app_commands.Choice(name="5 minutes", value=5),
            app_commands.Choice(name="15 minutes", value=15),
            app_commands.Choice(name="30 minutes", value=30),
            app_commands.Choice(name="60 minutes", value=60),
        ]
    )
    async def add(self, interaction: discord.Interaction, symbol: str, interval: int) -> None:
        """Create a recurring price stream for the current channel."""
        await interaction.response.defer(ephemeral=True)

        try:
            stream = await self.bot.streams_api.create_stream(
                symbol=symbol,
                channel_id=interaction.channel_id,
                interval_seconds=interval * 60,
                created_by=interaction.user.id,
            )
        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ Failed to create stream: {exc}", ephemeral=True)
            return

        embed = discord.Embed(
            title="📡 Price Stream Enabled",
            color=discord.Color.blue(),
            description=(
                f"Channel: <#{stream['channel_id']}>\n"
                f"Interval: {stream['interval_seconds']//60} minutes"
            ),
        )
        embed.add_field(name="Symbol", value=stream["symbol"], inline=True)
        embed.add_field(name="Stream ID", value=str(stream["id"]), inline=True)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @add.autocomplete("symbol")
    async def streams_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for /streams add symbol parameter."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [
            app_commands.Choice(name=self.bot.symbol_service.get_display_name(sym), value=sym)
            for sym in matches
        ]

    @app_commands.command(name="remove", description="Stop a price stream")
    @app_commands.describe(stream_id="Stream ID (see /streams list)")
    async def remove(self, interaction: discord.Interaction, stream_id: int) -> None:
        """Remove a stream by identifier."""
        await interaction.response.defer(ephemeral=True)

        try:
            await self.bot.streams_api.delete_stream(stream_id)
        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ Unable to remove stream: {exc}", ephemeral=True)
            return

        await interaction.followup.send(f"🗑️ Removed price stream #{stream_id}", ephemeral=True)

    @app_commands.command(name="list", description="View active price streams")
    async def list_streams(self, interaction: discord.Interaction) -> None:
        """List active streams."""
        await interaction.response.defer(ephemeral=True)

        try:
            streams = await self.bot.streams_api.list_streams()
        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ Unable to load streams: {exc}", ephemeral=True)
            return

        if not streams:
            await interaction.followup.send("✅ No active price streams.", ephemeral=True)
            return

        lines = [
            f"#{stream['id']} • {stream['symbol']} every {stream['interval_seconds']//60}m in <#{stream['channel_id']}>"
            for stream in streams
        ]
        embed = discord.Embed(
            title="Active Price Streams",
            description="\n".join(lines),
            color=discord.Color.blue(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


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
            description="Options trading strategy recommendations powered by ICT methodology",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="📊 Strategy Planning",
            value=(
                "**`/plan`** - Full strategy recommendations with ICT context\n"
                "**`/calc`** - Quick P/L calculator for specific strikes/strategies"
            ),
            inline=False,
        )

        embed.add_field(
            name="📈 Market Data",
            value=(
                "**`/price <symbol>`** - Current price + % change\n"
                "**`/quote <symbol>`** - Full quote (bid/ask, volume, spread)\n"
                "**`/iv <symbol>`** - IV, IV rank, IV percentile + regime\n"
                "**`/range <symbol>`** - 52-week high/low + current position\n"
                "**`/volume <symbol>`** - Volume vs 30-day average\n"
                "**`/sentiment <symbol>`** - Analyst ratings + news (S&P 500 only)\n"
                "**`/top [limit]`** - Top S&P 500 gainers/losers\n"
                "**`/earnings <symbol>`** - Next earnings date + days until"
            ),
            inline=False,
        )

        embed.add_field(
            name="🧮 Quick Calculators",
            value=(
                "**`/pop <delta>`** - Probability of profit from delta\n"
                "**`/delta <symbol> <strike> <type> <dte>`** - Get delta for strike\n"
                "**`/contracts <risk> <premium>`** - Contracts for target risk\n"
                "**`/risk <contracts> <premium>`** - Total risk calculation\n"
                "**`/dte <date>`** - Days to expiration (YYYY-MM-DD)\n"
                "**`/size <account> <risk%> <cost>`** - Position sizing\n"
                "**`/breakeven <strategy> <strikes> <cost>`** - Breakeven price"
            ),
            inline=False,
        )

        embed.add_field(
            name="✅ Validators & Tools",
            value=(
                "**`/spread <symbol> <width>`** - Validate spread width\n"
                "**`/check`** - System health check\n"
                "**`/help`** - Show this help message"
            ),
            inline=False,
        )

        embed.add_field(
            name="🔔 Alerts & Streams",
            value=(
                "**`/alerts add <symbol> <price>`** - Add price alert\n"
                "**`/alerts list`** - View active alerts\n"
                "**`/alerts remove <id>`** - Remove alert\n"
                "**`/streams add <symbol>`** - Subscribe to price stream\n"
                "**`/streams list`** - View active streams\n"
                "**`/streams remove <id>`** - Unsubscribe from stream"
            ),
            inline=False,
        )

        embed.add_field(
            name="💡 Quick Examples",
            value=(
                "• `/price SPY` - Get SPY current price\n"
                "• `/pop 0.30` - POP for Δ0.30 (70% for shorts)\n"
                "• `/contracts 500 125` - Contracts for $500 risk at $1.25 premium\n"
                "• `/iv AAPL` - Check AAPL IV regime\n"
                "• `/spread QQQ 5` - Validate 5-wide spread on QQQ\n"
                "• `/earnings TSLA` - When is TSLA earnings?\n"
                "• `/calc bull_put_spread SPY 540/535 7` - Calculate 540/535 BPS"
            ),
            inline=False,
        )

        embed.add_field(
            name="🎯 ICT Bias Reasons (/plan advanced)",
            value="`ssl_sweep` • `bsl_sweep` • `fvg_retest` • `structure_shift` • `user_manual`",
            inline=False,
        )

        embed.set_footer(text="Volaris Trading Intelligence • 26 Commands Available")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: VolarisBot) -> None:
    """Register utility cogs."""
    await bot.add_cog(AlertsCog(bot))
    await bot.add_cog(StreamsCog(bot))
    await bot.add_cog(UtilitiesCog(bot))
