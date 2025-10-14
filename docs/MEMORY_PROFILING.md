# Memory Profiling Guide

## Overview

Memory profiling tools to diagnose and optimize memory usage in the Volaris application, particularly for staying within Render's 512MB free tier limit.

## Components

### 1. Memory Profiler Utility
**File**: `app/utils/memory_profiler.py`

Provides core memory analysis functions:
- `get_memory_usage()` - Current process memory (RSS, VMS, %)
- `get_object_memory_breakdown()` - Top 20 object types by count
- `get_large_objects()` - Objects over 1MB
- `get_memory_summary()` - Comprehensive report with GC stats

### 2. Debug API Endpoints
**File**: `app/api/v1/debug.py`

Two endpoints for memory diagnostics:

#### GET /api/v1/debug/memory
Returns detailed memory breakdown:
```json
{
  "current_usage": {
    "rss_mb": 423.45,
    "vms_mb": 4234.56,
    "percent": 82.9,
    "available_mb": 89.12,
    "total_mb": 512.0
  },
  "top_objects": [
    {"type": "dict", "count": 12345, "avg_size_bytes": 240},
    {"type": "list", "count": 8901, "avg_size_bytes": 64}
  ],
  "large_objects": [
    {"type": "DataFrame", "size_mb": 45.2, "repr": "..."},
    {"type": "dict", "size_mb": 12.8, "repr": "..."}
  ],
  "gc_stats": {
    "collections": [234, 12, 3],
    "threshold": [700, 10, 10],
    "tracked_objects": 56789
  }
}
```

**Security**: Disabled in production (403 Forbidden)

#### GET /api/v1/debug/health
Lightweight health check with memory info:
```json
{
  "status": "ok",
  "environment": "development",
  "memory_mb": 423.45,
  "memory_percent": 82.9,
  "scheduler_enabled": true
}
```

### 3. Scheduler Job Memory Logging
**File**: `app/workers/scheduler.py`

Automatically logs memory usage after each scheduler job completes:
```
2025-10-14 15:30:15 - INFO - job_completed - job_id=prices_1m memory_mb=387.23 memory_percent=75.6
2025-10-14 15:32:15 - INFO - job_completed - job_id=prices_1m memory_mb=401.67 memory_percent=78.4
2025-10-14 15:45:15 - INFO - job_completed - job_id=options_refresh memory_mb=456.89 memory_percent=89.2
```

## Usage

### Monitor Memory in Production (Render)

1. **Check current memory via API**:
```bash
curl https://your-app.onrender.com/api/v1/debug/health
```

2. **Analyze Render logs**:
```bash
# View logs in Render dashboard
# Filter for "job_completed" to see memory after each job
# Look for patterns: which jobs cause spikes?
```

3. **Identify memory trends**:
- Baseline memory (no jobs running)
- Memory after each job type (prices, options, iv, sp500)
- Memory growth over time (memory leak?)
- Peak memory usage (OOM risk)

### Local Development Analysis

1. **Start the server**:
```bash
SCHEDULER_ENABLED=true uvicorn app.main:create_app --factory --reload
```

2. **Get detailed memory breakdown**:
```bash
curl http://localhost:8000/api/v1/debug/memory | jq
```

3. **Analyze the output**:

**Current Usage**:
- `rss_mb` > 450MB → Approaching Render limit, optimize
- `memory_percent` > 85% → Critical, may OOM soon

**Top Objects**:
- High dict/list counts → Expected for JSON/data processing
- Many DataFrame objects → Consider chunking/streaming
- Unexpected types → Potential memory leak

**Large Objects**:
- DataFrames > 10MB → Optimize queries, filter earlier
- Dicts > 5MB → Consider streaming or pagination
- Cached data > 20MB → Review cache TTL/size limits

**GC Stats**:
- High `tracked_objects` → May need manual gc.collect()
- Gen 2 collections → Old objects not being freed

## Optimization Strategies

### Based on Memory Profile Results

1. **High baseline memory (no jobs)**:
   - Reduce startup data loading (S&P 500 constituents)
   - Lazy-load heavy imports
   - Review global variables

2. **Specific job spikes**:
   - **prices_1m**: Reduce batch size, process in chunks
   - **options_refresh**: Limit strikes/expirations fetched
   - **iv_metrics**: Stream historical data vs loading all

