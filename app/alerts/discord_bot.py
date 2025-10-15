"""
Discord bot bootstrap for Volaris.

This module wires shared services, loads command cogs, and maintains background
tasks for price alerts, price streams, and daily market digests.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp
import discord
from aiohttp import web
from discord.ext import commands, tasks

from app.alerts.helpers import (
    MarketInsightsAPI,
    PriceAlertAPI,
    PriceStreamAPI,
    StrategyRecommendationAPI,
    SymbolService,
    VolatilityAPI,
    build_top_movers_embed,
)
from app.config import settings

logger = logging.getLogger("volaris.discord_bot")


class VolarisBot(commands.Bot):
    """Discord bot that exposes Volaris strategy tooling."""

    def __init__(self, api_base_url: str, guild_id: int | None = None) -> None:
        intents = discord.Intents.default()
        intents.message_content = False

        super().__init__(command_prefix="!", intents=intents)

        self.logger = logger
        self.api_token = settings.VOLARIS_API_TOKEN or ""
        self.api_client = StrategyRecommendationAPI(api_base_url)
        self.alerts_api = PriceAlertAPI(api_base_url)
        self.streams_api = PriceStreamAPI(api_base_url)
        self.market_api = MarketInsightsAPI(api_base_url, api_token=self.api_token, timeout=30)
        self.volatility_api = VolatilityAPI(api_base_url)
        self.symbol_service = SymbolService()
        self.guild_id = guild_id
        self.user_command_count: dict[int, list[float]] = {}
        self.last_digest_date: str | None = None
        self.est_tz = ZoneInfo("America/New_York")
        self.watchlist_admin_user_ids = set(settings.WATCHLIST_ADMIN_USER_IDS)
        self.watchlist_admin_role_ids = set(settings.WATCHLIST_ADMIN_ROLE_IDS)

    async def setup_hook(self) -> None:
        """Load cogs first, then sync slash commands."""
        # Load extensions BEFORE syncing to avoid CommandAlreadyRegistered errors
        extensions = [
            "app.alerts.cogs.strategy",
            "app.alerts.cogs.market_data",
            "app.alerts.cogs.calculators",
            "app.alerts.cogs.utilities",
            "app.alerts.cogs.watchlist",
        ]
        for extension in extensions:
            if extension in self.extensions:
                continue
            try:
                await self.load_extension(extension)
                self.logger.info("Loaded extension %s", extension)
            except Exception:  # pylint: disable=broad-except
                self.logger.exception("Failed to load extension %s", extension)

        # Now sync commands to Discord after all cogs are loaded
        if self.guild_id:
            guild = discord.Object(id=self.guild_id)
            # Log commands before sync
            all_commands = self.tree.get_commands(type=discord.AppCommandType.chat_input)
            self.logger.info("Commands in tree before sync: %d", len(all_commands))
            for cmd in all_commands[:5]:  # Log first 5
                self.logger.info("  - %s", cmd.name)

            try:
                # Clear existing commands first to avoid conflicts
                self.tree.clear_commands(guild=guild)
                self.logger.info("Cleared existing guild commands")

                # Copy commands to guild
                self.tree.copy_global_to(guild=guild)

                # Sync to guild (commands are already loaded)
                synced = await asyncio.wait_for(self.tree.sync(guild=guild), timeout=30.0)
                self.logger.info("✅ Synced %d commands to guild %s", len(synced), self.guild_id)
            except TimeoutError:
                self.logger.error("❌ Command sync timed out after 30s")
            except Exception as e:
                self.logger.error("❌ Command sync failed: %s", e, exc_info=True)
        else:
            synced = await self.tree.sync()
            self.logger.info("Synced %d commands globally", len(synced))

        await self.refresh_symbol_cache()

        if not self.poll_price_alerts.is_running():
            self.poll_price_alerts.start()
        if not self.poll_price_streams.is_running():
            self.poll_price_streams.start()
        if not self.daily_top_digest.is_running():
            self.daily_top_digest.start()

    async def on_ready(self) -> None:
        """Log bot identity when it becomes ready."""
        self.logger.info("Bot ready as %s (ID: %s)", self.user.name, self.user.id)

    async def close(self) -> None:
        """Cleanup resources before shutting down."""
        self.logger.info("Closing API client sessions...")
        await self.api_client.close()
        await self.alerts_api.close()
        await self.streams_api.close()
        await self.market_api.close()
        await self.volatility_api.close()
        await super().close()

    async def refresh_symbol_cache(self) -> None:
        """Refresh S&P 500 symbols from the API for autocomplete."""
        try:
            symbols = await self.market_api.fetch_sp500_symbols()
            if symbols:
                self.symbol_service.update(symbols)
                self.logger.info("Loaded %s symbols from API", len(self.symbol_service.symbols))
        except aiohttp.ClientError as exc:
            self.logger.warning("Failed to refresh symbols from API: %s", exc)
        except Exception:  # pylint: disable=broad-except
            self.logger.exception("Unexpected error refreshing symbols")

    def check_rate_limit(self, user_id: int, max_per_minute: int = 3) -> bool:
        """Simple per-user rate limiter used by high-cost commands."""
        now = asyncio.get_event_loop().time()
        if user_id not in self.user_command_count:
            self.user_command_count[user_id] = []

        recent = [ts for ts in self.user_command_count[user_id] if now - ts < 60]
        self.user_command_count[user_id] = recent

        if len(recent) >= max_per_minute:
            return False

        recent.append(now)
        return True

    # ---------------------------------------------------------------------
    # Price alert polling
    # ---------------------------------------------------------------------
    @tasks.loop(seconds=settings.PRICE_ALERT_POLL_SECONDS)
    async def poll_price_alerts(self) -> None:
        if not self.alerts_api:
            return

        try:
            triggered_alerts = await self.alerts_api.evaluate_alerts()
        except aiohttp.ClientError as exc:
            self.logger.error("Failed to evaluate price alerts: %s", exc)
            return
        except Exception:  # pylint: disable=broad-except
            self.logger.exception("Unexpected error while evaluating price alerts")
            return

        if not triggered_alerts:
            return

        for alert in triggered_alerts:
            channel_id = int(alert["channel_id"])
            channel = self.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.fetch_channel(channel_id)
                except Exception:  # pylint: disable=broad-except
                    self.logger.warning(
                        "Unable to locate channel for price alert", extra={"channel_id": channel_id}
                    )
                    continue

            direction = alert.get("direction", "above")
            symbol = alert.get("symbol", "")
            target_price = float(alert.get("target_price", 0))
            current_price = float(alert.get("current_price", 0))
            created_by = alert.get("created_by")

            emoji = "📈" if direction == "above" else "📉"
            direction_text = "≥" if direction == "above" else "≤"

            embed = discord.Embed(
                title=f"{emoji} Price Alert Triggered",
                color=discord.Color.green() if direction == "above" else discord.Color.red(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Symbol", value=symbol, inline=True)
            embed.add_field(name="Target", value=f"${target_price:,.2f}", inline=True)
            embed.add_field(name="Last Price", value=f"${current_price:,.2f}", inline=True)
            if created_by:
                embed.set_footer(
                    text=f"Created by <@{created_by}> • Fires when price {direction_text} target"
                )
            else:
                embed.set_footer(text=f"Fires when price {direction_text} target")

            try:
                await channel.send(embed=embed)
            except Exception:  # pylint: disable=broad-except
                self.logger.exception("Failed to send price alert notification")

    @poll_price_alerts.before_loop
    async def before_price_alert_loop(self) -> None:
        await self.wait_until_ready()

    # ---------------------------------------------------------------------
    # Price stream polling
    # ---------------------------------------------------------------------
    @tasks.loop(seconds=settings.PRICE_STREAM_POLL_SECONDS)
    async def poll_price_streams(self) -> None:
        try:
            streams = await self.streams_api.evaluate_streams()
        except aiohttp.ClientError as exc:
            self.logger.error("Failed to evaluate price streams: %s", exc)
            return
        except Exception:  # pylint: disable=broad-except
            self.logger.exception("Unexpected error evaluating price streams")
            return

        if not streams:
            return

        for stream in streams:
            channel_id = int(stream["channel_id"])
            channel = self.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.fetch_channel(channel_id)
                except Exception:  # pylint: disable=broad-except
                    self.logger.warning(
                        "Unable to locate channel for price stream",
                        extra={"channel_id": channel_id},
                    )
                    continue

            price = float(stream.get("price", 0))
            change = float(stream.get("change", 0))
            change_pct = float(stream.get("change_percent", 0))
            prev_close = float(stream.get("previous_close", 0))
            symbol = stream.get("symbol", "")

            if change > 0:
                color = discord.Color.green()
                emoji = "📈"
            elif change < 0:
                color = discord.Color.red()
                emoji = "📉"
            else:
                color = discord.Color.greyple()
                emoji = "➖"

            embed = discord.Embed(
                title=f"{emoji} {symbol} Price Update",
                color=color,
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Last", value=f"${price:,.2f}", inline=True)
            embed.add_field(name="Change", value=f"{change:+.2f} ({change_pct:+.2f}%)", inline=True)
            embed.add_field(name="Prev Close", value=f"${prev_close:,.2f}", inline=True)
            embed.set_footer(
                text=f"Interval: {stream['interval_seconds']//60} min • Stream #{stream['id']}"
            )

            try:
                await channel.send(embed=embed)
            except Exception:  # pylint: disable=broad-except
                self.logger.exception("Failed to send price stream update")

    @poll_price_streams.before_loop
    async def before_price_stream_loop(self) -> None:
        await self.wait_until_ready()

    # ---------------------------------------------------------------------
    # Daily top movers digest
    # ---------------------------------------------------------------------
    @tasks.loop(seconds=60)
    async def daily_top_digest(self) -> None:
        channel_id = settings.DISCORD_DEFAULT_CHANNEL_ID
        if not channel_id:
            return

        now_est = datetime.now(self.est_tz)
        if now_est.weekday() >= 5:
            return

        if now_est.hour == 16 and now_est.minute == 0:
            today_key = now_est.strftime("%Y-%m-%d")
            if self.last_digest_date == today_key:
                return

            try:
                data = await self.market_api.fetch_top_movers(settings.TOP_MOVERS_LIMIT)
            except aiohttp.ClientError as exc:
                self.logger.error("Failed to fetch top movers for digest: %s", exc)
                return
            except Exception:  # pylint: disable=broad-except
                self.logger.exception("Unexpected error fetching top movers")
                return

            channel = self.get_channel(int(channel_id))
            if channel is None:
                try:
                    channel = await self.fetch_channel(int(channel_id))
                except Exception:  # pylint: disable=broad-except
                    self.logger.warning(
                        "Unable to locate channel for daily digest",
                        extra={"channel_id": channel_id},
                    )
                    return

            data["limit"] = settings.TOP_MOVERS_LIMIT
            embed = build_top_movers_embed(data, title="🏁 S&P 500 Closing Movers")
            embed.set_footer(text="Automated daily digest • 4:00 PM ET")

            try:
                await channel.send(embed=embed)
                self.last_digest_date = today_key
            except Exception:  # pylint: disable=broad-except
                self.logger.exception("Failed to send daily digest")

    @daily_top_digest.before_loop
    async def before_top_digest_loop(self) -> None:
        await self.wait_until_ready()


bot: VolarisBot | None = None


def create_bot() -> VolarisBot:
    """Factory used by run_bot and tests."""
    guild_id_str = settings.discord_guild_id_resolved
    guild_id = int(guild_id_str) if guild_id_str else None
    return VolarisBot(api_base_url=settings.API_BASE_URL, guild_id=guild_id)


async def run_bot() -> None:
    """Run the Discord bot, optionally alongside the scheduler."""
    global bot  # noqa: PLW0603

    if not settings.DISCORD_BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN not configured")
        return

    if not settings.DISCORD_BOT_ENABLED:
        logger.info("Discord bot disabled (DISCORD_BOT_ENABLED=false)")
        return

    scheduler = None
    if settings.SCHEDULER_ENABLED:
        try:
            from app.db.database import init_db
            from app.workers import create_scheduler

            logger.info("Initializing database for scheduler...")
            await init_db()

            scheduler = create_scheduler()
            scheduler.start()
            logger.info("✅ Background scheduler started alongside Discord bot")
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed to start scheduler: %s", exc)
            logger.warning("Discord bot will continue without scheduler")

    bot = create_bot()

    # Start a simple HTTP health server for Render (runs on port 10000)
    # This prevents "no open ports" warnings when running as Web Service
    async def health_check(request):
        """Simple health endpoint for Render."""
        return web.json_response({"status": "running", "service": "Discord Bot"})

    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_get("/", health_check)

    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)

    try:
        # Start HTTP server in background
        await site.start()
        logger.info(f"Health server started on port {port}")

        # Start Discord bot (blocking)
        logger.info("Starting Discord bot...")
        await bot.start(settings.DISCORD_BOT_TOKEN)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Bot error: %s", exc)
    finally:
        if scheduler:
            logger.info("Shutting down scheduler...")
            scheduler.shutdown(wait=True)
            logger.info("Scheduler stopped")
        await runner.cleanup()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(run_bot())
