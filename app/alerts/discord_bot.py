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
        bias_reason: Optional[str] = None,
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
            bias_reason: ICT setup context (ssl_sweep, bsl_sweep, fvg_retest, structure_shift, user_manual)

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

        if bias_reason:
            objectives["bias_reason"] = bias_reason

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
    """Run the Discord bot with optional scheduler."""
    global bot

    if not settings.DISCORD_BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN not configured")
        return

    if not settings.DISCORD_BOT_ENABLED:
        logger.info("Discord bot disabled (DISCORD_BOT_ENABLED=false)")
        return

    # Start scheduler if enabled (allows single worker to run both bot + data fetching)
    scheduler = None
    if settings.SCHEDULER_ENABLED:
        try:
            from app.workers import create_scheduler
            from app.db.database import init_db

            logger.info("Initializing database for scheduler...")
            await init_db()

            scheduler = create_scheduler()
            scheduler.start()
            logger.info("✅ Background scheduler started alongside Discord bot")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}", exc_info=True)
            logger.warning("Discord bot will continue without scheduler")

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
        account_size="Account size for position sizing (optional)",
        bias_reason="ICT setup context (optional, advanced)"
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
        ],
        bias_reason=[
            app_commands.Choice(name="Manual (default)", value="user_manual"),
            app_commands.Choice(name="SSL Sweep", value="ssl_sweep"),
            app_commands.Choice(name="BSL Sweep", value="bsl_sweep"),
            app_commands.Choice(name="FVG Retest", value="fvg_retest"),
            app_commands.Choice(name="Structure Shift", value="structure_shift"),
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
        account_size: Optional[float] = None,
        bias_reason: Optional[str] = None
    ):
        """Get strategy recommendations."""
        # Validate DTE range
        if dte < 1 or dte > 365:
            await interaction.response.send_message(
                f"❌ Invalid DTE: {dte}. Must be between 1 and 365 days.",
                ephemeral=True
            )
            return

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
                account_size=account_size,
                bias_reason=bias_reason
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

    # Phase 3.6: Additional Discord Commands

    # /calc command - Quick strategy calculator
    @bot.tree.command(name="calc", description="Calculate P/L for a specific strategy")
    @app_commands.describe(
        strategy="Strategy type",
        symbol="Ticker symbol",
        strikes="Strike price(s): '540' for long, 'long/short' for spreads (e.g., '445/450')",
        dte="Days to expiration",
        premium="Net premium (optional - auto-fetches from Schwab API if omitted)",
        underlying_price="Current stock price (optional - auto-fetches if omitted)"
    )
    @app_commands.choices(
        strategy=[
            app_commands.Choice(name="Bull Call Spread (Debit)", value="bull_call_spread"),
            app_commands.Choice(name="Bear Put Spread (Debit)", value="bear_put_spread"),
            app_commands.Choice(name="Bull Put Spread (Credit)", value="bull_put_spread"),
            app_commands.Choice(name="Bear Call Spread (Credit)", value="bear_call_spread"),
            app_commands.Choice(name="Long Call", value="long_call"),
            app_commands.Choice(name="Long Put", value="long_put"),
        ]
    )
    @app_commands.autocomplete(symbol=symbol_autocomplete)
    async def calc(
        interaction: discord.Interaction,
        strategy: str,
        symbol: str,
        strikes: str,
        dte: int,
        premium: Optional[float] = None,
        underlying_price: Optional[float] = None
    ):
        """Calculate P/L for a specific strategy."""
        # Validate DTE range
        if dte < 1 or dte > 365:
            await interaction.response.send_message(
                f"❌ Invalid DTE: {dte}. Must be between 1 and 365 days.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            # Determine if spread or single option
            is_spread = strategy in ("bull_call_spread", "bear_put_spread", "bull_put_spread", "bear_call_spread")

            if is_spread:
                # Parse spread strikes (format: "long/short")
                if "/" not in strikes:
                    await interaction.followup.send(
                        f"❌ Spread requires two strikes in format 'long/short' (e.g., '445/450')"
                    )
                    return

                strike_parts = strikes.split("/")
                if len(strike_parts) != 2:
                    await interaction.followup.send("❌ Invalid format. Use 'long/short' (e.g., '445/450')")
                    return

                # Parse strikes - format is consistent across all spreads
                first_strike = float(strike_parts[0])
                second_strike = float(strike_parts[1])

                # Validate and assign based on strategy
                if strategy == "bull_call_spread":
                    # Bull Call Debit: Buy lower call + Sell higher call
                    # Format: lower/higher (e.g., 445/450)
                    # First = Long, Second = Short
                    if first_strike >= second_strike:
                        await interaction.followup.send(
                            f"❌ Bull Call Spread: Format is 'lower/higher' (e.g., '445/450')\n"
                            f"You entered: {first_strike}/{second_strike}"
                        )
                        return
                    long_strike = first_strike   # Buy the lower strike
                    short_strike = second_strike # Sell the higher strike
                    option_type = "call"
                    is_credit = False

                elif strategy == "bear_put_spread":
                    # Bear Put Debit: Buy higher put + Sell lower put
                    # Format: higher/lower (e.g., 450/445)
                    # First = Long, Second = Short
                    if first_strike <= second_strike:
                        await interaction.followup.send(
                            f"❌ Bear Put Spread: Format is 'higher/lower' (e.g., '450/445')\n"
                            f"You entered: {first_strike}/{second_strike}"
                        )
                        return
                    long_strike = first_strike   # Buy the higher strike
                    short_strike = second_strike # Sell the lower strike
                    option_type = "put"
                    is_credit = False

                elif strategy == "bull_put_spread":
                    # Bull Put Credit: Sell higher put + Buy lower put
                    # Format: higher/lower (e.g., 450/445)
                    # First = Short, Second = Long
                    if first_strike <= second_strike:
                        await interaction.followup.send(
                            f"❌ Bull Put Spread: Format is 'higher/lower' (e.g., '450/445')\n"
                            f"You entered: {first_strike}/{second_strike}"
                        )
                        return
                    short_strike = first_strike  # Sell the higher strike
                    long_strike = second_strike  # Buy the lower strike
                    option_type = "put"
                    is_credit = True

                elif strategy == "bear_call_spread":
                    # Bear Call Credit: Sell lower call + Buy higher call
                    # Format: lower/higher (e.g., 445/450)
                    # First = Short, Second = Long
                    if first_strike >= second_strike:
                        await interaction.followup.send(
                            f"❌ Bear Call Spread: Format is 'lower/higher' (e.g., '445/450')\n"
                            f"You entered: {first_strike}/{second_strike}"
                        )
                        return
                    short_strike = first_strike  # Sell the lower strike
                    long_strike = second_strike  # Buy the higher strike
                    option_type = "call"
                    is_credit = True

                # Build spread API request
                url = f"{bot.api_client.base_url}/api/v1/trade-planner/calculate/vertical-spread"

                # For spreads, calculate individual leg premiums from net premium
                # This is a simplified calculation - actual leg premiums would need option chain data
                if is_credit:
                    # Credit spread: we receive premium (short leg is more valuable)
                    short_premium = premium + (abs(long_strike - short_strike) / 2)
                    long_premium = short_premium - premium
                else:
                    # Debit spread: we pay premium (long leg is more valuable)
                    long_premium = premium + (abs(long_strike - short_strike) / 2)
                    short_premium = long_premium - premium

                payload = {
                    "underlying_symbol": symbol.upper(),
                    "underlying_price": underlying_price,
                    "long_strike": long_strike,
                    "short_strike": short_strike,
                    "long_premium": long_premium,
                    "short_premium": short_premium,
                    "option_type": option_type,
                    "is_credit": is_credit
                }

            else:
                # Long option (single strike)
                if "/" in strikes:
                    await interaction.followup.send(
                        f"❌ Long options require single strike only (e.g., '450')"
                    )
                    return

                single_strike = float(strikes)
                option_type = "call" if strategy == "long_call" else "put"

                # Build long option API request
                url = f"{bot.api_client.base_url}/api/v1/trade-planner/calculate/long-option"
                payload = {
                    "underlying_symbol": symbol.upper(),
                    "underlying_price": underlying_price,
                    "strike": single_strike,
                    "option_type": option_type,
                    "premium": premium
                }

            # Call API
            async with aiohttp.ClientSession(timeout=bot.api_client.timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        await interaction.followup.send(f"❌ API error: {error_text}")
                        return
                    result = await response.json()

            # Create embed with results
            strategy_name = {
                "bull_call_spread": "Bull Call Spread (Debit)",
                "bear_put_spread": "Bear Put Spread (Debit)",
                "bull_put_spread": "Bull Put Spread (Credit)",
                "bear_call_spread": "Bear Call Spread (Credit)",
                "long_call": "Long Call",
                "long_put": "Long Put"
            }

            embed = discord.Embed(
                title=f"📊 {strategy_name[strategy]} - {symbol.upper()}",
                color=discord.Color.green() if is_spread and is_credit else discord.Color.blue()
            )

            if is_spread:
                embed.add_field(
                    name="Strikes",
                    value=f"Long: ${long_strike:.2f}\nShort: ${short_strike:.2f}",
                    inline=True
                )
                if is_credit:
                    embed.add_field(name="💰 Credit", value=f"**${abs(float(result['net_premium'])):.2f}**", inline=True)
                else:
                    embed.add_field(name="💸 Debit", value=f"**${float(result['net_premium']):.2f}**", inline=True)
            else:
                embed.add_field(name="Strike", value=f"${single_strike:.2f}", inline=True)
                embed.add_field(name="💸 Premium", value=f"**${float(result['premium']):.2f}**", inline=True)

            embed.add_field(name="📈 Max Profit", value=f"${float(result.get('max_profit', 0)):.2f}", inline=True)
            embed.add_field(name="📉 Max Loss", value=f"${float(result['max_loss']):.2f}", inline=True)
            embed.add_field(name="⚖️ R:R", value=f"{float(result.get('risk_reward_ratio', 0)):.2f}:1", inline=True)
            embed.add_field(name="🎯 Breakeven", value=f"${float(result['breakeven']):.2f}", inline=True)

            if result.get("pop_proxy"):
                embed.add_field(name="📊 POP", value=f"{float(result['pop_proxy']):.0f}%", inline=True)

            # Add ICT context for spreads
            if is_spread:
                ict_context = {
                    "bull_call_spread": "Best after SSL sweep + bullish displacement",
                    "bear_put_spread": "Best after BSL sweep + bearish displacement",
                    "bull_put_spread": "Profit if price stays above short strike (bullish/neutral)",
                    "bear_call_spread": "Profit if price stays below short strike (bearish/neutral)"
                }
                embed.add_field(name="💡 ICT Context", value=ict_context[strategy], inline=False)

            await interaction.followup.send(embed=embed)

        except ValueError as e:
            await interaction.followup.send(f"❌ Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Error in /calc: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error: {str(e)}")

    # /size command - Position sizing helper
    @bot.tree.command(name="size", description="Calculate position sizing")
    @app_commands.describe(
        account_size="Your account value",
        max_risk_pct="Max risk as % of account (e.g., 2 for 2%)",
        strategy_cost="Cost per contract (premium or max loss)"
    )
    async def size(
        interaction: discord.Interaction,
        account_size: float,
        max_risk_pct: float,
        strategy_cost: float
    ):
        """Calculate recommended position size."""
        await interaction.response.defer()

        try:
            # Calculate position sizing
            max_risk_dollars = account_size * (max_risk_pct / 100)
            recommended_contracts = int(max_risk_dollars / strategy_cost)
            total_position_size = recommended_contracts * strategy_cost
            actual_risk_pct = (total_position_size / account_size) * 100

            # Create embed
            embed = discord.Embed(
                title="📐 Position Sizing Recommendation",
                color=discord.Color.green()
            )

            embed.add_field(name="Account Size", value=f"${account_size:,.2f}", inline=True)
            embed.add_field(name="Max Risk %", value=f"{max_risk_pct:.1f}%", inline=True)
            embed.add_field(name="Max Risk $", value=f"${max_risk_dollars:,.2f}", inline=True)
            embed.add_field(name="Cost/Contract", value=f"${strategy_cost:.2f}", inline=True)
            embed.add_field(name="✅ Contracts", value=f"**{recommended_contracts}**", inline=True)
            embed.add_field(name="Total Position", value=f"${total_position_size:,.2f}", inline=True)
            embed.add_field(name="Actual Risk %", value=f"{actual_risk_pct:.2f}%", inline=True)
            embed.add_field(name="Max Loss", value=f"${total_position_size:,.2f}", inline=True)

            if recommended_contracts == 0:
                embed.add_field(
                    name="⚠️ Warning",
                    value="Strategy cost exceeds risk limit. Consider reducing position size or using spreads.",
                    inline=False
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in /size: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error: {str(e)}")

    # /breakeven command - Quick breakeven calculator
    @bot.tree.command(name="breakeven", description="Calculate breakeven price")
    @app_commands.describe(
        strategy="Strategy type",
        strikes="Strike price(s): '540' for long options, '540/545' for spreads",
        cost="Premium paid or received (positive for debit, negative for credit)"
    )
    @app_commands.choices(
        strategy=[
            app_commands.Choice(name="Bull Call Spread", value="bull_call"),
            app_commands.Choice(name="Bear Put Spread", value="bear_put"),
            app_commands.Choice(name="Bull Put Spread (Credit)", value="bull_put"),
            app_commands.Choice(name="Bear Call Spread (Credit)", value="bear_call"),
            app_commands.Choice(name="Long Call", value="long_call"),
            app_commands.Choice(name="Long Put", value="long_put"),
        ]
    )
    async def breakeven(
        interaction: discord.Interaction,
        strategy: str,
        strikes: str,
        cost: float
    ):
        """Calculate breakeven price."""
        await interaction.response.defer()

        try:
            # Parse strikes
            if "/" in strikes:
                strike_parts = strikes.split("/")
                if len(strike_parts) != 2:
                    await interaction.followup.send("❌ Invalid strikes format. Use '540/545' for spreads.")
                    return
                long_strike = float(strike_parts[0])
                short_strike = float(strike_parts[1])

                # Calculate breakeven for spreads
                if strategy in ("bull_call", "bear_put"):
                    # Debit spreads
                    if strategy == "bull_call":
                        breakeven = long_strike + abs(cost)
                    else:  # bear_put
                        breakeven = long_strike - abs(cost)
                else:
                    # Credit spreads
                    if strategy == "bull_put":
                        breakeven = short_strike - abs(cost)
                    else:  # bear_call
                        breakeven = short_strike + abs(cost)
            else:
                # Long options
                strike = float(strikes)
                if strategy == "long_call":
                    breakeven = strike + abs(cost)
                else:  # long_put
                    breakeven = strike - abs(cost)

            # Assume current price for distance calculation (would need API call for real price)
            embed = discord.Embed(
                title=f"⚖️ Breakeven Calculator - {strategy.replace('_', ' ').title()}",
                color=discord.Color.gold()
            )

            if "/" in strikes:
                embed.add_field(name="Strikes", value=f"{long_strike:.2f}/{short_strike:.2f}", inline=True)
            else:
                embed.add_field(name="Strike", value=f"${strike:.2f}", inline=True)

            embed.add_field(name="Cost", value=f"${abs(cost):.2f}", inline=True)
            embed.add_field(name="✅ Breakeven", value=f"**${breakeven:.2f}**", inline=True)

            # Add explanation
            if "/" in strikes:
                if strategy in ("bull_call", "bear_put"):
                    embed.add_field(
                        name="Explanation",
                        value=f"Debit spread: Needs ${abs(cost):.2f} move beyond long strike to breakeven",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="Explanation",
                        value=f"Credit spread: Profit if price stays beyond ${breakeven:.2f}",
                        inline=False
                    )

            await interaction.followup.send(embed=embed)

        except ValueError as e:
            await interaction.followup.send(f"❌ Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Error in /breakeven: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error: {str(e)}")

    # /check command - Health check
    @bot.tree.command(name="check", description="Check bot and API health")
    async def check(interaction: discord.Interaction):
        """Check bot and API health."""
        await interaction.response.defer()

        try:
            import time
            start_time = time.time()

            # Call health endpoint
            url = f"{bot.api_client.base_url}/health"
            async with aiohttp.ClientSession(timeout=bot.api_client.timeout) as session:
                async with session.get(url) as response:
                    health_data = await response.json() if response.status == 200 else {}
                    api_status = "✅ Healthy" if response.status == 200 else f"❌ Error ({response.status})"

            response_time = (time.time() - start_time) * 1000  # Convert to ms

            # Create embed
            embed = discord.Embed(
                title="🏥 System Health Check",
                color=discord.Color.green() if response_time < 500 else discord.Color.orange()
            )

            embed.add_field(name="Bot Status", value="✅ Online", inline=True)
            embed.add_field(name="API Status", value=api_status, inline=True)
            embed.add_field(name="Response Time", value=f"{response_time:.0f}ms", inline=True)

            if health_data:
                embed.add_field(name="Database", value=health_data.get("database", "Unknown"), inline=True)
                embed.add_field(name="Redis", value=health_data.get("redis", "Unknown"), inline=True)
                if health_data.get("version"):
                    embed.add_field(name="Version", value=health_data["version"], inline=True)

            embed.set_footer(text=f"API: {bot.api_client.base_url}")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in /check: {e}", exc_info=True)
            embed = discord.Embed(
                title="🏥 System Health Check",
                color=discord.Color.red()
            )
            embed.add_field(name="Bot Status", value="✅ Online", inline=True)
            embed.add_field(name="API Status", value=f"❌ Error: {str(e)}", inline=False)
            await interaction.followup.send(embed=embed)

    # /help command - Command reference
    @bot.tree.command(name="help", description="Show all available commands and usage")
    async def help_command(interaction: discord.Interaction):
        """Display comprehensive command reference."""
        embed = discord.Embed(
            title="📚 Volaris Bot Commands",
            description="Options trading strategy recommendations powered by ICT methodology",
            color=discord.Color.blue()
        )

        # /plan command
        embed.add_field(
            name="📊 /plan",
            value=(
                "**Full strategy recommendations with ICT context**\n"
                "• Parameters: symbol, bias, dte, mode (optional), max_risk (optional), account_size (optional), bias_reason (optional)\n"
                "• Returns: Top 3 ranked strategies with detailed metrics\n"
                "• Features: 515 symbol autocomplete, DTE preferences, account sizing\n"
                "• Example: `/plan SPY bullish 7 auto 500 25000`"
            ),
            inline=False
        )

        # /calc command
        embed.add_field(
            name="🧮 /calc",
            value=(
                "**Quick P/L calculator for specific strategies**\n"
                "• Parameters: strategy, symbol, strikes, dte, premium (optional)\n\n"
                "**Strike Formats:**\n"
                "• Bull Call Spread (Debit): `lower/higher` → 1st=long, 2nd=short\n"
                "• Bear Put Spread (Debit): `higher/lower` → 1st=long, 2nd=short\n"
                "• Bull Put Spread (Credit): `higher/lower` → 1st=short, 2nd=long\n"
                "• Bear Call Spread (Credit): `lower/higher` → 1st=short, 2nd=long\n"
                "• Long Call/Put: single strike (e.g., `450`)\n\n"
                "**Examples:**\n"
                "• `/calc bull_call_spread SPY 540/545 7` (buy 540, sell 545)\n"
                "• `/calc bull_put_spread SPY 450/445 7` (sell 450, buy 445)\n"
                "• `/calc long_call SPY 540 7`"
            ),
            inline=False
        )

        # /size command
        embed.add_field(
            name="📐 /size",
            value=(
                "**Position sizing calculator**\n"
                "• Parameters: account_size, max_risk_pct, strategy_cost\n"
                "• Returns: Recommended contracts, total position size, risk %\n"
                "• Example: `/size 25000 2 350` (2% risk on $350 strategy)"
            ),
            inline=False
        )

        # /breakeven command
        embed.add_field(
            name="🎯 /breakeven",
            value=(
                "**Quick breakeven calculator**\n"
                "• Parameters: strategy, strikes, cost\n"
                "• Strategies: bull_call, bear_put, bull_put_credit, bear_call_credit, long_call, long_put\n"
                "• Example: `/breakeven bull_put_credit 540/545 125`"
            ),
            inline=False
        )

        # /check command
        embed.add_field(
            name="🏥 /check",
            value=(
                "**System health check**\n"
                "• Shows: Bot status, API status, database, Redis, response time\n"
                "• No parameters required"
            ),
            inline=False
        )

        # Additional info
        embed.add_field(
            name="ℹ️ Additional Info",
            value=(
                "**ICT Bias Reasons** (advanced /plan parameter):\n"
                "• `ssl_sweep` - Sell-side liquidity swept, bullish reversal\n"
                "• `bsl_sweep` - Buy-side liquidity swept, bearish reversal\n"
                "• `fvg_retest` - Fair Value Gap retest continuation\n"
                "• `structure_shift` - Market Structure Shift (MSS)\n"
                "• `user_manual` - Manual bias selection (default)\n\n"
                "**Rate Limits:** 3 commands per minute per user\n"
                "**DTE Range:** 1-365 days"
            ),
            inline=False
        )

        embed.set_footer(text="Volaris Trading Intelligence Platform | Phase 3 Complete")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Run bot
    try:
        logger.info("Starting Discord bot...")
        await bot.start(settings.DISCORD_BOT_TOKEN)
    except Exception as e:
        logger.error(f"Bot error: {e}", exc_info=True)
    finally:
        # Gracefully shutdown scheduler if it was started
        if scheduler:
            logger.info("Shutting down scheduler...")
            scheduler.shutdown(wait=True)
            logger.info("Scheduler stopped")


if __name__ == "__main__":
    # Standalone mode
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(run_bot())
