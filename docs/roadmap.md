# Volaris Development Roadmap

## Phase 1: Foundation & Core Infrastructure (Weeks 1-2)
**Status:** ✅ Complete

### 1.1 Project Setup ✅
- [x] Define project structure
- [x] Initialize FastAPI application
- [x] Configure environment management (config.py)
- [x] Set up Docker & docker-compose
- [x] Configure PostgreSQL (Neon/Supabase)
- [x] Configure Redis cache (Upstash)
- [x] Set up GitHub Actions CI/CD
- [x] Integrate Sentry monitoring

### 1.2 API Integrations ✅
- [x] Schwab API client with OAuth & token refresh
- [x] Tiingo API client (EOD data)
- [x] Alpaca API client (minute delayed historical)
- [x] Databento integration (historical backfills)
- [x] Finnhub client (fundamentals & news)
- [x] Rate limiting & retry logic
- [x] API health checks & fallback logic

---

## Phase 2: Data Layer & Market Data Pipeline (Weeks 3-4)

### 2.1 Database Models
- [x] Tickers & watchlist table
- [x] OHLC price data (minute, 5-min, daily)
- [x] Options chain data model
- [x] IV metrics (IV, IVR, skew)
- [x] Market structure levels (swing highs/lows, FVG, VWAP)
- [x] Trade plans & executions
- [x] Trade journal entries

### 2.2 Data Fetchers
- [x] Real-time price fetcher (Schwab 1m/5m)
- [x] Historical backfill worker (Databento/Alpaca)
- [x] EOD data sync (Tiingo)
- [x] Options chain fetcher
- [x] IV/IVR calculator
- [x] APScheduler job configuration

---

## Phase 3: Trade Planner & Options Strategy Engine (Weeks 5-7)
**Priority:** 🟢 HIGH

> _Prerequisite_: Configure Discord bot credentials (Phase 8 setup) so trade planner features can be exercised via slash commands during development.

### 3.1 Strategy Calculator ✅
- [x] Vertical spread calculator (bull/bear, credit/debit)
- [x] Long options calculator (calls/puts)
- [x] Breakeven computation
- [x] Max profit/loss calculation
- [x] Risk-reward ratio
- [x] Probability estimates (delta-based proxy)
- [x] Position sizing by risk (% of account or fixed $)

### 3.2 Strike Selection Engine
- [ ] Optimal strike/width recommendations (2-5 wide SPY/QQQ)
- [ ] Spread width logic for high-priced tickers (5-10 wide)
- [ ] Expected move alignment (inside vs outside EM)
- [ ] Premium target validation (≥25% of width for credits)
- [ ] Broker-ready order template export

### 3.3 Strategy Recommendation Logic
- [ ] IV regime detection (high/low/neutral)
- [ ] Trend + bias analysis
- [ ] Debit vs credit structure recommendation
- [ ] Reasoning explanation engine

---

## Phase 4: Volatility & Expected-Move Module (Weeks 6-8)
**Priority:** 🟡 MEDIUM-HIGH

### 4.1 IV Metrics Dashboard
- [ ] IV calculation (current, 30-day)
- [ ] IV Rank (IVR) calculation
- [ ] IV percentile tracking
- [ ] Term structure visualization
- [ ] Skew analysis (put/call skew)

### 4.2 Expected Move Calculator
- [ ] 1-7 day expected move (EM)
- [ ] 14-45 DTE expected move
- [ ] Straddle-based EM calculation
- [ ] EM alerts (strike inside/outside EM warnings)

### 4.3 Volatility Alerts
- [ ] IV crush risk detection
- [ ] High IV → credit spread recommendations
- [ ] Low IV → debit spread recommendations
- [ ] Term structure anomaly alerts

---

## Phase 5: Market Structure & Liquidity Alerts (Weeks 7-9)
**Priority:** 🟡 MEDIUM-HIGH

### 5.1 Level Detection
- [ ] Swing high/low identification
- [ ] Buy-side liquidity (BSL) detection
- [ ] Sell-side liquidity (SSL) detection
- [ ] Fair Value Gap (FVG) detection
- [ ] VWAP calculation & tracking
- [ ] 200-EMA calculation

### 5.2 Structure Events
- [ ] BSL/SSL sweep detection
- [ ] FVG tag + displacement alerts
- [ ] Range break detection
- [ ] VWAP reclaim/reject alerts
- [ ] Order block identification

### 5.3 Playbook Mapping
- [ ] Map structure events to trade setups
- [ ] Alert generation logic (e.g., "SSL swept + bullish → bull call spread")
- [ ] Discord webhook integration

---

## Phase 6: Macro & Event Guardrails (Weeks 8-10)
**Priority:** 🟡 MEDIUM

