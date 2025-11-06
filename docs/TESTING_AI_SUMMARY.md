# Testing AI Summary Feature - Local Development Guide

This guide provides complete steps to test the AI-powered summary feature (`/summary` command and API endpoint) locally before deploying to Render.

## Prerequisites

- ✅ Python 3.11+ with virtual environment activated
- ✅ PostgreSQL database (Neon) accessible
- ✅ Redis cache (Upstash) accessible
- ✅ OpenAI API key configured in `.env`
- ✅ `.env` file configured with `API_BASE_URL=http://localhost:8000`

## Configuration Check

### 1. Verify `.env` Settings

```bash
# Check critical settings
cat .env | grep -E "LLM_|API_BASE_URL|CORS_ORIGINS"
```

**Expected output:**
```bash
API_BASE_URL=http://localhost:8000                  # Local development
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
LLM_ENABLED=true
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-proj-...
LLM_TIMEOUT_SECONDS=12
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=800
LLM_SUMMARY_TTL_MINUTES=20
SUMMARY_TOP_K=5
PROMPT_VERSION=v1
```

**Important:**
- `CORS_ORIGINS` must be comma-separated (not JSON array)
- `API_BASE_URL` should point to localhost for local testing
- `LLM_API_KEY` must be a valid OpenAI API key

## Testing Steps

### Step 1: Start the FastAPI Server

```bash
# Terminal 1 - Start the API
uvicorn app.main:create_app --factory --reload
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using WatchFiles
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**If you get CORS_ORIGINS parsing error:**
- Verify `.env` has comma-separated format (not JSON)
- Check `app/config.py` accepts `str | list[str]` type
- See "Troubleshooting" section below

---

### Step 2: Test API Health

```bash
# Terminal 2 - Test health endpoint
curl http://localhost:8000/health
```

**Expected output:**
```json
{"status":"healthy"}
```

---

### Step 3: Check News Data Availability

```bash
# Check if SPY has news articles
curl -s "http://localhost:8000/api/v1/news/SPY" | python3 -m json.tool | head -30
```

**Expected output:**
```json
{
    "symbol": "SPY",
    "article_count": 2,
    "articles": [
        {
            "headline": "...",
            "summary": "...",
            "source": "SeekingAlpha",
            "sentiment_score": 0.625
        }
    ]
}
```

**If article_count is 0:**
```bash
# Refresh news for SPY (fetch last 7 days)
curl -X POST "http://localhost:8000/api/v1/news/SPY/refresh?days=7"
```

---

### Step 4: Test AI Summary Endpoint (Cold Start)

```bash
# First call - will hit OpenAI API (8-15 seconds)
time curl -s "http://localhost:8000/api/v1/news/SPY/summary" | python3 -m json.tool > summary_output.json

# View the output
cat summary_output.json | head -80
```

**Expected output structure:**
```json
{
    "structured": {
        "ticker": "SPY",
        "executive_summary": "Market sentiment remains stable...",
        "key_drivers": [
            {
                "theme": "End of Quantitative Tightening",
                "supporting_articles": [1]
            }
        ],
        "sentiment_snapshot": {
            "net_score": 0.21,
            "dispersion": "low",
            "recent_change": "stable"
        },
        "risk_flags": [],
        "follow_ups": [...],
        "sources": [...]
    },
    "markdown": "📊 **SPY Market Intelligence**\n\n...",
    "fallback_used": false,
    "cache_hit": false
}
```

**Key checks:**
- ✅ `fallback_used: false` (OpenAI API succeeded)
- ✅ `cache_hit: false` (first call)
- ✅ Response time: 8-15 seconds
- ✅ Executive summary is coherent and relevant
- ✅ Key drivers have article citations

---

### Step 5: Test Redis Caching

```bash
# Second call - should return cached result (<1 second)
time curl -s "http://localhost:8000/api/v1/news/SPY/summary" | python3 -c "import sys, json; data = json.load(sys.stdin); print(f'Cache hit: {data[\"cache_hit\"]}\nFallback: {data[\"fallback_used\"]}\nResponse time should be <1s')"
```

**Expected output:**
```
Cache hit: True
Fallback: False
Response time should be <1s

