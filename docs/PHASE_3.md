# Phase 3: Trade Planning & Strategy Engine

**Status:** 🟢 In Progress (3.1 ✅ Complete, 3.2 ✅ Complete)
**Version:** 2.0.0
**Last Updated:** 2025-10-11

---

## Overview

Phase 3 delivers a comprehensive trade planning system for options strategies, split into two major components:

- **Phase 3.1**: Strategy calculator for computing risk/reward metrics
- **Phase 3.2**: Strike selection engine for intelligent recommendations

Together, these modules enable traders to:
1. Calculate precise P/L, breakevens, and risk metrics for any spread or long option
2. Get intelligent strike recommendations based on IV regime and market data
3. Size positions based on account risk tolerance
4. Make data-driven trading decisions using stored option chain data

---

# Phase 3.1: Strategy Calculator ✅

**Status:** ✅ Complete
**Completed:** 2025-10-11

## Features

- **Vertical Spread Calculator**: Bull/bear call/put spreads with automatic debit/credit detection
- **Long Option Calculator**: Long calls and long puts with accurate max profit formulas
- **Risk Metrics**: Max profit, max loss, breakeven prices, risk/reward ratio
- **Position Sizing**: Risk-based contract calculation using account size and risk percentage
- **Probability Proxy**: Delta-based win probability estimation
- **FastAPI Endpoints**: RESTful API for integration

---

## Architecture

```
app/
├── core/
│   └── trade_planner.py              # Core calculation engine
├── api/v1/
│   ├── schemas/
│   │   └── trade_planner.py          # Pydantic request/response models
│   └── trade_planner.py              # FastAPI router
└── alerts/
    └── discord_handlers.py           # Discord bridge (Phase 8)

tests/
└── test_trade_planner.py             # 15 unit tests
```

---

## API Endpoints

### Base URL
```
http://localhost:8000/api/v1/trade-planner
```

### 1. Calculate Vertical Spread

**POST** `/calculate/vertical-spread`

**Request:**
```json
{
  "underlying_symbol": "SPY",
  "underlying_price": 450.00,
  "long_strike": 445.00,
  "short_strike": 450.00,
  "long_premium": 7.50,
  "short_premium": 3.00,
  "option_type": "call",
  "bias": "bullish",
  "contracts": 1,
  "dte": 30,
  "long_delta": 0.60,
  "short_delta": 0.40,
  "account_size": 25000.00,
  "risk_percentage": 2.0
}
```

**Response:**
```json
{
  "strategy_type": "vertical_debit",
  "bias": "bullish",
  "underlying_symbol": "SPY",
  "underlying_price": 450.00,
  "legs": [
    {"strike": 445.00, "premium": 7.50, "option_type": "call", "position": "long", "contracts": 1},
    {"strike": 450.00, "premium": 3.00, "option_type": "call", "position": "short", "contracts": 1}
  ],
  "max_profit": 50.00,
  "max_loss": 450.00,
  "breakeven_prices": [449.50],
  "risk_reward_ratio": 0.1111,
  "win_probability": 20.00,
  "recommended_contracts": 1,
  "position_size_dollars": 450.00,
  "net_premium": 450.00,
  "net_credit": null,
  "dte": 30,
  "total_delta": 0.20
}
```

---

### 2. Calculate Long Option

**POST** `/calculate/long-option`

**Request:**
```json
{
  "underlying_symbol": "AAPL",
  "underlying_price": 175.00,
  "strike": 180.00,
  "premium": 3.50,
  "option_type": "call",
  "bias": "bullish",
  "contracts": 1,
  "dte": 45,
  "delta": 0.35,
  "account_size": 25000.00,
  "risk_percentage": 2.0
}
```

**Response:**
```json
{
  "strategy_type": "long_call",
  "bias": "bullish",
  "underlying_symbol": "AAPL",
  "underlying_price": 175.00,
  "legs": [
    {"strike": 180.00, "premium": 3.50, "option_type": "call", "position": "long", "contracts": 1}
  ],
  "max_profit": null,
  "max_loss": 350.00,
  "breakeven_prices": [183.50],
  "risk_reward_ratio": null,
  "win_probability": 35.00,
  "recommended_contracts": 1,
  "position_size_dollars": 350.00,
  "net_premium": 350.00,
  "dte": 45,
  "total_delta": 0.35
}
```

---

### 3. Calculate Position Size

**POST** `/position-size`

**Request:**
```json
{
  "max_loss_per_contract": 450.00,
  "account_size": 25000.00,
  "risk_percentage": 2.0
}
```

**Response:**
```json
{
  "contracts": 1,
  "max_loss_per_contract": 450.00,
  "account_size": 25000.00,
  "risk_percentage": 2.0,
  "total_risk_dollars": 450.00,
  "risk_as_percent_of_account": 1.80
}
```

