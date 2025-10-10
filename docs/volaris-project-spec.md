# **Volaris – Trading Intelligence & Alert Platform**

## **Overview**
Volaris is a modular **trading intelligence and decision-support system** built to plan, monitor, and analyze short-dated (2-7 DTE) options trades.  
It combines multi-provider market data (Schwab, Tiingo, Alpaca, Databento, Finnhub) with rule-based and ML-driven analytics to generate trade setups, volatility insights, and Discord-delivered alerts.

---

## **Current Focus (Updated Priorities)**

| Priority | Component | Purpose |
|-----------|------------|----------|
| 🟢 1 | **Trade Planner & Options Strategy Engine** | Build 2–7 DTE (and 14–45 DTE) trade plans: choose **credit/debit spreads** or long options; auto-compute **breakevens, max P/L, risk-reward, and position size** vs account risk. Export one-click order templates. |
| 🟡 2 | **Volatility & Expected-Move Module** | Track **IV/IVR, term structure, and expected move** for SPY/QQQ + watchlist. Flag **IV crush risk** and recommend **debit vs credit** structures (e.g., high IV → credit spreads; low IV → debits). |
| 🟡 3 | **Market Structure & Liquidity Alerts** | Identify **swing highs/lows, BSL/SSL sweeps, FVG tags, VWAP & 200-EMA tests.** Alert when price taps key levels aligning with playbook logic (e.g., “SSL swept + bullish displacement → bull call spread 2–5 wide”). |
| 🟡 4 | **Macro & Event Guardrails** | Use **economic calendar** (CPI, FOMC, Jobs) + earnings + sector news to tag tickers with **event risk inside DTE window**; block risky credit spreads or suggest defensive structures. |
| 🟠 5 | **Risk & PDT Manager** | Track **open trades, DTE, theta exposure, and PDT count**. Warn before actions causing a 4th day trade. Highlight **let-expire vs close** choices for 0–1 DTE setups. |
| ⚪ 6 | **Performance & Post-Trade Analytics** | Auto-capture journal entries (setup screenshot, stats, thesis). Compute **win rate, avg RR, expectancy, IV regime outcomes** to refine future strategies. |

---

## **Core Use Cases**

### **1. Strategy Selection (2–7 DTE first)**
Recommend **bull/bear debit spreads, bull put/bear call credit spreads, or long calls/puts** based on trend + IV regime + expected move.  
Explain reasoning (e.g., “High IV, neutral bias → bear call spread favored; target premium ≥ 25% of width, RR ≤ 4:1”).

### **2. Strike & Width Builder**
Given ticker, bias, and target move, propose optimal strikes/widths (2–5 wide SPY/QQQ; 5–10 wide for high-priced names) with **breakeven, max P/L, probability proxy, and broker-ready order syntax.**

### **3. Liquidity & Structure Triggers**
Alert on **BSL/SSL sweeps, FVG touch + displacement, range breaks, VWAP reclaims/rejects**, mapped to playbook cues  
(e.g., “SSL taken + bullish displacement → consider bull call debit spread inside EM”).

### **4. Volatility & Expected Move Dashboard**
Display **IV, IVR, EM(1–7 D), skew per ticker.**  
Warn when planned strikes fall **inside EM** (risky for longs) or **far outside** (risky for credits).

### **5. Risk Controls & PDT Safety**
Compute position size by fixed $ risk or % of account (5–10 %), enforce max concurrent positions, track **PDT counter**, and issue alerts before day-trade violations.

### **6. Event Filters**
Blocklist **single-name credit spreads** within earnings windows unless override; apply **macro quiet mode** around FOMC/CPI with suggested neutral structures (iron condor vs directional debits).

### **7. Execution Helper (Discord Slash Commands)**
```
/plan SPY bull 5DTE     → returns 2–3 spread candidates with stats  
/em QQQ 7D              → IV, IVR, expected move, suggested structure  
/size 3000 8%           → contract count & dollar risk  
/risk                   → open trades, RR, theta, PDT meter  
/journal add …          → log trade thesis, screenshots, outcome
```

### **8. After-Action Analytics**
Auto-grade closed trades by **setup quality, RR, adherence to plan, IV regime**; surface performance metrics (e.g.,  
“Bear call spreads after BSL sweep → 71 % win, avg +0.32 R”).

---

## **Data & API Architecture**

### **Primary Decision Logic**
**If Schwab API Access Granted (✅ Current):**
- **Minute & 5-minute real-time OHLC:** Schwab API (rolling 3 mo/6 mo limits)  
- **Backfills beyond rolling window:** Databento (preferred) or Alpaca (delayed historical)  
- **Daily/EOD:** Tiingo  
- **Fundamentals & News:** Finnhub  
- **Polygon:** off until options chains needed  

**If Schwab Access Unavailable:**  
- Tiingo (daily), Alpaca (minute delayed), Databento (one-off historical), Finnhub (fundamentals/news).

---

## **Tech Stack**

| Layer | Technologies |
|-------|---------------|
| **Languages** | Python (backend logic, analysis), SQL |
| **Backend Frameworks** | FastAPI, SQLAlchemy (async), APScheduler |
| **Databases** | PostgreSQL (Neon/Supabase), Redis (Upstash) |
| **Data Providers** | Schwab (primary), Tiingo, Alpaca, Databento, Finnhub |
| **Analytics & Modeling** | Pandas, NumPy, (optional FinBERT for sentiment later) |
| **Alerting & UX** | Discord Webhooks + Slash Commands |
| **Infra & DevOps** | Docker, Render/Fly.io, GitHub Actions, Sentry |

---

## **Third-Party Services**

| Function | Service |
|-----------|----------|
| Hosting | Render / Fly.io |
| Database | Neon or Supabase (Postgres) |
| Cache | Upstash Redis |
| CI/CD | GitHub Actions |
| Monitoring | Sentry |
| API Testing | Postman |
| Containerization | Docker |

---

## **Recommended Project Structure**

```
Volaris/
├── app/
│   ├── main.py                 # FastAPI entrypoint
│   ├── config.py               # Environment & API keys
│   ├── db/                     # SQLAlchemy models, migrations
│   ├── services/               # API clients (schwab, tiingo, alpaca, finnhub)
│   ├── core/                   # trade planning, volatility calc, risk mgmt
│   ├── alerts/                 # Discord integration & slash commands
│   ├── workers/                # APScheduler jobs
│   └── utils/                  # rate-limit, retries, error handling
├── tests/
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## **Next Implementation Steps**
1. ✅ Integrate Schwab API client with OAuth & token refresh.  
2. 🟢 Implement price/IV fetchers (Schwab + Tiingo + Alpaca).  
3. 🟡 Add core modules: Trade Planner, Volatility Dashboard, Liquidity Alerts.  
4. 🟡 Set up Discord slash commands (`/plan`, `/em`, `/size`, `/risk`, `/journal`).  
5. 🟠 Integrate risk and PDT manager tracking.  
6. ⚪ Add post-trade analytics and journaling later.  
7. ⚙️ Deploy via Render or Fly.io; monitor via Sentry.  