### 6.1 Economic Calendar
- [ ] Integrate economic calendar API
- [ ] Track CPI, FOMC, Jobs reports
- [ ] Event risk detection within DTE window
- [ ] Macro quiet mode activation

### 6.2 Earnings & News
- [ ] Earnings date tracking (Finnhub)
- [ ] Sector news monitoring
- [ ] Event risk tagging per ticker

### 6.3 Risk Mitigation
- [ ] Block risky credit spreads during events
- [ ] Suggest defensive structures (iron condor, neutral)
- [ ] Override mechanism for advanced users

---

## Phase 7: Risk & PDT Manager (Weeks 9-11)
**Priority:** 🟠 MEDIUM

### 7.1 Position Tracking
- [ ] Open trade monitoring
- [ ] DTE countdown tracking
- [ ] Theta exposure calculation
- [ ] Greeks aggregation (delta, gamma, theta, vega)

### 7.2 PDT Counter
- [ ] Day trade detection logic
- [ ] PDT count tracking (rolling 5-day window)
- [ ] Pre-trade PDT warnings
- [ ] 4th day-trade violation alerts

### 7.3 Exit Management
- [ ] Let-expire vs close recommendations (0-1 DTE)
- [ ] Max loss breach alerts
- [ ] Profit target hit notifications
- [ ] Time-based exit reminders

---

## Phase 8: Discord Slash Commands & UX (Weeks 10-12)
**Priority:** 🟡 MEDIUM-HIGH

### 8.1 Command Implementation
- [ ] `/plan <ticker> <bias> <DTE>` - Strategy recommendations
- [ ] `/em <ticker> <days>` - IV, IVR, expected move
- [ ] `/size <risk$> <account%>` - Position sizing
- [ ] `/risk` - Open positions, RR, PDT status
- [ ] `/journal add` - Log trade thesis & screenshots
- [ ] `/journal view` - View past trades
- [ ] `/alerts config` - Configure alert preferences
- [ ] `/authorize` - Initiate Schwab OAuth renewal flow and guide refresh token updates

### 8.2 Discord Bot
- [ ] Discord bot setup & registration
- [ ] Slash command routing
- [ ] Embed formatting for rich alerts
- [ ] User authentication & multi-user support

---

## Phase 9: Performance & Post-Trade Analytics (Weeks 13-15)
**Priority:** ⚪ LOW (Later)

### 9.1 Trade Journaling
- [ ] Auto-capture trade entry (screenshot, stats, thesis)
- [ ] Manual journal entry via Discord
- [ ] Trade outcome recording
- [ ] P/L tracking

### 9.2 Performance Metrics
- [ ] Win rate calculation
- [ ] Average risk-reward (R-multiple)
- [ ] Expectancy formula
- [ ] IV regime outcome analysis
- [ ] Setup quality grading

### 9.3 Analytics Dashboard
- [ ] Strategy performance breakdown
- [ ] Time-based performance (weekly/monthly)
- [ ] Ticker-specific statistics
- [ ] Playbook efficacy reports (e.g., "BSL sweep → bull call → 71% win")

---

## Phase 10: Deployment & Production Hardening (Weeks 14-16)

### 10.1 Infrastructure
- [ ] Deploy to Render or Fly.io
- [ ] Production database setup (Neon/Supabase)
- [ ] Redis cache configuration
- [ ] Environment secrets management
- [ ] SSL/TLS configuration

### 10.2 Monitoring & Reliability
- [ ] Sentry error tracking
- [ ] Application logging (structured logs)
- [ ] API health endpoints
- [ ] Uptime monitoring
- [ ] Alerting for system failures

### 10.3 Testing & QA
- [ ] Unit tests (core calculation logic)
- [ ] Integration tests (API clients)
- [ ] End-to-end tests (Discord commands)
- [ ] Load testing
- [ ] API rate limit testing

---

## Phase 11: Future Enhancements (Post-MVP)

### 11.1 Advanced Analytics
- [ ] Machine learning price prediction models
- [ ] FinBERT sentiment analysis
- [ ] Correlation analysis across tickers
- [ ] Portfolio optimization

### 11.2 Extended Strategies
- [ ] Iron condor support
- [ ] Butterfly spreads
- [ ] Calendar spreads
- [ ] Diagonal spreads
- [ ] Multi-leg exotic strategies

### 11.3 Enhanced UX
- [ ] Web dashboard (React/Next.js)
- [ ] Mobile app (React Native)
- [ ] TradingView integration
- [ ] Broker integration (auto-execution)

### 11.4 Community Features
- [ ] Shared trade ideas
- [ ] Leaderboards
- [ ] Strategy backtesting UI
- [ ] Educational content

---

## Legend
- [x] Completed
- [ ] Not started
- 🟢 High priority
- 🟡 Medium-high priority
- 🟠 Medium priority
- ⚪ Low priority / Future
