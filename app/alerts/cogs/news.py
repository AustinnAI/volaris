"""
News & Sentiment slash commands for Phase 2.

Provides Discord commands to fetch recent news articles with VADER sentiment
analysis and aggregated sentiment metrics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from app.alerts.discord_bot import VolarisBot


class NewsCog(commands.Cog):
    """Discord commands for news and sentiment analysis (Phase 2)."""

    def __init__(self, bot: VolarisBot) -> None:
        self.bot = bot

    @app_commands.command(
        name="news", description="Get recent news articles with sentiment analysis"
    )
    @app_commands.describe(
        ticker="Ticker symbol (e.g., AAPL, SPY)",
        limit="Number of articles to show (1-10)",
        days="Lookback period in days (1-30)",
    )
    async def news(
        self, interaction: discord.Interaction, ticker: str, limit: int = 5, days: int = 7
    ) -> None:
        """Display recent news articles with sentiment scores."""
        await interaction.response.defer()

        # Validate inputs
        limit = min(max(limit, 1), 10)  # Clamp to 1-10 for Discord display
        days = min(max(days, 1), 30)

        try:
            data = await self.bot.news_api.get_news(ticker, limit=limit, days=days)
        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ Unable to fetch news: {exc}")
            return

        symbol = data.get("symbol", ticker.upper())
        articles = data.get("articles", [])
        count = data.get("article_count", 0)

        if not articles:
            await interaction.followup.send(
                f"📰 No news articles found for **{symbol}** in the last {days} day(s)."
            )
            return

        # Create embed with news articles
        embed = discord.Embed(
            title=f"📰 {symbol} News ({count} article{'' if count == 1 else 's'})",
            description=f"Recent news from the last {days} day(s)",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )

        for i, article in enumerate(articles[:limit], 1):
            headline = article.get("headline", "No headline")
            source = article.get("source", "Unknown")
            url = article.get("url", "")
            sentiment_label = article.get("sentiment_label", "neutral")
            sentiment_score = article.get("sentiment_score", 0.5)
            published_at = article.get("published_at", "")

            # Emoji based on sentiment
            if sentiment_label == "positive":
                emoji = "🟢"
            elif sentiment_label == "negative":
                emoji = "🔴"
            else:
                emoji = "⚪"

            # Format published date
            pub_date = published_at[:10] if len(published_at) >= 10 else published_at

            # Truncate headline if too long
            if len(headline) > 80:
                headline = headline[:77] + "..."

            field_value = (
                f"{emoji} **{sentiment_label.capitalize()}** ({sentiment_score:.2f})\n"
                f"*{source}* • {pub_date}\n"
                f"[Read article]({url})"
                if url
                else f"*{source}* • {pub_date}"
            )

            embed.add_field(
                name=f"{i}. {headline}",
                value=field_value,
                inline=False,
            )

        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="news-sentiment", description="Get aggregated news sentiment for a ticker"
    )
    @app_commands.describe(
        ticker="Ticker symbol (e.g., AAPL, SPY)",
        days="Lookback period in days (1-30)",
    )
    async def news_sentiment(
        self, interaction: discord.Interaction, ticker: str, days: int = 7
    ) -> None:
        """Display aggregated news sentiment with bullish/bearish breakdown."""
        await interaction.response.defer()

        # Validate days
        days = min(max(days, 1), 30)

        try:
            data = await self.bot.news_api.get_sentiment(ticker, days=days)
        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ Unable to fetch sentiment: {exc}")
            return

        symbol = data.get("symbol", ticker.upper())
        weighted_score = data.get("weighted_score", 0.5)
        compound = data.get("compound", 0.0)
        label = data.get("label", "neutral")
        article_count = data.get("article_count", 0)
        bullish_pct = data.get("bullish_percent", 0)
        bearish_pct = data.get("bearish_percent", 0)
        neutral_pct = 100 - bullish_pct - bearish_pct

        # Determine color based on sentiment
        if label == "positive":
            color = discord.Color.green()
            emoji = "📈"
        elif label == "negative":
            color = discord.Color.red()
            emoji = "📉"
        else:
            color = discord.Color.greyple()
            emoji = "➖"

        embed = discord.Embed(
            title=f"{emoji} {symbol} News Sentiment",
            description=f"Aggregated from {article_count} article{'' if article_count == 1 else 's'} over {days} day(s)",
            color=color,
            timestamp=discord.utils.utcnow(),
        )

        # Overall sentiment
        embed.add_field(
            name="Overall Sentiment",
            value=f"**{label.capitalize()}**\nScore: {weighted_score:.2f}\nCompound: {compound:+.2f}",
            inline=True,
        )

        # Breakdown
        embed.add_field(
            name="Breakdown",
            value=f"🟢 Bullish: {bullish_pct}%\n🔴 Bearish: {bearish_pct}%\n⚪ Neutral: {neutral_pct}%",
            inline=True,
        )

        # Interpretation
        if article_count == 0:
            interpretation = "No news articles available for sentiment analysis."
        elif bullish_pct > 60:
            interpretation = "Strong bullish sentiment in recent news."
        elif bearish_pct > 60:
            interpretation = "Strong bearish sentiment in recent news."
        elif bullish_pct > bearish_pct + 10:
            interpretation = "Moderately bullish sentiment."
        elif bearish_pct > bullish_pct + 10:
            interpretation = "Moderately bearish sentiment."
        else:
            interpretation = "Mixed or neutral sentiment in recent news."

        embed.add_field(
            name="Interpretation",
            value=interpretation,
            inline=False,
        )

        embed.set_footer(
            text=f"Requested by {interaction.user.display_name} • Uses exponential recency weighting (24h half-life)"
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="refresh-news", description="Force refresh news articles for a ticker"
    )
    @app_commands.describe(
        ticker="Ticker symbol (e.g., AAPL, SPY)",
        days="Lookback period in days (1-30)",
    )
    async def refresh_news(
        self, interaction: discord.Interaction, ticker: str, days: int = 7
    ) -> None:
        """Manually trigger news refresh from Finnhub."""
        await interaction.response.defer()

        # Validate days
        days = min(max(days, 1), 30)

        try:
            data = await self.bot.news_api.refresh_news(ticker, days=days)
        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ Failed to refresh news: {exc}")
            return

        symbol = data.get("symbol", ticker.upper())
        new_articles = data.get("new_articles", 0)
        message = data.get("message", f"Refreshed {new_articles} articles")

        if new_articles > 0:
            embed = discord.Embed(
                title=f"✅ {symbol} News Refreshed",
                description=message,
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(
                name="New Articles",
                value=str(new_articles),
                inline=True,
            )
            embed.add_field(
                name="Lookback Period",
                value=f"{days} day(s)",
                inline=True,
            )
        else:
            embed = discord.Embed(
                title=f"ℹ️ {symbol} News Up-to-Date",
                description="No new articles found (all articles already in database).",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow(),
            )

        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)


async def setup(bot: VolarisBot) -> None:
    """Load the News cog."""
    await bot.add_cog(NewsCog(bot))
