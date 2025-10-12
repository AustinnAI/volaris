# Local Discord Bot Testing Guide

## Prerequisites

1. **Discord Bot Setup:**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application (or use existing)
   - Go to "Bot" section → Reset/Copy bot token
   - Enable "MESSAGE CONTENT INTENT" under Privileged Gateway Intents
   - Go to "OAuth2" → "URL Generator":
     - Scopes: `bot`, `applications.commands`
     - Bot Permissions: `Send Messages`, `Use Slash Commands`, `Embed Links`
   - Copy generated URL and invite bot to your test server

2. **Environment Setup:**
   - Copy `.env.example` to `.env`
   - Set these required variables:
     ```bash
     DISCORD_BOT_TOKEN=your_bot_token_here
     DISCORD_SERVER_ID=your_server_id  # Right-click server → Copy ID (enable Developer Mode)
     DISCORD_GUILD_ID=your_server_id   # Same as SERVER_ID
     DISCORD_BOT_ENABLED=true
     API_BASE_URL=http://localhost:8000
     ```

3. **Database Setup:**
   - Make sure PostgreSQL is running
   - Update `DATABASE_URL` in `.env`

## Running Locally

### Terminal 1: Start FastAPI Server
```bash
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Application startup complete.
```

### Terminal 2: Start Discord Bot
```bash
source venv/bin/activate
python -m app.alerts.discord_bot
```

**Expected output:**
```
INFO - volaris.discord_bot - Loaded 515 S&P 500 symbols from CSV
INFO - volaris.discord_bot - Starting Discord bot...
INFO - discord.client - Logging in using static token.
INFO - volaris.discord_bot - Bot ready as Volaris (ID: ...)
INFO - volaris.discord_bot - Successfully synced 6 commands to guild ...
```

## Testing Commands

Once both are running, go to your Discord server and test:

### 1. Test /help (No API dependency)
```
/help
```
Should show ephemeral embed with all commands.

### 2. Test /check (Health check)
```
/check
```
Should show:
- ✅ Bot Status: Online
- ✅ API Status: Healthy
- Database: connected
- Redis: connected (or not_configured)
- Response time

### 3. Test /plan (Full recommendation)
```
/plan SPY bullish 7
```
**What happens:**
1. Bot validates DTE (1-365)
2. Bot checks rate limit (3/min per user)
3. Bot calls `http://localhost:8000/api/v1/strategy/recommend`
4. API fetches option chain data from database
5. Returns top 3 strategy recommendations

**Common errors:**
- ❌ "No option chain data" → Database empty, need to seed data
- ❌ "Ticker SPY not found" → Database missing ticker
- ❌ "API error: 500" → Check FastAPI terminal for errors

### 4. Test /calc (Quick calculator)

**NEW:** `/calc` now requires `premium` and `underlying_price` parameters (no database needed!)

```
/calc
```
Select/Enter:
- **Strategy:** Bull Put Spread (Credit)
- **Symbol:** SPY
- **Strikes:** 545/540
- **DTE:** 7
- **Premium:** 1.50 ← **REQUIRED** (net credit/debit)
- **Underlying Price:** 548.00 ← **REQUIRED** (current stock price)

**What happens:**
1. Bot parses strikes (545/540 → short=545, long=540)
2. Bot determines option type (put) and credit/debit (credit)
3. Bot calculates individual leg premiums from net premium
4. Calls `http://localhost:8000/api/v1/trade-planner/calculate/vertical-spread`
5. Returns P/L embed with max profit/loss, breakeven, R:R

**Strike Formats:**
- Bull Call Spread: `lower/higher` (e.g., `540/545`)
- Bear Put Spread: `higher/lower` (e.g., `550/545`)
- Bull Put Spread: `higher/lower` (e.g., `545/540`)
- Bear Call Spread: `lower/higher` (e.g., `545/550`)

**No database required!** Works immediately for testing.

### 5. Test /size
```
/size 25000 2 350
```
Calculates position sizing for $25k account, 2% risk, $350 strategy cost.

### 6. Test /breakeven
```
/breakeven bull_put_credit 540/545 125
```
Calculates breakeven for bull put credit with $1.25 credit.

## Troubleshooting

### Bot won't start
**Error:** `DISCORD_BOT_TOKEN not configured`
- Check `.env` has `DISCORD_BOT_TOKEN=...`
- Check `DISCORD_BOT_ENABLED=true`
- Restart bot after changing `.env`

### Commands don't appear in Discord
**Issue:** Slash commands not syncing
- Wait 5 minutes (Discord caches commands)
- Check bot logs: "Successfully synced X commands"
- Kick bot and re-invite with correct OAuth URL
- Check `DISCORD_GUILD_ID` matches your server ID

### API errors
**Error:** `Connection refused` or `404`
- Check FastAPI is running on port 8000
- Check `API_BASE_URL=http://localhost:8000` in `.env`
- Check FastAPI logs for errors

### Database errors
**Error:** `No option chain data` or `Ticker not found`
- You need seed data in database
- Phase 2 data fetchers must run first
- Or manually insert test data:
  ```sql
  INSERT INTO tickers (symbol, name, sector) VALUES ('SPY', 'SPDR S&P 500 ETF', 'ETF');
  ```

### Rate limit errors
**Error:** `Rate limit: Please wait...`
- Default: 3 commands per minute per user
- Wait 60 seconds or adjust in code:
  ```python
  # app/alerts/discord_bot.py line ~400
  def check_rate_limit(self, user_id: int) -> bool:
      # Change rate_limit from 3 to higher value
  ```

## Testing Your Error

**Your command:** `/calc Vertical Spread SPY 650/649 put 1`

**Expected behavior:**
- Long strike: 650
- Short strike: 649
- Position: put
- Since short (649) < long (650), this is a **Bear Put Debit** spread
- Should call calculator and return P/L

**If you get "API error":**
1. Check FastAPI terminal for actual error
2. Check database has SPY ticker and option chain data
3. Try simpler command first: `/check` to verify connectivity

## Next Steps

After basic testing works:
1. Deploy bot to Render (already done for you)
2. Update `API_BASE_URL` to production URL
3. Test with production data
4. Monitor logs in Render dashboard

## Quick Reference

| Command | Purpose | Requires DB |
|---------|---------|-------------|
| /help | Show commands | ❌ No |
| /check | Health check | ⚠️ Optional |
| /plan | Strategy recommendations | ✅ Yes |
| /calc | Quick calculator | ⚠️ Optional* |
| /size | Position sizing | ❌ No |
| /breakeven | Breakeven calc | ❌ No |

**/calc with premium parameter** works without DB. Without premium, it needs to fetch from DB.
