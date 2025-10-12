# Scheduler Setup Guide

This guide explains how to enable the background scheduler for automatic option chain and price data fetching.

---

## Overview

The Volaris platform uses **APScheduler** to run background jobs that:
- Fetch real-time price data (1m/5m candles) from **Schwab**
- Refresh option chains every 15 minutes from **Schwab**
- Sync end-of-day data from **Tiingo**
- Calculate IV metrics every 30 minutes
- Perform historical backfills from **Databento**

The scheduler works with **all configured APIs** (Schwab, Tiingo, Alpaca, Databento, Finnhub), but **Schwab** is the primary provider for real-time option chains needed by `/calc` and `/plan` commands.

---

## Local Development Setup

### Step 1: Enable Scheduler in `.env`

Add this to your `.env` file:

```bash
SCHEDULER_ENABLED=true
```

**Full scheduler configuration (already in `.env.example`):**

```bash
# ==========================================
# Scheduler (Phase 2.2)
# ==========================================
SCHEDULER_ENABLED=true                          # Enable background jobs
SCHEDULER_TIMEZONE=UTC                          # Job timezone
REALTIME_JOB_INTERVAL_SECONDS=60                # 1-minute price sync
FIVE_MINUTE_JOB_INTERVAL_SECONDS=300            # 5-minute price sync
OPTION_CHAIN_JOB_INTERVAL_MINUTES=15            # Option chain refresh (MOST IMPORTANT for Discord /calc)
IV_METRICS_JOB_INTERVAL_MINUTES=30              # IV metric calculations
EOD_SYNC_CRON_HOUR=22                           # Tiingo EOD sync (10pm UTC)
EOD_SYNC_CRON_MINUTE=15
HISTORICAL_BACKFILL_CRON_HOUR=3                 # Databento backfill (3am UTC)
HISTORICAL_BACKFILL_LOOKBACK_DAYS=30
```

**Recommendations:**
- **Local dev**: Set `OPTION_CHAIN_JOB_INTERVAL_MINUTES=15` (every 15 minutes)
- **Production**: Keep at 15 minutes to stay within Schwab API rate limits
- **Testing**: You can temporarily set to `1` minute for faster testing, but watch rate limits

---

### Step 2: Run Scheduler Locally

The scheduler is automatically started when you run the FastAPI app **if `SCHEDULER_ENABLED=true`**.

**Option A: Run with FastAPI (integrated)**
```bash
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The scheduler starts automatically via the `lifespan` context manager in [app/main.py:33-49](app/main.py#L33-L49).

**Option B: Run scheduler standalone (for testing)**
```bash
source venv/bin/activate
python -m app.workers.scheduler
```

This runs the scheduler in isolation without the FastAPI server.

---

### Step 3: Verify Scheduler is Running

**Check logs:**
```bash
# Look for these log messages:
2025-10-12 16:15:20 - INFO - APScheduler configured with background jobs
2025-10-12 16:15:21 - INFO - Scheduler started
2025-10-12 16:15:21 - INFO - Next option chain refresh: 2025-10-12 16:30:00 UTC
```

**Check database for option chain data:**
```bash
# After 15 minutes (first run), check if option contracts exist
psql $DATABASE_URL -c "SELECT symbol, COUNT(*) FROM option_contracts GROUP BY symbol;"
```

Expected output after first run:
```
 symbol | count
--------+-------
 SPY    |   450
 QQQ    |   380
 AAPL   |   320
```

---

## Production Setup (Render)

To enable auto-fetch on Render, you need **two services**:

### Service 1: Web Service (FastAPI + Discord Bot)
This is your existing service running the API and Discord bot.

**Configuration:**
- **Name**: `volaris-api`
- **Region**: Oregon (US West)
- **Instance Type**: Starter ($7/month)
- **Start Command**: `cd /opt/render/project/src && python -m app.alerts.discord_bot`
- **Environment Variables**: All your existing `.env` variables

**Important:** Do NOT enable `SCHEDULER_ENABLED=true` on this service. Scheduler should only run on the worker service.

---

### Service 2: Background Worker (NEW)
This service runs the scheduler to populate the database with option chain data.

**Step 1: Create Background Worker on Render**

1. Go to Render dashboard: https://dashboard.render.com
2. Click **"New"** → **"Background Worker"**
3. **Connect Repository**: Same repo as your web service (`volaris`)
4. **Configure Service:**
   - **Name**: `volaris-worker`
   - **Region**: Oregon (US West) — **MUST match web service region for low-latency DB access**
   - **Instance Type**: Starter ($7/month)
   - **Branch**: `main`
   - **Root Directory**: Leave blank (uses repo root)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**:
     ```bash
     cd /opt/render/project/src && python -m app.workers.scheduler
     ```

**Step 2: Add Environment Variables**

Click **"Environment"** tab and add these variables:

**Required (copy from your web service):**
```bash
DATABASE_URL=postgresql://...         # Same as web service
UPSTASH_REDIS_REST_URL=https://...    # Same as web service
UPSTASH_REDIS_REST_TOKEN=...          # Same as web service

