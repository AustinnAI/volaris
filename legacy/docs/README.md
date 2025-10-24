# Legacy Documentation (Pre-V1 Cleanup)

**Archived:** 2025-10-23
**Reason:** V1 Core MVP refactor - focusing on lightweight market intelligence

---

## What's Here

This directory contains documentation from the original roadmap before the V1 cleanup. These phases were either:
1. **Completed** but documented under the old phase numbering
2. **Deferred** to Version 2 (Pro Features)
3. **Partially completed** but restructured in V1

---

## Archived Files

### PHASE_1.md (Original)
**Status:** ✅ Complete (still relevant)
**Content:** Foundation & API integrations (1.1 + 1.2)
- FastAPI setup, database, Redis, Docker, CI/CD
- Provider integrations (Schwab, Tiingo, Alpaca, Databento, Finnhub)

**Note:** This content is still accurate but was restructured in the new roadmap as "Phase 1 - Foundation"

### PHASE_2.md (Original)
**Status:** ✅ Complete (but different scope)
**Content:** Data Layer & Pipeline (2.1 + 2.2)
- Database models (Ticker, PriceBar, OptionContract, IVMetric, etc.)
- APScheduler workers for background data ingestion

**Note:** In V1 cleanup, the scheduler was removed. Database models remain, but Phase 2 now refers to "News & Sentiment Engine" instead.

### PHASE_3.md (Original)
**Status:** ✅ Complete
**Content:** Trade Planning & Strategy Engine (3.1-3.6)
- Strategy calculator (vertical spreads, long options)
- Strike selection engine with IV-based recommendations
- Risk metrics and position sizing
- FastAPI endpoints and Discord helpers

**Note:** This functionality still exists and is part of V1 Core MVP. Documentation remains valid.

### PHASE_4.md (Original)
**Status:** ✅ Complete
**Content:** Volatility & Expected-Move Module
- IV/IVR/percentile calculations
- Term structure and skew analysis
- Expected move calculator (straddle-based)
- `/api/v1/vol/*` endpoints

**Note:** This functionality still exists and is part of V1 Core MVP. Documentation remains valid.

### volaris-project-spec.md (Original)
**Status:** Outdated
**Content:** Initial project vision and architecture
- Heavy focus on ICT patterns and market structure
- 24/7 scheduler-based architecture
- Multi-provider arbitration

**Note:** V1 refocused on lightweight market intelligence (news + sentiment + options flow) without heavy scheduler. Many features deferred to V2.

---

## New V1 Roadmap Structure

The current roadmap (`docs/roadmap.md`) restructured phases as:

**Version 1 - Core MVP:**
- Phase 1: Foundation ✅
- Phase 2: News & Sentiment Engine ✅ (NEW - replaces old Phase 2)
- Phase 3: Options Flow Monitor 📋
- Phase 4: Discord Commands 📋
- Phase 5: SPY/QQQ Trade Planning 📋

**Version 2 - Pro Features:**
- Market structure detection (ICT patterns, FVG, VWAP)
- Portfolio analytics
- Enhanced bot interactions
- Advanced integrations

---

## Restoration Notes

If you need to restore any removed functionality:

1. **APScheduler (24/7 background jobs):**
   - See `legacy/workers/scheduler.py`, `legacy/workers/jobs.py`
   - Removed in V1 due to memory constraints on Render free tier
   - Use on-demand refresh + GitHub Actions instead

2. **Multi-provider arbitration:**
   - Provider manager pruned to {Schwab, Tiingo, Alpaca, Finnhub} in V1
   - Original implementation in `legacy/workers/tasks.py`

3. **Top movers endpoint:**
   - Removed `/top` Discord command (required Polygon or populated price_bars)
   - See `legacy/` for implementation

4. **Unused providers:**
   - `legacy/services/databento.py`
   - `legacy/services/polygon.py`
   - `legacy/services/marketstack.py`

---

## Questions?

If you need clarification on what was moved or how to restore something, check:
- `legacy/README.md` - Overview of removed components
- `docs/roadmap.md` - Current V1 roadmap
- Git history - All changes committed with detailed messages
