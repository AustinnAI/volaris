"""
Watchlist management commands for Discord admins.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from app.alerts.discord_bot import VolarisBot


class WatchlistCog(
    commands.GroupCog, name="watchlist", group_description="Manage Volaris watchlist"
):
    """Admin-only commands to view and update the server-side watchlist."""

    def __init__(self, bot: VolarisBot) -> None:
        self.bot = bot
        super().__init__()

    def _is_authorized(self, interaction: discord.Interaction) -> bool:
        """Return True if the user is allowed to manage the watchlist."""
        if not isinstance(interaction.user, discord.Member):
            return False

        allowed_users = getattr(self.bot, "watchlist_admin_user_ids", set())
        allowed_roles = getattr(self.bot, "watchlist_admin_role_ids", set())

        if allowed_users and interaction.user.id in allowed_users:
            return True

        if allowed_roles:
            user_roles = {role.id for role in getattr(interaction.user, "roles", [])}
            if user_roles & allowed_roles:
                return True

        return interaction.user.guild_permissions.administrator

    @app_commands.command(name="get", description="Show the current server watchlist symbols")
    async def get_watchlist(self, interaction: discord.Interaction) -> None:
        """Display watchlist symbols to authorized users."""
        if not self._is_authorized(interaction):
            await interaction.response.send_message(
                "❌ You do not have permission to manage the watchlist.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            symbols = await self.bot.market_api.get_watchlist()
        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ Failed to load watchlist: {exc}", ephemeral=True)
            return

        if not symbols:
            await interaction.followup.send("⚠️ Watchlist is empty.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Server Watchlist",
            description=", ".join(symbols),
            color=discord.Color.blue(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="set", description="Replace the watchlist symbols (space separated)")
    @app_commands.describe(symbols="Space or comma separated tickers, e.g. AAPL MSFT NVDA")
    async def set_watchlist(self, interaction: discord.Interaction, symbols: str) -> None:
        """Persist a new watchlist list."""
        if not self._is_authorized(interaction):
            await interaction.response.send_message(
                "❌ You do not have permission to manage the watchlist.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        parts = [
            token.strip().upper() for token in symbols.replace(",", " ").split() if token.strip()
        ]
        if not parts:
            await interaction.followup.send("❌ Provide at least one symbol.", ephemeral=True)
            return

        try:
            updated = await self.bot.market_api.set_watchlist(parts)
        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ Failed to update watchlist: {exc}", ephemeral=True)
            return

        embed = discord.Embed(
            title="✅ Watchlist Updated",
            description=", ".join(updated),
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: VolarisBot) -> None:
    await bot.add_cog(WatchlistCog(bot))