real    0m0.234s
```

**Key checks:**
- ✅ `cache_hit: true`
- ✅ Response time < 1 second

---

### Step 6: Test Force Refresh

```bash
# Force regenerate (skip cache)
curl -s "http://localhost:8000/api/v1/news/SPY/summary?force_refresh=true" | python3 -c "import sys, json; data = json.load(sys.stdin); print(f'Cache hit: {data[\"cache_hit\"]}\nFallback: {data[\"fallback_used\"]}')"
```

**Expected output:**
```
Cache hit: False
Fallback: False
```

---

### Step 7: View Discord-Formatted Markdown

```bash
# Extract and view markdown output
curl -s "http://localhost:8000/api/v1/news/SPY/summary" | python3 -c "import sys, json; print(json.load(sys.stdin)['markdown'])"
```

**Expected output:**
```
📊 **SPY Market Intelligence**

**Executive Summary:**
Market sentiment remains stable as quantitative tightening approaches its conclusion...

**Key Drivers:**
• End of Quantitative Tightening ([1])
• Navigating 2026 Market Themes ([2])

**Sentiment:**
🟢 Positive (+0.21) • Stable • Dispersion: low

**Follow-ups:**
• How will the end of tightening affect SPY?

**Sources:**
[1] Quantitative Tightening Coming To An End
[2] Solving For 2026 - 5 Themes For Navigating Markets

_Generated: 2025-11-06T16:53:26.014645_
```

---

### Step 8: Test Different Tickers

```bash
# Test with AAPL (may need refresh first)
curl -X POST "http://localhost:8000/api/v1/news/AAPL/refresh?days=7"
curl -s "http://localhost:8000/api/v1/news/AAPL/summary" | python3 -c "import sys, json; data = json.load(sys.stdin); print(f'Ticker: {data[\"structured\"][\"ticker\"]}\nCache: {data[\"cache_hit\"]}\nFallback: {data[\"fallback_used\"]}')"
```

---

### Step 9: Test Fallback Mode (Optional)

Test what happens when LLM is disabled or fails.

```bash
# Temporarily disable LLM in .env
# Change: LLM_ENABLED=false
# Restart API: Ctrl+C then uvicorn app.main:create_app --factory --reload

# Test fallback
curl -s "http://localhost:8000/api/v1/news/SPY/summary" | python3 -c "import sys, json; data = json.load(sys.stdin); print(f'Fallback: {data[\"fallback_used\"]}\nSummary type: {\"Deterministic\" if data[\"fallback_used\"] else \"AI-generated\"}')"
```

**Expected output:**
```
Fallback: True
Summary type: Deterministic
```

**Remember to re-enable:** Set `LLM_ENABLED=true` and restart API

---

### Step 10: Test Error Handling

```bash
# Test with non-existent ticker
curl -s "http://localhost:8000/api/v1/news/INVALIDTICKER/summary" | python3 -m json.tool

# Test with ticker that has no news
curl -s "http://localhost:8000/api/v1/news/XYZ/summary" | python3 -c "import sys, json; data = json.load(sys.stdin); print(f'Fallback: {data[\"fallback_used\"]}')"
```

---

## Performance Benchmarks

| Scenario | Expected Time | Cache Hit |
|----------|---------------|-----------|
| First call (cold start) | 8-15 seconds | False |
| Cached call | <1 second | True |
| Force refresh | 8-15 seconds | False |
| Fallback mode | <2 seconds | False |

---

## Troubleshooting

### Issue: CORS_ORIGINS parsing error

**Error:**
```
pydantic_settings.sources.SettingsError: error parsing value for field "CORS_ORIGINS"
json.decoder.JSONDecodeError: Expecting value: line 1 column 2 (char 1)
```

**Fix:**
```bash
# In .env, use comma-separated format (NOT JSON)
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# NOT this:
# CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]
```

### Issue: OpenAI API timeout

**Error:**
```
HTTPException: status_code=500, detail="LLM provider timed out"
```

**Fixes:**
1. Check internet connection
2. Verify OpenAI API key is valid: https://platform.openai.com/api-keys
3. Increase timeout in `.env`: `LLM_TIMEOUT_SECONDS=30`
4. Check OpenAI status: https://status.openai.com/

### Issue: No news articles available

**Error:**
```
{"article_count": 0}
```

**Fix:**
```bash
# Refresh news for the ticker
curl -X POST "http://localhost:8000/api/v1/news/SPY/refresh?days=7"

