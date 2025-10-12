# Render Background Worker - Quick Setup Guide

This is a quick reference for setting up the Volaris background worker on Render to enable auto-fetch functionality for `/calc` and `/plan` commands.

---

## Overview

You need **two separate services** on Render:
1. **Web Service** (existing): Runs Discord bot + FastAPI
2. **Background Worker** (new): Runs scheduler for option chain fetching

---

## Step 1: Create Background Worker

1. Go to https://dashboard.render.com
2. Click **"New"** → **"Background Worker"**
3. Select your `volaris` repository

---

## Step 2: Configure Service

**Name:** `volaris-worker`

**Region:** Oregon (US West) — **Must match your web service region**

**Instance Type:** Starter ($7/month)

**Build Command:**
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
cd /opt/render/project/src && python -m app.workers.scheduler
```

---

## Step 3: Add Environment Variables

Click **"Environment"** tab and copy ALL variables from your existing web service, then add:

### Required Additions:
```bash
SCHEDULER_ENABLED=true
```

### Already in your .env (copy these too):
```bash
# Database & Redis (MUST match web service)
DATABASE_URL=postgresql://...
UPSTASH_REDIS_REST_URL=https://...
UPSTASH_REDIS_REST_TOKEN=...

# Schwab API (for option chains)
SCHWAB_APP_KEY=...
SCHWAB_SECRET_KEY=...
SCHWAB_REFRESH_TOKEN=...
SCHWAB_API_BASE=https://api.schwabapi.com

# Other providers (optional)
TIINGO_API_KEY=...
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
DATABENTO_API_KEY=...
FINNHUB_API_KEY=...

# Application
ENVIRONMENT=production
LOG_LEVEL=INFO
DEBUG=false
```

### Scheduler Configuration (defaults are fine):
```bash
SCHEDULER_TIMEZONE=UTC
OPTION_CHAIN_JOB_INTERVAL_MINUTES=15
IV_METRICS_JOB_INTERVAL_MINUTES=30
REALTIME_JOB_INTERVAL_SECONDS=60
FIVE_MINUTE_JOB_INTERVAL_SECONDS=300
EOD_SYNC_CRON_HOUR=22
EOD_SYNC_CRON_MINUTE=15
HISTORICAL_BACKFILL_CRON_HOUR=3
HISTORICAL_BACKFILL_LOOKBACK_DAYS=30
```

---

## Step 4: Deploy

Click **"Create Background Worker"**

---

## Step 5: Verify Deployment

**Check Render logs (should see):**
```
==> Your service is live 🎉
2025-10-12 16:20:30 - INFO - APScheduler configured with background jobs
2025-10-12 16:20:30 - INFO - Scheduler started
2025-10-12 16:20:30 - INFO - Added job "options_refresh" to job store "default"
2025-10-12 16:20:30 - INFO - Next run time: 2025-10-12 16:35:00 UTC
```

**Wait 15 minutes**, then test on Discord:
```
/calc
Strategy: Long Call
Symbol: SPY
Strikes: 580
DTE: 7
Premium: [leave blank]
Underlying Price: [leave blank]
```

✅ If it works, you'll see option metrics
❌ If it fails, check logs for errors

---

## Common Issues

### Issue: "DISCORD_BOT_TOKEN not configured"
**Fix:** Worker doesn't need Discord credentials. Ignore this error (or add token to silence it).

### Issue: "Option chain refresh failed"
**Fix:**
1. Check Schwab credentials are correct
2. Verify `SCHWAB_REFRESH_TOKEN` is valid
3. Check database connection

### Issue: "Database connection refused"
**Fix:** Ensure `DATABASE_URL` is exactly the same as web service (copy/paste from web service env vars)

---

## Cost Summary

| Service | Cost |
|---------|------|
| Web Service (Discord + API) | $7/month |
| Background Worker (Scheduler) | $7/month |
| **Total** | **$14/month** |

Database (Neon) and Redis (Upstash) are on free tiers.

---

## What the Worker Does

**Every 15 minutes:**
- Fetches option chains for SPY, QQQ, AAPL, etc. from Schwab API
- Stores contracts in database
- Updates IV metrics

**Every 1/5 minutes:**
- Fetches real-time price data (for future chart analysis)

**Daily:**
- Syncs end-of-day data from Tiingo (10:15pm UTC)
- Backfills historical data from Databento (3am UTC)

**Result:**
- `/calc` and `/plan` commands automatically fetch option data from database
- No need to manually provide `premium` or `underlying_price` parameters
- Real-time option metrics available in Discord

---

## Local Testing (Optional)

To test scheduler locally before deploying:

```bash
# .env
SCHEDULER_ENABLED=true

# Terminal 1: Run API
source venv/bin/activate
uvicorn app.main:app --reload

# Wait 15 minutes, then test /calc on Discord
```

---

## Next Steps

1. Create background worker on Render (5 minutes)
2. Wait 15 minutes for first option chain refresh
3. Test `/calc` on Discord without premium parameter
4. Monitor logs for any errors
5. Enjoy auto-fetch functionality! 🎉

---

For detailed documentation, see [SCHEDULER_SETUP.md](SCHEDULER_SETUP.md).
