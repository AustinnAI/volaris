# Legacy Code (V1 Cleanup - 2025-01-23)

Removed from V1 Core MVP scope. Retained for reference.

## Scheduler (workers/)
- **APScheduler 24/7 background jobs removed**
- Use GitHub Actions + on-demand refresh instead
- Files: `scheduler.py`, `jobs.py`, `__main__.py`, `tasks.py`, `utils.py`
- Rationale: V1 targets Render free/starter tier (<512 MB RAM). APScheduler consumes 150-400 MB continuously. GitHub Actions workflow calls batch refresh endpoints hourly instead.

## Providers (services/)
- **`databento.py`** - Historical backfills (Phase 4+ backtesting only)
- **`polygon.py`** - News/top movers (replaced by Finnhub for news, removed for movers)
- **`marketstack.py`** - EOD fallback (Tiingo is primary, Alpaca is secondary)
- Rationale: V1 uses {Schwab, Tiingo, Alpaca, Finnhub} only. Multi-provider complexity deferred to V2.

## Restoration
To restore any component:
```bash
git checkout refactor-pre-v1-cleanup -- app/workers/scheduler.py
# or copy from legacy/ and restore imports/config
```

## V1 Scope
- News + Sentiment (Finnhub)
- Options Flow (single provider TBD)
- SPY/QQQ Trade Planning (Expected Move, IV/IVR via Tiingo/Alpaca)
- GitHub Actions hourly refresh (no in-process scheduler)
