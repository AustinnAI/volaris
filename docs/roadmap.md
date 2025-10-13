# Volaris Development Roadmap

> **ICT Integration:** This roadmap integrates ICT (Inner Circle Trader) methodology from `trading-guide.txt`. Phases marked with 🎯 align with liquidity-first trading concepts: BSL/SSL sweeps, FVGs, displacement, MSS, and HTF/LTF alignment.

## ICT Methodology Overview

**Core Concepts Applied Throughout:**
- **Liquidity Pools:** BSL (buy-side) above swing highs, SSL (sell-side) below swing lows
- **Fair Value Gaps (FVGs):** Internal liquidity - price inefficiencies/imbalances
- **Sweeps:** Price briefly pushes through levels to trigger stops, then reverses
- **Displacement:** Strong impulsive moves with momentum (validates direction)
- **Market Structure Shift (MSS):** Change from lower highs/lows to higher highs (or vice versa)
- **Entry Models:** iFVG, CISD, MSS + FVG return
- **Timeframe Alignment:** HTF (4H/daily) for liquidity pools, LTF (5m/15m) for entries
- **DTE Strategy:** 0-7 DTE → long calls/puts, 14-45 DTE → spreads
- **Setup Rule:** BSL sweep → bearish bias, SSL sweep → bullish bias

**Implementation Status:**
- ✅ Phase 3: Foundation complete (spreads, strikes, IV logic)
- ✅ Phase 3.8: Discord bot refactor shipped (modular cogs, helpers, tests)
- 🎯 Phase 3.4-3.5: DTE logic + bias context (quick wins)
- 🎯 Phase 4.4: Expected move validation
- 🧠 Phase 4.5: Sentiment intelligence pipeline (NLP scoring)
- 🎯 Phase 5: Core ICT structure detection (BSL/SSL, FVGs, sweeps, MSS)
- 🎯 Phase 7.4: ICT-based stops & targets
- 🎯 Phase 8.3-8.5: ICT Discord commands

---

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

### 2.2 Data Fetchers ✅
- [x] Real-time price fetcher (Schwab 1m/5m)
- [x] Historical backfill worker (Databento/Alpaca)
- [x] EOD data sync (Tiingo)
- [x] Options chain fetcher
- [x] IV/IVR calculator
- [x] APScheduler job configuration
- [x] **Scheduler Setup & Production Deployment**
  - [x] Background worker configuration for Render
  - [x] Auto-fetch option chains every 15 minutes (Schwab)
  - [x] Database seeding scripts for tickers (`scripts/seed_tickers.py`)
  - [x] **Two deployment options:**
    - **Option 1 (Recommended)**: Single worker - Discord bot + scheduler in same process (`SCHEDULER_ENABLED=true` on `volaris-bot`)
    - **Option 2**: Separate workers - Dedicated scheduler worker (`python -m app.workers`)
  - [x] Cost: $7/month (Option 1) or $14/month (Option 2)
  - [x] Documentation:
    - `docs/SCHEDULER_SETUP.md` - Complete setup guide
    - `docs/RENDER_DEPLOYMENT_OPTIONS.md` - Comparison of deployment strategies
    - `docs/RENDER_WORKER_QUICKSTART.md` - Quick reference
  - [x] Jobs: Option chains (15m), prices (1m/5m), IV metrics (30m), EOD sync (daily), historical backfill (daily)

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

### 3.2 Strike Selection Engine ✅
- [x] Optimal strike/width recommendations (2-5 wide SPY/QQQ)
- [x] Spread width logic for high-priced tickers (5-10 wide)
- [x] IV regime-based strategy selection
- [x] Premium target validation (≥25% of width for credits)
- [ ] Expected move alignment (inside vs outside EM) → **Deferred to Phase 4**
- [ ] Broker-ready order template export → **Deferred to Phase 6**

**Note:** Core strike selection complete. Expected move logic will be implemented in Phase 4 (Expected Move Calculator), and order templates will be added in Phase 6 (Trade Execution).

### 3.3 Strategy Recommendation Logic ✅
- [x] IV regime detection (high/low/neutral)
- [x] Bias-based strategy family selection
- [x] Explicit debit vs credit selection
- [x] Reasoning explanation engine
- [x] Composite scoring & ranking
- [x] Constraint filtering (max risk, min POP, min R:R)
- [x] Position sizing recommendations
- [x] Unified recommendation API

### 3.4 ICT-Aligned DTE Logic ✅
> _Practical DTE strategy selection based on buying power and ICT methodology_

- [x] DTE-based strategy preference weighting
  - **0-7 DTE (Primary focus):**
    - Prioritize credit spreads (capital efficient, high POP, theta decay advantage)
    - Long calls/puts as secondary option when high conviction + adequate buying power
    - Rationale: Lower capital requirement, faster theta decay, defined risk
  - **14-45 DTE:**
    - Prefer credit spreads for neutral/range-bound setups (less IV crush impact)
    - Debit spreads for directional plays (defined risk, lower cost than naked)
    - Long options only for strong ICT setups with significant expected move
