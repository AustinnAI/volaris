# Quick Answer: Scheduler Setup (No Extra Cost!)

## TL;DR

**You DON'T need to create a new background worker!** ✅

Just add this to your existing `volaris-bot` environment variables on Render:

```bash
SCHEDULER_ENABLED=true
```

**Cost:** $7/month (same as before, no additional service needed)

---

## What Happens

When you set `SCHEDULER_ENABLED=true` on your existing Discord bot worker:

1. Bot starts Discord slash commands (as usual)
2. Bot also starts scheduler in same process
3. Scheduler fetches option chains every 15 minutes from Schwab
4. `/calc` and `/plan` commands automatically use database data

**No code changes. No new service. Just one environment variable.**

---

## Step-by-Step on Render

1. Go to https://dashboard.render.com
2. Click on your existing **`volaris-bot`** service
3. Click **"Environment"** tab
4. Find `SCHEDULER_ENABLED` (or add it if missing)
5. Set value to `true`
6. Click **"Save Changes"**
7. Service will auto-restart

**Done!** Wait 15 minutes, then test `/calc` without `premium` parameter.

---

## Verify It's Working

**Check Render logs for `volaris-bot`:**

```
✅ You should see:
2025-10-12 16:20:30 - INFO - Starting Discord bot...
2025-10-12 16:20:30 - INFO - Initializing database for scheduler...
2025-10-12 16:20:31 - INFO - ✅ Background scheduler started alongside Discord bot
2025-10-12 16:20:32 - INFO - Bot logged in as Volaris#1234

❌ If you see:
"SCHEDULER_ENABLED=false in config"
→ Environment variable not set correctly
```

**After 15 minutes, test on Discord:**
```
/calc
Strategy: Long Call
Symbol: SPY
Strikes: 580
DTE: 7
Premium: [leave blank]
Underlying Price: [leave blank]
```

✅ Should return option metrics from database
❌ If it asks for premium, check logs for errors

---

## Alternative: Separate Worker (If Needed)

If you want isolation between Discord bot and scheduler (recommended for production):

- **Cost:** $14/month (2 workers)
- **See:** [RENDER_DEPLOYMENT_OPTIONS.md](docs/RENDER_DEPLOYMENT_OPTIONS.md)

**Most users should start with the single worker option above.**

---

## Summary

**Q1: Should I add a `SCHEDULER_ENABLED` variable?**
✅ Yes, add `SCHEDULER_ENABLED=true` to your existing `volaris-bot` service

**Q2: Should there be a scheduler variable for all APIs or just Schwab?**
✅ One variable controls all APIs. Scheduler fetches from Schwab (option chains), Tiingo (EOD), Alpaca (historical), etc.

**Q3: How do I get Render to start the worker automatically?**
✅ Just set `SCHEDULER_ENABLED=true` on your existing `volaris-bot`. No new worker needed!

---

## Files Changed

- [app/alerts/discord_bot.py:440-455](app/alerts/discord_bot.py#L440-L455) - Added scheduler startup logic
- [app/workers/__main__.py](app/workers/__main__.py) - Standalone entry point (for separate worker option)
- [docs/RENDER_DEPLOYMENT_OPTIONS.md](docs/RENDER_DEPLOYMENT_OPTIONS.md) - Comparison guide
- [docs/SCHEDULER_SETUP.md](docs/SCHEDULER_SETUP.md) - Complete setup guide

---

## Next Steps

1. Set `SCHEDULER_ENABLED=true` on `volaris-bot` (1 minute)
2. Wait for service restart (2 minutes)
3. Wait for first option chain refresh (15 minutes)
4. Test `/calc` on Discord
5. Enjoy auto-fetch! 🎉