---

## Calculation Formulas

### Vertical Spread (Debit)

```
Net Premium = (Long Premium - Short Premium) × Contracts × 100
Max Loss = Net Premium
Max Profit = Spread Width - Net Premium
Risk/Reward = Max Profit / Max Loss

Breakeven (Call) = Long Strike + (Net Premium / (Contracts × 100))
Breakeven (Put) = Long Strike - (Net Premium / (Contracts × 100))
```

### Vertical Spread (Credit)

```
Net Premium = (Long Premium - Short Premium) × Contracts × 100  (negative)
Max Profit = |Net Premium|
Max Loss = Spread Width - |Net Premium|
position_size_dollars = Max Loss  (risk, not credit)

Breakeven (Call) = Short Strike + (|Net Premium| / (Contracts × 100))
Breakeven (Put) = Short Strike - (|Net Premium| / (Contracts × 100))
```

### Long Call

```
Max Loss = Premium × Contracts × 100
Max Profit = None (unlimited)
Risk/Reward = None
Breakeven = Strike + Premium
```

### Long Put

```
Max Loss = Premium × Contracts × 100
Max Profit = (Strike - Premium) × 100 × Contracts
Risk/Reward = Max Profit / Max Loss
Breakeven = Strike - Premium
```

### Position Sizing

```
Max Risk Dollars = Account Size × (Risk % / 100)
Recommended Contracts = floor(Max Risk Dollars / Max Loss per Contract)
```

---

## Test Coverage

**15/15 tests passing:**
- ✅ Bull call spread (debit)
- ✅ Bear put spread (debit)
- ✅ Bull put spread (credit)
- ✅ Bear call spread (credit)
- ✅ Long call (unlimited profit)
- ✅ Long put (correct max profit formula)
- ✅ Position sizing with account size
- ✅ Delta-based probability calculations
- ✅ Multiple contracts
- ✅ Edge cases

---

## Files Created

- `app/core/trade_planner.py` - Core calculation logic
- `app/api/v1/schemas/trade_planner.py` - Pydantic schemas
- `app/api/v1/trade_planner.py` - FastAPI endpoints
- `app/alerts/discord_handlers.py` - Discord bridge placeholder
- `tests/test_trade_planner.py` - Unit tests

---

# Phase 3.2: Strike Selection Engine ✅

**Status:** ✅ Complete (Enhanced v2.0)
**Completed:** 2025-10-11
**Enhanced:** 2025-10-11 (Credit spread fix + quality improvements)

## Features

### Core Functionality
- **Intelligent Strike Recommendations**: ITM, ATM, OTM candidates for spreads and long options
- **Dynamic Spread Width**: 2-5 wide for low-priced, 5-10 for high-priced tickers (configurable)
- **IV Regime Detection**: Auto-selects credit vs debit strategies based on IV rank
- **Database Integration**: Pulls from stored `OptionChainSnapshot` and `IVMetric` tables
- **Credit Validation**: Minimum 25% credit filter (configurable)
- **Data Quality Warnings**: Flags missing or stale data

### Version 2.0 Enhancements (NEW)
- **✅ Fixed Credit Spread Construction**: Credit spreads now correctly built as short-near/long-far
- **✅ Explicit Strategy Determination**: Auto mode explicitly chooses credit/debit based on IV regime
- **✅ Liquidity Filtering**: Configurable min open interest, volume, and mark price filters
- **✅ Composite Quality Scoring**: Candidates ranked by risk/reward, POP, credit quality, and position
- **✅ Enhanced Response Fields**: `is_credit`, `net_credit`, `net_debit`, `width_points`, `width_dollars`, `quality_score`
- **✅ Config-Driven Thresholds**: All limits moved to `app/config.py` for easy tuning
- **✅ Strike Width Validation**: Rejects strikes >20% off target width to avoid bad fills

---

## Architecture

```
app/
├── core/
│   └── strike_selection.py           # Strike selection logic
├── services/
│   └── strike_data_service.py        # Database queries
├── api/v1/
│   ├── schemas/
│   │   └── strike_selection.py       # Pydantic schemas
│   └── strike_selection.py           # FastAPI endpoint

tests/
└── test_strike_selection.py          # 24 unit tests
```

---

## Configuration

All thresholds are configurable in `app/config.py`:

```python
# IV Regime Thresholds
IV_HIGH_THRESHOLD = 50.0  # IV percentile > 50 = high regime
IV_LOW_THRESHOLD = 25.0   # IV percentile < 25 = low regime

# Credit Spread Thresholds
MIN_CREDIT_PCT = 0.25  # Minimum credit as 25% of spread width

# Strike Classification
ATM_THRESHOLD_PCT = 2.0  # ±2% of underlying price = ATM

# Liquidity Filters
MIN_OPEN_INTEREST = 10   # Minimum open interest for contracts
MIN_VOLUME = 5           # Minimum daily volume
MIN_MARK_PRICE = 0.01    # Minimum mark price (avoids $0.00 stale contracts)

# Spread Width Limits (in points)
SPREAD_WIDTH_LOW_PRICE_MAX = 5    # < $100 stocks
SPREAD_WIDTH_MID_PRICE = 5        # $100-300 stocks
SPREAD_WIDTH_HIGH_PRICE_MAX = 10  # > $300 stocks
```

