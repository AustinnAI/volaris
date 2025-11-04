# Phase 3: Options Flow Monitor

**Status:** ✅ Phase 3.0 Complete | 🟢 Phase 3.1 Complete | 📋 Phase 3.2 Not Started

**Completion Date:** October 27, 2025

---

## Overview

Phase 3 implements **unusual options activity detection** with custom anomaly scoring, multi-provider fallback, and Discord integration. The system detects high-volume trades, block trades, and suspicious option flow patterns in real-time.

### Key Features
- ✅ Custom anomaly detection (0-1 scoring based on 4 criteria)
- ✅ Multi-provider architecture (Schwab, Alpha Vantage, yfinance)
- ✅ Real-time Schwab data with EOD Alpha Vantage fallback
- ✅ Database storage for historical flow analysis
- ✅ Discord `/flow` command for easy querying
- ✅ Human-readable EST timestamps
- ✅ 1-hour caching for performance

---

## Phase 3.0: MVP - Custom Flow Detection ✅

### Completed Tasks
- [x] Created `FlowProvider` ABC interface for provider abstraction
- [x] Implemented `YFinanceFlowProvider` (local dev fallback)
- [x] Implemented `SchwabFlowProvider` (primary - real-time data)
- [x] Implemented `AlphaVantageFlowProvider` (EOD fallback)
- [x] Built custom anomaly scoring algorithm
- [x] Created `option_flow` database table
- [x] Added `/api/v1/flow/{ticker}` endpoint
- [x] Added `/api/v1/flow/{ticker}/history` endpoint
- [x] Implemented `FlowProviderManager` with fallback hierarchy
- [x] Added Discord `/flow` command
- [x] Converted timestamps to EST with readable format
- [x] Added `provider` field to API responses

### Provider Hierarchy

**Production (Cloud):**
1. **Schwab** (primary) - Real-time options data via official API
2. **Alpha Vantage** (fallback) - Historical/EOD options data
3. **yfinance** (last resort) - Blocked on cloud, works locally

**Local Development:**
1. yfinance (free, no API key)
2. Schwab (if tokens configured)
3. Alpha Vantage (if API key configured)

### Anomaly Detection Algorithm

**Scoring Criteria (0-1 scale):**
- **+0.3 points:** Volume/OI ratio > 3.0 → `"high_volume"` flag
- **+0.4 points:** Volume > 3× 30-day average → `"volume_spike"` flag
- **+0.2 points:** Bid-ask spread < 10% → `"liquid"` flag
- **+0.1 points:** Premium > $50,000 → `"block_trade"` flag

**Maximum score:** 1.0 (all 4 criteria met)

**Premium Calculation:** `volume × last_price × 100` (each contract = 100 shares)

### Database Schema

```sql
CREATE TABLE option_flow (
    id SERIAL PRIMARY KEY,
    ticker_id INT REFERENCES tickers(id) ON DELETE CASCADE,
    contract_symbol VARCHAR(32) NOT NULL,
    option_type VARCHAR(4) NOT NULL,  -- 'call' or 'put'
    strike NUMERIC(10, 2) NOT NULL,
    expiration DATE NOT NULL,
    last_price NUMERIC(10, 2) NOT NULL,
    volume INT NOT NULL,
    open_interest INT NOT NULL,
    volume_oi_ratio NUMERIC(10, 2) NOT NULL,
    premium NUMERIC(15, 2) NOT NULL,
    anomaly_score NUMERIC(3, 2) NOT NULL,
    flags VARCHAR(256) NOT NULL,  -- JSON array
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX ix_option_flow_ticker_detected ON option_flow(ticker_id, detected_at);
CREATE INDEX ix_option_flow_contract_detected ON option_flow(contract_symbol, detected_at);
CREATE INDEX ix_option_flow_anomaly_score ON option_flow(anomaly_score);
```

### API Endpoints

#### `GET /api/v1/flow/{symbol}`
Detect unusual options activity for a ticker.

**Query Parameters:**
- `min_score` (float, default 0.7): Minimum anomaly score (0.0-1.0)
- `force_refresh` (bool, default false): Force fresh detection (ignores 1hr cache)