# Schwab API (for option chains)
SCHWAB_APP_KEY=...
SCHWAB_SECRET_KEY=...
SCHWAB_REFRESH_TOKEN=...
SCHWAB_API_BASE=https://api.schwabapi.com
SCHWAB_REDIRECT_URI=https://volaris.onrender.com/auth/schwab/callback

# Other providers (optional but recommended)
TIINGO_API_KEY=...
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
DATABENTO_API_KEY=...
FINNHUB_API_KEY=...
```

**Scheduler configuration:**
```bash
SCHEDULER_ENABLED=true                          # ← REQUIRED
SCHEDULER_TIMEZONE=UTC
OPTION_CHAIN_JOB_INTERVAL_MINUTES=15            # Refresh every 15 minutes
IV_METRICS_JOB_INTERVAL_MINUTES=30
REALTIME_JOB_INTERVAL_SECONDS=60
FIVE_MINUTE_JOB_INTERVAL_SECONDS=300
EOD_SYNC_CRON_HOUR=22
EOD_SYNC_CRON_MINUTE=15
HISTORICAL_BACKFILL_CRON_HOUR=3
HISTORICAL_BACKFILL_LOOKBACK_DAYS=30
```

**Application settings:**
```bash
ENVIRONMENT=production
LOG_LEVEL=INFO
DEBUG=false
```

**Step 3: Deploy Worker**

Click **"Create Background Worker"**. Render will:
1. Clone your repo
2. Run `pip install -r requirements.txt`
3. Execute `python -m app.workers.scheduler`
4. Keep the worker running 24/7

**Step 4: Verify Worker is Running**

**Check Render logs:**
```
==> Your service is live 🎉
2025-10-12 16:20:30 - INFO - APScheduler configured with background jobs
2025-10-12 16:20:30 - INFO - Scheduler started
2025-10-12 16:20:30 - INFO - Added job "prices_1m" to job store "default"
2025-10-12 16:20:30 - INFO - Added job "options_refresh" to job store "default"
```

**Test /calc on Discord (after 15 minutes):**
```
/calc
Strategy: Long Call
Symbol: SPY
Strikes: 580
DTE: 7
Premium: [leave blank]
Underlying Price: [leave blank]
```

If auto-fetch works, you'll get option metrics. If database is empty, you'll get an error asking for manual premium.

---

## Scheduler Jobs Explained

### 1. Option Chain Refresh (`options_refresh`)
**Frequency:** Every 15 minutes
**Provider:** Schwab API
**Purpose:** Fetch all option contracts for active tickers (SPY, QQQ, AAPL, etc.)
**Critical For:** `/calc` and `/plan` commands

**Job details:**
- Fetches call/put chains for all tickers in `tickers` table where `is_active=true`
- Stores contracts in `option_contracts` table
- Updates `last_updated` timestamp
- Skips stale contracts with `mark_price < 0.01`

**File:** [app/workers/jobs.py](app/workers/jobs.py)

---

### 2. Real-Time Price Sync (`prices_1m`, `prices_5m`)
**Frequency:** 1 minute, 5 minutes
**Provider:** Schwab API
**Purpose:** Fetch 1m/5m candlestick data
**Critical For:** Future chart analysis, liquidity sweeps

---

### 3. IV Metric Calculation (`iv_metrics`)
**Frequency:** Every 30 minutes
**Provider:** Calculates from option chain data
**Purpose:** Compute IV rank, IV percentile, term structure
**Critical For:** High IV / Low IV regime detection in `/plan`

---

### 4. End-of-Day Sync (`eod_sync`)
**Frequency:** Daily at 10:15pm UTC (5:15pm EST)
**Provider:** Tiingo API
**Purpose:** Fetch daily OHLCV data for all tickers
**Critical For:** Historical backtesting, swing high/low analysis

---

### 5. Historical Backfill (`historical_backfill`)
**Frequency:** Daily at 3:00am UTC
**Provider:** Databento API
**Purpose:** Backfill missing historical data (30-day lookback)
**Critical For:** Filling gaps in price history

---

## Troubleshooting

### Problem: "Option chain refresh failed"
**Symptoms:** `/calc` returns error, logs show `Option chain refresh failed`
**Causes:**
1. Schwab API credentials missing or invalid
2. Schwab refresh token expired
3. Rate limit exceeded
4. Database connection issue

**Solutions:**
```bash
# Check Schwab credentials
echo $SCHWAB_APP_KEY
echo $SCHWAB_SECRET_KEY
echo $SCHWAB_REFRESH_TOKEN