---

## API Endpoint

### POST `/api/v1/strike-selection/recommend`

Recommends optimal strikes based on stored option chain data and IV metrics.

**Behavior Changes in v2.0:**
- Credit spreads now correctly constructed (e.g., bull put: short 445, long 440)
- Auto mode explicitly picks credit (high IV) or debit/long (low IV) strategies
- Liquidity filters applied by default (disable with DB query override)
- Results sorted by quality score (best candidate first)

**Request:**
```json
{
  "underlying_symbol": "SPY",
  "bias": "bullish",
  "strategy_type": "vertical_spread",
  "target_dte": 30,
  "dte_tolerance": 3,
  "min_credit_pct": 25.0,
  "max_spread_width": 5,
  "iv_regime_override": null
}
```

**Strategy Types:**
- `vertical_spread` - Recommend ITM/ATM/OTM vertical spreads
- `long_call` - Recommend long call strikes
- `long_put` - Recommend long put strikes
- `auto` - Auto-select based on IV regime

**Response:**
```json
{
  "underlying_symbol": "SPY",
  "underlying_price": 450.00,
  "strategy_type": "vertical_spread",
  "bias": "bullish",
  "dte": 30,
  "iv_rank": 42.5,
  "iv_regime": "neutral",
  "spread_candidates": [
    {
      "position": "atm",
      "long_strike": 445.00,
      "short_strike": 450.00,
      "long_premium": 8.75,
      "short_premium": 5.25,
      "net_premium": 350.00,
      "is_credit": false,
      "net_credit": null,
      "net_debit": 350.00,
      "width_points": 5.00,
      "width_dollars": 500.00,
      "spread_width": 500.00,  // DEPRECATED: use width_dollars
      "breakeven": 448.50,
      "max_profit": 150.00,
      "max_loss": 350.00,
      "risk_reward_ratio": 0.4286,
      "pop_proxy": 15.00,
      "long_delta": 0.65,
      "short_delta": 0.50,
      "notes": ["ITM spread", "~15% POP"]
    },
    {
      "position": "atm",
      "long_strike": 450.00,
      "short_strike": 455.00,
      "long_premium": 5.25,
      "short_premium": 2.75,
      "net_premium": 250.00,
      "spread_width": 500.00,
      "breakeven": 452.50,
      "max_profit": 250.00,
      "max_loss": 250.00,
      "risk_reward_ratio": 1.00,
      "pop_proxy": 15.00,
      "long_delta": 0.50,
      "short_delta": 0.35,
      "quality_score": 72.50,
      "notes": ["ATM spread", "~15% POP"]
    },
    {
      "position": "otm",
      "long_strike": 455.00,
      "short_strike": 460.00,
      "long_premium": 2.75,
      "short_premium": 1.25,
      "net_premium": 150.00,
      "is_credit": false,
      "net_credit": null,
      "net_debit": 150.00,
      "width_points": 5.00,
      "width_dollars": 500.00,
      "spread_width": 500.00,
      "breakeven": 456.50,
      "max_profit": 350.00,
      "max_loss": 150.00,
      "risk_reward_ratio": 2.33,
      "pop_proxy": 15.00,
      "long_delta": 0.35,
      "short_delta": 0.20,
      "quality_score": 65.00,
      "notes": ["OTM spread", "~15% POP"]
    }
  ],
  "long_option_candidates": null,
  "data_timestamp": "2025-10-11T12:00:00Z",
  "warnings": []
}
```

---

## IV Regime Logic

**IV Rank Thresholds:**
- **High IV** (>50): Favor credit spreads (sell premium)
- **Neutral IV** (25-50): Balanced approach
- **Low IV** (<25): Favor debit spreads / long options (buy premium)

**Auto Strategy Selection (v2.0):**
When `strategy_type="auto"`, the engine **explicitly** determines credit/debit:
- **High IV (>50)** → Credit spreads (sell premium, collect decay)
  - Bullish: Bull put credit spread
  - Bearish: Bear call credit spread
- **Low IV (<25)** → Long options (cheap premium, unlimited upside)
  - Bullish: Long calls
  - Bearish: Long puts
- **Neutral IV (25-50)** → Debit spreads (defined risk/reward)
  - Bullish: Bull call debit spread
  - Bearish: Bear put debit spread

This explicit selection ensures credits actually materialize rather than depending on "magical" price behavior.

