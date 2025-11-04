"""
Recurring price stream commands - MOVED TO LEGACY (unused, low value).

StreamsCog allowed users to subscribe to recurring price updates in channels.
Removed in favor of more targeted flow alerts and on-demand queries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from app.alerts.discord_bot import VolarisBot


class StreamsCog(
    commands.GroupCog, name="streams", group_description="Manage recurring price streams"
):
    """Slash command group for scheduled price stream management."""

    def __init__(self, bot: VolarisBot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name="add", description="Start a recurring price update")
    @app_commands.describe(ticker="Ticker symbol (e.g., SPY)", interval="Update cadence in minutes")
    @app_commands.choices(
        interval=[
            app_commands.Choice(name="5 minutes", value=5),
            app_commands.Choice(name="15 minutes", value=15),
            app_commands.Choice(name="30 minutes", value=30),
            app_commands.Choice(name="60 minutes", value=60),
        ]
    )
    async def add(self, interaction: discord.Interaction, ticker: str, interval: int) -> None:
        """Create a recurring price stream for the current channel."""
        await interaction.response.defer(ephemeral=True)

        try:
            stream = await self.bot.streams_api.create_stream(
                symbol=ticker,
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

    @add.autocomplete("ticker")
    async def streams_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for /streams add ticker parameter."""
        _ = interaction
        try:
            matches = self.bot.symbol_service.matches(current)
            return [
                app_commands.Choice(name=self.bot.symbol_service.get_display_name(sym), value=sym)
                for sym in matches
            ]
        except Exception:  # pylint: disable=broad-except
            self.bot.logger.error("Autocomplete error in /streams add", exc_info=True)
            return []

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


async def setup(bot: VolarisBot) -> None:
    """Register streams cog (legacy)."""
    await bot.add_cog(StreamsCog(bot))
