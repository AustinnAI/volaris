"""
Minimal Discord Bot for Volaris Strategy Recommendations
Provides /plan slash command to get trade recommendations from Phase 3.3
"""

import asyncio
import csv
import logging
from pathlib import Path
from typing import Optional
from decimal import Decimal

import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

from app.config import settings

# Configure logging
logger = logging.getLogger("volaris.discord_bot")

# Load S&P 500 symbols from CSV
def load_sp500_symbols() -> list[str]:
    """Load S&P 500 symbols from SP500.csv file."""
    symbols = []
    csv_path = Path(__file__).parent.parent.parent / "SP500.csv"

    # Major ETFs to prepend (prioritize these in autocomplete)
    priority_symbols = [
        "SPY", "QQQ", "IWM", "DIA", "VOO", "VTI", "GLD", "SLV", "TLT", "EEM"
    ]

    try:
        if csv_path.exists():
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    symbol = row.get('Symbol', '').strip()
                    if symbol:
                        symbols.append(symbol)
            logger.info(f"Loaded {len(symbols)} S&P 500 symbols from CSV")
        else:
            logger.warning(f"SP500.csv not found at {csv_path}, using fallback list")
            # Fallback to major tickers if CSV not found
            symbols = [
                "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "NFLX",
                "JPM", "BAC", "V", "MA", "WMT", "HD", "UNH", "JNJ"
            ]
    except Exception as e:
        logger.error(f"Error loading SP500.csv: {e}")
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]

    # Combine priority ETFs with S&P 500 (ETFs first for better autocomplete UX)
    return priority_symbols + [s for s in symbols if s not in priority_symbols]

# Load symbols once at module level
AVAILABLE_SYMBOLS = load_sp500_symbols()