# Test Schwab API manually
curl -H "Authorization: Bearer $SCHWAB_REFRESH_TOKEN" \
  "https://api.schwabapi.com/marketdata/v1/chains?symbol=SPY"

# Check database connection
psql $DATABASE_URL -c "SELECT 1;"
```

---

### Problem: Worker restarts frequently on Render
**Symptoms:** Logs show repeated "Service restarting..." messages
**Causes:**
1. Missing required environment variables
2. Database URL incorrect
3. Redis connection failing

**Solutions:**
1. Verify all environment variables are set on worker service
2. Ensure DATABASE_URL uses `postgresql://` not `postgres://`
3. Check Redis URL and token are correct

---

### Problem: Database not populating with option data
**Symptoms:** `/calc` still requires manual premium after 30+ minutes
**Causes:**
1. Scheduler not enabled (`SCHEDULER_ENABLED=false`)
2. No active tickers in database
3. Option chain job failing silently

**Solutions:**
```bash
# Check if scheduler is enabled
psql $DATABASE_URL -c "SELECT 1;" && echo "Scheduler should be enabled"

# Check active tickers
psql $DATABASE_URL -c "SELECT symbol FROM tickers WHERE is_active = true;"

# If no tickers, run seeding script:
python scripts/seed_tickers.py

# Check scheduler logs for errors
# (Render logs or local terminal)
```

---

### Problem: Rate limit errors from Schwab
**Symptoms:** Logs show "429 Too Many Requests"
**Causes:**
1. `OPTION_CHAIN_JOB_INTERVAL_MINUTES` set too low (e.g., 1 minute)
2. Multiple instances of scheduler running

**Solutions:**
1. Set `OPTION_CHAIN_JOB_INTERVAL_MINUTES=15` (recommended minimum)
2. Ensure only ONE worker service is running (not both web + worker with scheduler enabled)
3. Add retry logic with exponential backoff (already implemented in `app/workers/jobs.py`)

---

## Cost Breakdown (Render)

| Service | Type | Cost |
|---------|------|------|
| Web Service (API + Discord Bot) | Starter Instance | $7/month |
| Background Worker (Scheduler) | Starter Instance | $7/month |
| **Total** | | **$14/month** |

**Database & Redis:**
- PostgreSQL (Neon): Free tier (512 MB, sufficient for 50k option contracts)
- Redis (Upstash): Free tier (10k commands/day, sufficient for caching)

---

## Next Steps

1. **Local Testing:**
   - Set `SCHEDULER_ENABLED=true` in `.env`
   - Run `uvicorn app.main:app --reload`
   - Wait 15 minutes, then test `/calc` without `premium` parameter

2. **Production Deployment:**
   - Create background worker on Render with start command: `python -m app.workers.scheduler`
   - Set `SCHEDULER_ENABLED=true` on worker only
   - Deploy and monitor logs for "Scheduler started"

3. **Verify Auto-Fetch:**
   - After 15 minutes, run `/calc Long Call SPY 580 7` (no premium/price)
   - Should return option metrics from database

---

## Summary

**For Local Development:**
```bash
# .env
SCHEDULER_ENABLED=true

# Run
uvicorn app.main:app --reload
```

**For Production (Render):**
- **Web Service**: `SCHEDULER_ENABLED=false` (runs Discord bot + API)
- **Worker Service**: `SCHEDULER_ENABLED=true` (runs scheduler jobs)
- **Start Command**: `cd /opt/render/project/src && python -m app.workers.scheduler`

**Key Jobs:**
- Option chains refresh every 15 minutes (Schwab)
- Real-time prices every 1m/5m (Schwab)
- IV metrics every 30 minutes (calculated)
- EOD sync daily at 10:15pm UTC (Tiingo)
- Historical backfill daily at 3am UTC (Databento)

**Result:**
- `/calc` and `/plan` commands auto-fetch option data from database
- No manual `premium` parameter needed
- Discord bot provides real-time option metrics