3. **Memory not released after jobs**:
   - Add explicit `gc.collect()` after large operations
   - Close database sessions promptly
   - Clear caches between jobs

4. **Large objects in memory**:
   - DataFrames: Use iterators, avoid `.to_dict()`
   - Dicts: Use generators, process incrementally
   - Strings: Avoid duplicating large text (logs, responses)

### Emergency Mitigations

If memory exceeds 512MB in production:

1. **Immediate** (no code changes):
   - Set `SCHEDULER_ENABLED=false` in Render
   - Restart service
   - Commands still work (on-demand data)

2. **Quick wins** (config changes):
   - Increase job intervals (already at 120s/30m/60m)
   - Reduce batch sizes in .env:
     ```bash
     REALTIME_SYNC_BATCH_SIZE=10  # was 25
     ```
   - Disable optional features

3. **Code optimizations** (requires deployment):
   - Add streaming/chunking to data jobs
   - Implement cache size limits
   - Add manual GC calls after heavy operations

## Current Optimizations Applied

✅ **Scheduler Optimizations** (implemented):
- Removed 3 jobs: prices_5m, eod_sync, historical_backfill
- Increased intervals: prices (60s→120s), options (15m→30m), iv (30m→60m)
- Reduced batch size: 50→25 for realtime sync
- Expected memory: ~400MB (was ~1GB)

🔄 **Pending Analysis**:
- Use `/api/v1/debug/memory` after next deployment
- Monitor `job_completed` logs for spikes
- Identify which job causes highest memory usage
- Determine if further optimization needed

## Examples

### Example 1: Identify Memory Leak

**Before optimization**:
```
15:00 - job_completed - job_id=prices_1m memory_mb=350
15:02 - job_completed - job_id=prices_1m memory_mb=365
15:04 - job_completed - job_id=prices_1m memory_mb=380
15:06 - job_completed - job_id=prices_1m memory_mb=395
```

**Diagnosis**: Memory increasing by ~15MB every 2 minutes → likely not releasing session/connection

**Fix**: Add explicit cleanup in `realtime_prices_job`:
```python
try:
    # ... job logic ...
finally:
    await session.close()
    gc.collect()
```

### Example 2: Reduce Large Object Size

**Memory profile shows**:
```json
"large_objects": [
  {"type": "DataFrame", "size_mb": 78.3, "repr": "<DataFrame: 500 rows x 50 cols>"}
]
```

**Diagnosis**: Loading full historical data into single DataFrame

**Fix**: Use chunked processing:
```python
# Instead of:
df = pd.DataFrame(all_historical_data)  # 78MB

# Use:
for chunk in pd.read_sql(..., chunksize=100):
    process_chunk(chunk)  # Peak: ~15MB
```

### Example 3: High Object Count

**Memory profile shows**:
```json
"top_objects": [
  {"type": "PriceData", "count": 45678, "avg_size_bytes": 156}
]
```

**Diagnosis**: 45K PriceData objects = ~7MB just for metadata

**Fix**: Use bulk operations, avoid ORM overhead:
```python
# Instead of:
for ticker in tickers:
    session.add(PriceData(ticker=ticker, ...))  # 500 objects

# Use:
session.bulk_insert_mappings(
    PriceData,
    [{"ticker": t, ...} for t in tickers]  # 1 operation
)
```

## Monitoring Checklist

After deploying optimizations:

- [ ] Check `/api/v1/debug/health` - memory under 450MB?
- [ ] Review Render logs - any OOM events?
- [ ] Monitor job logs - memory stable after each job?
- [ ] Run for 24 hours - memory trending up or stable?
- [ ] Test all Discord commands - still working?
- [ ] Check API response times - performance acceptable?

## Next Steps

1. **Deploy current changes** with memory profiling enabled
2. **Monitor for 24-48 hours** to establish baseline
3. **Analyze memory profile** using `/api/v1/debug/memory`
4. **Identify top consumers** from logs and API
5. **Apply targeted optimizations** based on data
6. **Repeat** until memory stays under 400MB consistently

## Additional Resources

- [psutil documentation](https://psutil.readthedocs.io/)
- [Python memory profiling guide](https://docs.python.org/3/library/tracemalloc.html)
- [Render memory limits](https://render.com/docs/free#free-web-services)
- [APScheduler performance tuning](https://apscheduler.readthedocs.io/)