---

## Leg Orientation Fix (v2.0)

### Problem (v1.0)
The original implementation always used `long=anchor, short=other` for both debit and credit spreads, causing credits to be built as debits.

### Solution (v2.0)
Leg roles are now explicitly reversed based on strategy type:

**Debit Spreads** (buy premium):
- Bull call: Long 445, Short 450 → Pay $3.50 net debit
- Bear put: Long 450, Short 445 → Pay $3.50 net debit

**Credit Spreads** (sell premium):
- Bull put: **Short 445**, Long 440 → Receive $1.50 net credit
- Bear call: **Short 450**, Long 455 → Receive $1.50 net credit

The key: **credit spreads have the short leg nearer to the money**, generating positive cash flow upfront.

---

## Quality Scoring (v2.0)

Candidates are ranked by a composite score (0-100):

**Scoring Formula:**
- **Risk/Reward (40%)**: Higher R:R = better score
- **POP Proxy (30%)**: Delta-based probability of profit
- **Credit Quality (20%)**: For credits, % of spread width collected
- **Position Preference (10%)**: ATM > OTM > ITM

Candidates are sorted by score, best first. This helps users quickly identify the most attractive setups.

---

## Spread Width Logic

**Price-Based Width:**
- **< $100**: 2-5 wide (e.g., low-priced stocks, ETFs)
- **$100-$300**: 5 wide (e.g., SPY, QQQ)
- **> $300**: 5-10 wide (e.g., TSLA, AMZN)

**Configurable:** Use `max_spread_width` parameter to cap width

---

## Credit Spread Validation

**Minimum Credit Filter:**
- Default: 25% of spread width
- Example: $5 wide spread requires $1.25+ credit (25%)
- Configurable via `min_credit_pct` parameter
- **v2.0:** Candidates below threshold are **rejected**, not just warned

**Strike Width Tolerance:**
- Rejects strikes >20% off target width (e.g., for 5-wide, rejects if actual is <4 or >6)
- Prevents bad fills from illiquid strike chains

---

## Liquidity Filtering (v2.0)

**Applied by default to all recommendations:**

```python
# Contracts must pass ALL filters:
- mark >= $0.01  # Avoid stale $0.00 contracts
- open_interest >= 10  # Minimum tradeable interest
- volume >= 5  # Minimum daily activity
```

**Benefits:**
- Eliminates illiquid strikes that cause wide bid/ask spreads
- Prevents recommendations with stale pricing
- Ensures contracts can actually be traded

**Configuration:**
All thresholds configurable in `app/config.py`.

---

## Data Integration

**Sources:**
1. **Option Chains**: `OptionChainSnapshot` + `OptionContract` tables
2. **IV Metrics**: `iv_metrics` table (30-day IV rank)
3. **Prices**: `price_bars` table (1m/daily fallback)

**Data Quality:**
- Finds nearest snapshot within DTE tolerance (default ±3 days)
- Returns warnings for missing/stale data
- Skips contracts without mark prices
- Provides data timestamp in response

---

## Recommendation Logic

### Vertical Spreads

1. Find ITM, ATM, OTM long strikes
2. For each position, find short strike at target width
3. Calculate net premium, breakeven, P/L, R:R
4. Validate credit percentage (for credit spreads)
5. Compute delta-based POP proxy
6. Return 2-3 candidates with notes

### Long Options

1. Find ITM, ATM, OTM strikes
2. Calculate breakeven and max loss
3. Max profit: `None` for calls, `(strike - premium) × 100` for puts
4. Compute delta-based POP proxy
5. Return 2-3 candidates with notes

---

## Test Coverage

**26/26 tests passing (v2.0):**
- ✅ IV regime classification (high/neutral/low)
- ✅ Spread width logic (low/mid/high priced tickers)
- ✅ Spread metrics calculation (debit/credit)
- ✅ Strike position classification (ITM/ATM/OTM)
- ✅ Finding nearest strikes (calls/puts)
- ✅ Vertical spread recommendations (ITM/ATM/OTM)
- ✅ **Bull put credit spreads (NEW)** - verifies correct leg orientation
- ✅ **Bear call credit spreads (NEW)** - verifies correct leg orientation
- ✅ Long option recommendations (calls/puts)
- ✅ Minimum credit filtering (rejects low-credit candidates)
- ✅ Edge cases (empty data, missing marks)

**Key Test Additions (v2.0):**
```python
def test_bullish_put_spread_credit(self, spy_contracts):
    """Verify bull put credit has short 445, long 440."""
    candidates = recommend_vertical_spreads(
        spy_contracts, Decimal("450"), "put", "bullish", target_width=5,
    )
    atm = next((c for c in candidates if c.position == StrikePosition.ATM), None)
    assert atm.long_strike < atm.short_strike  # Correct orientation
    assert atm.net_premium < 0  # Credit spread
    assert atm.max_profit == abs(atm.net_premium)  # Credit = max profit
```

