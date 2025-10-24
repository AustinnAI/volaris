# Volaris Development Roadmap

> **Product Vision:** A lightweight, real-time market intelligence platform focused on actionable insights for SPY/QQQ and large-cap stocks through news sentiment and options flow analysis.

---

## Version 1 – Core MVP (Real-Time Market Intelligence)

**Goal:** Deliver actionable insights on SPY/QQQ and large-cap stocks through timely news sentiment and options flow, keeping the system lightweight and stable for Render's free/starter tier.

### 🔹 Phase 1 – Foundation
**Status:** ✅ Complete

**Deliverables:**
- [x] FastAPI backend with minimal endpoints
- [x] PostgreSQL (Neon) + Redis (Upstash) configuration
- [x] Modular provider integrations (Schwab, Tiingo, Alpaca, Databento, Finnhub)
- [x] Auth, logging, error-handling, and rate-limit middleware
- [x] Docker & docker-compose setup
- [x] GitHub Actions CI/CD
- [x] Sentry monitoring integration

### 🔹 Phase 2 – News & Sentiment Engine
**Status:** ✅ Complete

**Deliverables:**
- [x] Fetch top headlines for tickers from Finnhub
- [x] Lightweight sentiment analysis (VADER)
- [x] Cache sentiment results (10-min TTL in Redis)
- [x] `/api/v1/news/{ticker}` and `/api/v1/news/{ticker}/sentiment` endpoints
- [x] Ranked summary endpoint for multi-ticker sentiment (`/api/v1/news/sentiment/summary`)
- [x] GitHub Action workflow for automated refresh (every 3h market hours + overnight)
- [x] Database model with 30-day retention and URL-based deduplication
- [x] Batch refresh endpoint for S&P 500 (`/api/v1/news/refresh/batch`)
- [x] Exponential recency weighting (24h half-life) for sentiment aggregation
- [x] Weekly pruning of old articles via GitHub Actions

**Key Features:**
- ✅ Real-time news aggregation with URL deduplication
- ✅ VADER sentiment scoring with compound scores
- ✅ Ticker-level aggregate scores weighted by recency
- ✅ Redis caching for sentiment responses (10-min TTL)
- ✅ Automated batch refresh via GitHub Actions
- ✅ 30-day article retention with automated pruning

**Documentation:** See [docs/PHASE_2.md](docs/PHASE_2.md)

### 🔹 Phase 3 – Options Flow Monitor
**Status:** 📋 Not Started

**Deliverables:**
- [ ] Integrate one flow provider (Unusual Whales or alternative)
- [ ] Pull large trades/sweeps for SPY & QQQ (and top large caps on demand)
- [ ] Detect spikes in volume vs. average; store top N events in DB
- [ ] `/api/v1/flow/{ticker}` endpoint
- [ ] "Unusual activity" Discord alert webhook
- [ ] Rate-limiting + backoff logic per provider

**Key Features:**
- Real-time flow detection for large block trades
- Volume anomaly detection (vs. 30-day average)
- Discord alerts for significant flow events
- Historical flow data storage for pattern analysis

### 🔹 Phase 4 – Trade Planning Tools (SPY/QQQ)
**Status:** 🟢 Partial (Core complete, IV/EM pending)

**Completed:**
- [x] Vertical spread calculator (bull/bear, credit/debit)
- [x] Long options calculator (calls/puts)
- [x] Strike selection engine with IV regime detection
- [x] Strategy recommendation logic with bias context
- [x] DTE-based strategy weighting (0-7 DTE vs 14-45 DTE)
- [x] Position sizing by risk (% of account or fixed $)
- [x] Discord bot with 18 slash commands (`/plan`, `/calc`, `/size`, `/price`, `/iv`, etc.)

**Pending:**
- [ ] Use Tiingo or Alpaca for historical & IV data
- [ ] Compute Expected Move (1–7 DTE and 14–45 DTE) and IV Rank (IVR)
- [ ] `/api/v1/expected_move/{ticker}` and `/api/v1/volatility/{ticker}` endpoints
- [ ] Discord command: `/em` to query expected move and volatility snapshot
- [ ] Continue using GitHub Actions for periodic refreshes (no in-process scheduler)

**Key Features:**
- IV regime-based strategy selection
- Expected move validation for strike positioning
- Real-time option chain data from Schwab
- Capital-efficient recommendations for small accounts (<$25k)

### 🔹 Phase 5 – Refinement & Deployment Hardening
**Status:** 🟡 In Progress

**Deliverables:**
- [ ] Replace heavy pandas workflows with async + orjson
- [ ] Improve caching + batch endpoints
- [ ] Add watchlist management API (`GET/POST /api/v1/watchlist`)
- [ ] Optimize Docker builds and memory profile
- [ ] Optional migration of scheduler to Cloud Run (2 GiB free) if needed

**Memory Optimization:**
- Target: < 512 MB RAM for Render free tier
- Strategy: On-demand data refresh per command (no continuous scheduler)
- Fallback: GitHub Actions workflow for hourly watchlist refresh

---

## Version 2 – Pro Features (Future)

**Note:** These features require dedicated infrastructure (>1 GiB RAM, dedicated scheduler) and will be implemented once V1 is stable and delivering useful insights.