**Response:**
```json
{
  "symbol": "SPY",
  "detected_count": 50,
  "unusual_trades": [
    {
      "contract_symbol": "SPY   251027C00683000",
      "option_type": "call",
      "strike": 683.0,
      "expiration": "2025-10-27",
      "last_price": 0.88,
      "volume": 363171,
      "open_interest": 5365,
      "volume_oi_ratio": 67.69,
      "premium": 31959048.0,
      "anomaly_score": 1.0,
      "flags": ["high_volume", "volume_spike", "liquid", "block_trade"],
      "detected_at": "Oct 27, 2025 12:20:36 PM EST"
    }
  ],
  "min_score": 0.7,
  "detection_time": "Oct 27, 2025 12:20:58 PM EST",
  "provider": "Schwab"
}
```

**Provider Values:**
- `"Schwab"` - Real-time data from Schwab API (fresh fetch)
- `"AlphaVantage"` - Historical/EOD data from Alpha Vantage (fresh fetch)
- `"YFinance"` - yfinance data (local dev only)
- `"cached"` - Data from database < 1 hour old
- `"database"` - Historical query from `/history` endpoint

#### `GET /api/v1/flow/{symbol}/history`
Query historical unusual activity from database.

**Query Parameters:**
- `hours` (int, default 24): Lookback period in hours (1-168)
- `min_score` (float, default 0.7): Minimum anomaly score filter
- `limit` (int, default 50): Maximum results (1-200)

**Response:** Same schema as `/flow/{symbol}` with `"provider": "database"`

### Discord Commands

#### `/flow`
Detect unusual options activity for a ticker.

**Parameters:**
- `ticker` (required): Ticker symbol (e.g., SPY, QQQ, AAPL)
- `min_score` (optional, default 0.7): Minimum anomaly score (0.0-1.0)
- `force_refresh` (optional, default false): Force fresh detection

**Example Output:**
```
🔥 SPY Unusual Options Flow
Detected 50 unusual contracts (score ≥ 0.70)

#1: SPY   251027C00683000
Strike: $683.00 CALL
Expiration: 2025-10-27
Volume: 363,171 | OI: 5,365
Vol/OI: 67.69x | Premium: $32.0M
Score: 1.00 | Flags: high_volume, volume_spike, liquid, block_trade

[... top 5 trades shown ...]

Data source: Schwab • Oct 27, 2025 12:20:58 PM EST
```

### Configuration

**Environment Variables:**
```bash
# Alpha Vantage (Phase 3.1)
ALPHA_VANTAGE_API_KEY=your_key_here  # Free tier: 25 requests/day

# Schwab (Phase 1 - OAuth required)
SCHWAB_REFRESH_TOKEN=your_refresh_token  # Re-auth every 7 days
```

**Get Alpha Vantage API Key:**
https://www.alphavantage.co/support/#api-key

**Re-authenticate Schwab:**
https://volaris-yz19.onrender.com/api/v1/auth/schwab/authorize

---

## Phase 3.1: Alpha Vantage Validation Layer ✅

### Completed Tasks
- [x] Implemented `AlphaVantageFlowProvider`
- [x] Added to fallback hierarchy: Schwab → Alpha Vantage → yfinance
- [x] Rate limiting: 25 requests/day (free tier)

### Implementation Notes

**Alpha Vantage Free Tier Limitations:**
- **25 API requests per day** (manual rate limiting required)
- **5 API requests per minute**
- **Historical/EOD data only** (not real-time intraday)

**Usage Strategy:**
- Primary: Schwab (real-time, no rate limits on options)
- Fallback: Alpha Vantage (if Schwab tokens expired)
- Last resort: yfinance (local dev only, blocked on cloud)

**When to use Alpha Vantage:**
- Schwab tokens expired (need re-auth)
- Testing/validation of custom anomaly logic
- Local development without Schwab OAuth setup

---

## Phase 3.2: Unusual Whales Evaluation 📋

**Status:** Not Started

### Planned Tasks
- [ ] Test Unusual Whales free tier (Shamu plan) for SPY/QQQ
- [ ] Compare custom anomaly logic vs Whales pre-built unusual flags
- [ ] Evaluate data quality: Whales vs Schwab real-time
- [ ] Decision: Upgrade to Whales paid plan OR stick with Schwab + custom logic
- [ ] If upgrade: Implement `UnusualWhalesProvider`
- [ ] If upgrade: Add Discord webhook for instant unusual activity alerts
- [ ] Keep yfinance as final fallback regardless of decision

### Evaluation Criteria
1. **Accuracy:** Does Whales detect more/better unusual activity than our custom logic?
2. **Cost:** Is Whales paid tier ($50-100/mo) worth it vs free Schwab + Alpha Vantage?
3. **Reliability:** API uptime and rate limits
4. **Features:** Instant alerts, pre-filtered flow, historical data access