- [x] Account size consideration: Weight credit spreads higher for accounts < $25k
  - Small (<$10k): Credit spreads only
  - Medium ($10-25k): 90% credit spreads
  - Large (>$25k): Flexible, allows long options
- [x] Buying power checks: Only suggest long options when adequate buying power
- [x] Reasoning engine: Explain DTE + capital efficiency context
- [x] Tests: 10 comprehensive tests validating all DTE scenarios (100% pass)
- [x] Integration: `apply_dte_preferences()` function integrated into recommendation flow
- [ ] Discord: Update `/plan` response to show DTE rationale (auto-displayed in reasoning)

### 3.5 Bias Context Enhancement ✅
> _Foundation for Phase 5 automated sweep detection_

- [x] Add `bias_reason` optional parameter to recommendation API
  - Values: `ssl_sweep`, `bsl_sweep`, `fvg_retest`, `structure_shift`, `user_manual`
  - Default: `user_manual`
  - Validation: Pydantic field_validator ensures valid values
- [x] Update reasoning engine to incorporate sweep context
  - `get_bias_context_reasoning()` function generates ICT setup explanations
  - SSL sweep → explains bullish reversal, targeting BSL
  - BSL sweep → explains bearish reversal, targeting SSL
  - FVG retest → explains continuation setup
  - MSS → explains structure shift confirmation
- [x] Integration: Bias context prepended to strategy reasoning automatically
- [x] Tests: 11 comprehensive tests validating all bias_reason scenarios (100% pass)
- [ ] Discord: Allow advanced users to specify setup context (future enhancement)
- [x] Foundation for Phase 5 liquidity-first workflow

### 3.6 Additional Discord Commands 🎯
> _Expose Phase 3 functionality via convenient slash commands for faster workflow_

**Strategy Recommendation (Complete) ✅:**
- [x] `/plan` - Full strategy recommendations with ICT context
  - Parameters: symbol, bias, dte, mode, max_risk (optional), account_size (optional)
  - Response: Top 3 ranked strategies with 15+ detail fields, interactive "Show More" button
  - Symbol autocomplete: 515 S&P 500 + ETF tickers
  - Rate limiting: 3 commands/minute per user
  - **Status:** LIVE on Render

**Quick Calculators (Priority 1 - Complete) ✅:**
- [x] `/calc` - Calculate P/L for specific strategy without full recommendation flow
  - Parameters: strategy, symbol, strikes, dte, premium (optional)
  - **6 Strategy Choices with Consistent Strike Formats:**
    - **Bull Call Spread (Debit):** `lower/higher` (1st=long, 2nd=short) - e.g., `445/450`
    - **Bear Put Spread (Debit):** `higher/lower` (1st=long, 2nd=short) - e.g., `450/445`
    - **Bull Put Spread (Credit):** `higher/lower` (1st=short, 2nd=long) - e.g., `450/445`
    - **Bear Call Spread (Credit):** `lower/higher` (1st=short, 2nd=long) - e.g., `445/450`
    - **Long Call, Long Put:** Single strike - e.g., `450`
  - **Strike Format Rules:**
    - Debit Call: lower/higher
    - Debit Put: higher/lower
    - Credit Call: lower/higher
    - Credit Put: higher/lower
  - **Validation:** Enforces correct strike order with clear error messages
  - Response: Max profit/loss, breakeven, R:R, POP, credit/debit, ICT context
  - Wraps Phase 3.1 calculator endpoints
  - Symbol autocomplete: 515 S&P 500 + ETF tickers

- [x] `/size` - Position sizing helper
  - Parameters: account_size, max_risk_pct OR max_risk_dollars, strategy_cost
  - Response: Recommended contracts, total position size, risk %, max loss
  - Wraps Phase 3.1 position sizing endpoint

- [x] `/breakeven` - Quick breakeven calculator
  - Parameters: strategy, strikes, cost (premium paid/received)
  - Response: Breakeven price(s), distance from current, % move needed
  - Simple calculation wrapper

- [x] `/check` - Bot and API health check
  - Parameters: None
  - Response: Bot status, API status, Schwab connectivity, DB/Redis status, response time
  - Calls existing /health endpoint

- [x] `/help` - Command reference and usage guide
  - Parameters: None
  - Response: Comprehensive embed with all commands, parameters, examples, ICT bias reasons
  - Shows: Command descriptions, parameter formats, usage examples, rate limits, DTE ranges
  - **Status:** LIVE - Ephemeral response (visible only to requester)