### 🧠 Market Structure & Alerting
**Goal:** Continuous signal detection and live streaming alerts

**Deliverables:**
- [ ] Fair Value Gap (FVG) detection
- [ ] VWAP and range break monitoring
- [ ] Live streaming feed with Discord alerts
- [ ] Dedicated scheduler with >1 GiB RAM (Google Cloud Run or Fly.io)

**Requirements:**
- Real-time data processing
- Message queue system (Redis Streams or RabbitMQ)
- Background worker for continuous monitoring

### 💬 Enhanced Bot Interactions
**Goal:** Advanced Discord commands for flow analysis and sentiment summaries

**Deliverables:**
- [ ] `/flow-leaderboard` - Top flow activity across tickers
- [ ] `/sentiment-summary` - Multi-ticker sentiment overview
- [ ] `/watchlist` commands (add, remove, list)
- [ ] Custom alert preferences per user
- [ ] Message queue system for event processing

**Requirements:**
- User authentication and preferences storage
- Multi-guild support
- Rate limiting per user/guild

### 📈 Portfolio & Trade Analytics
**Goal:** Track user positions and compute PnL, risk, Greeks

**Deliverables:**
- [ ] Position tracking with P/L calculation
- [ ] Greeks aggregation (delta, gamma, theta, vega)
- [ ] Risk exposure dashboard
- [ ] Trade journal with manual entry and auto-capture
- [ ] Performance metrics (win rate, expectancy, R-multiple)
- [ ] Optional dashboard UI (React or Next.js)

**Requirements:**
- User authentication and portfolio database
- Real-time Greeks calculation
- Historical trade data storage

### 🔄 Advanced Integrations
**Goal:** Multi-provider arbitration, ML-based signal ranking

**Deliverables:**
- [ ] Provider fallback hierarchy with automatic switching
- [ ] ML-based trade setup validation (Phase 3+ beyond V2)
- [ ] FinBERT sentiment analysis (upgrade from VADER)
- [ ] Correlation analysis across tickers
- [ ] Broker integration for auto-execution (TDA/Schwab API)

**Requirements:**
- Machine learning infrastructure
- Advanced data pipelines
- Real-time model inference

---

## Deployment Strategy

### Version 1 Architecture
**Infrastructure:** Render Free/Starter Tier ($0-$7/month)

**Services:**
- `volaris-api`: FastAPI app with health checks
- `volaris-bot`: Discord bot with slash commands
- External DB: Neon (PostgreSQL, free tier)
- External Cache: Upstash (Redis, free tier)

**Data Refresh Strategy:**
- On-demand: Commands trigger `/api/v1/market/refresh/{symbol}` for requested ticker only
- Scheduled: GitHub Actions workflow calls batch refresh endpoints hourly for watchlist (no in-process scheduler)
- Rationale: Avoids memory overhead of APScheduler (400-1000 MB)

**Memory Budget:**
- Target: < 512 MB per service
- Optimization: Async operations, orjson for JSON, no pandas in hot paths

### Version 2 Architecture
**Infrastructure:** Cloud Run or Fly.io ($20-50/month)

**Services:**
- `volaris-api`: FastAPI app (same as V1)
- `volaris-bot`: Discord bot (same as V1)
- `volaris-worker`: Dedicated background worker with APScheduler
- External DB: Neon or Supabase (PostgreSQL)
- External Cache: Upstash (Redis)
- Message Queue: Redis Streams or RabbitMQ

**Data Refresh Strategy:**
- Continuous: APScheduler jobs refresh price/options/IV every 15-60 minutes for monitored tickers
- Real-time: Streaming endpoints for live flow and structure alerts
- Memory: 1-2 GiB RAM allocated for worker process

---

## Success Metrics

### Version 1 Metrics
- [ ] API response time < 2s (95th percentile)
- [ ] Discord command latency < 3s
- [ ] Uptime > 99% for critical endpoints
- [ ] Memory usage < 512 MB per service
- [ ] News sentiment accuracy > 70% (manual validation)
- [ ] Options flow alerts < 5 min latency from trade execution

### Version 2 Metrics
- [ ] Real-time alert latency < 30s from event detection
- [ ] Structure detection accuracy > 80% (vs. manual chart analysis)
- [ ] User engagement: > 10 daily active users per Discord server
- [ ] Trade journal entries: > 50% of recommended trades tracked

---

## Priority Queue

### Immediate (This Week)
1. Complete Phase 4 IV/EM endpoints
2. Optimize memory usage in existing commands
3. Add `/em` Discord command for expected move queries

### Near-term (2-3 Weeks)
1. Implement Phase 2 (News & Sentiment Engine)
2. Add watchlist management API
3. Optimize Docker builds for faster deployments

### Mid-term (1-2 Months)
1. Implement Phase 3 (Options Flow Monitor)
2. Complete Phase 5 (Deployment Hardening)
3. Evaluate infrastructure upgrade path for V2

### Long-term (3+ Months)
1. Begin Version 2 development (Market Structure & Alerting)
2. Enhanced bot interactions with user preferences
3. Portfolio & trade analytics dashboard

---

## Legend
- [x] Completed
- [ ] Not started
- ✅ Complete
- 🟢 In Progress
- 🟡 Partial
- 📋 Not Started
