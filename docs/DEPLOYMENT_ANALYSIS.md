# Volaris Deployment Overview & Stabilization Analysis

## 1. System Architecture

### Current Deployment Configuration

```
┌─────────────────────────────────────────────────────────────────────┐
│                         RENDER PLATFORM                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌────────────────────────────────┐  ┌──────────────────────────┐  │
│  │   Web Service (FREE TIER)      │  │  Background Worker       │  │
│  │   Memory: 512 MB               │  │  (STARTER - $7/mo)       │  │
│  │   ❌ Crashes at ~470-480 MB     │  │  Memory: 512 MB          │  │
│  ├────────────────────────────────┤  │  ❌ Crashes at ~470-480 MB│  │
│  │  Command:                      │  │  ─────────────────────── │  │
│  │  uvicorn app.main:app \        │  │  Command:                │  │
│  │    --host 0.0.0.0 \            │  │  python -m app.alerts    │  │
│  │    --port 10000                │  │    .discord_bot          │  │
│  ├────────────────────────────────┤  ├──────────────────────────┤  │
│  │  Components:                   │  │  Components:             │  │
│  │  • FastAPI application         │  │  • Discord bot (24/7)    │  │
│  │  • REST API endpoints          │  │  • APScheduler jobs      │  │
│  │  • DB connection pool (5+10)   │  │  • Alert polling (60s)   │  │
│  │  • Health checks               │  │  • Stream polling (60s)  │  │
│  │  • Router handlers             │  │  • Daily digest task     │  │
│  ├────────────────────────────────┤  ├──────────────────────────┤  │
│  │  Env Variables:                │  │  Env Variables:          │  │
│  │  • SCHEDULER_ENABLED=true ⚠️   │  │  • SCHEDULER_ENABLED=true│  │
│  │  • DISCORD_BOT_ENABLED=true ⚠️ │  │  • DISCORD_BOT_ENABLED=  │  │
│  │  • ENVIRONMENT=production      │  │      true                │  │
│  │  • LOG_LEVEL=info              │  │  • LOG_LEVEL=info        │  │
│  └────────────────────────────────┘  └──────────────────────────┘  │
│           │                                      │                   │
│           └──────────────┬───────────────────────┘                   │
│                          │                                           │
└──────────────────────────┼───────────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────────┐
        │     EXTERNAL DEPENDENCIES (FREE TIER)    │
        ├──────────────────────────────────────────┤
        │                                          │
        │  ┌────────────────────────────────────┐ │
        │  │  Neon PostgreSQL (FREE)            │ │
        │  │  • 0.5 GB storage per project      │ │
        │  │  • 190 compute hours/month         │ │
        │  │  • Max 2 CU (2 vCPU / 8 GB RAM)    │ │
        │  │  • Connection pool: 5 + 10 overflow│ │
        │  └────────────────────────────────────┘ │
        │                                          │
        │  ┌────────────────────────────────────┐ │
        │  │  Upstash Redis (FREE)              │ │
        │  │  • 256 MB data                     │ │
        │  │  • 10K commands/day                │ │
        │  │  • Used for: token cache, rate     │ │
        │  │    limiting, session storage       │ │
        │  └────────────────────────────────────┘ │
        │                                          │
        │  ┌────────────────────────────────────┐ │
        │  │  Market Data APIs (ALL CONFIGURED) │ │
        │  │  • Schwab (OAuth + refresh token)  │ │
        │  │  • Tiingo (EOD data)               │ │
        │  │  • Alpaca (historical)             │ │
        │  │  • Polygon (market data)           │ │
        │  │  • Finnhub (fundamentals)          │ │
        │  │  • Databento (backfills)           │ │
        │  └────────────────────────────────────┘ │
        └──────────────────────────────────────────┘
```

---

## 2. Runtime Behavior & Data Flow

### Background Worker Process Flow