**Market Data Commands (Complete) ✅:**
- [x] `/price <symbol>` - Current stock price + % change
  - Response: Current price, previous close, change ($), change (%), volume
  - API: `/api/v1/market/price/{symbol}` (Schwab fallback)

- [x] `/quote <symbol>` - Full quote with bid/ask/volume
  - Response: Last price, bid, ask, bid-ask spread, volume, avg volume, volume ratio
  - API: `/api/v1/market/quote/{symbol}` (Schwab)

- [x] `/iv <symbol>` - IV metrics (IV, IVR, IV percentile)
  - Response: Current IV, IV rank, IV percentile, regime (high/low/neutral), strategy suggestion
  - API: `/api/v1/market/iv/{symbol}` (database + fallback)

- [x] `/range <symbol>` - 52-week high/low + position
  - Response: Current price, 52W high/low, position % in range, ICT context
  - API: `/api/v1/market/range/{symbol}` (database)

- [x] `/volume <symbol>` - Volume vs 30-day average
  - Response: Current volume, 30D avg volume, volume ratio, trading implication
  - API: `/api/v1/market/volume/{symbol}` (database)

- [x] `/earnings <symbol>` - Next earnings date
  - Response: Earnings date, days until, status, trading recommendation
  - API: `/api/v1/market/earnings/{symbol}` (Finnhub)

**Quick Calculators (Complete) ✅:**
- [x] `/pop <delta>` - Probability of profit from delta
  - Response: Short option POP, long option POP, explanation, common targets
  - Pure calculation (no API call)

- [x] `/delta <symbol> <strike> <type> <dte>` - Get delta for strike
  - Response: Delta, POP (short), classification (ITM/ATM/OTM)
  - API: `/api/v1/market/delta/{symbol}/{strike}/{type}/{dte}` (database)

- [x] `/contracts <risk> <premium>` - Contracts for target risk
  - Response: Number of contracts, actual risk, remaining budget, risk %
  - Pure calculation (no API call)

- [x] `/risk <contracts> <premium>` - Total risk calculation
  - Response: Total risk, % of various account sizes
  - Pure calculation (no API call)

- [x] `/dte <date>` - Days to expiration calculator
  - Response: DTE, classification (0-7/8-45/45+), ICT strategy suggestion
  - Pure calculation (no API call)

**Validators & Tools (Complete) ✅:**
- [x] `/spread <symbol> <width>` - Validate spread width
  - Response: Verdict (optimal/too narrow/too wide), recommended range, price tier
  - API: `/api/v1/market/price/{symbol}` + validation logic

**Summary:**
- **Total Commands:** 18 (6 original + 12 new)
- **Market Data:** 6 commands (price, quote, iv, range, volume, earnings)
- **Quick Calculators:** 5 commands (pop, delta, contracts, risk, dte)
- **Validators:** 1 command (spread)
- **API Endpoints:** 8 new endpoints in `/api/v1/market/*`
- **Impact:** Complete suite of quick reference and validation tools for faster trading workflow

**Analysis Tools (Priority 2 - Future):**
- [ ] `/strikes` - Show available strikes and premiums
  - Parameters: symbol, dte, type (calls/puts/both), range (atm/otm/itm/all)
  - Response: List of strikes with premium, delta, OI, volume; highlights ATM
  - Uses existing strike data service

- [ ] `/compare` - Side-by-side strategy comparison
  - Parameters: symbol, bias, dte, strategies (comma-separated)
  - Response: Table comparing max profit/loss, breakeven, R:R, POP, cost + recommendation
  - Calls multiple Phase 3 endpoints and formats comparison

**Advanced (Priority 3 - Future):**
- [ ] `/greek` - Greeks summary for potential position
  - Parameters: symbol, strategy, strikes, position, contracts
  - Response: Delta, gamma, theta, vega with explanations
  - Requires Greek calculation implementation

### 3.7 Streaming & Market Snapshot Commands 📡
> _Deliver richer Discord workflows (streams, sentiment, market movers) before Phase 4_

**Status:** ✅ Complete  
**Focus:** Introduce recurring channel updates and additional market insight commands for S&P 500 names.

**Objectives:**
- [x] `/streams` command group to list/add/remove auto-updating price posts per ticker & channel (configurable intervals).
- [x] `/sentiment <symbol>` command summarizing bullish/bearish sentiment, news snippets, and analyst leaning.
- [x] `/top` command plus daily 4 PM ET digest covering S&P 500 top gainers/losers.
- [x] Replace static `SP500.csv` with scheduled refresh from an external API (Finnhub `index/constituents`) with CSV fallback.