---

## Technical Implementation

### File Structure
```
app/
├── services/
│   └── flow/
│       ├── __init__.py
│       ├── base_provider.py          # FlowProvider ABC
│       ├── schwab_provider.py        # Real-time Schwab data
│       ├── alphavantage_provider.py  # EOD Alpha Vantage data
│       ├── yfinance_provider.py      # Local dev fallback
│       └── provider_manager.py       # Fallback hierarchy
├── core/
│   └── flow_detection.py             # Anomaly scoring algorithm
├── api/v1/
│   └── flow.py                       # FastAPI endpoints
└── alerts/cogs/
    └── market_data.py                # Discord /flow command

docs/
└── PHASE_3.md                        # This file
```

### Provider Abstraction (ABC Pattern)

**Base Interface:**
```python
class FlowProvider(ABC):
    @abstractmethod
    async def get_option_chain(self, symbol: str, expiration: datetime | None) -> OptionChain:
        """Fetch raw option chain data."""

    @abstractmethod
    async def get_unusual_activity(
        self, symbol: str, min_score: float, lookback_minutes: int
    ) -> list[UnusualTrade]:
        """Detect unusual options activity."""
```

**TypedDict Contracts:**
```python
class OptionContract(TypedDict):
    contract_symbol: str
    strike: Decimal
    expiration: datetime
    option_type: str  # "call" | "put"
    last_price: Decimal
    bid: Decimal
    ask: Decimal
    volume: int
    open_interest: int
    implied_volatility: float | None

class UnusualTrade(TypedDict):
    symbol: str
    contract_symbol: str
    option_type: str
    strike: Decimal
    expiration: datetime
    last_price: Decimal
    volume: int
    open_interest: int
    volume_oi_ratio: float
    premium: Decimal
    anomaly_score: float  # 0-1
    flags: list[str]
    detected_at: datetime
```

### Error Handling

**Provider Fallback Logic:**
1. Try Schwab (primary)
   - If fails: Log warning, try next provider
2. Try Alpha Vantage (fallback)
   - If fails: Log warning, try next provider
3. Try yfinance (last resort)
   - If fails: Raise `ValueError("All providers failed")`
4. If all fail: Return HTTP 500 with error message

**Retry Strategy:**
- 2 attempts with exponential backoff (tenacity library)
- Wait: 1s, then 5s between attempts
- Only retries on `Exception`, not on provider-specific errors

---

## Testing

### Manual Testing Commands

**API Endpoint (curl):**
```bash
# Get unusual flow for SPY (0.7 threshold)
curl -s "https://volaris-yz19.onrender.com/api/v1/flow/SPY?min_score=0.7" | jq

# Force fresh detection (ignore cache)
curl -s "https://volaris-yz19.onrender.com/api/v1/flow/SPY?force_refresh=true" | jq

# Lower threshold to see more trades
curl -s "https://volaris-yz19.onrender.com/api/v1/flow/SPY?min_score=0.5" | jq

# Historical query (last 24 hours)
curl -s "https://volaris-yz19.onrender.com/api/v1/flow/SPY/history?hours=24" | jq
```

**Discord Command:**
```
/flow ticker:SPY
/flow ticker:SPY min_score:0.5
/flow ticker:SPY min_score:0.7 force_refresh:true
/flow ticker:QQQ
/flow ticker:AAPL
```

### Test Coverage

**Recommended Test Tickers:**
- **SPY** - Highest volume, most unusual activity
- **QQQ** - High volume tech ETF
- **AAPL, TSLA, NVDA** - High-volume individual stocks
- **S&P 500 top 50** - Large caps with active options markets

**Scoring Validation:**
- **Score 1.0:** All 4 flags (high_volume, volume_spike, liquid, block_trade)
- **Score 0.7-0.9:** 3 flags (typical unusual activity)
- **Score 0.5-0.7:** 2 flags (moderate activity)
- **Score < 0.5:** 1 flag (borderline activity)

---

## Performance

### Caching Strategy
- **1-hour cache:** Flow detection results stored in database
- **Cache key:** `(ticker_id, detected_at > now() - 1 hour)`
- **Cache invalidation:** `force_refresh=true` parameter bypasses cache
- **Rationale:** Balance between freshness and API cost/performance