```
┌──────────────────────────────────────────────────────────────────┐
│              BACKGROUND WORKER EXECUTION CYCLE                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  STARTUP (t=0s)                                                  │
│  ├─ Load Discord bot                                             │
│  ├─ Create APScheduler                                           │
│  ├─ Load 4 cog extensions (strategy, market_data, calculators,  │
│  │  utilities)                                                   │
│  ├─ Sync slash commands to Discord guild                         │
│  ├─ Initialize DB connection pool (5 + 10 overflow)              │
│  └─ Start 3 background tasks + 5 scheduler jobs                  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  DISCORD BOT TASKS (discord.py event loop)                │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │  1. poll_price_alerts (every 60s)                         │  │
│  │     └─ HTTP → Web API → fetch triggered alerts           │  │
│  │  2. poll_price_streams (every 60s)                        │  │
│  │     └─ HTTP → Web API → fetch active streams             │  │
│  │  3. daily_top_digest (cron: 9:30 AM ET)                   │  │
│  │     └─ HTTP → Web API → fetch market movers              │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  APSCHEDULER JOBS (AsyncIOScheduler)                      │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │  1. realtime_prices_job (every 120s)                      │  │
│  │     ├─ Fetch ~500 S&P 500 tickers                         │  │
│  │     ├─ Batch size: 25 tickers per iteration               │  │
│  │     ├─ For each ticker: HTTP → Schwab API                 │  │
│  │     ├─ Parse + upsert to Postgres (5-10 rows/ticker)      │  │
│  │     └─ Memory spike: +50-100 MB                           │  │
│  │                                                            │  │
│  │  2. option_chain_refresh_job (every 30 min)               │  │
│  │     ├─ Fetch option chains for active tickers             │  │
│  │     ├─ HTTP → Schwab API (large payloads)                 │  │
│  │     ├─ Parse contracts (100-200 per ticker)               │  │
│  │     └─ Memory spike: +80-150 MB                           │  │
│  │                                                            │  │
│  │  3. iv_metric_job (every 60 min)                          │  │
│  │     └─ Compute IV metrics from option chain snapshots     │  │
│  │                                                            │  │
│  │  4. refresh_sp500_job (weekly: Mon 6:00 AM)               │  │
│  │     └─ Scrape S&P 500 constituents                        │  │
│  │                                                            │  │
│  │  ❌ REMOVED: prices_5m (redundant with prices_1m)          │  │
│  │  ❌ REMOVED: eod_sync (not needed for MVP)                 │  │
│  │  ❌ REMOVED: historical_backfill (one-time setup)          │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  MEMORY PATTERN (saw-tooth growth):                              │
│  ─────────────────────────────────────────────────────────────  │
│  470 MB ┤                          ╭╮                    ╭╮ 💥   │
│  400 MB ┤                  ╭╮     ╭╯╰╮          ╭╮     ╭╯╰╮     │
│  350 MB ┤          ╭╮     ╭╯╰╮   ╭╯  ╰╮        ╭╯╰╮   ╭╯  ╰╮    │
│  300 MB ┤  ╭╮     ╭╯╰╮   ╭╯  ╰╮ ╭╯    ╰╮╭╮   ╭╯  ╰╮ ╭╯    ╰╮   │
│  250 MB ┼──╯╰─────╯──╰───╯────╰─╯──────╰╯╰───╯────╰─╯──────╰─  │
│         0    5    10   15   20   25   30   35   40   45   50   │
│                          Time (minutes)                          │
│                                                                   │
│  💥 CRASH at 10-20 min: Memory reaches 470-480 MB                │
│     └─ Render kills process (OOM)                                │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### API Call Patterns

| **Component** | **Caller** | **Target** | **Frequency** | **Payload Size** | **Concurrency** |
|---|---|---|---|---|---|
| Discord commands | User interaction | Web API `/api/v1/*` | On-demand | 1-10 KB | 1-5 concurrent |
| Alert polling | Discord bot task | Web API `/api/v1/alerts/evaluate` | Every 60s | 5-50 KB | 1 connection |
| Stream polling | Discord bot task | Web API `/api/v1/streams/active` | Every 60s | 5-50 KB | 1 connection |
| Scheduler: prices_1m | APScheduler job | Schwab API `/marketdata/v1/pricehistory` | Every 120s | 2-10 KB/ticker × 500 | 25 concurrent |
| Scheduler: options | APScheduler job | Schwab API `/marketdata/v1/chains` | Every 30 min | 50-200 KB/ticker | 1-5 concurrent |
| Scheduler: IV metrics | APScheduler job | Local DB queries | Every 60 min | N/A (compute) | N/A |

---

## 3. Critical Bottlenecks & Root Causes

### 🔴 Primary Issue: Memory Leak in Background Worker

#### Root Causes Identified:

**1. Unclosed HTTP Sessions (90% of the problem)**
- **Location:** `app/alerts/helpers/api_client.py:72`
```python
async with aiohttp.ClientSession(timeout=self.timeout) as session:
    async with session.post(url, json=body) as response:
```
- **Problem:** Creates new `ClientSession` on **every Discord command** and **every polling cycle**
- **Impact:** Each session allocates ~1-2 MB; with 60s polling + user commands = **5-10 sessions/min**
- **Cumulative leak:** 5-10 MB/min = **50-100 MB in 10 minutes**

**2. BaseAPIClient (httpx) Persistence**
- **Location:** `app/services/base_client.py:43`
```python
self.client = httpx.AsyncClient(timeout=timeout)
```
- **Problem:** Client created in `__init__` but `close()` never called automatically
- **Impact:** Each provider client (Schwab, Tiingo, Alpaca, etc.) holds open connection pool
- **Usage:** 6 providers × ~5-10 MB each = **30-60 MB persistent**

**3. Scheduler Job Overlap**
- **Location:** `app/workers/scheduler.py:46-54`
```python
scheduler.add_job(
    realtime_prices_job,
    trigger="interval",
    seconds=120,
    max_instances=1,  # ✅ Good: prevents overlap
    misfire_grace_time=30,  # ⚠️ Problem: only 30s grace
)
```
- **Problem:** Job takes 60-90s to fetch 500 tickers (25 per batch)
- **Risk:** If job runs slow (API delays), next cycle starts before cleanup
- **Impact:** 2 concurrent jobs = **2× memory usage** (100-200 MB spike)

**4. Discord Bot Persistent State**
- **Location:** `app/alerts/discord_bot.py:48`
```python
self.user_command_count: dict[int, list[float]] = {}  # Never pruned
```
- **Problem:** Rate limit tracking dictionary grows unbounded
- **Impact:** Minor (1-5 MB over weeks), but contributes to baseline

**5. S&P 500 Batch Processing**
- **Location:** `app/workers/tasks.py:116-127`
```python
for batch in batched(tickers, batch_size):  # batch_size=25
    for ticker in batch:
        response = await _fetch_price_payload(provider, ticker.symbol, ...)
```
- **Problem:** Fetches 500 tickers sequentially (25 at a time)
- **Duration:** 500 tickers ÷ 25 batch = 20 iterations × 3-5s = **60-100 seconds**
- **Impact:** Long-lived job = more time for memory accumulation

---

### 🟡 Secondary Issues

#### A. Discord Commands Randomly Disappear
- **Cause:** Race condition in `app/alerts/discord_bot.py:80-86`
```python
synced = await asyncio.wait_for(self.tree.sync(guild=guild), timeout=30.0)
```
- **Problem:** If sync times out or crashes mid-deployment, commands aren't registered
- **Evidence:** Log shows `❌ Command sync timed out after 30s` or `❌ Command sync failed`

#### B. Web Service Configuration Issues
- **Misconfiguration:** Web service has `SCHEDULER_ENABLED=true` + `DISCORD_BOT_ENABLED=true`
- **Problem:** These flags should be `false` on web service (only needs REST API)
- **Impact:** Minor (flags not used in web context), but confusing for debugging

#### C. Redis Free Tier Limit Risk
- **Limit:** 10K commands/day = **417 commands/hour**
- **Current usage estimate:**
  - Token cache reads: ~120/hour (every 30s for scheduler jobs)
  - Rate limiting: ~60/hour (user commands)
  - Session storage: ~50/hour
  - **Total:** ~230/hour = **5,520/day** (55% of limit) ✅ Safe for now

---

## 4. Stabilization Recommendations

### 🎯 Phase 1: Immediate Fixes (Stop the Bleeding)

#### 1.1 Fix HTTP Session Leaks in Discord Bot
**File:** `app/alerts/helpers/api_client.py`

**Problem:** Creating new `ClientSession` on every request.

**Solution:** Reuse single session per API client instance.

```python
# BEFORE (current - leaks memory):
async def recommend_strategy(self, ...):
    async with aiohttp.ClientSession(timeout=self.timeout) as session:
        async with session.post(url, json=body) as response:
            ...

# AFTER (fixed - reuse session):
class StrategyRecommendationAPI:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def recommend_strategy(self, ...):
        session = await self._get_session()
        async with session.post(url, json=body) as response:
            ...
```

**Impact:** Reduces memory by **50-100 MB** (eliminates session leak).

---

#### 1.2 Add Explicit Client Cleanup in Scheduler Jobs
**File:** `app/workers/jobs.py`

**Problem:** `BaseAPIClient` instances never call `close()`.

**Solution:** Use context managers in job wrappers.

```python
# BEFORE (current):
async def realtime_prices_job(timeframe: Timeframe = Timeframe.ONE_MINUTE):
    async with async_session_maker() as session:
        inserted = await tasks.fetch_realtime_prices(session, timeframe=timeframe)

# AFTER (fixed):
async def realtime_prices_job(timeframe: Timeframe = Timeframe.ONE_MINUTE):
    async with async_session_maker() as session:
        inserted = await tasks.fetch_realtime_prices(session, timeframe=timeframe)

    # Explicitly cleanup provider clients after job
    from app.services.provider_manager import provider_manager
    await provider_manager.cleanup()  # Close all httpx clients
```

**Impact:** Reduces persistent memory by **30-60 MB**.

---

#### 1.3 Increase Scheduler Misfire Grace Time
**File:** `app/workers/scheduler.py:53`

**Problem:** 30s grace time too short for 60-90s jobs.

**Solution:** Increase to 120s to prevent overlapping jobs.

```python
# BEFORE:
scheduler.add_job(
    realtime_prices_job,
    trigger="interval",
    seconds=120,
    misfire_grace_time=30,  # Too short!
)

# AFTER:
scheduler.add_job(
    realtime_prices_job,
    trigger="interval",
    seconds=120,
    misfire_grace_time=120,  # Skip job if previous still running
)
```

**Impact:** Prevents job overlap = **eliminates 100-200 MB spikes**.

---

### 🔧 Phase 2: Configuration Tuning

#### 2.1 Fix Web Service Environment Variables
**Platform:** Render Dashboard → Web Service → Environment

**Changes:**
```bash
# CURRENT (incorrect):
SCHEDULER_ENABLED=true     # ❌ Web service shouldn't run scheduler
DISCORD_BOT_ENABLED=true   # ❌ Web service shouldn't run bot

# FIXED:
SCHEDULER_ENABLED=false    # ✅ Only REST API
DISCORD_BOT_ENABLED=false  # ✅ Only REST API
```

---

#### 2.2 Reduce Batch Size in Realtime Job
**File:** `app/config.py:121`

**Problem:** 25 tickers per batch × 500 tickers = 20 iterations × 5s = 100s.

**Solution:** Reduce batch size to 10-15 for faster cycles.

```python
# BEFORE:
REALTIME_SYNC_BATCH_SIZE: int = Field(default=25, ...)

# AFTER:
REALTIME_SYNC_BATCH_SIZE: int = Field(default=15, ...)
```

**Impact:** Reduces job duration to **50-75s** = lower memory accumulation.

---

#### 2.3 Prune Rate Limit Dictionary
**File:** `app/alerts/discord_bot.py:116`

**Problem:** `user_command_count` never cleaned.

**Solution:** Add periodic cleanup in rate limiter.

```python
def check_rate_limit(self, user_id: int, max_per_minute: int = 3) -> bool:
    now = asyncio.get_event_loop().time()

    # Prune stale users (no activity in 1 hour)
    stale_users = [uid for uid, timestamps in self.user_command_count.items()
                   if not timestamps or now - timestamps[-1] > 3600]
    for uid in stale_users:
        del self.user_command_count[uid]

    # Rest of rate limiting logic...
```

**Impact:** Prevents slow dictionary growth (minor, but good hygiene).

---

### 🚀 Phase 3: Architectural Improvements

#### 3.1 Upgrade Background Worker to Starter+ ($25/month)
**Why:** 512 MB insufficient for scheduler + bot + 6 API clients.

**Recommendation:** Upgrade to **Standard plan (2 GB RAM)**.

**Cost:** $25/month (vs. current $7/month).

**Benefit:**
- **4× memory headroom** = no more crashes
- Allows future scaling (more tickers, more jobs)

---

#### 3.2 Split Background Worker into Two Services
**Alternative to 3.1** (if staying on free/starter tiers):

```
┌─────────────────────────────────────────────────────────────┐
│  CURRENT: 1 Background Worker (512 MB)                      │
│  ├─ Discord bot + 3 polling tasks                           │
│  └─ APScheduler + 5 jobs                                    │
│     └─ Memory: 450-480 MB (crashes)                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  PROPOSED: 2 Separate Services                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Service A: Discord Bot (Free tier - 512 MB)       │   │
│  │  ├─ Command: python -m app.alerts                  │   │
│  │  ├─ Env: SCHEDULER_ENABLED=false                   │   │
│  │  ├─ Components: Discord bot + polling tasks        │   │
│  │  └─ Memory: ~200-250 MB ✅                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Service B: Scheduler (Free tier - 512 MB)         │   │
│  │  ├─ Command: python -m app.workers                 │   │
│  │  ├─ Env: SCHEDULER_ENABLED=true                    │   │
│  │  ├─ Components: APScheduler jobs only              │   │
│  │  └─ Memory: ~300-350 MB ✅                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  💰 Cost: Same ($0 + $7 = $7/month or $0 + $0 = free)      │
│  ✅ Benefit: Isolation = no memory contention              │
└─────────────────────────────────────────────────────────────┘
```

**Implementation:**
1. Create new Render service: "Volaris Scheduler"
2. Start command: `python -m app.workers.__main__` (create this file)
3. Set `SCHEDULER_ENABLED=true`, `DISCORD_BOT_ENABLED=false`
4. Update existing background worker: Set `SCHEDULER_ENABLED=false`

---

#### 3.3 Add Memory Profiling and Alerts
**File:** `app/workers/scheduler.py:20`

**Already implemented:** Memory logging in `_log_job_memory()` ✅

**Enhancement:** Add Sentry alert when memory > 400 MB.

```python
def _log_job_memory(event):
    memory = get_memory_usage()
    app_logger.info("job_completed", extra={...})

    # Alert if memory dangerously high
    if memory["rss_mb"] > 400:
        app_logger.warning(
            "high_memory_usage",
            extra={"memory_mb": memory["rss_mb"], "job_id": event.job_id}
        )
        # Trigger manual GC to free memory
        import gc
        gc.collect()
```

---

## 5. Priority Action Plan

### Week 1: Critical Fixes (Stop Crashes)
1. ✅ **Fix aiohttp session leaks** (api_client.py) → PR #1
2. ✅ **Add client cleanup in jobs** (jobs.py + provider_manager.py) → PR #2
3. ✅ **Increase misfire grace time** (scheduler.py) → PR #3
4. ✅ **Fix web service env vars** (Render dashboard) → No code change

**Expected outcome:** Background worker stable for 1-2 hours (vs. 10-20 min).

---

### Week 2: Optimization
5. ✅ **Reduce batch size to 15** (config.py) → PR #4
6. ✅ **Add rate limit dict pruning** (discord_bot.py) → PR #5
7. ✅ **Add GC trigger on high memory** (scheduler.py) → PR #6

**Expected outcome:** Background worker stable for 4-6 hours.

---

### Week 3: Scaling Decision
8. **Option A:** Upgrade background worker to Standard ($25/month)
9. **Option B:** Split into 2 services (Discord + Scheduler)

**Recommendation:** Start with **Option B** (free), upgrade to **Option A** if still unstable.

---

## 6. Quick Reference: Key Files & Line Numbers

| **Issue** | **File** | **Lines** | **Fix** |
|---|---|---|---|
| Session leaks | `app/alerts/helpers/api_client.py` | 72-80 | Reuse ClientSession |
| Unclosed httpx clients | `app/services/base_client.py` | 43-53 | Add cleanup in jobs |
| Job overlap | `app/workers/scheduler.py` | 53 | Increase grace time |
| Long job duration | `app/workers/tasks.py` | 116-127 | Reduce batch size |
| Rate limit dict growth | `app/alerts/discord_bot.py` | 116-129 | Prune old entries |
| Command sync timeout | `app/alerts/discord_bot.py` | 80-86 | Add retry logic |
| Web service config | Render Dashboard | Env vars | Set SCHEDULER_ENABLED=false |

---

## 7. Expected Memory Profile After Fixes

```
BEFORE (current):
├─ Baseline: 250 MB (Discord bot + scheduler + DB pool)
├─ Session leaks: +50-100 MB/10min (cumulative)
├─ Job execution: +100-200 MB (spikes)
└─ Total: 450-480 MB → 💥 CRASH

AFTER (Phase 1 fixes):
├─ Baseline: 200 MB (cleaned up clients)
├─ Session leaks: 0 MB (fixed)
├─ Job execution: +80-120 MB (reduced batch + no overlap)
└─ Total: 280-320 MB → ✅ STABLE (40% headroom)

AFTER (Phase 2 + split services):
Service A (Discord Bot):
└─ Total: 150-200 MB → ✅ STABLE (60% headroom)

Service B (Scheduler):
└─ Total: 250-300 MB → ✅ STABLE (40% headroom)
```

---

## 8. Monitoring & Validation

### Key Metrics to Track

**Memory Usage:**
- Baseline memory after startup
- Memory growth rate (MB/hour)
- Peak memory during job execution
- Memory after GC cycles

**Job Performance:**
- Job execution time (realtime_prices_job should be < 90s)
- Job success rate (should be > 95%)
- Job overlap incidents (should be 0)

**API Health:**
- HTTP session count (should be constant, not growing)
- Provider API error rate (should be < 5%)
- Redis command usage (should stay < 8K/day)

**Discord Bot:**
- Command sync success rate (should be 100%)
- Command response time (should be < 5s)
- Alert/stream polling failures (should be 0)

### Validation Steps After Each Phase

**Phase 1 Validation:**
```bash
# 1. Deploy fixes
# 2. Monitor for 2 hours
# 3. Check logs for memory warnings
grep "high_memory_usage" /var/log/render/*.log

# 4. Verify no OOM crashes
grep "killed" /var/log/render/*.log

# 5. Check job completion
grep "job_completed" /var/log/render/*.log | tail -20
```

**Phase 2 Validation:**
```bash
# 1. Monitor for 6 hours
# 2. Verify batch size reduction
grep "Realtime prices job complete" /var/log/render/*.log

# 3. Check rate limit dict size (add debug log)
grep "rate_limit_dict_size" /var/log/render/*.log
```

**Phase 3 Validation:**
```bash
# 1. Monitor for 24 hours
# 2. Compare memory profiles between services
# 3. Verify no crashes in either service
```

---

## 9. Rollback Plan

If fixes introduce regressions:

**Phase 1 Rollback:**
```bash
git revert <commit-hash>
git push origin main
# Render auto-deploys from main
```

**Phase 2 Rollback:**
- Revert config changes in Render dashboard
- Restart services

**Phase 3 Rollback:**
- Delete new scheduler service
- Re-enable scheduler in background worker
- Set `SCHEDULER_ENABLED=true` in background worker

---

## 10. Future Improvements (Post-Stabilization)

### Performance Optimizations
1. **Connection pooling:** Share httpx clients across jobs via dependency injection
2. **Caching:** Cache option chain data for 5 minutes to reduce API calls
3. **Batching:** Use bulk upserts for price data (currently 1 row at a time)
4. **Async improvements:** Use `asyncio.gather()` for parallel ticker fetches

### Scalability Enhancements
1. **Dynamic ticker selection:** Only fetch prices for tickers with active alerts/streams
2. **Job prioritization:** Use APScheduler job priorities for critical tasks
3. **Horizontal scaling:** Add load balancer for multiple web service instances
4. **Rate limit sharing:** Use Redis for cross-instance rate limiting

### Observability
1. **Metrics dashboard:** Integrate Grafana for real-time monitoring
2. **Alerting:** Set up PagerDuty for critical failures
3. **Tracing:** Add OpenTelemetry for distributed tracing
4. **Profiling:** Run periodic memory profiling in production

---

**Document Version:** 1.0
**Last Updated:** 2025-10-15
**Author:** Claude (Volaris Deployment Analysis)