**Implementation Notes:**
- Created `price_streams` table + REST endpoints (`/api/v1/streams`) leveraged by the Discord bot poller.
- Added market endpoints for sentiment (recommendation trend + recent news) and constituent retrieval with caching.
- `/top` command currently surfaces a paid-plan notice; Tiingo IEX data is required for movers. Evaluating Polygon.io or in-house calculation as follow-up.
- Extended the Discord bot with `/streams`, `/sentiment`, `/top`, price stream polling, and daily movers digest (digest posts when premium data is available).
- Added weekly APScheduler job to sync S&P 500 constituents and refresh autocomplete cache (falls back to bundled CSV when APIs are unavailable).

**Dependencies:** Finnhub & Tiingo API keys, Redis cache, scheduler enabled in deployment.

**Success Metrics:**
- Stream messages delivered within ±60 s of configured interval.
- Sentiment command latency observed < 2 s with Redis caching.
- `/top` digest becomes active once an IEX-enabled provider is configured; otherwise the command communicates the requirement.

### 3.8 Discord Bot Refactoring (Technical Debt) 🔧
**Priority:** 🟢 COMPLETE (Technical Improvement)
**Status:** ✅ Refactor merged – modular bot with cog architecture

**New Architecture:**
```
app/alerts/
├── discord_bot.py        # Bootstrap + background tasks + cog loading
├── helpers/              # API clients, embeds, autocomplete, views
└── cogs/                 # strategy, market_data, calculators, utilities
```

**Highlights:**
- ☑️ Split all 18 slash commands into dedicated cogs for easier maintenance.
- ☑️ Extracted helper modules (API clients, embed builders, symbol cache, Discord views).
- ☑️ Background tasks (alerts, streams, daily digest) retained with improved logging.
- ☑️ Added helper-focused tests to cover embed formatting and autocomplete behaviour.

**Implementation Steps:**
- [x] Create tests up front to lock in command behaviour and helper interfaces.
- [x] Stand up new helper modules (API clients, embeds, autocomplete) and wire them into the bot.
- [x] Split the monolithic command file into strategy, market-data, calculator, and utilities cogs.
- [x] Trim `discord_bot.py` into a bootstrapper that loads cogs and supervises background jobs.
- [x] Deploy to Render, verify slash command sync, and smoke test `/plan`, `/price`, `/alerts`, and `/streams`.
- [x] Retire the legacy bot implementation once the modular version proved stable.

**Follow-ups:**

**Scheduler strategy recap:**
- Keep `SCHEDULER_ENABLED=false` during lightweight Discord usage; slash commands now trigger on-demand refreshes for the requested symbol only.
- Use the GitHub Actions workflow to call `/api/v1/market/refresh/price|options|iv/{symbol}` on a curated watchlist every hour so data stays reasonably fresh without running APScheduler.
- When building real-time detectors (Phase 4/5), turn the in-process scheduler back on for the universe of symbols you monitor so the rolling datasets stay up-to-date.

- 🔄 Re-run full pytest suite once `discord.py` dependency is available in CI/local env.
- 🚀 Deploy refactored bot to Render and perform smoke tests on live guild.
- 🛠️ Consider admin-only `/reload` utility for hot-reloading cogs during development.
- 🪬 Plan for mixed strategy: keep `SCHEDULER_ENABLED=false` by default (on-demand refresh per command) but establish a lightweight periodic job to hit `/api/v1/market/refresh/price|options|iv/{symbol}` for a curated watchlist.
- 📈 When building real-time anomaly detection (Phase 4+/5), re-enable the scheduler continuously for the target symbols so background jobs maintain the rolling datasets those features depend on.

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

### 4.4 Expected Move + Liquidity Validation 🎯
> _ICT Integration: Validate strike positioning relative to expected move_

- [ ] EM calculation for target DTE (straddle-based)
- [ ] Strike validation: Inside vs outside EM
  - Inside EM: Higher POP, suitable for credit spreads
  - Outside EM: Lower POP, suitable for debit spreads (big move expected)
- [ ] Reasoning engine: Explain strike positioning relative to EM
- [ ] Phase 3 integration: Use EM in strike selection scoring
- [ ] Discord: Show EM context in `/plan` response

---

## Phase 4.5: Sentiment Intelligence (Weeks 8-9)
**Priority:** 🧠 MEDIUM (Enhances discretionary context before ICT automation)

### 4.5.1 News Ingestion & Storage
- [ ] Aggregate headlines from Polygon (real time) + backup source (Finnhub/NewsAPI)
- [ ] Persist normalized articles (ticker, published_at, source, url, summary)
- [ ] Schedule hourly refresh with deduplication + retention policy

### 4.5.2 NLP Scoring Pipeline
- [ ] Implement sentiment scoring (baseline: VADER/TextBlob)
- [ ] Evaluate transformer-based model (FinBERT) for accuracy uplift
- [ ] Compute ticker-level aggregate scores (weighted by recency + source reliability)
- [ ] Cache sentiment snapshots in Redis for low-latency responses

