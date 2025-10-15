# Render Service Configuration Guide

This guide shows how to set up the 3-service architecture for Volaris on Render.

## Overview

```
┌────────────────────────────────────────────────────────────┐
│  3-Service Architecture (Total: $7/month)                  │
├────────────────────────────────────────────────────────────┤
│  1. Web Service (FREE)        - FastAPI REST API           │
│  2. Discord Bot (FREE)        - Discord commands + polling │
│  3. Scheduler (STARTER $7)    - Background jobs            │
└────────────────────────────────────────────────────────────┘
```

---

## Service 1: Web Service (FREE Tier)

**Purpose:** FastAPI REST API for Discord bot and external requests

### Configuration

| Setting | Value |
|---------|-------|
| **Name** | `volaris-web` |
| **Environment** | `Web Service` |
| **Region** | `Oregon (US West)` (closest to Neon) |
| **Branch** | `main` |
| **Root Directory** | ` ` (leave blank) |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port 10000` |
| **Plan** | **Free** |

### Environment Variables

**Important:** Use an **Environment Group** shared across all 3 services for common variables.

#### Shared Group: `volaris-production`
```bash
# Database
DATABASE_URL=<your-neon-postgres-url>
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10

# Redis
UPSTASH_REDIS_REST_URL=<your-upstash-url>
UPSTASH_REDIS_REST_TOKEN=<your-upstash-token>

# Environment
ENVIRONMENT=production
LOG_LEVEL=info

# API Keys (all 6 providers)
SCHWAB_APP_KEY=<your-key>
SCHWAB_SECRET_KEY=<your-secret>
SCHWAB_REFRESH_TOKEN=<your-token>
TIINGO_API_KEY=<your-key>
ALPACA_API_KEY=<your-key>
ALPACA_API_SECRET=<your-secret>
POLYGON_API_KEY=<your-key>
FINNHUB_API_KEY=<your-key>
DATABENTO_API_KEY=<your-key>

# Discord (shared)
DISCORD_BOT_TOKEN=<your-token>
DISCORD_GUILD_ID=<your-guild-id>
API_BASE_URL=<your-render-web-url>  # e.g., https://volaris-web.onrender.com
```

#### Service-Specific Variables (Web Service Only)
```bash
# Service behavior
SCHEDULER_ENABLED=false    # ✅ CRITICAL: Web service does NOT run scheduler
DISCORD_BOT_ENABLED=false  # ✅ CRITICAL: Web service does NOT run bot
```

### Health Check
- **Path:** `/health`
- Render will ping this to verify the service is running

---

## Service 2: Discord Bot (FREE Tier)

**Purpose:** Discord slash commands + alert/stream polling

### Configuration

| Setting | Value |
|---------|-------|
| **Name** | `volaris-discord-bot` |
| **Environment** | `Background Worker` (NOT Web Service) |
| **Region** | `Oregon (US West)` |
| **Branch** | `main` |
| **Root Directory** | ` ` (leave blank) |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python -m app.alerts` |
| **Plan** | **Free** |

### Environment Variables

#### Use Same Environment Group
- Link to `volaris-production` group (created above)

#### Service-Specific Variables (Discord Bot Only)
```bash
# Service behavior
SCHEDULER_ENABLED=false    # ✅ CRITICAL: Bot does NOT run scheduler
DISCORD_BOT_ENABLED=true   # ✅ Bot is enabled
```

### Why This Works on Free Tier
- **Memory usage:** ~180-200 MB (after Phase 1 fixes)
- **CPU usage:** Minimal (just HTTP polling every 60s)
- **No health checks:** Background workers don't need HTTP endpoints

---

## Service 3: Scheduler (STARTER Tier - $7/month)

**Purpose:** APScheduler background jobs (price sync, option chains, IV metrics)

### Configuration

