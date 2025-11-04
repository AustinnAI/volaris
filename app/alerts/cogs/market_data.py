"""
Market data and analytics slash commands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from app.config import settings

if TYPE_CHECKING:
    from app.alerts.discord_bot import VolarisBot


class MarketDataCog(commands.Cog):
    """Surface sentiment, prices, and fundamental context via slash commands."""

    def __init__(self, bot: VolarisBot) -> None:
        self.bot = bot

    async def _maybe_refresh_price(self, symbol: str) -> None:
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

    async def _maybe_refresh_option_context(self, symbol: str) -> None:
        if settings.SCHEDULER_ENABLED:
            return
        try:
            await self.bot.market_api.refresh_price(symbol)
            await self.bot.market_api.refresh_option_chain(symbol)
            await self.bot.market_api.refresh_iv_metrics(symbol)
        except aiohttp.ClientError as exc:
            self.bot.logger.warning(
                "Option context refresh failed", extra={"symbol": symbol, "error": str(exc)}
            )
        except Exception:  # pylint: disable=broad-except
            self.bot.logger.exception("Unexpected option refresh failure", extra={"symbol": symbol})

    # -------------------------------------------------------------------------
    # Sentiment
    # -------------------------------------------------------------------------
    @app_commands.command(
        name="sentiment", description="Show sentiment metrics for an S&P 500 stock"
    )
    @app_commands.describe(ticker="Ticker symbol (S&P 500 only)")
    async def sentiment(self, interaction: discord.Interaction, ticker: str) -> None:
        """Return aggregated sentiment metrics."""
        await interaction.response.defer()

        try:
            data = await self.bot.market_api.fetch_sentiment(ticker)
        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ Unable to fetch sentiment: {exc}")
            return

        bullish = data.get("bullish_percent") or 0.0
        bearish = data.get("bearish_percent") or 0.0
        color = discord.Color.green() if bullish >= bearish else discord.Color.red()

        embed = discord.Embed(
            title=f"🧠 {ticker.upper()} Sentiment",
            color=color,
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(name="Bullish", value=f"{bullish:.2f}%", inline=True)
        embed.add_field(name="Bearish", value=f"{bearish:.2f}%", inline=True)
        embed.add_field(
            name="News Buzz",
            value=f"Score: {data.get('buzz', {}).get('articlesInLastWeek', 0)} articles",
            inline=True,
        )

        sector_avg = data.get("sector_average_bullish_percent")
        if sector_avg is not None:
            embed.add_field(name="Sector Avg Bullish%", value=f"{sector_avg:.2f}%", inline=True)

        recommendations = data.get("recommendation_trend", {})
        if recommendations:
            embed.add_field(
                name="Analyst Trend",
                value=(
                    f"Strong Buy: {recommendations.get('strongBuy', 0)} | Buy: {recommendations.get('buy', 0)}\n"
                    f"Hold: {recommendations.get('hold', 0)} | Sell: {recommendations.get('sell', 0)} | "
                    f"Strong Sell: {recommendations.get('strongSell', 0)}"
                ),
                inline=False,
            )

        embed.set_footer(text="Sentiment data sourced from Finnhub")

        await interaction.followup.send(embed=embed)

    @sentiment.autocomplete("ticker")
    async def sentiment_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for sentiment ticker selection."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [
            app_commands.Choice(name=self.bot.symbol_service.get_display_name(sym), value=sym)
            for sym in matches
        ]

    # -------------------------------------------------------------------------
    # Top movers - REMOVED in V1 (requires Polygon or populated price_bars)
    # -------------------------------------------------------------------------
    # See legacy/ for removed /top command
    # Restore in V2 when scheduler populates price_bars or Polygon is added

    # -------------------------------------------------------------------------
    # Price command
    # -------------------------------------------------------------------------
    @app_commands.command(name="price", description="Get current stock price and % change")
    @app_commands.describe(ticker="Ticker symbol (e.g., SPY, AAPL)")
    async def price(self, interaction: discord.Interaction, ticker: str) -> None:
        """Fetch the latest price snapshot."""
        await interaction.response.defer()

        try:
            symbol_clean = ticker.upper().strip()
            await self._maybe_refresh_price(symbol_clean)
            url = f"{self.bot.api_client.base_url}/api/v1/market/price/{symbol_clean}"

            async with aiohttp.ClientSession(timeout=self.bot.api_client.timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        await interaction.followup.send(f"❌ API error: {error_text}")
                        return
                    data = await response.json()

            current_price = data.get("price", 0.0)
            previous_close = data.get("previous_close", current_price)
            change = current_price - previous_close
            change_pct = (change / previous_close * 100) if previous_close else 0

            if change > 0:
                color = discord.Color.green()
                emoji = "📈"
            elif change < 0:
                color = discord.Color.red()
                emoji = "📉"
            else:
                color = discord.Color.greyple()
                emoji = "➡️"

            embed = discord.Embed(title=f"{emoji} {symbol_clean} Price", color=color)
            embed.add_field(name="Current Price", value=f"**${current_price:.2f}**", inline=True)
            embed.add_field(
                name="Change", value=f"${change:+.2f} ({change_pct:+.2f}%)", inline=True
            )
            embed.add_field(name="Previous Close", value=f"${previous_close:.2f}", inline=True)

            volume = data.get("volume")
            if volume:
                embed.add_field(name="Volume", value=f"{volume:,}", inline=True)

            embed.set_footer(text=f"Real-time data • {symbol_clean}")

            await interaction.followup.send(embed=embed)

        except Exception as exc:  # pylint: disable=broad-except
            self.bot.logger.error("Error in /price", exc_info=True)
            await interaction.followup.send(f"❌ Error: {exc}")

    @price.autocomplete("ticker")
    async def price_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for /price."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [
            app_commands.Choice(name=self.bot.symbol_service.get_display_name(sym), value=sym)
            for sym in matches
        ]

    # -------------------------------------------------------------------------
    # Implied volatility
    # -------------------------------------------------------------------------
    @app_commands.command(name="iv", description="Get IV, IV rank, and IV percentile for a stock")
    @app_commands.describe(ticker="Ticker symbol (e.g., SPY, AAPL)")
    async def iv(self, interaction: discord.Interaction, ticker: str) -> None:
        """Return IV statistics and regime classification."""
        await interaction.response.defer()

        try:
            symbol_clean = ticker.upper().strip()
            await self._maybe_refresh_option_context(symbol_clean)
            url = f"{self.bot.api_client.base_url}/api/v1/market/iv/{symbol_clean}"

            async with aiohttp.ClientSession(timeout=self.bot.api_client.timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        await interaction.followup.send(f"❌ API error: {error_text}")
                        return
                    data = await response.json()

            current_iv = data.get("current_iv", 0.0)
            iv_rank = data.get("iv_rank", 0.0)
            iv_percentile = data.get("iv_percentile", 0.0)
            iv_regime = data.get("regime", "unknown")

            if iv_regime == "high":
                color = discord.Color.red()
                emoji = "🔥"
            elif iv_regime == "low":
                color = discord.Color.green()
                emoji = "❄️"
            else:
                color = discord.Color.gold()
                emoji = "📊"

            embed = discord.Embed(title=f"{emoji} {symbol_clean} Implied Volatility", color=color)
            embed.add_field(name="Current IV", value=f"**{current_iv:.1f}%**", inline=True)
            embed.add_field(name="IV Rank", value=f"{iv_rank:.1f}%", inline=True)
            embed.add_field(name="IV Percentile", value=f"{iv_percentile:.1f}%", inline=True)
            embed.add_field(name="IV Regime", value=f"**{iv_regime.upper()}**", inline=False)

            if iv_regime == "high":
                strategy = "Favor credit spreads (sell premium, high IV = high premiums)"
            elif iv_regime == "low":
                strategy = "Favor debit spreads/long options (buy premium, low cost)"
            else:
                strategy = "Neutral - both credit and debit strategies viable"

            embed.add_field(name="💡 Strategy Suggestion", value=strategy, inline=False)
            embed.set_footer(text=f"IV Rank: % of days in past year IV was lower • {symbol_clean}")

            await interaction.followup.send(embed=embed)

        except Exception as exc:  # pylint: disable=broad-except
            self.bot.logger.error("Error in /iv", exc_info=True)
            await interaction.followup.send(f"❌ Error: {exc}")

    @iv.autocomplete("ticker")
    async def iv_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for /iv."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [
            app_commands.Choice(name=self.bot.symbol_service.get_display_name(sym), value=sym)
            for sym in matches
        ]

    # -------------------------------------------------------------------------
    # Quote - REMOVED (redundant with /price)
    # -------------------------------------------------------------------------
    # Entire /quote command commented out - use /price instead

    # -------------------------------------------------------------------------
    # Earnings - REMOVED (low priority for V1 sentiment/flow focus)
    # -------------------------------------------------------------------------
    # Entire /earnings command commented out - may be added back in Phase 4

    # -------------------------------------------------------------------------
    # 52-week range
    # -------------------------------------------------------------------------
    @app_commands.command(name="range", description="Get 52-week high/low and current position")
    @app_commands.describe(ticker="Ticker symbol (e.g., SPY)")
    async def range(self, interaction: discord.Interaction, ticker: str) -> None:
        """Show where the stock trades within its 52-week range."""
        await interaction.response.defer()

        try:
            symbol_clean = ticker.upper().strip()
            await self._maybe_refresh_price(symbol_clean)
            url = f"{self.bot.api_client.base_url}/api/v1/market/range/{symbol_clean}"

            async with aiohttp.ClientSession(timeout=self.bot.api_client.timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        await interaction.followup.send(f"❌ API error: {error_text}")
                        return
                    data = await response.json()

            price = data.get("current_price", 0.0)
            high_52w = data.get("high_52w", 0.0)
            low_52w = data.get("low_52w", 0.0)

            range_size = high_52w - low_52w
            position_pct = ((price - low_52w) / range_size * 100) if range_size > 0 else 50

            if position_pct >= 80:
                color = discord.Color.red()
                emoji = "🔴"
                context = "Near 52W high (overbought zone)"
            elif position_pct >= 60:
                color = discord.Color.orange()
                emoji = "🟠"
                context = "Upper range (bullish territory)"
            elif position_pct >= 40:
                color = discord.Color.blue()
                emoji = "🔵"
                context = "Mid-range (neutral)"
            elif position_pct >= 20:
                color = discord.Color.gold()
                emoji = "🟡"
                context = "Lower range (bearish territory)"
            else:
                color = discord.Color.green()
                emoji = "🟢"
                context = "Near 52W low (oversold zone)"

            embed = discord.Embed(title=f"{emoji} {symbol_clean} 52-Week Range", color=color)
            embed.add_field(name="Current Price", value=f"**${price:.2f}**", inline=True)
            embed.add_field(name="52W High", value=f"${high_52w:.2f}", inline=True)
            embed.add_field(name="52W Low", value=f"${low_52w:.2f}", inline=True)
            embed.add_field(name="Range Position", value=f"**{position_pct:.0f}%**", inline=True)
            embed.add_field(name="Context", value=context, inline=False)

            if position_pct >= 80:
                ict_context = "Look for BSL sweeps above highs for bearish reversals"
            elif position_pct <= 20:
                ict_context = "Look for SSL sweeps below lows for bullish reversals"
            else:
                ict_context = "Monitor for liquidity sweeps at swing highs/lows"

            embed.add_field(name="💡 ICT Context", value=ict_context, inline=False)
            embed.set_footer(text=f"52-week range data • {symbol_clean}")

            await interaction.followup.send(embed=embed)

        except Exception as exc:  # pylint: disable=broad-except
            self.bot.logger.error("Error in /range", exc_info=True)
            await interaction.followup.send(f"❌ Error: {exc}")

    @range.autocomplete("ticker")
    async def range_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for /range."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [
            app_commands.Choice(name=self.bot.symbol_service.get_display_name(sym), value=sym)
            for sym in matches
        ]

    # -------------------------------------------------------------------------
    # Volume analysis
    # -------------------------------------------------------------------------
    @app_commands.command(name="volume", description="Compare today's volume to 30-day average")
    @app_commands.describe(ticker="Ticker symbol (e.g., SPY)")
    async def volume(self, interaction: discord.Interaction, ticker: str) -> None:
        """Compare intraday volume to 30-day average."""
        await interaction.response.defer()

        try:
            symbol_clean = ticker.upper().strip()
            await self._maybe_refresh_price(symbol_clean)
            url = f"{self.bot.api_client.base_url}/api/v1/market/volume/{symbol_clean}"

            async with aiohttp.ClientSession(timeout=self.bot.api_client.timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        await interaction.followup.send(f"❌ API error: {error_text}")
                        return
                    data = await response.json()

            current_volume = data.get("current_volume", 0)
            avg_volume = data.get("avg_volume_30d", 0)
            volume_ratio = (current_volume / avg_volume) if avg_volume > 0 else 1

            if volume_ratio >= 2.0:
                color = discord.Color.red()
                emoji = "🚀"
                context = "Exceptionally high (2x+ average)"
            elif volume_ratio >= 1.5:
                color = discord.Color.orange()
                emoji = "📈"
                context = "Above average (1.5-2x)"
            elif volume_ratio >= 0.75:
                color = discord.Color.blue()
                emoji = "➡️"
                context = "Normal (0.75-1.5x)"
            else:
                color = discord.Color.greyple()
                emoji = "📉"
                context = "Below average (<0.75x)"

            embed = discord.Embed(title=f"{emoji} {symbol_clean} Volume Analysis", color=color)
            embed.add_field(name="Today's Volume", value=f"**{current_volume:,}**", inline=True)
            embed.add_field(name="30D Avg Volume", value=f"{avg_volume:,}", inline=True)
            embed.add_field(name="Ratio", value=f"**{volume_ratio:.2f}x**", inline=True)
            embed.add_field(name="Context", value=context, inline=False)

            if volume_ratio >= 2.0:
                implication = "High volume confirms strong moves. Good for momentum trades."
            elif volume_ratio >= 1.5:
                implication = "Above-average participation. Moves may have follow-through."
            elif volume_ratio >= 0.75:
                implication = "Normal volume. Standard liquidity conditions."
            else:
                implication = "Low volume. Be cautious with wide bid-ask spreads."

            embed.add_field(name="💡 Trading Implication", value=implication, inline=False)
            embed.set_footer(text=f"Volume data • {symbol_clean}")

            await interaction.followup.send(embed=embed)

        except Exception as exc:  # pylint: disable=broad-except
            self.bot.logger.error("Error in /volume", exc_info=True)
            await interaction.followup.send(f"❌ Error: {exc}")

    @volume.autocomplete("ticker")
    async def volume_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for /volume."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [
            app_commands.Choice(name=self.bot.symbol_service.get_display_name(sym), value=sym)
            for sym in matches
        ]

    # -------------------------------------------------------------------------
    # Options Flow (Phase 3)
    # -------------------------------------------------------------------------
    @app_commands.command(
        name="flow",
        description="Detect unusual options activity (high volume, block trades, etc.)",
    )
    @app_commands.describe(
        ticker="Ticker symbol (e.g., SPY, QQQ, AAPL)",
        min_score="Minimum anomaly score (0.0-1.0, default 0.7)",
        force_refresh="Force fresh detection (ignores 1hr cache)",
    )
    async def flow(
        self,
        interaction: discord.Interaction,
        ticker: str,
        min_score: float = 0.7,
        force_refresh: bool = False,
    ) -> None:
        """Show unusual options flow for a ticker."""
        await interaction.response.defer()

        # Validate min_score range
        if not 0.0 <= min_score <= 1.0:
            await interaction.followup.send("❌ `min_score` must be between 0.0 and 1.0")
            return

        try:
            data = await self.bot.market_api.fetch_flow(
                ticker, min_score=min_score, force_refresh=force_refresh
            )
        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ Unable to fetch flow: {exc}")
            return

        symbol = data.get("symbol", ticker.upper())
        detected_count = data.get("detected_count", 0)
        unusual_trades = data.get("unusual_trades", [])
        provider = data.get("provider", "unknown")
        detection_time = data.get("detection_time", "")

        if detected_count == 0:
            embed = discord.Embed(
                title=f"📊 {symbol} Options Flow",
                description=f"No unusual activity detected (min_score ≥ {min_score:.2f})",
                color=discord.Color.light_gray(),
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text=f"Data source: {provider} • {detection_time}")
            await interaction.followup.send(embed=embed)
            return

        # Show summary embed with top 5 unusual trades
        color = discord.Color.gold()
        embed = discord.Embed(
            title=f"🔥 {symbol} Unusual Options Flow",
            description=f"Detected {detected_count} unusual contracts (score ≥ {min_score:.2f})",
            color=color,
            timestamp=discord.utils.utcnow(),
        )

        # Show top 5 trades by anomaly score
        top_trades = sorted(unusual_trades, key=lambda t: t["anomaly_score"], reverse=True)[:5]

        for i, trade in enumerate(top_trades, 1):
            contract = trade["contract_symbol"]
            option_type = trade["option_type"].upper()
            strike = trade["strike"]
            expiration = trade["expiration"]
            volume = trade["volume"]
            open_interest = trade["open_interest"]
            vol_oi_ratio = trade["volume_oi_ratio"]
            premium = trade["premium"]
            score = trade["anomaly_score"]
            flags = ", ".join(trade["flags"])

            # Format premium in millions/thousands
            if premium >= 1_000_000:
                premium_str = f"${premium / 1_000_000:.2f}M"
            elif premium >= 1_000:
                premium_str = f"${premium / 1_000:.1f}k"
            else:
                premium_str = f"${premium:.0f}"

            field_value = (
                f"**Strike:** ${strike:.2f} {option_type}\n"
                f"**Expiration:** {expiration}\n"
                f"**Volume:** {volume:,} | **OI:** {open_interest:,}\n"
                f"**Vol/OI:** {vol_oi_ratio:.2f}x | **Premium:** {premium_str}\n"
                f"**Score:** {score:.2f} | **Flags:** {flags}"
            )

            embed.add_field(
                name=f"#{i}: {contract}",
                value=field_value,
                inline=False,
            )

        embed.set_footer(text=f"Data source: {provider} • {detection_time}")

        await interaction.followup.send(embed=embed)

    @flow.autocomplete("ticker")
    async def flow_ticker_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for /flow ticker."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [
            app_commands.Choice(name=self.bot.symbol_service.get_display_name(sym), value=sym)
            for sym in matches
        ]

    # -------------------------------------------------------------------------
    # Flow Subscriptions (Phase 3.2 - Automated Alerts)
    # -------------------------------------------------------------------------
    @app_commands.command(
        name="flow-subscribe",
        description="Subscribe to automatic unusual flow alerts for a ticker",
    )
    @app_commands.describe(
        ticker="Ticker symbol (e.g., SPY, QQQ)",
        min_score="Minimum anomaly score for alerts (0.0-1.0, default 0.75)",
    )
    async def flow_subscribe(
        self,
        interaction: discord.Interaction,
        ticker: str,
        min_score: float = 0.75,
    ) -> None:
        """Subscribe to unusual flow alerts for a ticker."""
        await interaction.response.defer(ephemeral=True)

        # Validate min_score
        if not 0.0 <= min_score <= 1.0:
            await interaction.followup.send(
                "❌ `min_score` must be between 0.0 and 1.0", ephemeral=True
            )
            return

        symbol = ticker.upper().strip()
        user_id = str(interaction.user.id)
        channel_id = str(interaction.channel_id)

        try:
            url = f"{self.bot.api_client.base_url}/api/v1/flow/subscribe"
            payload = {
                "user_id": user_id,
                "symbol": symbol,
                "channel_id": channel_id,
                "min_score": min_score,
            }

            async with aiohttp.ClientSession(timeout=self.bot.api_client.timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        await interaction.followup.send(
                            f"✅ Subscribed to **{symbol}** flow alerts (score ≥ {min_score:.2f})\n"
                            f"You'll receive notifications in this channel when unusual activity is detected.",
                            ephemeral=True,
                        )
                    elif response.status == 409:
                        await interaction.followup.send(
                            f"ℹ️ You're already subscribed to **{symbol}** flow alerts.\n"
                            f"Use `/flow-unsubscribe {symbol}` to remove, then resubscribe with new settings.",
                            ephemeral=True,
                        )
                    else:
                        error_data = await response.json()
                        await interaction.followup.send(
                            f"❌ Failed to subscribe: {error_data.get('detail', 'Unknown error')}",
                            ephemeral=True,
                        )
        except Exception as exc:
            self.bot.logger.error("Error in /flow-subscribe", exc_info=True)
            await interaction.followup.send(f"❌ Error: {exc}", ephemeral=True)

    @flow_subscribe.autocomplete("ticker")
    async def flow_subscribe_ticker_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for /flow-subscribe ticker."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [
            app_commands.Choice(name=self.bot.symbol_service.get_display_name(sym), value=sym)
            for sym in matches
        ]

    @app_commands.command(
        name="flow-unsubscribe",
        description="Unsubscribe from unusual flow alerts for a ticker",
    )
    @app_commands.describe(ticker="Ticker symbol (e.g., SPY, QQQ)")
    async def flow_unsubscribe(self, interaction: discord.Interaction, ticker: str) -> None:
        """Unsubscribe from flow alerts for a ticker."""
        await interaction.response.defer(ephemeral=True)

        symbol = ticker.upper().strip()
        user_id = str(interaction.user.id)

        try:
            url = f"{self.bot.api_client.base_url}/api/v1/flow/unsubscribe"
            payload = {"user_id": user_id, "symbol": symbol}

            async with aiohttp.ClientSession(timeout=self.bot.api_client.timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        await interaction.followup.send(
                            f"✅ Unsubscribed from **{symbol}** flow alerts", ephemeral=True
                        )
                    elif response.status == 404:
                        await interaction.followup.send(
                            f"ℹ️ You don't have an active subscription to **{symbol}**",
                            ephemeral=True,
                        )
                    else:
                        error_data = await response.json()
                        await interaction.followup.send(
                            f"❌ Failed to unsubscribe: {error_data.get('detail', 'Unknown error')}",
                            ephemeral=True,
                        )
        except Exception as exc:
            self.bot.logger.error("Error in /flow-unsubscribe", exc_info=True)
            await interaction.followup.send(f"❌ Error: {exc}", ephemeral=True)

    @flow_unsubscribe.autocomplete("ticker")
    async def flow_unsubscribe_ticker_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for /flow-unsubscribe ticker."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [
            app_commands.Choice(name=self.bot.symbol_service.get_display_name(sym), value=sym)
            for sym in matches
        ]

    @app_commands.command(
        name="flow-subscriptions",
        description="List your active flow alert subscriptions",
    )
    async def flow_subscriptions(self, interaction: discord.Interaction) -> None:
        """List user's flow subscriptions."""
        await interaction.response.defer(ephemeral=True)

        user_id = str(interaction.user.id)

        try:
            url = f"{self.bot.api_client.base_url}/api/v1/flow/subscriptions/{user_id}"

            async with aiohttp.ClientSession(timeout=self.bot.api_client.timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        error_data = await response.json()
                        await interaction.followup.send(
                            f"❌ Failed to fetch subscriptions: {error_data.get('detail', 'Unknown error')}",
                            ephemeral=True,
                        )
                        return

                    data = await response.json()
                    subscriptions = data.get("subscriptions", [])

                    if not subscriptions:
                        await interaction.followup.send(
                            "📭 You don't have any active flow subscriptions.\n"
                            "Use `/flow-subscribe` to get alerts for unusual options activity!",
                            ephemeral=True,
                        )
                        return

                    embed = discord.Embed(
                        title="📊 Your Flow Alert Subscriptions",
                        description=f"You're subscribed to {len(subscriptions)} ticker(s)",
                        color=discord.Color.blue(),
                    )

                    for sub in subscriptions[:25]:  # Discord max 25 fields
                        symbol = sub.get("symbol", "???")
                        min_score = sub.get("min_score", 0.75)
                        created_at = sub.get("created_at", "")

                        embed.add_field(
                            name=f"📍 {symbol}",
                            value=f"Min Score: {min_score:.2f} • Since: {created_at}",
                            inline=True,
                        )

                    embed.set_footer(
                        text="Use /flow-unsubscribe to remove • Alerts sent to this channel"
                    )

                    await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as exc:
            self.bot.logger.error("Error in /flow-subscriptions", exc_info=True)
            await interaction.followup.send(f"❌ Error: {exc}", ephemeral=True)


async def setup(bot: VolarisBot) -> None:
    """Register the market data cog."""
    await bot.add_cog(MarketDataCog(bot))