### 4.5.3 API & Discord Surfacing
- [ ] `/api/v1/market/sentiment` returns score, trend, headline snippets, and methodology metadata
- [ ] `/sentiment` command shows numeric sentiment score, confidence, and top positive/negative headlines
- [ ] Add guardrails (rate limiting, fallback to cached score, graceful degradation when NLP offline)

### 4.5.4 Validation & QA
- [ ] Backtest sentiment vs. price reaction on recent earnings/major events
- [ ] Add unit tests for scoring pipeline and caching behavior
- [ ] Document sentiment interpretation guidelines in `docs/SENTIMENT_PIPELINE.md`

---

## Phase 5: Market Structure & Liquidity Alerts (Weeks 7-9) 🎯
**Priority:** 🟢 HIGH (Core ICT Integration Phase)

> _This phase implements the liquidity-first trading methodology from trading-guide.txt_

### 5.1 Level Detection (Enhanced)
**External Liquidity (Swing Points):**
- [ ] Swing high/low identification (local peaks/troughs)
- [ ] Buy-side liquidity (BSL) detection (above swing highs)
- [ ] Sell-side liquidity (SSL) detection (below swing lows)

**Internal Liquidity (Inefficiencies):**
- [ ] Fair Value Gap (FVG) detection (price imbalances)
- [ ] Order block identification (last consolidation before displacement)
- [ ] Grab wick detection (wick left after sweep - stop placement reference)

**Reference Levels:**
- [ ] VWAP calculation & tracking
- [ ] 200-EMA calculation
- [ ] Key HTF levels (daily/4H swings for intraday)

**ICT-Specific Detection:**
- [ ] Displacement detection (strong impulsive moves with momentum)
- [ ] Manipulation detection (weak sweeps that reverse)

### 5.2 Structure Events (Enhanced)
**Liquidity Sweeps:**
- [ ] BSL sweep detection (price pushes above swing high briefly)
- [ ] SSL sweep detection (price pushes below swing low briefly)
- [ ] Sweep + reversal confirmation

**Market Structure:**
- [ ] Market Structure Shift (MSS) detection (higher highs vs lower lows)
- [ ] FVG tag + displacement alerts (retest of inefficiency)
- [ ] Power of 3 phase detection (Accumulation → Stop Run → Displacement)

**HTF/LTF Alignment:**
- [ ] HTF liquidity pool identification (4H/daily)
- [ ] LTF entry trigger detection (5m/15m)
- [ ] Timeframe alignment validation

**Traditional Alerts:**
- [ ] Range break detection
- [ ] VWAP reclaim/reject alerts

### 5.3 ICT Entry Model Detection
> _Implements iFVG, CISD, and MSS + FVG return models from trading-guide.txt_

**Model 1: iFVG (Inverted FVG)**
- [ ] HTF key level tap detection
- [ ] LTF FVG down into level → bullish reversal
- [ ] Entry signal: Bull Call Spread or Long Call
- [ ] Stop: Under manipulation low
- [ ] Target: HTF swing high (BSL)

**Model 2: CISD (Change in State of Delivery)**
- [ ] Liquidity sweep detection
- [ ] Engulfing candle confirmation
- [ ] Entry signal: Directional strategy based on engulf
- [ ] Stop: Beyond grab wick
- [ ] Target: Opposite liquidity pool

**Model 3: MSS + FVG Return**
- [ ] Structure shift confirmation
- [ ] Retrace into FVG
- [ ] Entry signal: Strategy in displacement direction
- [ ] Stop: Below/above FVG
- [ ] Target: Next swing point

### 5.4 Liquidity-First Recommendation Flow
> _"Charts first, option chain second" - trading-guide.txt line 160_

**New Workflow:**
- [ ] Detect current market structure
- [ ] Identify liquidity pools (BSL/SSL)
- [ ] Check for recent sweep events
- [ ] Confirm displacement (not manipulation)
- [ ] Integrate with Phase 4 expected move
- [ ] Select strikes based on structure + EM
- [ ] Recommend strategy family with ICT context
- [ ] Return trade plan with setup explanation

**API Integration:**
- [ ] New endpoint: `GET /api/v1/structure/analyze/{symbol}`
- [ ] New endpoint: `GET /api/v1/liquidity/pools/{symbol}`
- [ ] New endpoint: `GET /api/v1/sweeps/recent/{symbol}`
- [ ] Enhanced: `POST /api/v1/strategy/recommend` includes structure context

### 5.5 Playbook Mapping & Alerts
- [ ] Map structure events to trade setups
- [ ] Alert generation: "SSL swept + bullish displacement → Bull Call Spread"
- [ ] Alert generation: "BSL swept + bearish displacement → Bear Put Spread"
- [ ] Discord webhook integration
- [ ] Reasoning: Explain why setup is valid per ICT rules

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