| Setting | Value |
|---------|-------|
| **Name** | `volaris-scheduler` (rename existing worker) |
| **Environment** | `Background Worker` |
| **Region** | `Oregon (US West)` |
| **Branch** | `main` |
| **Root Directory** | ` ` (leave blank) |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python -m app.workers` |
| **Plan** | **Starter ($7/month)** |

### Environment Variables

#### Use Same Environment Group
- Link to `volaris-production` group

#### Service-Specific Variables (Scheduler Only)
```bash
# Service behavior
SCHEDULER_ENABLED=true     # ✅ Scheduler is enabled
DISCORD_BOT_ENABLED=false  # ✅ CRITICAL: Scheduler does NOT run bot
```

### Why This Needs Paid Tier
- **Memory usage:** ~250-300 MB (after Phase 1 fixes)
- **CPU usage:** High (500 tickers every 2 min)
- **Long-running jobs:** Needs reliable uptime

---

## Migration Steps (From Current 2-Service Setup)

### Step 1: Apply Phase 1 Code Fixes (DONE ✅)
```bash
git checkout -b fix/memory-leaks-phase1
git add app/alerts/helpers/api_client.py app/alerts/discord_bot.py app/services/base_client.py app/workers/scheduler.py
git commit -m "fix(memory): resolve session leaks and prevent scheduler job overlap"
git push -u origin fix/memory-leaks-phase1
# Merge to main
```

### Step 2: Create Environment Group on Render
1. Go to **Render Dashboard** → **Environment Groups** → **New Environment Group**
2. Name: `volaris-production`
3. Add all variables from "Shared Group" section above
4. Save

### Step 3: Update Existing Web Service
1. Go to **Web Service** → **Environment**
2. **Remove all variables** (they'll come from group)
3. Click **Link Environment Group** → Select `volaris-production`
4. Add service-specific variables:
   - `SCHEDULER_ENABLED=false`
   - `DISCORD_BOT_ENABLED=false`
5. Save Changes
6. Service will auto-redeploy

### Step 4: Create New Discord Bot Service
1. **Render Dashboard** → **New** → **Background Worker**
2. Connect to your GitHub repo
3. Fill in configuration (see "Service 2" above)
4. Link to `volaris-production` environment group
5. Add service-specific variables:
   - `SCHEDULER_ENABLED=false`
   - `DISCORD_BOT_ENABLED=true`
6. Create Service
7. Wait for deployment (~2-3 min)

### Step 5: Update Existing Background Worker (Scheduler)
1. Go to **Background Worker** → **Settings**
2. Rename to `volaris-scheduler` (optional, for clarity)
3. **Environment** tab:
   - Remove all variables
   - Link to `volaris-production` group
   - Add service-specific variables:
     - `SCHEDULER_ENABLED=true`
     - `DISCORD_BOT_ENABLED=false`
4. **Settings** tab:
   - Update **Start Command** to `python -m app.workers`
5. Save Changes
6. Service will auto-redeploy

### Step 6: Verify All Services Running
Check Render Dashboard:
- ✅ `volaris-web` (Free) - Status: Live
- ✅ `volaris-discord-bot` (Free) - Status: Running
- ✅ `volaris-scheduler` (Starter) - Status: Running

### Step 7: Monitor Logs
**Discord Bot Logs (check for successful startup):**
```
Bot ready as Volaris (ID: ...)
✅ Synced 15 commands to guild ...
Loaded 500 symbols from API
```

**Scheduler Logs (check for jobs running):**
```
APScheduler configured with background jobs
Realtime prices job complete (inserted: 450)
job_completed (memory_mb: 280, memory_percent: 54%)
```

**Web Service Logs (check API works):**
```
INFO: Uvicorn running on http://0.0.0.0:10000
INFO: Application startup complete
```

---

## Troubleshooting

### Discord Commands Don't Appear
**Cause:** Bot service hasn't synced commands to Discord yet.

**Fix:**
1. Check Discord bot logs for `✅ Synced X commands`
2. If timeout error, wait 1-2 min and restart bot service
3. In Discord, type `/` and wait 10 seconds for commands to populate

### "Failed to refresh symbols from API"
**Cause:** Discord bot can't reach web service API.

**Fix:**
1. Verify `API_BASE_URL` in environment group is correct (e.g., `https://volaris-web.onrender.com`)
2. Check web service is Live (not sleeping)
3. Test manually: `curl https://volaris-web.onrender.com/health`

### Scheduler Jobs Not Running
**Cause:** `SCHEDULER_ENABLED=false` or database connection failed.

**Fix:**
1. Check scheduler service environment: `SCHEDULER_ENABLED=true`
2. Check logs for `Database connection failed`
3. Verify `DATABASE_URL` is correct in environment group

### Memory Still High After Fixes
**Symptom:** Memory > 400 MB after 1 hour.

**Action:**
1. Check logs for `high_memory_usage` warnings
2. Verify Phase 1 code fixes were deployed (check git commit hash in logs)
3. If still high, proceed to Phase 2 optimizations (reduce batch size)

---

## Expected Memory Usage After Split

| Service | Baseline | Peak | Headroom |
|---------|----------|------|----------|
| Web Service | 120 MB | 180 MB | **65%** ✅ |
| Discord Bot | 150 MB | 220 MB | **57%** ✅ |
| Scheduler | 220 MB | 320 MB | **37%** ✅ |

All services well under 512 MB limit = **No crashes!**

---

## Cost Breakdown

| Service | Plan | Cost |
|---------|------|------|
| Web Service | Free | $0 |
| Discord Bot | Free | $0 |
| Scheduler | Starter | $7/month |
| **Total** | | **$7/month** |

Same cost as before, but 3× safer!

---

## Rollback Plan

If something breaks during migration:

**Emergency Rollback:**
1. Stop Discord bot service (Render Dashboard → Settings → Delete Service)
2. Update existing background worker:
   - Start command: `python -m app.alerts`
   - Env: `SCHEDULER_ENABLED=true`, `DISCORD_BOT_ENABLED=true`
3. Restart background worker

This reverts to the original 2-service setup.

---

**Questions?** Check logs first, then review troubleshooting section above.
