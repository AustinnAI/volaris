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

    @app_commands.command(name="view", description="View watchlist with AI portfolio insights")
    async def view_watchlist(self, interaction: discord.Interaction) -> None:
        """Display watchlist with sentiment and optional AI insights (public)."""
        await interaction.response.defer()

        try:
            # Get watchlist symbols
            symbols = await self.bot.market_api.get_watchlist()
            if not symbols:
                await interaction.followup.send("⚠️ Watchlist is empty.")
                return

            # Get sentiment data for all watchlist symbols
            symbols_param = ",".join(symbols)
            url = f"{self.bot.config.API_BASE_URL}/api/v1/news/sentiment/summary?symbols={symbols_param}&days=7"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    result = await response.json()

            watchlist_data = result.get("tickers", [])
            if not watchlist_data:
                await interaction.followup.send("❌ No sentiment data available for watchlist.")
                return

            # Try to get AI insights
            insights = None
            try:
                from app.config import settings
                from app.core.ai.llm_client import get_llm_client
                from app.core.ai.prompts import build_watchlist_cache_key, build_watchlist_insights_prompt
                from app.utils.cache import cache
                import json

                if settings.LLM_WATCHLIST_INSIGHTS_ENABLED and settings.LLM_ENABLED:
                    all_symbols = [t["symbol"] for t in watchlist_data]
                    cache_key = build_watchlist_cache_key(all_symbols)

                    cached = await cache.get(cache_key)
                    if cached:
                        insights = json.loads(cached).get("insights")

                    if not insights:
                        llm_client = get_llm_client()
                        if llm_client:
                            prompt = build_watchlist_insights_prompt(watchlist_data)
                            response = await llm_client.summarize(
                                prompt=prompt,
                                model=settings.LLM_MODEL,
                                max_tokens=300,
                                temperature=settings.LLM_TEMPERATURE,
                            )
                            insights = response.get("insights")
                            if insights:
                                ttl = settings.LLM_WATCHLIST_INSIGHTS_TTL_MINUTES * 60
                                await cache.set(cache_key, json.dumps({"insights": insights}), ttl)
                        else:
                            self.bot.logger.debug("LLM client unavailable for /watchlist view")
            except Exception as e:
                self.bot.logger.warning(f"Failed to generate watchlist insights: {e}")

            # Build embed
            description = f"Tracking {len(watchlist_data)} symbols"
            if insights:
                description = f"💡 **Portfolio Insights:** {insights}\n\n{description}"

            embed = discord.Embed(
                title="📊 Watchlist Overview",
                description=description,
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow(),
            )

            # Group by sentiment
            bullish = [t for t in watchlist_data if t["label"] == "positive"]
            bearish = [t for t in watchlist_data if t["label"] == "negative"]
            neutral = [t for t in watchlist_data if t["label"] == "neutral"]

            if bullish:
                bullish_text = "\n".join([
                    f"**{t['symbol']}** • {t['weighted_score']:.2f}"
                    for t in bullish[:10]
                ])
                embed.add_field(name=f"🟢 Bullish ({len(bullish)})", value=bullish_text, inline=False)

            if bearish:
                bearish_text = "\n".join([
                    f"**{t['symbol']}** • {t['weighted_score']:.2f}"
                    for t in bearish[:10]
                ])
                embed.add_field(name=f"🔴 Bearish ({len(bearish)})", value=bearish_text, inline=False)

            if neutral:
                neutral_text = "\n".join([
                    f"**{t['symbol']}** • {t['weighted_score']:.2f}"
                    for t in neutral[:10]
                ])
                embed.add_field(name=f"⚪ Neutral ({len(neutral)})", value=neutral_text, inline=False)

            embed.set_footer(text=f"Requested by {interaction.user.display_name} • Based on 7-day sentiment")
            await interaction.followup.send(embed=embed)

        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ API error: {exc}")
        except Exception as exc:
            await interaction.followup.send(f"❌ Error: {str(exc)[:100]}")


async def setup(bot: VolarisBot) -> None:
    await bot.add_cog(WatchlistCog(bot))