class StrategyRecommendationAPI:
    """Client wrapper for calling the Volaris strategy recommendation API."""

    def __init__(self, base_url: str, timeout: int = 30):
        """
        Initialize API client.

        Args:
            base_url: Base URL of API (e.g., http://localhost:8000)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def recommend_strategy(
        self,
        symbol: str,
        bias: str,
        dte: int,
        mode: str = "auto",
        max_risk: Optional[float] = None,
        account_size: Optional[float] = None,
    ) -> dict:
        """
        Call strategy recommendation API.

        Args:
            symbol: Ticker symbol
            bias: bullish, bearish, or neutral
            dte: Days to expiration
            mode: auto, debit, or credit
            max_risk: Max risk per trade
            account_size: Account size for position sizing

        Returns:
            API response dict

        Raises:
            aiohttp.ClientError: On API errors
        """
        url = f"{self.base_url}/api/v1/strategy/recommend"

        # Build request body
        body = {
            "underlying_symbol": symbol.upper(),
            "bias": bias,
            "target_dte": dte,
            "dte_tolerance": 3,
        }

        # Map mode to objectives/constraints
        objectives = {}
        constraints = {}

        if account_size:
            objectives["account_size"] = account_size

        if max_risk:
            objectives["max_risk_per_trade"] = max_risk

        if mode == "credit":
            objectives["prefer_credit"] = True
            constraints["min_credit_pct"] = 25
        elif mode == "debit":
            objectives["prefer_credit"] = False

        if objectives:
            body["objectives"] = objectives
        if constraints:
            body["constraints"] = constraints

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url, json=body) as response:
                if response.status == 404:
                    data = await response.json()
                    raise ValueError(data.get("detail", "No data available"))
                elif response.status != 200:
                    try:
                        data = await response.json()
                        error_msg = data.get("detail", f"HTTP {response.status}")
                    except:
                        error_msg = f"HTTP {response.status}"
                    raise aiohttp.ClientError(f"API error: {error_msg}")

                return await response.json()


class VolarisBot(commands.Bot):
    """Minimal Discord bot for Volaris strategy recommendations."""

    def __init__(self, api_base_url: str, guild_id: Optional[int] = None):
        """
        Initialize bot.

        Args:
            api_base_url: Base URL for Volaris API
            guild_id: Guild ID for command registration (dev mode)
        """
        intents = discord.Intents.default()
        intents.message_content = False  # Not reading messages

        super().__init__(command_prefix="!", intents=intents)

        self.api_client = StrategyRecommendationAPI(api_base_url)
        self.guild_id = guild_id
        self.user_command_count = {}  # Simple rate limiter

    async def setup_hook(self):
        """Setup hook called when bot is ready."""
        # Register commands
        if self.guild_id:
            guild = discord.Object(id=self.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"Synced commands to guild {self.guild_id}")
        else:
            await self.tree.sync()
            logger.info("Synced commands globally")

    async def on_ready(self):
        """Called when bot is ready."""
        logger.info(f"Bot ready as {self.user.name} (ID: {self.user.id})")

    def check_rate_limit(self, user_id: int, max_per_minute: int = 3) -> bool:
        """
        Simple rate limit check.

        Args:
            user_id: Discord user ID
            max_per_minute: Max commands per minute

        Returns:
            True if allowed, False if rate limited
        """
        import time

        now = time.time()
        if user_id not in self.user_command_count:
            self.user_command_count[user_id] = []

        # Clean old timestamps (>60s ago)
        self.user_command_count[user_id] = [
            ts for ts in self.user_command_count[user_id] if now - ts < 60
        ]

        if len(self.user_command_count[user_id]) >= max_per_minute:
            return False

        self.user_command_count[user_id].append(now)
        return True


# Global bot instance
bot: Optional[VolarisBot] = None


def create_embed_for_recommendation(
    recommendation: dict,
    symbol: str,
    underlying_price: float,
    iv_regime: Optional[str],
    chosen_strategy: str,
) -> discord.Embed:
    """
    Create rich embed for a recommendation.

    Args:
        recommendation: Recommendation dict from API
        symbol: Ticker symbol
        underlying_price: Current price
        iv_regime: IV regime
        chosen_strategy: Strategy family

    Returns:
        Discord embed
    """
    rank = recommendation["rank"]
    strategy = recommendation["strategy_family"]
    position = recommendation["position"].upper()

    # Build title
    title = f"#{rank} {strategy.replace('_', ' ').title()} - {symbol} @ ${underlying_price:.2f}"

    # Determine color based on strategy
    color = discord.Color.green() if "credit" in strategy else discord.Color.blue()
    if "long" in strategy:
        color = discord.Color.gold()

    embed = discord.Embed(
        title=title,
        description=f"**IV Regime:** {iv_regime or 'N/A'} | **DTE:** {recommendation.get('dte', 'N/A')}",
        color=color
    )

    # Strikes
    if recommendation.get("long_strike"):
        long_strike = float(recommendation["long_strike"])
        short_strike = float(recommendation["short_strike"])
        embed.add_field(
            name="📊 Strikes",
            value=f"Long: **${long_strike:.2f}**\nShort: **${short_strike:.2f}**",
            inline=True
        )
    elif recommendation.get("strike"):
        strike = float(recommendation["strike"])
        embed.add_field(
            name="📊 Strike",
            value=f"**${strike:.2f}** {position}",
            inline=True
        )

    # Width (for spreads)
    if recommendation.get("width_points"):
        width_pts = float(recommendation["width_points"])
        width_dollars = float(recommendation["width_dollars"])
        embed.add_field(
            name="📏 Width",
            value=f"**${width_pts:.0f}** pts (${width_dollars:.0f})",
            inline=True
        )

    # Net Cost
    net_premium = float(recommendation.get("net_premium", 0))
    is_credit = recommendation.get("is_credit", False)

    if is_credit:
        net_credit = abs(net_premium)
        embed.add_field(
            name="💰 Credit",
            value=f"**${net_credit:.2f}**",
            inline=True
        )
    else:
        net_debit = net_premium
        embed.add_field(
            name="💸 Debit",
            value=f"**${net_debit:.2f}**",
            inline=True
        )

    # P/L
    max_profit = recommendation.get("max_profit")
    max_loss = float(recommendation.get("max_loss", 0))

    profit_str = f"${max_profit:.2f}" if max_profit else "Unlimited ♾️"
    embed.add_field(
        name="📈 Max Profit",
        value=f"**{profit_str}**",
        inline=True
    )
    embed.add_field(
        name="📉 Max Loss",
        value=f"**${max_loss:.2f}**",
        inline=True
    )

    # R:R and POP
    rr = recommendation.get("risk_reward_ratio")
    pop = recommendation.get("pop_proxy")

    if rr:
        embed.add_field(
            name="⚖️ R:R",
            value=f"**{float(rr):.2f}:1**",
            inline=True
        )

    if pop:
        embed.add_field(
            name="🎯 POP",
            value=f"**{float(pop):.0f}%**",
            inline=True
        )

    # Position sizing
    rec_contracts = recommendation.get("recommended_contracts")
    pos_size = recommendation.get("position_size_dollars")

    if rec_contracts:
        embed.add_field(
            name="📦 Size",
            value=f"**{rec_contracts}** contracts\n(${float(pos_size):.2f} risk)" if pos_size else f"**{rec_contracts}** contracts",
            inline=True
        )

    # Breakeven
    breakeven = float(recommendation.get("breakeven", 0))
    if breakeven > 0:
        embed.add_field(
            name="🎲 Breakeven",
            value=f"**${breakeven:.2f}**",
            inline=True
        )

    # Score
    score = recommendation.get("composite_score")
    if score:
        embed.add_field(
            name="⭐ Score",
            value=f"**{float(score):.1f}/100**",
            inline=True
        )

    # Reasoning
    reasons = recommendation.get("reasons", [])
    if reasons:
        # Take first 4 reasons to fit in embed
        reason_text = "\n".join(f"• {r}" for r in reasons[:4])
        embed.add_field(
            name="💡 Why This Trade",
            value=reason_text,
            inline=False
        )

    # Warnings
    warnings = recommendation.get("warnings", [])
    if warnings:
        warning_text = "\n".join(f"⚠️ {w}" for w in warnings[:2])
        embed.add_field(
            name="⚠️ Warnings",
            value=warning_text,
            inline=False
        )

    embed.set_footer(text=f"Volaris Strategy Planner • Rank #{rank}")

    return embed


class MoreCandidatesView(discord.ui.View):
    """View with button to show more candidates."""

    def __init__(self, all_recommendations: list, symbol: str, underlying_price: float, iv_regime: str, strategy: str):
        super().__init__(timeout=300)  # 5 minute timeout
        self.all_recommendations = all_recommendations
        self.symbol = symbol
        self.underlying_price = underlying_price
        self.iv_regime = iv_regime
        self.strategy = strategy
        self.current_page = 0

    @discord.ui.button(label="Show More Candidates", style=discord.ButtonStyle.primary, emoji="📋")
    async def show_more(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show additional candidates."""
        # Show recommendations 2 and 3
        if len(self.all_recommendations) > 1:
            embeds = []
            for rec in self.all_recommendations[1:3]:  # Show #2 and #3
                embed = create_embed_for_recommendation(
                    rec,
                    self.symbol,
                    self.underlying_price,
                    self.iv_regime,
                    self.strategy
                )
                embeds.append(embed)

            await interaction.response.send_message(embeds=embeds, ephemeral=True)
        else:
            await interaction.response.send_message("No additional candidates available.", ephemeral=True)


