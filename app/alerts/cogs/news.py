"""
News & Sentiment slash commands for Phase 2.

Provides Discord commands to fetch recent news articles with VADER sentiment
analysis and aggregated sentiment metrics.
"""

from __future__ import annotations

import asyncio
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

        # Try to get AI narrative (Phase 2.2)
        narrative = None
        try:
            from app.services.news_service import generate_news_narrative
            from app.db.session import get_db

            async for db in get_db():
                narrative, fallback_used = await generate_news_narrative(db, symbol)
                if fallback_used and narrative is None:
                    self.bot.logger.debug(f"AI narrative disabled or unavailable for {symbol}")
                break
        except Exception as e:
            # Silently fail - narrative is optional enhancement
            self.bot.logger.warning(f"Failed to generate AI narrative for {symbol}: {e}")

        # Create embed with news articles
        description = f"Recent news from the last {days} day(s)"
        if narrative:
            description = f"💡 **AI Insight:** {narrative}\n\n{description}"

        embed = discord.Embed(
            title=f"📰 {symbol} News ({count} article{'' if count == 1 else 's'})",
            description=description,
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

    @app_commands.command(
        name="summary",
        description="Get AI-powered market intelligence summary",
    )
    @app_commands.describe(
        ticker="Ticker symbol (e.g., SPY, QQQ, AAPL)",
        force_refresh="Skip cache and generate fresh summary",
    )
    async def summary(
        self, interaction: discord.Interaction, ticker: str, force_refresh: bool = False
    ) -> None:
        """
        Generate AI-powered market intelligence summary with key drivers and insights.

        Uses OpenAI gpt-4o-mini to analyze recent news articles and sentiment,
        producing structured insights with citations.
        """
        await interaction.response.defer()

        try:
            # Call AI summary endpoint (increase timeout for LLM operations)
            url = f"{self.bot.api_client.base_url}/api/v1/news/{ticker}/summary"
            # Convert bool to string for aiohttp query params
            params = {"force_refresh": str(force_refresh).lower()}

            # Log the request for debugging
            print(f"[DEBUG] Calling summary API: {url}")

            # Use 60s timeout for AI summary (can take 10-15s on first call)
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params) as response:
                    print(f"[DEBUG] Response status: {response.status}")
                    if response.status == 404:
                        await interaction.followup.send(
                            f"❌ Ticker **{ticker.upper()}** not found or no news articles available."
                        )
                        return
                    elif response.status != 200:
                        error_detail = await response.text()
                        await interaction.followup.send(
                            f"❌ Failed to generate AI summary: {error_detail[:100]}"
                        )
                        return

                    data = await response.json()

        except (asyncio.TimeoutError, TimeoutError, aiohttp.ServerTimeoutError):
            await interaction.followup.send(
                "❌ Request timed out. AI summary generation can take 10-15s on first call. Try again - it should be cached now."
            )
            return
        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ Unable to fetch AI summary: {exc}")
            return
        except Exception as exc:
            await interaction.followup.send(
                f"❌ Unexpected error: {str(exc)[:100]}. Check that the API is running."
            )
            return

        # Extract response fields
        markdown = data.get("markdown", "")
        fallback_used = data.get("fallback_used", False)
        cache_hit = data.get("cache_hit", False)

        if not markdown:
            await interaction.followup.send(
                f"❌ No summary available for **{ticker.upper()}**. Try refreshing news first with `/refresh-news {ticker}`"
            )
            return

        # Determine embed color based on sentiment
        structured = data.get("structured", {})
        sentiment_snapshot = structured.get("sentiment_snapshot", {})
        net_score = sentiment_snapshot.get("net_score", 0.0)

        if net_score > 0.05:
            color = discord.Color.green()
        elif net_score < -0.05:
            color = discord.Color.red()
        else:
            color = discord.Color.greyple()

        # Create embed
        embed = discord.Embed(
            description=markdown,
            color=color,
            timestamp=discord.utils.utcnow(),
        )

        # Add footer with indicators
        footer_parts = [f"Requested by {interaction.user.display_name}"]
        if cache_hit:
            footer_parts.append("📦 Cached")
        if fallback_used:
            footer_parts.append("⚙️ Fallback Mode (LLM unavailable)")

        embed.set_footer(text=" • ".join(footer_parts))

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="top",
        description="Show top sentiment movers from liquid stocks",
    )
    @app_commands.describe(
        limit="Number of gainers/losers to show (3-10)",
        index="Index to analyze: liquid (default), nasdaq100, or sp500",
    )
    async def top(
        self,
        interaction: discord.Interaction,
        limit: int = 5,
        index: str = "liquid",
    ) -> None:
        """Display top sentiment movers from liquid stocks with optional AI narrative."""
        await interaction.response.defer()

        limit = min(max(limit, 3), 10)

        # Validate index parameter
        valid_indices = ["liquid", "nasdaq100", "sp500"]
        index_lower = index.lower()
        if index_lower not in valid_indices:
            await interaction.followup.send(
                f"❌ Invalid index. Use: {', '.join(valid_indices)}"
            )
            return

        try:
            # Call sentiment summary endpoint with min_articles filter and hybrid liquidity strategy
            # Default: liquid stocks (NASDAQ-100 + S&P 500) with volume >= 5M/day and at least 5 articles
            # Use hybrid filtering (index + volume) for better quality results
            url = f"{self.bot.api_client.base_url}/api/v1/news/sentiment/summary?symbols={index_lower}&days=7&min_articles=5&liquidity_strategy=hybrid"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    result = await response.json()

            tickers = result.get("tickers", [])
            if not tickers:
                await interaction.followup.send("❌ No newsworthy tickers found with minimum 5 articles.")
                return

            # Split into gainers (top) and losers (bottom)
            gainers = tickers[:limit]
            losers = tickers[-limit:][::-1]

            # Try to get AI narrative
            narrative = None
            try:
                from app.config import settings
                from app.core.ai.llm_client import get_llm_client
                from app.core.ai.prompts import build_top_movers_cache_key, build_top_movers_prompt
                from app.utils.cache import cache
                import json

                if settings.LLM_TOP_NARRATIVE_ENABLED and settings.LLM_ENABLED:
                    all_symbols = [t["symbol"] for t in tickers]
                    cache_key = build_top_movers_cache_key(all_symbols)

                    cached = await cache.get(cache_key)
                    if cached:
                        narrative = json.loads(cached).get("narrative")

                    if not narrative:
                        llm_client = get_llm_client()
                        if llm_client:
                            prompt = build_top_movers_prompt(gainers, losers)
                            response = await llm_client.summarize(
                                prompt=prompt,
                                model=settings.LLM_MODEL,
                                max_tokens=250,
                                temperature=settings.LLM_TEMPERATURE,
                            )
                            narrative = response.get("narrative")
                            if narrative:
                                ttl = settings.LLM_TOP_NARRATIVE_TTL_MINUTES * 60
                                await cache.set(cache_key, json.dumps({"narrative": narrative}), ttl)
                        else:
                            self.bot.logger.debug("LLM client unavailable for /top command")
            except Exception as e:
                self.bot.logger.warning(f"Failed to generate market pulse narrative: {e}")

            # Build embed
            description = "S&P 500 sentiment movers (last 7 days)"
            if narrative:
                description = f"💡 **Market Pulse:** {narrative}\n\n{description}"

            embed = discord.Embed(
                title="📈 Top Sentiment Movers",
                description=description,
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow(),
            )

            gainers_text = "\n".join([
                f"**{i+1}. {t['symbol']}** • {t['weighted_score']:.2f} • {t['article_count']} articles"
                for i, t in enumerate(gainers)
            ])
            embed.add_field(name="🟢 Gainers", value=gainers_text, inline=False)

            losers_text = "\n".join([
                f"**{i+1}. {t['symbol']}** • {t['weighted_score']:.2f} • {t['article_count']} articles"
                for i, t in enumerate(losers)
            ])
            embed.add_field(name="🔴 Losers", value=losers_text, inline=False)

            # Map index names to display names
            index_labels = {
                "liquid": "NASDAQ-100 + S&P 500",
                "nasdaq100": "NASDAQ-100",
                "sp500": "S&P 500"
            }
            footer = f"{index_labels.get(index_lower, index_lower)} • Min 5 articles • {interaction.user.display_name}"
            embed.set_footer(text=footer)
            await interaction.followup.send(embed=embed)

        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"❌ API error: {exc}")
        except Exception as exc:
            await interaction.followup.send(f"❌ Error: {str(exc)[:100]}")


async def setup(bot: VolarisBot) -> None:
    """Load the News cog."""
    await bot.add_cog(NewsCog(bot))
