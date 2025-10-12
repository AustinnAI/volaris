# Render Deployment Options

This guide compares two deployment strategies for running the Volaris Discord bot with auto-fetch functionality.

---

## Option 1: Single Worker (Bot + Scheduler) ✅ **RECOMMENDED**

**Cost:** $7/month (1 background worker)

Run both Discord bot AND scheduler in a single process. The bot automatically starts the scheduler when `SCHEDULER_ENABLED=true`.

### Setup

**1. Configure Existing Worker (`volaris-bot`)**

Add this environment variable to your existing `volaris-bot` service:

```bash
SCHEDULER_ENABLED=true
```

**That's it!** The bot will automatically start the scheduler on startup.

### How It Works

The Discord bot checks `SCHEDULER_ENABLED` on startup:
- If `true`: Starts scheduler in same process (option chains refresh every 15 min)
- If `false`: Runs bot only (no auto-fetch)

See [app/alerts/discord_bot.py:440-455](app/alerts/discord_bot.py#L440-L455)

### Verify Deployment

**Check Render logs for `volaris-bot`:**

```
2025-10-12 16:20:30 - INFO - Starting Discord bot...
2025-10-12 16:20:30 - INFO - Initializing database for scheduler...
2025-10-12 16:20:31 - INFO - APScheduler configured with background jobs
2025-10-12 16:20:31 - INFO - ✅ Background scheduler started alongside Discord bot
2025-10-12 16:20:32 - INFO - Bot logged in as Volaris#1234
2025-10-12 16:20:32 - INFO - Commands synced to guild 1234567890
```

**After 15 minutes**, test on Discord:
```
/calc
Strategy: Long Call
Symbol: SPY
Strikes: 580
DTE: 7
Premium: [leave blank]
Underlying Price: [leave blank]
```

### Pros & Cons

✅ **Pros:**
- **Cheaper**: $7/month instead of $14/month
- **Simpler**: One service to manage
- **Easier debugging**: All logs in one place
- **No extra setup**: Just set `SCHEDULER_ENABLED=true`

❌ **Cons:**
- If scheduler crashes, Discord bot might also crash
- Both processes share same resources (512 MB RAM)
- Can't scale bot and scheduler independently

---

## Option 2: Separate Workers (Bot + Dedicated Scheduler)

**Cost:** $14/month (2 background workers)

Run Discord bot and scheduler as separate services for better isolation and resilience.

### Setup

**1. Keep Existing Worker (`volaris-bot`)**

Environment variables:
```bash
SCHEDULER_ENABLED=false    # Bot only, no scheduler
DISCORD_BOT_ENABLED=true
# ... all other Discord/API credentials
```

**2. Create New Background Worker (`volaris-worker`)**

- **Name**: `volaris-worker`
- **Start Command**: `cd /opt/render/project/src && python -m app.workers`
- **Environment Variables**: Copy ALL from `volaris-bot`, then set:
  ```bash
  SCHEDULER_ENABLED=true
  DISCORD_BOT_ENABLED=false  # Optional: worker doesn't need bot
  ```

### Verify Deployment

**Check `volaris-worker` logs:**
```
2025-10-12 16:20:30 - INFO - Initializing background worker...
2025-10-12 16:20:30 - INFO - APScheduler configured with background jobs
2025-10-12 16:20:30 - INFO - Scheduler started
2025-10-12 16:20:30 - INFO - Background worker started. Press Ctrl+C to stop.
```

**Check `volaris-bot` logs:**
```
2025-10-12 16:20:30 - INFO - Starting Discord bot...
2025-10-12 16:20:32 - INFO - Bot logged in as Volaris#1234
```

### Pros & Cons

✅ **Pros:**
- **Isolation**: Bot and scheduler can't crash each other
- **Independent scaling**: Can upgrade scheduler instance size separately
- **Better resource allocation**: Each service gets dedicated 512 MB RAM
- **Easier troubleshooting**: Separate logs for bot vs data fetching

❌ **Cons:**
- **More expensive**: $14/month vs $7/month
- **Extra setup**: Need to create and manage second service
- **More complex**: Two services to monitor and deploy

---

## Comparison Table

| Feature | Option 1: Single Worker | Option 2: Separate Workers |
|---------|------------------------|----------------------------|
| **Monthly Cost** | $7 | $14 |
| **Setup Complexity** | Very Simple | Moderate |
| **Services to Manage** | 1 | 2 |
| **Resource Isolation** | Shared (512 MB) | Separate (512 MB each) |
| **Failure Isolation** | ❌ Shared fate | ✅ Independent |
| **Scaling Flexibility** | ❌ All-or-nothing | ✅ Independent |
| **Debugging** | ✅ Single log stream | ❌ Two log streams |
| **Recommended For** | MVP, tight budget | Production, high availability |

---

## Recommendation

**For MVP / Small Projects:** Use **Option 1** (Single Worker)
- You're testing the bot and don't need 99.9% uptime
- $7/month budget is important
- Easier to get started

**For Production / Critical Systems:** Use **Option 2** (Separate Workers)
- You have users depending on the bot
- You need independent scaling (e.g., increase scheduler frequency)
- Willing to pay $14/month for better reliability

---

## Migration Path

**Start with Option 1, upgrade to Option 2 later:**

1. **Initially**: Set `SCHEDULER_ENABLED=true` on `volaris-bot` ($7/month)
2. **Later**: Create `volaris-worker`, set `SCHEDULER_ENABLED=false` on bot ($14/month)
3. **Rollback**: Delete `volaris-worker`, set `SCHEDULER_ENABLED=true` on bot ($7/month)

No code changes needed - just environment variable configuration!

---

## Quick Setup Instructions

### Option 1: Single Worker (Bot + Scheduler)

```bash
# On Render dashboard → volaris-bot → Environment
# Add/update this variable:
SCHEDULER_ENABLED=true

# Restart service
# That's it!
```

### Option 2: Separate Workers

```bash
# 1. Update volaris-bot environment:
SCHEDULER_ENABLED=false

# 2. Create new background worker:
# Name: volaris-worker
# Start command: cd /opt/render/project/src && python -m app.workers
# Environment: Copy all from volaris-bot, then set:
SCHEDULER_ENABLED=true

# 3. Deploy both services
```

---

## Troubleshooting

### Single Worker: "Scheduler not starting"

**Symptoms:** Logs show bot starting but no scheduler messages

**Solution:**
1. Check `SCHEDULER_ENABLED=true` in environment variables
2. Check logs for import errors: `from app.workers import create_scheduler`
3. Verify database connection (scheduler needs DB to store job state)

---

### Separate Workers: "Database connection refused"

**Symptoms:** `volaris-worker` logs show DB connection errors

**Solution:**
1. Ensure `DATABASE_URL` matches exactly between bot and worker
2. Verify both services in same Render region (Oregon US West)
3. Check Neon database allows multiple connections (free tier: 10 connections)

---

### Both Options: "/calc still requires premium parameter"

**Symptoms:** After 15+ minutes, `/calc` still asks for manual premium

**Solution:**
1. Check scheduler is actually running (look for "Scheduler started" in logs)
2. Check database has tickers: `psql $DATABASE_URL -c "SELECT * FROM tickers WHERE is_active = true;"`
3. Wait for first job run (15 minutes from scheduler start)
4. Check option_contracts table: `psql $DATABASE_URL -c "SELECT symbol, COUNT(*) FROM option_contracts GROUP BY symbol;"`

---

## Summary

**Recommended:** Start with **Option 1** (single worker) for simplicity and cost savings.

**Environment Variable:**
```bash
SCHEDULER_ENABLED=true
```

**Expected Cost:**
- Option 1: $7/month
- Option 2: $14/month

**Both options enable:**
- Auto-fetch option chains every 15 minutes
- Real-time price updates
- `/calc` and `/plan` commands work without manual premium input