async def run_bot():
    """Run the Discord bot."""
    global bot

    if not settings.DISCORD_BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN not configured")
        return

    if not settings.DISCORD_BOT_ENABLED:
        logger.info("Discord bot disabled (DISCORD_BOT_ENABLED=false)")
        return

    # Create bot instance
    # Use DISCORD_GUILD_ID if set, otherwise fall back to DISCORD_SERVER_ID
    guild_id_str = settings.discord_guild_id_resolved
    guild_id = int(guild_id_str) if guild_id_str else None
    bot = VolarisBot(api_base_url=settings.API_BASE_URL, guild_id=guild_id)

    # Autocomplete for symbol parameter
    async def symbol_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete S&P 500 symbols."""
        current_upper = current.upper()
        matches = [s for s in AVAILABLE_SYMBOLS if s.startswith(current_upper)]
        # Discord limits to 25 choices
        return [app_commands.Choice(name=symbol, value=symbol) for symbol in matches[:25]]

    # Define /plan command
    @bot.tree.command(name="plan", description="Get options strategy recommendations")
    @app_commands.describe(
        symbol="Ticker symbol (e.g., SPY, AAPL)",
        bias="Market bias",
        dte="Days to expiration",
        mode="Strategy preference (auto selects based on IV)",
        max_risk="Maximum risk per trade in dollars (optional)",
        account_size="Account size for position sizing (optional)"
    )
    @app_commands.choices(
        bias=[
            app_commands.Choice(name="Bullish", value="bullish"),
            app_commands.Choice(name="Bearish", value="bearish"),
            app_commands.Choice(name="Neutral", value="neutral"),
        ],
        mode=[
            app_commands.Choice(name="Auto (IV-based)", value="auto"),
            app_commands.Choice(name="Force Credit", value="credit"),
            app_commands.Choice(name="Force Debit", value="debit"),
        ]
    )
    @app_commands.autocomplete(symbol=symbol_autocomplete)
    async def plan(
        interaction: discord.Interaction,
        symbol: str,
        bias: str,
        dte: int,
        mode: str = "auto",
        max_risk: Optional[float] = None,
        account_size: Optional[float] = None
    ):
        """Get strategy recommendations."""
        # Rate limit check
        if not bot.check_rate_limit(interaction.user.id):
            await interaction.response.send_message(
                "⚠️ Rate limit: Please wait before requesting another recommendation.",
                ephemeral=True
            )
            return

        # Defer response (API call might take a moment)
        await interaction.response.defer()

        try:
            # Call API
            result = await bot.api_client.recommend_strategy(
                symbol=symbol,
                bias=bias,
                dte=dte,
                mode=mode,
                max_risk=max_risk,
                account_size=account_size
            )

            # Extract data
            recommendations = result.get("recommendations", [])
            if not recommendations:
                await interaction.followup.send(
                    f"❌ No recommendations found for {symbol.upper()}.\n"
                    f"Warnings: {', '.join(result.get('warnings', ['No data available']))}"
                )
                return

            # Create embed for top recommendation
            top_rec = recommendations[0]
            embed = create_embed_for_recommendation(
                top_rec,
                result["underlying_symbol"],
                float(result["underlying_price"]),
                result.get("iv_regime"),
                result["chosen_strategy_family"]
            )

            # Add system warnings if any
            system_warnings = result.get("warnings", [])
            if system_warnings:
                warning_text = "\n".join(f"• {w}" for w in system_warnings[:2])
                embed.add_field(
                    name="ℹ️ System Info",
                    value=warning_text,
                    inline=False
                )

            # Create view with "More" button if multiple candidates
            view = None
            if len(recommendations) > 1:
                view = MoreCandidatesView(
                    recommendations,
                    result["underlying_symbol"],
                    float(result["underlying_price"]),
                    result.get("iv_regime"),
                    result["chosen_strategy_family"]
                )

            await interaction.followup.send(embed=embed, view=view)

        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except aiohttp.ClientError as e:
            logger.error(f"API error in /plan: {e}")
            await interaction.followup.send(f"❌ API error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in /plan: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Unexpected error: {str(e)}")

    # Run bot
    try:
        logger.info("Starting Discord bot...")
        await bot.start(settings.DISCORD_BOT_TOKEN)
    except Exception as e:
        logger.error(f"Bot error: {e}", exc_info=True)


if __name__ == "__main__":
    # Standalone mode
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(run_bot())