### 6.4 ICT Structure-Only Mode 🎯
> _Allow pure technical structure trading without macro filters_

- [ ] Toggle: "structure-only mode" to bypass event filters
- [ ] Reasoning: ICT methodology focuses on price action, not fundamentals
- [ ] Use case: Advanced users trading sweeps regardless of macro events
- [ ] Discord: `/plan` flag `--ignore-events` for pure technical setups

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

### 7.4 ICT-Based Stop & Target Management 🎯
> _Structure-based risk management from trading-guide.txt_

**Stop Placement:**
- [ ] Calculate stop beyond grab wick (not fixed % or ATR)
- [ ] Stop below manipulation low for bullish setups
- [ ] Stop above manipulation high for bearish setups
- [ ] Adjust stops when FVG is tagged on retrace

**Target Management:**
- [ ] Track progress toward opposite liquidity pool (BSL/SSL)
- [ ] Partial exit alerts when internal liquidity (FVG) reached
- [ ] Full exit alerts when external liquidity (swing point) reached
- [ ] VWAP/midpoint partial exit recommendations

**Trailing Stops:**
- [ ] Structure-based trailing (new swing lows/highs)
- [ ] FVG-based trailing (lock in profit after internal liquidity hit)
- [ ] Discord: Alerts for stop adjustments based on structure changes

---

## Phase 8: Discord Slash Commands & UX (Weeks 10-12)
**Priority:** 🟡 MEDIUM-HIGH

### 8.1 Command Implementation (Baseline - Partial Complete) ✅
- [x] `/plan <ticker> <bias> <DTE>` - Strategy recommendations (LIVE)
- [ ] `/em <ticker> <days>` - IV, IVR, expected move
- [ ] `/size <risk$> <account%>` - Position sizing
- [ ] `/risk` - Open positions, RR, PDT status
- [ ] `/journal add` - Log trade thesis & screenshots
- [ ] `/journal view` - View past trades
- [ ] `/alerts config` - Configure alert preferences
- [ ] `/authorize` - Initiate Schwab OAuth renewal flow and guide refresh token updates

### 8.2 Discord Bot (Baseline - Complete) ✅
- [x] Discord bot setup & registration (LIVE on Render)
- [x] Slash command routing (`/plan` functional)
- [x] Embed formatting for rich alerts (15+ fields)
- [x] Interactive buttons ("Show More Candidates")
- [x] Rate limiting (3 commands/minute per user)
- [ ] User authentication & multi-user support

### 8.3 Enhanced `/plan` Command 🎯
> _Add ICT context parameters for advanced users_

**New Optional Parameters:**
- [ ] `setup_type` (iFVG, CISD, MSS, auto) - Specify ICT entry model
- [ ] `htf_timeframe` (4H, daily, weekly) - Higher timeframe for liquidity pools
- [ ] `ltf_timeframe` (5m, 15m, 1H) - Lower timeframe for entry triggers
- [ ] `--ignore-events` flag - Bypass Phase 6 macro filters for pure structure trades

**Response Enhancement:**
- [ ] Show detected structure context (recent sweeps, FVGs)
- [ ] Explain HTF/LTF alignment
- [ ] Display setup validation (iFVG, CISD, MSS criteria met/not met)

### 8.4 New ICT Discord Commands 🎯
> _Expose Phase 5 structure analysis via Discord_

**Liquidity Analysis:**
- [ ] `/liquidity [symbol] [timeframe]` - Show BSL/SSL levels, FVGs
  - Display swing highs/lows with liquidity pools
  - Show identified FVGs (internal liquidity)
  - Indicate recent sweeps
  - Visual: Price chart with levels marked

**Structure Analysis:**
- [ ] `/structure [symbol]` - Display market structure analysis
  - Current MSS status (bullish/bearish/neutral)
  - Recent displacement events
  - Order blocks
  - Power of 3 phase (Accumulation/Stop Run/Displacement)

**Sweep Detection:**
- [ ] `/sweep [symbol] [lookback_hours]` - Check for recent liquidity sweeps
  - BSL sweeps (bearish bias)
  - SSL sweeps (bullish bias)
  - Sweep + reversal confirmation

**Setup Validation:**
- [ ] `/setup [symbol]` - Check for active ICT entry models
  - iFVG setup detected? (HTF tap + LTF FVG)
  - CISD setup detected? (sweep + engulf)
  - MSS + FVG return setup detected?
  - Recommended action if setup is valid

### 8.5 Proactive Webhook Alerts 🎯
> _Automated alerts when ICT setups trigger_

**Setup Alerts:**
- [ ] "SPY SSL swept at $540 → Bullish displacement detected → Bull Call Spread recommended"
- [ ] "AAPL MSS confirmed → Retrace into FVG expected at $175 → Watching for entry"
- [ ] "QQQ BSL swept at $450 → Bearish reversal → Bear Put Spread setup"