# Verify Finnhub API key is valid
cat .env | grep FINNHUB_API_KEY
```

### Issue: Redis connection failed

**Error:**
```
Failed to connect to Redis
```

**Fix:**
```bash
# Verify Upstash Redis credentials
cat .env | grep UPSTASH_REDIS

# Test Redis connection
curl "${UPSTASH_REDIS_REST_URL}/ping" \
  -H "Authorization: Bearer ${UPSTASH_REDIS_REST_TOKEN}"
```

### Issue: API starts but endpoints return 404

**Problem:** FastAPI router not registered

**Fix:**
```bash
# Check logs for router registration errors
# Ensure app/main.py includes news router
grep "include_router" app/main.py
```

---

## Discord Bot Testing (Optional)

If you want to test the `/summary` Discord command locally:

### 1. Ensure API is running on localhost:8000

```bash
# Terminal 1
uvicorn app.main:create_app --factory --reload
```

### 2. Start Discord bot (pointing to local API)

```bash
# Terminal 2
# Verify API_BASE_URL in .env
cat .env | grep API_BASE_URL
# Should show: API_BASE_URL=http://localhost:8000

# Start bot (note: bot runs via API startup, not standalone)
# The bot starts automatically with the API if DISCORD_BOT_ENABLED=true
```

### 3. Test in Discord

```
/summary SPY
/summary AAPL force_refresh:True
```

**Expected behavior:**
- Bot responds with "Volaris is thinking..."
- After 8-15 seconds (first call) or <1 second (cached), shows formatted summary
- Cached calls are nearly instant

---

## Cost Monitoring

Monitor OpenAI API usage at: https://platform.openai.com/usage

**Expected costs:**
- ~$0.001 per summary (gpt-4o-mini)
- 100 summaries/day ≈ $0.10/day
- Monthly estimate: $1-3 for moderate usage

---

## Next Steps After Local Testing

Once all tests pass:

1. **Update Render environment variables**
   ```bash
   # In Render dashboard, set:
   API_BASE_URL=https://volaris-yz19.onrender.com
   CORS_ORIGINS=https://volaris-yz19.onrender.com,http://localhost:8000
   LLM_ENABLED=true
   LLM_API_KEY=sk-proj-...
   ```

2. **Deploy to Render**
   - Push changes to GitHub
   - Render will auto-deploy
   - Monitor deploy logs for errors

3. **Test in production**
   ```bash
   curl "https://volaris-yz19.onrender.com/api/v1/news/SPY/summary"
   ```

4. **Test Discord bot in production**
   ```
   /summary SPY
   ```

---

## Pre-Commit Checklist

Before committing changes:

```bash
# 1. Format code
venv/bin/black app/ tests/ --exclude tests/disabled

# 2. Lint code
venv/bin/ruff check app/ tests/ --exclude tests/disabled

# 3. Run tests
venv/bin/pytest tests/ -q

# 4. Verify all pass
echo "✅ All checks passed - ready to commit"
```

---

## Summary

**Successful local test confirms:**
- ✅ API starts without errors
- ✅ OpenAI integration works
- ✅ Redis caching works (20-min TTL)
- ✅ Fallback mode available
- ✅ Discord markdown formatting correct
- ✅ Performance targets met (<1s cached, <15s cold)
- ✅ Error handling graceful

**Ready for production deployment!**
