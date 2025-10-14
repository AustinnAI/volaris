"""
Market data and analytics slash commands.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from app.alerts.helpers import build_top_movers_embed
from app.config import settings

if TYPE_CHECKING:
    from app.alerts.discord_bot import VolarisBot


class MarketDataCog(commands.Cog):
    """Surface sentiment, prices, and fundamental context via slash commands."""

    def __init__(self, bot: "VolarisBot") -> None:
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
    @app_commands.describe(symbol="Ticker symbol (S&P 500 only)")
    async def sentiment(self, interaction: discord.Interaction, symbol: str) -> None:
        """Return aggregated sentiment metrics."""
        await interaction.response.defer()

        try:
            data = await self.bot.market_api.fetch_sentiment(symbol)
        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ Unable to fetch sentiment: {exc}")
            return

        bullish = data.get("bullish_percent") or 0.0
        bearish = data.get("bearish_percent") or 0.0
        color = discord.Color.green() if bullish >= bearish else discord.Color.red()

        embed = discord.Embed(
            title=f"🧠 {symbol.upper()} Sentiment",
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

    @sentiment.autocomplete("symbol")
    async def sentiment_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for sentiment symbol selection."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [app_commands.Choice(name=sym, value=sym) for sym in matches]

    # -------------------------------------------------------------------------
    # Top movers digest
    # -------------------------------------------------------------------------
    @app_commands.command(name="top", description="Show top S&P 500 gainers and losers")
    @app_commands.describe(limit="Number of gainers/losers to show (default from config)")
    async def top(self, interaction: discord.Interaction, limit: Optional[int] = None) -> None:
        """Display top movers using cached Tiingo/Finnhub data."""
        await interaction.response.defer()

        movers_limit = limit or settings.TOP_MOVERS_LIMIT
        try:
            data = await self.bot.market_api.fetch_top_movers(movers_limit)
        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ Unable to fetch top movers: {exc}")
            return

        data["limit"] = movers_limit
        embed = build_top_movers_embed(data, title=f"Top {movers_limit} S&P 500 Movers")
        await interaction.followup.send(embed=embed)

    # -------------------------------------------------------------------------
    # Price command
    # -------------------------------------------------------------------------
    @app_commands.command(name="price", description="Get current stock price and % change")
    @app_commands.describe(symbol="Ticker symbol (e.g., SPY, AAPL)")
    async def price(self, interaction: discord.Interaction, symbol: str) -> None:
        """Fetch the latest price snapshot."""
        await interaction.response.defer()

        try:
            symbol_clean = symbol.upper().strip()
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

    @price.autocomplete("symbol")
    async def price_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for /price."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [app_commands.Choice(name=sym, value=sym) for sym in matches]

    # -------------------------------------------------------------------------
    # Implied volatility
    # -------------------------------------------------------------------------
    @app_commands.command(name="iv", description="Get IV, IV rank, and IV percentile for a stock")
    @app_commands.describe(symbol="Ticker symbol (e.g., SPY, AAPL)")
    async def iv(self, interaction: discord.Interaction, symbol: str) -> None:
        """Return IV statistics and regime classification."""
        await interaction.response.defer()

        try:
            symbol_clean = symbol.upper().strip()
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

    @iv.autocomplete("symbol")
    async def iv_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for /iv."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [app_commands.Choice(name=sym, value=sym) for sym in matches]

    # -------------------------------------------------------------------------
    # Quote
    # -------------------------------------------------------------------------
    @app_commands.command(
        name="quote", description="Get full quote with price, volume, and bid/ask"
    )
    @app_commands.describe(symbol="Ticker symbol (e.g., SPY, AAPL)")
    async def quote(self, interaction: discord.Interaction, symbol: str) -> None:
        """Return a richer quote with bid/ask context."""
        await interaction.response.defer()

        try:
            symbol_clean = symbol.upper().strip()
            await self._maybe_refresh_price(symbol_clean)
            url = f"{self.bot.api_client.base_url}/api/v1/market/quote/{symbol_clean}"

            # DEBUG: Log the URL being called
            self.bot.logger.info(f"Calling quote API: {url}")

            async with aiohttp.ClientSession(timeout=self.bot.api_client.timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        await interaction.followup.send(f"❌ API error: {error_text}")
                        return
                    data = await response.json()

            price = data.get("price", 0.0)
            bid = data.get("bid", 0.0)
            ask = data.get("ask", 0.0)
            volume = data.get("volume", 0)
            avg_volume = data.get("avg_volume", volume)
            change_pct = data.get("change_pct", 0.0)

            # DEBUG: Log what API returned
            self.bot.logger.info(
                f"Quote API response for {symbol_clean}: change_pct={change_pct}, data={data}"
            )

            if change_pct > 0:
                color = discord.Color.green()
            elif change_pct < 0:
                color = discord.Color.red()
            else:
                color = discord.Color.greyple()

            embed = discord.Embed(title=f"📋 {symbol_clean} Quote", color=color)
            embed.add_field(name="Last Price", value=f"**${price:.2f}**", inline=True)
            embed.add_field(name="Bid", value=f"${bid:.2f}", inline=True)
            embed.add_field(name="Ask", value=f"${ask:.2f}", inline=True)

            spread = ask - bid
            spread_pct = (spread / price * 100) if price > 0 else 0
            embed.add_field(
                name="Bid-Ask Spread", value=f"${spread:.2f} ({spread_pct:.2f}%)", inline=True
            )
            embed.add_field(name="Change", value=f"{change_pct:+.2f}%", inline=True)
            embed.add_field(name="Volume", value=f"{volume:,}", inline=True)

            if avg_volume > 0:
                volume_ratio = volume / avg_volume
                embed.add_field(name="Avg Volume", value=f"{avg_volume:,}", inline=True)
                embed.add_field(name="Volume Ratio", value=f"{volume_ratio:.2f}x", inline=True)

            embed.set_footer(text=f"Real-time quote • {symbol_clean}")

            await interaction.followup.send(embed=embed)

        except Exception as exc:  # pylint: disable=broad-except
            self.bot.logger.error("Error in /quote", exc_info=True)
            await interaction.followup.send(f"❌ Error: {exc}")

    @quote.autocomplete("symbol")
    async def quote_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for /quote."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [app_commands.Choice(name=sym, value=sym) for sym in matches]

    # -------------------------------------------------------------------------
    # Earnings
    # -------------------------------------------------------------------------
    @app_commands.command(name="earnings", description="Get next earnings date for a stock")
    @app_commands.describe(symbol="Ticker symbol (e.g., AAPL)")
    async def earnings(self, interaction: discord.Interaction, symbol: str) -> None:
        """Return next earnings date and how far out it is."""
        await interaction.response.defer()

        try:
            symbol_clean = symbol.upper().strip()
            url = f"{self.bot.api_client.base_url}/api/v1/market/earnings/{symbol_clean}"

            async with aiohttp.ClientSession(timeout=self.bot.api_client.timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        await interaction.followup.send(f"❌ API error: {error_text}")
                        return
                    data = await response.json()

            earnings_date_str = data.get("earnings_date")
            if not earnings_date_str:
                await interaction.followup.send(f"❌ No earnings date available for {symbol_clean}")
                return

            earnings_date = datetime.fromisoformat(earnings_date_str.replace("Z", "+00:00")).date()
            today = date.today()
            days_until = (earnings_date - today).days

            if days_until < 0:
                color = discord.Color.greyple()
                emoji = "📅"
                status = "Past"
            elif days_until <= 7:
                color = discord.Color.red()
                emoji = "⚠️"
                status = "Imminent (Avoid trades)"
            elif days_until <= 30:
                color = discord.Color.gold()
                emoji = "📊"
                status = "Upcoming (Use caution)"
            else:
                color = discord.Color.green()
                emoji = "✅"
                status = "Far out (Safe to trade)"

            embed = discord.Embed(title=f"{emoji} {symbol_clean} Earnings", color=color)
            embed.add_field(
                name="Next Earnings", value=earnings_date.strftime("%B %d, %Y"), inline=True
            )
            embed.add_field(name="Days Until", value=f"**{days_until}** days", inline=True)
            embed.add_field(name="Status", value=status, inline=True)

            if days_until <= 7:
                recommendation = "❌ Avoid new positions (high IV crush risk, unpredictable moves)"
            elif days_until <= 30:
                recommendation = "⚠️ Use shorter DTE or wait (IV may be elevated)"
            else:
                recommendation = "✅ Safe to trade (no immediate earnings risk)"

            embed.add_field(name="💡 Trading Recommendation", value=recommendation, inline=False)
            embed.set_footer(text=f"Earnings data • {symbol_clean}")

            await interaction.followup.send(embed=embed)

        except Exception as exc:  # pylint: disable=broad-except
            self.bot.logger.error("Error in /earnings", exc_info=True)
            await interaction.followup.send(f"❌ Error: {exc}")

    @earnings.autocomplete("symbol")
    async def earnings_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for /earnings."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [app_commands.Choice(name=sym, value=sym) for sym in matches]

    # -------------------------------------------------------------------------
    # 52-week range
    # -------------------------------------------------------------------------
    @app_commands.command(name="range", description="Get 52-week high/low and current position")
    @app_commands.describe(symbol="Ticker symbol (e.g., SPY)")
    async def range(self, interaction: discord.Interaction, symbol: str) -> None:
        """Show where the stock trades within its 52-week range."""
        await interaction.response.defer()

        try:
            symbol_clean = symbol.upper().strip()
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

    @range.autocomplete("symbol")
    async def range_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for /range."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [app_commands.Choice(name=sym, value=sym) for sym in matches]

    # -------------------------------------------------------------------------
    # Volume analysis
    # -------------------------------------------------------------------------
    @app_commands.command(name="volume", description="Compare today's volume to 30-day average")
    @app_commands.describe(symbol="Ticker symbol (e.g., SPY)")
    async def volume(self, interaction: discord.Interaction, symbol: str) -> None:
        """Compare intraday volume to 30-day average."""
        await interaction.response.defer()

        try:
            symbol_clean = symbol.upper().strip()
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

    @volume.autocomplete("symbol")
    async def volume_symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for /volume."""
        _ = interaction
        matches = self.bot.symbol_service.matches(current)
        return [app_commands.Choice(name=sym, value=sym) for sym in matches]


async def setup(bot: "VolarisBot") -> None:
    """Register the market data cog."""
    await bot.add_cog(MarketDataCog(bot))