**Structure Alerts:**
- [ ] FVG created: "New FVG detected on SPY 15m @ $538-540"
- [ ] Sweep detected: "SSL sweep on AAPL @ $170 (4H swing low)"
- [ ] Displacement: "Strong bullish displacement on QQQ → momentum confirmed"

**Configuration:**
- [ ] User preferences: Which tickers to watch
- [ ] Alert frequency: Immediate, daily summary, both
- [ ] Filter: Only setups matching user's preferred bias/DTE

---

## ICT Implementation Guide

> **Reference:** Based on `trading-guide.txt` - comprehensive guide covering liquidity, market structure, and ICT options methodology.

### Phase 3 Current State Analysis

**✅ Strengths (Already ICT-Aligned):**
- Vertical spreads (bull/bear, credit/debit) support ICT directional setups
- Long calls/puts for fast execution (0-7 DTE preference)
- IV regime detection helps with credit vs debit selection
- Risk-reward ratios align with ICT risk management
- Position sizing by account % or fixed $ matches ICT principles

**⚠️ Gaps (Missing ICT Context):**
- No liquidity detection (BSL/SSL levels not identified)
- No market structure analysis (swing highs/lows not tracked)
- No sweep detection (user must manually identify)
- No FVG detection (internal liquidity not analyzed)
- No displacement confirmation (momentum not validated)
- No timeframe alignment (single timeframe analysis only)
- Strategy recommendations lack structure context

### ICT Entry Models (Implemented in Phase 5.3)

**Model 1: iFVG (Inverted Fair Value Gap)**
```
Trigger: HTF key level tap + LTF FVG down into level + reversal bullish
Action: Recommend Bull Call Spread or Long Call
Stop: Under manipulation low
Target: HTF swing high (BSL)
Example: SPY daily swing tapped → 15m FVG into level → bullish reversal
```

**Model 2: CISD (Change in State of Delivery)**
```
Trigger: Liquidity sweep + engulfing candle
Action: Recommend directional strategy based on engulf direction
Stop: Beyond grab wick
Target: Opposite liquidity pool
Example: SPY SSL swept → engulfing bullish candle → long call entry
```

**Model 3: MSS + FVG Return**
```
Trigger: Market structure shift confirmed + retrace into FVG
Action: Recommend strategy in displacement direction
Stop: Below/above FVG
Target: Next swing point
Example: QQQ MSS bullish → retrace to FVG @ $450 → continuation long
```

### ICT Workflow Integration

**Current Flow (Phase 3):**
```
User provides bias → Select IV regime → Recommend strategy → Calculate P/L
```

**Future Flow (Phase 5+):**
```
1. Detect market structure (swings, MSS)
2. Identify liquidity pools (BSL/SSL, FVGs)
3. Monitor for sweep events
4. Confirm displacement (not manipulation)
5. Calculate expected move (Phase 4)
6. Select strikes based on structure + EM
7. Recommend strategy with ICT context
8. Return trade plan with setup explanation
```

### Timeframe Alignment (Phase 5.2)

**ICT Timeframe Pairs:**
- Weekly → 4H (swing trading)
- Daily → 1H (multi-day positions)
- 4H → 15m (intraday day trading, **recommended for options**)
- 1H → 5m (scalping)
- 15m → 1m (high-frequency)

**Implementation:**
- User specifies HTF (for liquidity pools) and LTF (for entries)
- System validates alignment and checks for setup confluence
- Discord `/plan` accepts `htf_timeframe` and `ltf_timeframe` parameters

### DTE Strategy Rules (Phase 3.4)

**From trading-guide.txt lines 132-136 (Adapted for Capital Efficiency):**
```
0-7 DTE: Primary focus = Credit spreads (capital efficient, high theta decay)
         Secondary = Long calls/puts (when buying power permits + high conviction)
14-45 DTE: Credit spreads for neutral setups, debit spreads for directional
```

**Practical Implementation for Small Accounts (<$25k):**
- **0-7 DTE:** Heavily weight credit spreads
  - Bull put spreads after SSL sweeps (bullish)
  - Bear call spreads after BSL sweeps (bearish)
  - Advantages: Lower capital requirement, faster theta decay, defined risk
  - Long options: Only when strong ICT setup + position fits within 2-5% account risk

- **14-45 DTE:** Prefer spreads over naked options
  - Credit spreads: Neutral/range-bound expectations (less IV crush)
  - Debit spreads: Directional plays with defined risk
  - Long options: Reserved for significant expected moves (EM validation)

**Account Size Logic:**
- Accounts < $10k: Credit spreads only (capital preservation)
- Accounts $10-25k: 90% credit spreads, 10% debit spreads or long options
- Accounts > $25k: More flexibility, long options viable for strong setups