---

## Usage Examples

### cURL: Bullish Call Spread

```bash
curl -X POST http://localhost:8000/api/v1/strike-selection/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "underlying_symbol": "SPY",
    "bias": "bullish",
    "strategy_type": "vertical_spread",
    "target_dte": 30,
    "dte_tolerance": 3,
    "max_spread_width": 5
  }'
```

### cURL: Auto Strategy (IV-Based)

```bash
curl -X POST http://localhost:8000/api/v1/strike-selection/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "underlying_symbol": "SPY",
    "bias": "bullish",
    "strategy_type": "auto",
    "target_dte": 30
  }'
```

### cURL: Long Call Recommendations

```bash
curl -X POST http://localhost:8000/api/v1/strike-selection/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "underlying_symbol": "AAPL",
    "bias": "bullish",
    "strategy_type": "long_call",
    "target_dte": 45
  }'
```

### Python: Using Recommendations

```python
from app.core.strike_selection import recommend_vertical_spreads, OptionContractData
from decimal import Decimal

# Sample contract data (from database)
contracts = [
    OptionContractData(
        strike=Decimal("445"), option_type="call",
        mark=Decimal("8.75"), delta=Decimal("0.65"), ...
    ),
    # ... more contracts
]

# Get recommendations
candidates = recommend_vertical_spreads(
    contracts=contracts,
    underlying_price=Decimal("450"),
    option_type="call",
    bias="bullish",
    target_width=5,
    min_credit_pct=Decimal("25.0"),
)

# Use first (best) candidate
best = candidates[0]
print(f"Spread: {best.long_strike}/{best.short_strike}")
print(f"Max Loss: ${best.max_loss}")
print(f"Max Profit: ${best.max_profit}")
print(f"POP: {best.pop_proxy}%")
```

---

## Files Created

- `app/core/strike_selection.py` - Core recommendation logic
- `app/services/strike_data_service.py` - Database queries
- `app/api/v1/schemas/strike_selection.py` - Pydantic schemas
- `app/api/v1/strike_selection.py` - FastAPI endpoint
- `tests/test_strike_selection.py` - Unit tests

---

## Configuration

### Default Parameters

```python
# Spread width
min_width: int = 2
max_width: int = 10

# Credit validation
min_credit_pct: Decimal = 25.0  # 25% of spread width

# DTE tolerance
dte_tolerance: int = 3  # ±3 days

# ATM threshold
atm_threshold: Decimal = 2.0  # 2% from spot price

# IV regime thresholds
HIGH_IV = 50    # IV Rank > 50
LOW_IV = 25     # IV Rank < 25
```

---

## Error Handling

**404 Errors:**
- Ticker not found in database
- No price data available
- No option chain for requested DTE

**Warnings (non-fatal):**
- No IV metrics available
- Option chain older than DTE tolerance
- Contract missing mark prices
- Credit below minimum threshold

---

## Next Steps (Phase 3.3+)

- [ ] Expected move alignment (inside vs outside EM)
- [ ] Integrate with real-time price updates
- [ ] Save recommendations to `trade_plans` table
- [ ] Add Iron Condor / Iron Butterfly support
- [ ] Broker-ready order template export
- [ ] Discord command integration (Phase 8)
- [ ] Greeks-based probability models
- [ ] Historical backtesting of recommendations

---

## References