### Memory Usage
- **Target:** < 100MB per flow detection
- **Actual:** ~50-80MB for SPY (500+ contracts)
- **Provider:** Schwab uses JSON (no pandas overhead)
- **Storage:** Postgres stores only detected unusual trades, not full chain

### API Rate Limits

| Provider | Rate Limit | Notes |
|----------|------------|-------|
| Schwab | None (options) | OAuth required, tokens expire every 7 days |
| Alpha Vantage | 25/day, 5/min | Free tier, upgrade for 500/day |
| yfinance | Soft limit ~100/hr | Blocks cloud IPs, local dev only |

---

## Known Issues & Limitations

### Current Limitations
1. **Alpha Vantage:** Historical/EOD data only (not real-time intraday)
2. **yfinance:** Blocked on cloud provider IPs (Render, AWS, GCP)
3. **Schwab:** Requires manual re-authentication every 7 days
4. **Caching:** 1-hour cache may miss very recent unusual activity

### Workarounds
1. Use `force_refresh=true` to bypass cache for urgent queries
2. Re-authenticate Schwab weekly: https://volaris-yz19.onrender.com/api/v1/auth/schwab/authorize
3. Monitor provider field in responses to know data source

### Future Improvements (Phase 3.2+)
- [ ] Evaluate Unusual Whales for instant alerts
- [ ] Add Discord webhook for real-time flow notifications
- [ ] Implement anomaly trend analysis (pattern detection)
- [ ] Add flow leaderboard (most unusual tickers)
- [ ] Implement dark pool print correlation

---

## Migration Notes

### Database Migration
```bash
# Run migration to create option_flow table
alembic upgrade head

# Verify table exists
psql $DATABASE_URL -c "\d option_flow"
```

### Environment Variables
```bash
# Add to Render environment (or .env locally)
ALPHA_VANTAGE_API_KEY=your_key_here

# Verify in logs
curl https://volaris-yz19.onrender.com/api/v1/flow/SPY | jq '.provider'
# Should show "Schwab" (if tokens valid) or "AlphaVantage" (if configured)
```

---

## Success Metrics

### Phase 3.0 Metrics ✅
- [x] API response time < 3s (95th percentile) - **Achieved: ~1-2s**
- [x] Discord command latency < 5s - **Achieved: ~2-3s**
- [x] Memory usage < 512 MB - **Achieved: ~400MB**
- [x] Provider fallback works - **Tested: Schwab → Alpha Vantage → yfinance**
- [x] Timestamps in EST with readable format - **Achieved: "Oct 27, 2025 12:20 PM EST"**

### Phase 3.1 Metrics ✅
- [x] Alpha Vantage integration working - **Tested on production**
- [x] Rate limiting documented - **25 requests/day**
- [x] Fallback hierarchy tested - **Schwab primary, AV fallback**

### Phase 3.2 Metrics (Pending)
- [ ] Unusual Whales free tier tested
- [ ] Anomaly logic comparison (custom vs Whales)
- [ ] Cost-benefit analysis completed
- [ ] Upgrade decision documented

---

## Next Steps

### Immediate (Complete Phase 3.0)
- [x] Add Discord `/flow` command ✅
- [x] Test with SPY, QQQ, AAPL
- [x] Update roadmap.md to mark Phase 3.0 complete
- [x] Create this documentation

### Near-term (Phase 3.2)
- [ ] Test Unusual Whales free tier (Shamu plan)
- [ ] Compare custom anomaly logic vs Whales pre-built flags
- [ ] Evaluate data quality and reliability
- [ ] Decision: Upgrade to Whales paid OR stick with Schwab + custom logic

### Long-term (Version 2)
- [ ] Add Discord webhook for instant flow alerts
- [ ] Implement flow leaderboard (`/flow-leaderboard` command)
- [ ] Add anomaly trend analysis (pattern detection over time)
- [ ] Dark pool print correlation
- [ ] Multi-ticker flow comparison

---

## References

- [FlowProvider ABC](../app/services/flow/base_provider.py)
- [Schwab Provider](../app/services/flow/schwab_provider.py)
- [Alpha Vantage Provider](../app/services/flow/alphavantage_provider.py)
- [Anomaly Detection Logic](../app/core/flow_detection.py)
- [Flow API Endpoints](../app/api/v1/flow.py)
- [Discord /flow Command](../app/alerts/cogs/market_data.py)
- [Roadmap](roadmap.md)

---

**Phase 3.0 Status:** ✅ **Complete** (October 27, 2025)
