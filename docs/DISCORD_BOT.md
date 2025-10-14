# Discord Bot - Setup & Usage Guide

## Current Status

✅ **Your Discord bot is already configured!**

- Bot token: Configured in `.env`
- Server ID: `1413243234569818346`
- Webhook: Configured for alerts
- Render deployment: `https://volaris-yz19.onrender.com`

**What's needed:** Just add `DISCORD_BOT_ENABLED=true` to your `.env` and run the bot!

---

## Quick Start (5 minutes)

### 1. Enable the Bot

Add these two lines to your `.env` file:

```bash
# Add these to your existing .env
DISCORD_BOT_ENABLED=true
API_BASE_URL=http://localhost:8000  # For local testing
# API_BASE_URL=https://volaris-yz19.onrender.com  # For Render deployment (future)
```

**Note:** The bot will use your existing `DISCORD_SERVER_ID` (1413243234569818346) for command registration. No need to set `DISCORD_GUILD_ID` separately.

### 2. Verify Bot Permissions

Your bot needs these permissions in Discord:
- ✅ Send Messages
- ✅ Embed Links
- ✅ Use Slash Commands
- ✅ Server Members Intent (enabled in Developer Portal)

If not already invited, use the OAuth2 URL from [Discord Developer Portal](https://discord.com/developers/applications) with scopes: `bot`, `applications.commands`

### 3. Run the Bot

**Option A: Local Testing (Recommended)**

```bash
# Terminal 1: Start the API
source venv/bin/activate
uvicorn app.main:app --reload

# Terminal 2: Start the bot
source venv/bin/activate
python -m app.alerts.discord_bot
```

You should see:
```
INFO - Bot ready as Volaris (ID: ...)
INFO - Synced commands to guild 1413243234569818346
```

**On-demand refresh:** With `SCHEDULER_ENABLED=false`, the bot now refetches price bars, option chains, and IV metrics for the requested symbol just before responding. This keeps the Render worker light while still delivering fresh data whenever you run a slash command.

**Option B: Render Deployment (Future)**

When your Render deployment is live:
1. Set `API_BASE_URL=https://volaris-yz19.onrender.com` in `.env`
2. Run bot as a separate worker or background process
3. Bot will call your production API

---

## Command Scheduler Dependencies

### Commands that work WITHOUT the scheduler

These commands work with `SCHEDULER_ENABLED=false` and perform on-demand data fetching:

#### Pure Calculators (no external data)
- `/pop` - Probability of profit from delta
- `/contracts` - Calculate contracts from risk/premium
- `/risk` - Calculate total risk from contracts/premium
- `/dte` - Calculate days to expiration
- `/size` - Position sizing calculator
- `/breakeven` - Calculate breakeven price

#### Market Data (on-demand refresh)
- `/price` - Current stock price
- `/quote` - Full quote with bid/ask
- `/range` - 52-week high/low
- `/volume` - Volume analysis
- `/sentiment` - Sentiment metrics (Finnhub)
- `/top` - Top movers (Tiingo/Finnhub)
- `/earnings` - Next earnings date
- `/spread` - Spread width validator

#### Utilities
- `/check` - Health check
- `/help` - Command reference
- `/alerts add/remove/list` - Price alert management
- `/streams add/remove/list` - Price stream management

### Commands that REQUIRE the scheduler (or historical data)

These commands depend on historical IV data for accurate IV rank/percentile calculations:

- **`/plan`** - Strategy recommendations
  - **Can work with on-demand refresh** (calls `/refresh/price`, `/refresh/options`, `/refresh/iv`)
  - **Limitation:** IV rank/percentile requires historical IV data (ideally 252 days)
  - Without historical data: IV regime defaults to "neutral", may provide suboptimal strategy recommendations
  - Error when no data: `"No IV data available for {symbol}. Enable scheduler to populate data."`

- **`/iv`** - IV rank and IV percentile
  - **Can fetch current IV on-demand**, but IV rank/percentile requires historical comparison
  - Computes IV rank as: `(current_iv - min_iv) / (max_iv - min_iv) * 100`
  - Needs multiple historical snapshots to calculate rank accurately
  - Returns 404 error if no IV metrics exist in database

- **`/calc`** - Strategy calculator (with auto-pricing)
  - ✅ Works without scheduler if premium/price provided manually
  - Can auto-fetch option chain pricing on-demand if omitted

- **`/delta`** - Get delta for specific strike
  - Can fetch option chain data on-demand
  - Requires option chain snapshot for the requested DTE (±3 days tolerance)

**Bottom line:** `/plan` and `/iv` will technically work with on-demand refresh, but **IV regime detection** (high/low/neutral) will be inaccurate without historical data. For best results, either:
1. Enable the scheduler to build historical IV data over time
2. Run a one-time backfill of historical option chains and IV metrics
3. Accept "neutral" IV regime for all recommendations (less optimal strategy selection)

---

## Using /plan Command

### Command Structure

```
/plan symbol:<TICKER> bias:<bullish|bearish|neutral> dte:<DAYS> [mode] [max_risk] [account_size]
```

### Parameters

| Parameter | Required | Type | Description | Example |
|-----------|----------|------|-------------|---------|
| `symbol` | ✅ | String | Ticker symbol | `SPY`, `AAPL`, `QQQ` |
| `bias` | ✅ | Choice | Market bias | `bullish`, `bearish`, `neutral` |
| `dte` | ✅ | Integer | Days to expiration | `30`, `45`, `21` |
| `mode` | ❌ | Choice | Strategy preference | `auto` (default), `credit`, `debit` |
| `max_risk` | ❌ | Number | Max $ risk per trade | `500`, `1000` |
| `account_size` | ❌ | Number | Account size for position sizing | `25000`, `50000` |

### Real Examples

**1. Auto Strategy (IV-Based)**
```
/plan symbol:SPY bias:bullish dte:30
```
**→** If IV is high: Bull put credit spread
**→** If IV is low: Long call
**→** If IV is neutral: Bull call debit spread

**2. Force Credit Spread**
```
/plan symbol:AAPL bias:bearish dte:45 mode:credit max_risk:500
```
**→** Bear call credit spread with max $500 risk

**3. With Position Sizing**
```
/plan symbol:QQQ bias:bullish dte:21 account_size:25000
```
**→** Recommended contracts based on 2% account risk

**4. Force Debit Spread**
```
/plan symbol:TSLA bias:bearish dte:30 mode:debit
```
**→** Bear put debit spread regardless of IV

---

## Response Format

The bot returns a **rich embed** with comprehensive trade details:

### Example Response

```
┌─────────────────────────────────────────────────┐
│ #1 Bull Put Credit - SPY @ $450.00             │
│ IV Regime: high | DTE: 30                       │
├─────────────────────────────────────────────────┤
│ 📊 Strikes          📏 Width                    │
│ Long: $440.00       $5 pts ($500)               │
│ Short: $445.00                                   │
│                                                  │
│ 💰 Credit           📈 Max Profit               │
│ $175.00             $175.00                      │
│                                                  │
│ 📉 Max Loss         ⚖️ R:R        🎯 POP       │
│ $325.00             0.54:1         70%           │
│                                                  │
│ 📦 Size             🎲 Breakeven   ⭐ Score    │
│ 2 contracts         $443.25        78.5/100      │
│ ($650 risk)                                      │
│                                                  │
│ 💡 Why This Trade                               │
│ • High IV regime favors selling premium         │
│ • At-the-money put                              │
│ • Attractive R:R of 0.54:1                      │
│ • High probability setup (~70% POP)             │
│ • Strong credit collection (35% of width)       │
│ • $5 spread width for ATM                       │
│ • Good liquidity (OI: 500)                      │
└─────────────────────────────────────────────────┘
[Show More Candidates] button
```

### Field Descriptions

| Icon | Field | Description |
|------|-------|-------------|
| 📊 | **Strikes** | Long and short strike prices |
| 📏 | **Width** | Spread width in points and dollars |
| 💰 | **Credit/Debit** | Net cost (credit is negative) |
| 📈 | **Max Profit** | Maximum profit (unlimited for long calls ♾️) |
| 📉 | **Max Loss** | Maximum loss (your risk) |
| ⚖️ | **R:R** | Risk/reward ratio |
| 🎯 | **POP** | Probability of profit proxy (delta-based) |
| 📦 | **Size** | Recommended contracts + total risk |
| 🎲 | **Breakeven** | Price needed to break even |
| ⭐ | **Score** | Composite quality score (0-100) |
| 💡 | **Why This Trade** | AI-generated reasoning bullets |

### Interactive Buttons

**"Show More Candidates"** → View recommendations #2 and #3
(Click for additional ITM/OTM options)

---

## Using /calc Command

### Command Structure

```
/calc strategy:<STRATEGY> symbol:<TICKER> strikes:<STRIKES> dte:<DAYS> [premium] [underlying_price]
```

### Parameters

| Parameter | Required | Type | Description | Example |
|-----------|----------|------|-------------|---------|
| `strategy` | ✅ | Choice | Strategy type | `bull_put_spread`, `long_call` |
| `symbol` | ✅ | String | Ticker symbol | `SPY`, `AAPL` |
| `strikes` | ✅ | String | Strike price(s) | `667/665` (spread), `450` (single) |
| `dte` | ✅ | Integer | Days to expiration | `6`, `30`, `45` |
| `premium` | ❌ | Number | Net premium (credit/debit) | `0.83`, `2.50` |
| `underlying_price` | ❌ | Number | Current stock price | `665.00` |

### Strike Format Convention

**"Interact First" - Enter the strike you trade first:**

| Strategy | Format | Example | Explanation |
|----------|--------|---------|-------------|
| **Bull Call Spread** (Debit) | `lower/higher` | `445/450` | BUY 445 call first, SELL 450 call |
| **Bear Put Spread** (Debit) | `higher/lower` | `450/445` | BUY 450 put first, SELL 445 put |
| **Bull Put Spread** (Credit) | `higher/lower` | `667/665` | SELL 667 put first, BUY 665 put |
| **Bear Call Spread** (Credit) | `lower/higher` | `445/450` | SELL 445 call first, BUY 450 call |
| **Long Call/Put** | `single` | `450` | Single strike |

### Real Examples

**1. Bull Put Spread with Net Premium**
```
/calc strategy:Bull Put Spread (Credit) symbol:SPY strikes:667/665 dte:6 premium:0.83 underlying_price:665
```
**→** Calculates P/L for 667/665 bull put with $0.83 credit

**2. Long Call (Auto-Fetch Price)**
```
/calc strategy:Long Call symbol:AAPL strikes:180 dte:30
```
**→** Fetches current AAPL price and estimates P/L

**3. Bear Call Spread with Manual Inputs**
```
/calc strategy:Bear Call Spread (Credit) symbol:QQQ strikes:490/495 dte:21 premium:1.25 underlying_price:487.50
```
**→** Manual override for custom scenarios

---

### Current Limitations ⚠️

**For Spread Strategies:**

When providing a single `premium` value for spreads, the bot **estimates individual leg premiums** using spread width:
- Credit spread: `short_premium = net_credit + (spread_width × 0.4)`
- Debit spread: `long_premium = net_debit + (spread_width × 0.4)`

#### What's Accurate ✅
- **Max profit** - Based on net premium
- **Max loss** - Based on spread width and net premium
- **Breakeven** - Calculated from strikes and net premium
- **Risk/reward ratio** - Derived from max profit/loss
- **All P/L calculations** - Dollar amounts are correct

#### What's Inaccurate ❌
- **Win probability (POP)** - Needs real deltas from individual legs
- **Greeks** (delta, theta, gamma) - Not currently calculated, would need real premiums
- **Position sizing based on POP** - Currently uses simplified delta proxy

#### Example of Estimation Inaccuracy

**Real trade:** Bull Put Spread 667/665
- Actual: Sell 667 put @ $5.00, Buy 665 put @ $4.20 → Net: $0.80
- Estimated: Sell 667 put @ $1.60, Buy 665 put @ $0.80 → Net: $0.80

Both have the **same net premium** ($0.80), so P/L calculations are identical, but probability estimates would differ due to different deltas.

#### Recommendations

For **basic P/L analysis**: Current estimation is sufficient
- Use when you just need max profit, max loss, breakeven, R:R

For **probability-based decisions**: Provide actual leg premiums or use `/plan`
- `/plan` fetches real option chain data and calculates accurate deltas
- Better for trade selection and position sizing

**Future improvement (Phase 5):** Auto-fetch individual leg premiums from option chains when `premium` is omitted.

---

## Deployment Options

### Option 1: Local Development (Current)

**Setup:**
```bash
API_BASE_URL=http://localhost:8000
DISCORD_BOT_ENABLED=true
```

**Run:**
```bash
# Terminal 1
uvicorn app.main:app --reload

# Terminal 2
python -m app.alerts.discord_bot
```

**Pros:**
- Instant testing
- Fast iteration
- Full control

**Cons:**
- Bot offline when laptop sleeps
- Requires two terminals

---

### Option 2: Render Deployment (Future)

**Setup:**
```bash
API_BASE_URL=https://volaris-yz19.onrender.com
DISCORD_BOT_ENABLED=true
```

**Deployment Options:**

#### A. Separate Worker Service

Add a second Render service:
```yaml
# render.yaml
services:
  - type: web
    name: volaris-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT

  - type: worker
    name: volaris-discord-bot
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python -m app.alerts.discord_bot
    envVars:
      - key: DISCORD_BOT_ENABLED
        value: true
      - key: API_BASE_URL
        value: https://volaris-yz19.onrender.com
```

**Pros:**
- Always online
- Separate scaling
- Independent restarts

**Cons:**
- Two services to manage
- Additional cost

#### B. Background Task in FastAPI (Simpler)

Modify `app/main.py` lifespan:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler = None
    bot_task = None

    try:
        if settings.SCHEDULER_ENABLED:
            scheduler = create_scheduler()
            scheduler.start()

        # Start Discord bot in background
        if settings.DISCORD_BOT_ENABLED:
            from app.alerts.discord_bot import run_bot
            bot_task = asyncio.create_task(run_bot())
            logger.info("Discord bot started in background")

        yield
    finally:
        if bot_task:
            bot_task.cancel()
        if scheduler:
            scheduler.shutdown(wait=False)
        await close_db()
```

**Pros:**
- Single service
- Simpler deployment
- No extra cost

**Cons:**
- Bot and API share resources
- API restart = bot restart

---

## Rate Limiting

**Built-in protection:**
- 3 commands per minute per user
- Prevents API abuse
- Automatic cooldown messages

**If rate limited:**
```
⚠️ Rate limit: Please wait before requesting another recommendation.
```

Wait 60 seconds and try again.

---

## Error Messages

### Common Errors & Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `❌ No data available` | No option chain for DTE | Try different DTE (e.g., 30, 45, 60) |
| `❌ API error: HTTP 404` | Ticker not found | Verify ticker symbol (SPY not SP500) |
| `❌ API error: HTTP 500` | Server error | Check API logs, restart if needed |
| `⚠️ Rate limit` | Too many commands | Wait 60 seconds |
| Bot doesn't respond | Bot offline or permissions | Check bot status, verify permissions |
| Command doesn't show | Not synced | Wait 5 min or restart bot |

---

## Troubleshooting

### Bot Won't Start

**Error: `ModuleNotFoundError: No module named 'audioop'`**

```bash
# Python 3.13+ requires audioop-lts
pip install audioop-lts
```

**Error: `DISCORD_BOT_TOKEN not configured`**

```bash
# Verify .env has token
grep DISCORD_BOT_TOKEN .env
```

**Error: `Discord bot disabled`**

```bash
# Add to .env
DISCORD_BOT_ENABLED=true
```

### Command Not Showing

1. **Check bot is online** in Discord (green status)
2. **Wait 5 minutes** for command sync
3. **Restart bot** to force re-sync
4. **Check guild ID** matches your server

### API Connection Fails

```bash
# Test API is running
curl http://localhost:8000/health

# Should return:
{"status":"healthy","database":"connected","cache":"connected"}
```

### Bot Shows as Online but /plan Fails

1. **Check API_BASE_URL** matches running API
2. **Test API endpoint** directly:
   ```bash
   curl -X POST http://localhost:8000/api/v1/strategy/recommend \
     -H "Content-Type: application/json" \
     -d '{"underlying_symbol":"SPY","bias":"bullish","target_dte":30}'
   ```
3. **Check bot logs** for error details

---

## Development Tips

### Enable Debug Logging

```python
# In discord_bot.py, change:
logging.basicConfig(level=logging.DEBUG)
```

### Test API Call Directly

```bash
# Test recommendation API
curl -X POST http://localhost:8000/api/v1/strategy/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "underlying_symbol": "SPY",
    "bias": "bullish",
    "target_dte": 30,
    "objectives": {"account_size": 25000}
  }'