**Implementation:**
- Strategy recommender checks `account_size` parameter
- Weights credit spreads heavily for smaller accounts
- Only suggests long options when position size <= max_risk parameter
- Reasoning engine explains: "Credit spread recommended (capital efficient for 0-7 DTE)"
- Discord `/plan` response shows capital requirements vs account size

### Bias Context (Phase 3.5)

**Setup Reasons:**
- `ssl_sweep`: SSL taken → bullish bias (buy call, bull call spread)
- `bsl_sweep`: BSL taken → bearish bias (buy put, bear put spread)
- `fvg_retest`: Price returning to FVG → continuation expected
- `structure_shift`: MSS confirmed → trend change validated
- `user_manual`: User-specified bias without structure detection

**Implementation:**
- Add optional `bias_reason` parameter to recommendation API
- Phase 5 automated detection passes specific reasons
- Reasoning engine incorporates sweep/structure context
- Foundation for Phase 8 proactive alerts

### Expected Move Integration (Phase 4.4)

**Strike Validation:**
- **Inside EM:** Higher probability of success → credit spreads suitable
- **Outside EM:** Lower probability, expecting big move → debit spreads suitable
- **At EM boundary:** Neutral zone → iron condors, calendars

**ICT Application:**
- Validate strikes against both EM and structure levels
- Example: Short strike outside EM + above BSL = high-quality credit spread
- Reasoning: "Short strike at $545 is outside 1 SD EM ($540) and above BSL ($542)"

### Stop Placement Rules (Phase 7.4)

**ICT Stop Logic:**
- **Grab wick:** Wick left after sweep shows rejection point
- **Bullish setup:** Stop below manipulation low (SSL sweep low)
- **Bearish setup:** Stop above manipulation high (BSL sweep high)
- **FVG retest:** Stop below/above FVG if tagged on retrace

**Implementation:**
- Calculate stop distance from grab wick, not fixed % or ATR
- Options: Use defined-risk spreads naturally limit risk
- Position sizing accounts for structure-based stop distance

### Target Management (Phase 7.4)

**ICT Target Hierarchy:**
1. **Internal liquidity (FVG):** Take partials when FVG reached
2. **VWAP/Midpoint:** Secondary partial exit zone
3. **External liquidity (opposite swing):** Full exit target

**Implementation:**
- Track progress toward opposite BSL/SSL
- Alert when FVG reached: "Take 25-50% off"
- Alert when swing point reached: "Full exit recommended"
- Structure-based trailing stops using new swing formation

### Priority Implementation Order

**🟢 Immediate (This Week - 3-5 hours total):**
1. Phase 3.4: DTE-based strategy weighting
2. Phase 3.5: Add `bias_reason` parameter

**🟡 Near-term (Phase 4 - 2-3 weeks):**
3. Phase 4.4: Expected move calculation + strike validation

**🟢 Core ICT (Phase 5 - 3-4 weeks):**
4. Swing high/low detection
5. BSL/SSL identification
6. FVG detection
7. Sweep detection
8. Displacement vs manipulation classification
9. MSS detection
10. Three entry model implementations (iFVG, CISD, MSS)
11. HTF/LTF alignment validation
12. Liquidity-first recommendation flow

**🔵 Advanced (Phases 6-8 - 2-3 weeks):**
13. Structure-only mode (Phase 6.4)
14. ICT stop & target management (Phase 7.4)
15. Discord ICT commands (Phase 8.4)
16. Proactive webhook alerts (Phase 8.5)

### Success Metrics

**Phase 3.4/3.5 Success:**
- [ ] DTE logic correctly weights long options for 0-7 DTE
- [ ] Spreads prioritized for 14-45 DTE
- [ ] Reasoning engine explains DTE selection
- [ ] `bias_reason` parameter accepted and stored

**Phase 5 Success:**
- [ ] Swing highs/lows correctly identified on charts
- [ ] BSL/SSL levels match manual analysis
- [ ] FVGs detected and tracked
- [ ] Sweeps identified with reversal confirmation
- [ ] At least one entry model (iFVG, CISD, or MSS) operational
- [ ] Setup alerts trigger correctly via Discord

**Integration Success:**
- [ ] `/plan` recommendations include structure context
- [ ] Discord bot shows recent sweeps when detected
- [ ] Proactive alerts fire when ICT setups trigger
- [ ] Stop/target suggestions align with ICT methodology

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

> **Lightweight periodic refresh idea:** If the Render worker can’t keep the full scheduler on, consider a small external runner (cron job, GitHub Action, or Render cron task) that calls `/api/v1/market/refresh/price/{symbol}`, `/refresh/options/{symbol}`, and `/refresh/iv/{symbol}` for the symbols that matter. That keeps data reasonably fresh without the heavy APScheduler load.