- [OptionChainSnapshot Model](../app/db/models.py#L219)
- [OptionContract Model](../app/db/models.py#L240)
- [IVMetric Model](../app/db/models.py#L270)
- [TastyTrade - Option Strike Selection](https://www.tastytrade.com/)

---

---

# Phase 3.3: Strategy Recommendation Layer ✅

**Status:** ✅ Complete
**Completed:** 2025-10-11

## Overview

Phase 3.3 delivers an intelligent strategy recommendation system that combines Phase 3.1 (calculator) and Phase 3.2 (strike selection) into a unified API. The system analyzes IV regime, applies trading objectives and constraints, scores candidates, and returns ranked recommendations with clear reasoning.

**Key Innovation**: Explicit strategy family selection based on IV regime eliminates ambiguity—credits materialize when selling premium makes sense, debits/longs appear when buying is optimal.

---

## Features

### Core Capabilities
- **IV-Based Strategy Selection**: Automatically chooses optimal strategy family (credit/debit/long) based on IV regime
- **Constraint Filtering**: Filters candidates by max risk, min POP, min R:R, credit quality, and liquidity
- **Composite Scoring**: Ranks candidates using weighted metrics (POP, R:R, credit quality, liquidity)
- **Reasoning Generation**: Provides clear bullet points explaining why each recommendation was selected
- **Position Sizing**: Calculates recommended contracts based on account size and risk tolerance
- **Flexible Objectives**: Supports explicit preferences (force credit/debit) or auto mode

---

## Architecture

```
app/
├── core/
│   └── strategy_recommender.py         # Strategy recommendation engine
├── api/v1/
│   ├── schemas/
│   │   └── strategy_recommendation.py  # Request/response models
│   └── strategy_recommendation.py       # FastAPI endpoint
├── services/
│   └── strike_data_service.py          # Data access (reused from 3.2)

tests/
└── test_strategy_recommendation.py      # 25 unit tests
```

---

## API Endpoint

### POST `/api/v1/strategy/recommend`

Generates intelligent strategy recommendations based on IV regime and market conditions.

**Request:**
```json
{
  "underlying_symbol": "SPY",
  "bias": "bullish",
  "target_dte": 30,
  "dte_tolerance": 3,
  "target_move_pct": 2.0,
  "objectives": {
    "max_risk_per_trade": 500,
    "min_pop_pct": 50,
    "min_risk_reward": 0.5,
    "prefer_credit": null,
    "avoid_earnings": false,
    "account_size": 25000
  },
  "constraints": {
    "min_credit_pct": 25,
    "max_spread_width": 5,
    "iv_regime_override": null,
    "min_open_interest": 100,
    "min_volume": 50,
    "min_mark_price": 0.01
  }
}
```

**Response:**
```json
{
  "underlying_symbol": "SPY",
  "underlying_price": 450.00,
  "chosen_strategy_family": "vertical_credit",
  "iv_rank": 68.5,
  "iv_regime": "high",
  "dte": 30,
  "expected_move_pct": 2.0,
  "data_timestamp": "2025-10-11T16:30:00Z",
  "recommendations": [
    {
      "rank": 1,
      "strategy_family": "vertical_credit",
      "option_type": "put",
      "position": "atm",
      "long_strike": 440.00,
      "short_strike": 445.00,
      "long_premium": 1.75,
      "short_premium": 3.50,
      "net_premium": -175.00,
      "is_credit": true,
      "net_credit": 175.00,
      "net_debit": null,
      "width_points": 5.00,
      "width_dollars": 500.00,
      "breakeven": 443.25,
      "max_profit": 175.00,
      "max_loss": 325.00,
      "risk_reward_ratio": 0.54,
      "pop_proxy": 70.0,
      "long_delta": -0.20,
      "short_delta": -0.35,
      "recommended_contracts": 2,
      "position_size_dollars": 650.00,
      "composite_score": 78.5,
      "avg_open_interest": 500,
      "avg_volume": 150,
      "reasons": [
        "High IV (high) regime favors selling premium - bull put credit spread",
        "At-the-money put",
        "Attractive R:R of 0.54:1",
        "High probability setup (~70% POP)",
        "Strong credit collection (35% of width)",
        "$5 spread width for ATM",
        "Good liquidity (OI: 500)"
      ],
      "warnings": []
    }
  ],
  "config_used": {
    "iv_high_threshold": 50.0,
    "iv_low_threshold": 25.0,
    "min_credit_pct": 25.0,
    "spread_width": 5,
    "scoring_weights": {
      "pop": 0.30,
      "rr": 0.30,
      "credit": 0.25,
      "liquidity": 0.10,
      "width_efficiency": 0.05
    }
  },
  "warnings": ["1 candidate(s) rejected due to constraint violations"]
}
```

---

## Strategy Selection Rules

### IV Regime → Strategy Family Mapping

| IV Regime | Bias | Strategy Family | Reasoning |
|-----------|------|----------------|-----------|
| **High (>50)** | Bullish | Bull Put Credit | Sell expensive premium, collect decay |
| **High (>50)** | Bearish | Bear Call Credit | Sell expensive premium, collect decay |
| **High (>50)** | Neutral | Credit Spread | Sell premium, neutral positioning |
| **Low (<25)** | Bullish | Long Call | Buy cheap premium, unlimited upside |
| **Low (<25)** | Bearish | Long Put | Buy cheap premium, defined downside capture |
| **Low (<25)** | Neutral | Debit Spread | Defined risk with cheap premium |
| **Neutral (25-50)** | Bullish | Bull Call Debit | Balanced defined risk/reward |
| **Neutral (25-50)** | Bearish | Bear Put Debit | Balanced defined risk/reward |
| **Neutral (25-50)** | Neutral | Debit Spread | Defined risk, moderate cost |

### Explicit Preferences Override

- `objectives.prefer_credit = true` → Forces credit spreads regardless of IV
- `objectives.prefer_credit = false` → Forces debit spreads/long options regardless of IV
- `constraints.iv_regime_override = "high"` → Treats IV as high regardless of actual IV rank

---

## Composite Scoring Formula

Candidates are scored 0-100 using weighted metrics:

### Formula
```
Score = (POP × 30%) + (R:R × 30%) + (Credit Quality × 25%) + (Liquidity × 10%) + (Position × 5%)
```

### Component Details

**1. POP Proxy (30 points max)**
- Based on delta-based probability of profit
- Normalized: 0-100% POP → 0-30 points
- High POP = better score

**2. Risk/Reward (30 points max)**
- Based on max profit / max loss ratio
- Normalized: R:R capped at 3:1 for scoring
- Higher R:R = better score

**3. Credit Quality (25 points max)**
- **For credit spreads**: Credit as % of spread width
  - 25% credit = 12.5 points, 50% credit = 25 points
- **For debit spreads**: Cost efficiency (profit/loss ratio)
  - Rewards lower cost relative to max profit

**4. Liquidity (10 points max)**
- Based on average open interest
- Normalized: 100 OI = 5 points, 500+ OI = 10 points
- Higher liquidity = better score

**5. Position Preference (5 points max)**
- **ATM**: 5 points (optimal balance)
- **OTM**: 2.5 points (higher risk/reward)
- **ITM**: 0 points (conservative)

---

## Constraints & Filtering

Candidates are filtered **before** scoring. Failed candidates are rejected and counted in warnings.

### Supported Constraints

**Objectives:**
- `max_risk_per_trade`: Maximum $ loss per trade
- `min_pop_pct`: Minimum probability of profit %
- `min_risk_reward`: Minimum R:R ratio

**Constraints:**
- `min_credit_pct`: Minimum credit as % of spread width (credit spreads only)
- `max_spread_width`: Maximum spread width in points
- `min_open_interest`: Minimum OI for liquidity
- `min_volume`: Minimum daily volume
- `min_mark_price`: Minimum mark price (avoids stale $0.00 contracts)

**Example**: If `max_risk_per_trade = 500`, all candidates with `max_loss > 500` are rejected.

---

## Reasoning Bullets

Each recommendation includes 5-7 reasoning bullets explaining selection:

### Reasoning Components

1. **Strategy Selection Reason**: IV regime justification
   - Example: "High IV (high) regime favors selling premium - bull put credit spread"

2. **Position Context**: Strike positioning
   - Example: "At-the-money put"

3. **Risk/Reward Assessment**: R:R quality
   - Example: "Attractive R:R of 1.8:1" (if R:R ≥ 1.5)

4. **Probability Assessment**: POP context
   - High (≥60%): "High probability setup"
   - Moderate (40-60%): "Moderate probability"
   - Lower (<40%): "Lower probability, higher reward"

5. **Credit Quality** (credit spreads only):
   - Example: "Strong credit collection (35% of width)"

6. **Width Efficiency**:
   - Example: "$5 spread width for ATM"

7. **Liquidity Context**:
   - Example: "Good liquidity (OI: 500)"

---

## Test Coverage

**25/25 tests passing:**

### Strategy Selection (8 tests)
- ✅ High IV + bullish → bull put credit
- ✅ High IV + bearish → bear call credit
- ✅ Low IV + bullish → long call
- ✅ Low IV + bearish → long put
- ✅ Neutral IV + bullish → bull call debit
- ✅ Neutral IV + bearish → bear put debit
- ✅ Explicit prefer_credit overrides IV regime
- ✅ Explicit prefer_debit overrides IV regime

### Composite Scoring (3 tests)
- ✅ High score for good metrics (POP, R:R, liquidity)
- ✅ Low score for poor metrics
- ✅ Credit quality contributes to score

### Constraints (4 tests)
- ✅ Max risk constraint rejects high-loss candidates
- ✅ Min POP constraint rejects low-probability candidates
- ✅ Min credit constraint rejects weak credits
- ✅ All constraints pass for compliant candidate

### Reasoning (3 tests)
- ✅ Includes strategy selection reason
- ✅ Includes position context
- ✅ Highlights attractive R:R

### End-to-End (7 tests)
- ✅ High IV + bullish recommends credit spreads
- ✅ Low IV + bearish recommends long puts
- ✅ Recommendations ranked by score
- ✅ Constraints filter candidates (rejected count in warnings)
- ✅ Position sizing with account size
- ✅ IV regime override works
- ✅ Reasoning bullets present with IV justification

---

## Usage Example

### High IV Bullish Credit Spread

```bash
curl -X POST http://localhost:8000/api/v1/strategy/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "underlying_symbol": "SPY",
    "bias": "bullish",
    "target_dte": 30,
    "dte_tolerance": 3,
    "objectives": {
      "max_risk_per_trade": 500,
      "min_pop_pct": 60,
      "account_size": 25000
    },
    "constraints": {
      "min_credit_pct": 30,
      "max_spread_width": 5
    }
  }'
```

**Expected Result**:
- Strategy: Bull put credit spread
- Reasoning: "High IV regime favors selling premium"
- 2-3 ranked candidates (ATM, OTM)
- Position sizing: 2-3 contracts based on risk tolerance

### Low IV Bearish Long Put

```bash
curl -X POST http://localhost:8000/api/v1/strategy/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "underlying_symbol": "AAPL",
    "bias": "bearish",
    "target_dte": 45,
    "objectives": {
      "max_risk_per_trade": 300,
      "account_size": 25000
    }
  }'
```

**Expected Result**:
- Strategy: Long put
- Reasoning: "Low IV regime favors buying cheap premium"
- 2-3 strike recommendations (ITM, ATM, OTM)
- Max loss ≤ $300 per contract

---

## Files Created

- [`app/core/strategy_recommender.py`](../app/core/strategy_recommender.py) - Core recommendation engine (650 lines)
- [`app/api/v1/schemas/strategy_recommendation.py`](../app/api/v1/schemas/strategy_recommendation.py) - Pydantic schemas
- [`app/api/v1/strategy_recommendation.py`](../app/api/v1/strategy_recommendation.py) - FastAPI endpoint
- [`tests/test_strategy_recommendation.py`](../tests/test_strategy_recommendation.py) - 25 comprehensive tests

---

## Next Steps (Phase 4+)

- [ ] Expected move alignment validation (trade inside/outside EM)
- [ ] Earnings calendar integration (avoid earnings if `avoid_earnings = true`)
- [ ] Save recommendations to `trade_plans` table
- [ ] Iron Condor / Iron Butterfly support
- [ ] Greeks-based probability refinement (replace delta proxy)
- [ ] Historical backtesting of recommendations
- [ ] Discord command integration (Phase 8)
- [ ] ML-based re-ranking (future enhancement)

---

**Phase 3 Status:** ✅ **3.1 COMPLETE** | ✅ **3.2 COMPLETE** | ✅ **3.3 COMPLETE**

---

## Deployment & Configuration

### Scheduler Setup (Auto-Fetch)

To enable auto-fetching of option chains and market data:

**Option 1: Single Worker (Recommended - $7/month)**
```bash
# On Render: volaris-bot service
SCHEDULER_ENABLED=true
```

The Discord bot automatically starts the scheduler when this flag is enabled.

**Option 2: Separate Worker ($14/month)**
- Create new Background Worker on Render
- Start command: `cd /opt/render/project/src && python -m app.workers`
- Set `SCHEDULER_ENABLED=true` on worker only

**Scheduler Jobs:**
- Option chains: Every 15 minutes (Schwab)
- Real-time prices: Every 1m/5m (Schwab)
- IV metrics: Every 30 minutes
- EOD data: Daily at 10:15pm UTC (Tiingo)
- Historical backfill: Daily at 3am UTC (Databento)

### Database Seeding

Seed tickers before enabling scheduler:

```bash
python scripts/seed_tickers.py
```

This seeds 12 essential tickers (SPY, QQQ, IWM, DIA, AAPL, MSFT, NVDA, TSLA, AMZN, GOOGL, META, JPM).

### Discord Commands

**18 Commands Available:**

**Strategy Planning (2):**
- `/plan` - Full recommendations with ICT context
- `/calc` - Quick P/L calculator

**Market Data (6):**
- `/price <symbol>` - Current price + % change
- `/quote <symbol>` - Full quote (bid/ask, volume)
- `/iv <symbol>` - IV, IVR, IV percentile
- `/range <symbol>` - 52-week high/low
- `/volume <symbol>` - Volume vs 30D average
- `/earnings <symbol>` - Next earnings date

**Calculators (5):**
- `/pop <delta>` - Probability from delta
- `/delta <symbol> <strike> <type> <dte>` - Get delta
- `/contracts <risk> <premium>` - Contracts for risk
- `/risk <contracts> <premium>` - Total risk
- `/dte <date>` - Days to expiration

**Tools (5):**
- `/spread <symbol> <width>` - Validate width
- `/size` - Position sizing
- `/breakeven` - Breakeven calculator
- `/check` - Health check
- `/help` - Command reference

**Example Workflow:**
```
/price SPY                    # Check price
/iv SPY                       # Check IV regime
/earnings SPY                 # Check earnings
/spread SPY 5                 # Validate 5-wide spread
/calc bull_put_spread SPY 540/535 7
/contracts 500 125            # Calculate contracts
```

### Strike Format Reference

**Debit Spreads:**
- Bull Call: `lower/higher` (1st=long, 2nd=short) → `445/450`
- Bear Put: `higher/lower` (1st=long, 2nd=short) → `450/445`

**Credit Spreads:**
- Bull Put: `higher/lower` (1st=short, 2nd=long) → `450/445`
- Bear Call: `lower/higher` (1st=short, 2nd=long) → `445/450`

**Long Options:**
- Single strike: `450`