```

### Command Registration

**Guild commands (Current):**
- Updates instantly
- Only visible in your test server
- Set via `DISCORD_SERVER_ID`

**Global commands (Future):**
- Takes up to 1 hour to propagate
- Visible in all servers with bot
- Remove `guild_id` parameter

---

## Security Checklist

- ✅ Never commit `.env` to git
- ✅ Token is in `.gitignore`
- ✅ Rate limiting enabled (3/min)
- ✅ API calls timeout after 30s
- ✅ Bot has minimal permissions

**If token is exposed:**
1. Go to Discord Developer Portal
2. Bot → Reset Token
3. Update `.env` with new token
4. Restart bot

---

## Streaming & Market Snapshots (Phase 3.7)

### Price Streams
- `/streams add <symbol> <interval>` — start a recurring update in the current channel (interval choices: 5, 15, 30, 60 min).
- `/streams list` — view all active streams, including stream IDs and channels.
- `/streams remove <stream_id>` — stop a stream by ID.
- Updates are powered by `/api/v1/streams/price` and post live Schwab quotes with change/percent change.

> **Tip:** Set `PRICE_STREAM_DEFAULT_INTERVAL_SECONDS`, `PRICE_STREAM_MIN_INTERVAL_SECONDS`, and `PRICE_STREAM_MAX_INTERVAL_SECONDS` in `.env` to control allowed cadences.

### Sentiment Snapshot
- `/sentiment <symbol>` (S&P 500 only) — combines Finnhub news sentiment with latest analyst recommendation trends.
- Responses show bullish/bearish percentages, sector averages, and latest recommendation breakdown.

### Top Movers & Daily Digest
- `/top [limit]` — fetches top S&P 500 gainers/losers (default limit from `TOP_MOVERS_LIMIT`).
  - **Free-tier note:** Tiingo's top-movers endpoint requires the paid IEX add-on. With a free key, the command will respond with guidance instead of data. Configure a paid key or alternative provider before relying on the digest.
- Automated digest posts at **4:00 PM ET** each trading day when `DISCORD_DEFAULT_CHANNEL_ID` is set and premium data is available.
- We're evaluating alternatives (Polygon.io, Alpha Vantage, or in-house computation) to remove the paid dependency in a future phase.

### Dynamic S&P 500 Membership
- Weekly APScheduler job (`sp500_refresh`) updates constituents via Finnhub `/index/constituents`.
- `/api/v1/market/sp500` exposes the live membership list; the bot refreshes its autocomplete cache at startup.

> **Required secrets:** `FINNHUB_API_KEY`, `TIINGO_API_KEY`, and Redis config for caching.

---

## Next Steps

### Phase 8 Enhancements

- [ ] "Tighten credit filter" button (+5% min credit)
- [ ] Export to TastyTrade/ToS order format
- [ ] Save recommendations to `trade_plans` table
- [ ] User watchlist integration
- [x] Price alerts (`/alerts add`, `/alerts list`, `/alerts remove`)
- [x] Price streams (`/streams add|list|remove`)
- [x] Sentiment snapshot (`/sentiment <symbol>`)
- [x] Top movers digest (`/top`, daily 4 PM ET summary)
- [x] Realtime job batch tuning via `REALTIME_SYNC_BATCH_SIZE` (lower if Render worker RAM constrained)
- [ ] Trade journal commands (`/journal add`)
- [ ] Position tracking (`/positions`)
- [ ] P/L reporting (`/pnl weekly`)



### APScheduler Reference

When `SCHEDULER_ENABLED=true`, the bot boots an in-process APScheduler instance with these jobs:

| Job | Default cadence | Purpose |
| --- | --- | --- |
| `realtime_prices_job` | every `REALTIME_JOB_INTERVAL_SECONDS` (60s) | Pull minute bars for every ticker marked `is_active` via Schwab; feeds `/price`, `/quote`, and intraday analytics. |
| `historical_backfill_job` | daily @ `HISTORICAL_BACKFILL_CRON_HOUR` | Refresh multi-day OHLC candles (Databento/Alpaca) for backtesting and analytics. |
| `eod_sync_job` | daily @ `EOD_SYNC_CRON_*` | Update Tiingo end-of-day prices and close data. |
| `option_chain_refresh_job` | every `OPTION_CHAIN_JOB_INTERVAL_MINUTES` (15m) | Snapshot option chains in the database so `/plan` and `/iv` have recent legs. |
| `iv_metric_job` | every `IV_METRICS_JOB_INTERVAL_MINUTES` (30m) | Derive IV/IVR metrics from the latest option chains. |
| `refresh_sp500_job` | weekly (Mon 06:00 UTC) | Refresh S&P 500 constituents for autocomplete and market endpoints. |

**Recommended usage:** keep the scheduler off for lightweight Discord usage and rely on the GitHub Actions watchlist refresher plus on-demand command refresh. Re-enable it later when launching features that rely on continuously updated datasets (e.g., real-time anomaly detection).
### Production Checklist

- [ ] Choose deployment option (worker vs background task)
- [ ] Set `API_BASE_URL` to Render URL
- [ ] Test with production API
- [ ] Monitor bot uptime
- [ ] Set up error alerting (Sentry)
- [ ] Document for team

---

## Support & References

**Resources:**
- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [Discord Developer Portal](https://discord.com/developers/applications)
- [Phase 3.3 API Docs](./PHASE_3.md#phase-33-strategy-recommendation-layer-)
- [Render Deployment Guide](https://render.com/docs)

**Your Setup:**
- Server ID: `1413243234569818346`
- Render URL: `https://volaris-yz19.onrender.com`
- API endpoint: `/api/v1/strategy/recommend`

---

**Ready to test?** Run the Quick Start commands above and use `/plan symbol:SPY bias:bullish dte:30` in your Discord server! 🚀
