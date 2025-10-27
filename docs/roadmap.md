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

**Provider Strategy:**
- **Phase 3.0 (MVP - Week 1):** yfinance (primary) with custom anomaly detection
- **Phase 3.1 (Week 2-3):** Add Alpha Vantage as EOD validator
- **Phase 3.2 (Month 2):** Evaluate Unusual Whales free tier, upgrade if superior
- **V2 (Future):** Add Tradier for real-time data, Unusual Whales premium for alerts

**Phase 3.0 MVP - Custom Flow Detection (yfinance)**
- [ ] Create `FlowProvider` interface pattern (ABC)
- [ ] Implement `YFinanceFlowProvider` with custom anomaly logic
- [ ] Build anomaly detection: volume/OI ratio > 3.0, volume > 3× avg, bid-ask < 10%
- [ ] Create `option_flow` database table for unusual activity storage
- [ ] Add `/api/v1/flow/{ticker}` endpoint (returns unusual contracts)
- [ ] Implement `FlowProviderManager` with yfinance-only fallback
- [ ] Add Discord `/flow` command to query unusual activity
- [ ] Focus: SPY, QQQ, + S&P 500 top 50 by market cap

**Phase 3.1 - Validation Layer (Alpha Vantage)**
- [ ] Implement `AlphaVantageFlowProvider`
- [ ] Add to fallback hierarchy: yfinance → Alpha Vantage
- [ ] Daily comparison report (yfinance vs Alpha Vantage unusual flags)
- [ ] Rate limiting: 500 req/day = 1 check per ticker every 3 hours

**Phase 3.2 - Premium Upgrade Path (Unusual Whales)**
- [ ] Test Unusual Whales free tier (Shamu plan) for SPY/QQQ
- [ ] Compare custom anomaly logic vs Whales pre-built flags
- [ ] If Whales superior: implement `UnusualWhalesProvider` and upgrade to paid
- [ ] Add Discord webhook for instant unusual activity alerts (if paid plan)
- [ ] Keep yfinance as fallback if Whales API down

**Key Features:**
- Custom anomaly scoring (0-1) based on volume, OI, liquidity, premium
- Volume spike detection (vs. 30-day rolling average)
- Block trade identification (premium > $50k)
- Historical flow data storage for pattern analysis
- Discord alerts for significant flow events
- Provider abstraction for easy swapping/upgrading

**Technical Decisions:**
- **No Tradier in V1:** Requires OAuth flow, adds complexity without critical value for MVP
- **No Intrinio:** 2-week trial only, too expensive for indie project
- **No Polygon.io:** Free tier excludes options data
- **Memory Budget:** <100MB for yfinance pandas operations (within 512MB Render limit)

**Dependencies:**
- `yfinance` - Free Yahoo Finance API (will add in Phase 3.0)
- `pandas==2.2.3` - Already installed (Phase 2)
- `numpy==2.1.2` - Already installed (Phase 2)
- Alpha Vantage API key (free tier, 500 req/day) - will add in Phase 3.1

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
1. ✅ ~~Complete Phase 2 (News & Sentiment Engine)~~ - DONE
2. Begin Phase 3.0 (Options Flow Monitor MVP with yfinance)
3. Create flow provider architecture and custom anomaly detection

### Near-term (2-3 Weeks)
1. Complete Phase 3.0 (yfinance flow detection + Discord `/flow` command)
2. Implement Phase 3.1 (Add Alpha Vantage validation layer)
3. Test and refine custom anomaly scoring logic

### Mid-term (1-2 Months)
1. Phase 3.2: Evaluate Unusual Whales free tier vs custom logic
2. Decide on paid upgrade path (Whales premium vs stick with yfinance)
3. Complete Phase 5 (Deployment Hardening) - memory optimization

### Long-term (3+ Months)
1. Phase 4 enhancements: Complete IV/EM endpoints, add `/em` Discord command
2. Begin Version 2 development (Market Structure & Alerting with Tradier)
3. Enhanced bot interactions with user preferences and portfolio tracking

---

## Legend
- [x] Completed
- [ ] Not started
- ✅ Complete
- 🟢 In Progress
- 🟡 Partial
- 📋 Not Started
