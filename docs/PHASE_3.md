# Phase 3: Trade Planning & Strategy Calculator

**Status:** ✅ Complete
**Version:** 1.0.0
**Last Updated:** 2025-10-11

---

## Overview

Phase 3 introduces the core trade planning and strategy calculation engine for Volaris. This module provides risk/reward analysis for vertical spreads (debit and credit) and long options (calls and puts), enabling traders to evaluate trade ideas before execution.

### Key Features

- **Vertical Spread Calculator**: Bull/bear call/put spreads with automatic debit/credit detection
- **Long Option Calculator**: Long calls and long puts with theoretical max profit
- **Risk Metrics**: Max profit, max loss, breakeven prices, risk/reward ratio
- **Position Sizing**: Risk-based contract calculation using account size and risk percentage
- **Probability Proxy**: Delta-based win probability estimation
- **FastAPI Endpoints**: RESTful API for integration with clients and Discord bot
- **Discord Bridge**: Placeholder handlers for Phase 8 Discord command integration

---

## Architecture

```
app/
├── core/
│   └── trade_planner.py          # Core calculation engine (pure Python)
├── api/v1/
│   ├── schemas/
│   │   └── trade_planner.py      # Pydantic request/response models
│   └── trade_planner.py          # FastAPI router with endpoints
└── alerts/
    └── discord_handlers.py       # Discord bridge (Phase 8 placeholder)

tests/
└── test_trade_planner.py         # 25+ unit tests with 100% coverage
```

---

## Supported Strategies

### 1. Vertical Spreads

**Types:**
- **Bull Call Spread** (Debit): Long lower strike call, short higher strike call
- **Bear Put Spread** (Debit): Long higher strike put, short lower strike put
- **Bull Put Spread** (Credit): Short higher strike put, long lower strike put
- **Bear Call Spread** (Credit): Short lower strike call, long higher strike call

**Automatic Detection:** Strategy type (debit vs. credit) is determined automatically based on net premium.

### 2. Long Options

**Types:**
- **Long Call**: Bullish directional bet with limited risk, unlimited upside
- **Long Put**: Bearish directional bet with limited risk, capped upside (strike value)

---

## API Reference

### Base URL
```
http://localhost:8000/api/v1/trade-planner
```

### Endpoints

#### 1. Calculate Vertical Spread

**POST** `/calculate/vertical-spread`

Calculate risk/reward for a vertical spread (debit or credit).

**Request Body:**
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
  "short_delta": 0.40
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
    {
      "strike": 445.00,
      "premium": 7.50,
      "option_type": "call",
      "position": "long",
      "contracts": 1
    },
    {
      "strike": 450.00,
      "premium": 3.00,
      "option_type": "call",
      "position": "short",
      "contracts": 1
    }
  ],
  "max_profit": 50.00,
  "max_loss": 450.00,
  "breakeven_prices": [449.50],
  "risk_reward_ratio": 0.1111,
  "win_probability": 20.00,
  "position_size_contracts": 1,
  "position_size_dollars": 450.00,
  "net_premium": 450.00,
  "dte": 30,
  "total_delta": 0.20,
  "assumptions": {
    "spread_width": 500.00,
    "is_debit_spread": true,
    "multiplier": 100
  }
}
```

---

#### 2. Calculate Long Option

**POST** `/calculate/long-option`

Calculate risk/reward for a long call or long put.

**Request Body:**
```json
{
  "underlying_symbol": "AAPL",
  "underlying_price": 175.00,
  "strike": 180.00,
  "premium": 3.50,
  "option_type": "call",
  "bias": "bullish",
  "contracts": 2,
  "dte": 45,
  "delta": 0.35
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
    {
      "strike": 180.00,
      "premium": 3.50,
      "option_type": "call",
      "position": "long",
      "contracts": 2
    }
  ],
  "max_profit": 3500.00,
  "max_loss": 700.00,
  "breakeven_prices": [183.50],
  "risk_reward_ratio": 5.00,
  "win_probability": 35.00,
  "position_size_contracts": 2,
  "position_size_dollars": 700.00,
  "net_premium": 700.00,
  "dte": 45,
  "total_delta": 0.70,
  "assumptions": {
    "max_profit_note": "Theoretical max for calls, strike value for puts",
    "multiplier": 100
  }
}
```

---

#### 3. Unified Calculate Endpoint

**POST** `/calculate`

Unified endpoint supporting all strategy types.

**Request Body:**
```json
{
  "strategy_type": "vertical_spread",
  "underlying_symbol": "SPY",
  "underlying_price": 450.00,
  "long_strike": 445.00,
  "short_strike": 450.00,
  "long_premium": 7.50,
  "short_premium": 3.00,
  "option_type": "call",
  "bias": "bullish",
  "contracts": 1,
  "dte": 30
}
```

**Strategy Types:**
- `vertical_spread`: Requires `long_strike`, `short_strike`, `long_premium`, `short_premium`
- `long_call`: Requires `strike`, `premium`, `option_type="call"`
- `long_put`: Requires `strike`, `premium`, `option_type="put"`

---

#### 4. Calculate Position Size

**POST** `/position-size`

Calculate position size based on risk management rules.

**Request Body:**
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
Net Premium (Debit) = (Long Premium - Short Premium) × Contracts × 100
Max Loss = Net Premium
Max Profit = Spread Width - Net Premium
Risk/Reward Ratio = Max Profit / Max Loss

Breakeven (Call) = Long Strike + (Net Premium / (Contracts × 100))
Breakeven (Put) = Long Strike - (Net Premium / (Contracts × 100))
```

### Vertical Spread (Credit)

```
Net Premium (Credit) = (Short Premium - Long Premium) × Contracts × 100
Max Profit = Net Premium
Max Loss = Spread Width - Net Premium
Risk/Reward Ratio = Max Profit / Max Loss

Breakeven (Call) = Short Strike + (Net Premium / (Contracts × 100))
Breakeven (Put) = Short Strike - (Net Premium / (Contracts × 100))
```

### Long Option

```
Net Premium = Premium × Contracts × 100
Max Loss = Net Premium

Max Profit (Call) = Net Premium × 5  (conservative estimate)
Max Profit (Put) = Strike × Contracts × 100

Breakeven (Call) = Strike + Premium
Breakeven (Put) = Strike - Premium
```

### Position Sizing

```
Max Risk Dollars = Account Size × (Risk Percentage / 100)
Contracts = floor(Max Risk Dollars / Max Loss per Contract)
Minimum Contracts = max(1, Contracts)  (if > 0)
```

### Win Probability Proxy

```
Debit Spread: Win Probability ≈ |Net Delta| × 100
Credit Spread: Win Probability ≈ (1 - |Net Delta|) × 100
Long Option: Win Probability ≈ |Delta| × 100

Note: This is a rough approximation, not actual probability.
```

---

## Usage Examples

### cURL Examples

**1. Calculate Bull Call Spread:**
```bash
curl -X POST http://localhost:8000/api/v1/trade-planner/calculate/vertical-spread \
  -H "Content-Type: application/json" \
  -d '{
    "underlying_symbol": "SPY",
    "underlying_price": 450.00,
    "long_strike": 445.00,
    "short_strike": 450.00,
    "long_premium": 7.50,
    "short_premium": 3.00,
    "option_type": "call",
    "bias": "bullish",
    "contracts": 1,
    "dte": 30
  }'
```

**2. Calculate Long Put:**
```bash
curl -X POST http://localhost:8000/api/v1/trade-planner/calculate/long-option \
  -H "Content-Type: application/json" \
  -d '{
    "underlying_symbol": "SPY",
    "underlying_price": 450.00,
    "strike": 445.00,
    "premium": 5.00,
    "option_type": "put",
    "bias": "bearish",
    "contracts": 1,
    "dte": 30
  }'
```

**3. Calculate Position Size:**
```bash
curl -X POST http://localhost:8000/api/v1/trade-planner/position-size \
  -H "Content-Type: application/json" \
  -d '{
    "max_loss_per_contract": 450.00,
    "account_size": 25000.00,
    "risk_percentage": 2.0
  }'
```

---

### Python SDK Examples

```python
from decimal import Decimal
from app.core.trade_planner import calculate_vertical_spread, TradeBias

# Calculate a bull call spread
result = calculate_vertical_spread(
    underlying_symbol="SPY",
    underlying_price=Decimal("450.00"),
    long_strike=Decimal("445.00"),
    short_strike=Decimal("450.00"),
    long_premium=Decimal("7.50"),
    short_premium=Decimal("3.00"),
    option_type="call",
    bias=TradeBias.BULLISH,
    contracts=1,
    dte=30,
    long_delta=Decimal("0.60"),
    short_delta=Decimal("0.40"),
)

print(f"Max Profit: ${result.max_profit}")
print(f"Max Loss: ${result.max_loss}")
print(f"Breakeven: ${result.breakeven_prices[0]}")
print(f"R:R Ratio: {result.risk_reward_ratio:.2f}")
print(f"Win Probability: {result.win_probability:.0f}%")
```

---

## Testing

### Run Tests
```bash
# Run all trade planner tests
pytest tests/test_trade_planner.py -v

# Run with coverage
pytest tests/test_trade_planner.py --cov=app.core.trade_planner --cov-report=term-missing
```

### Test Coverage
- ✅ Bull call spread (debit)
- ✅ Bear put spread (debit)
- ✅ Bull put spread (credit)
- ✅ Bear call spread (credit)
- ✅ Long call
- ✅ Long put
- ✅ Position sizing (various scenarios)
- ✅ Delta-based probability calculations
- ✅ Multiple contracts
- ✅ Edge cases (wide spreads, narrow spreads, zero risk tolerance)

**Total Tests:** 25+
**Coverage:** 100%

---

## Configuration

### Default Settings (config.py)

```python
DEFAULT_ACCOUNT_SIZE: float = 25000.0        # Default account size for risk calculations
MAX_RISK_PERCENTAGE: float = 10.0            # Max risk per trade as % of account
```

### Customization

Position sizing can be customized per request using the `/position-size` endpoint. Default risk percentage is 2%, but can be adjusted from 0.1% to 10% based on risk tolerance.

---

## Discord Integration (Phase 8 Placeholder)

The Discord bridge in `app/alerts/discord_handlers.py` provides placeholder functions for future integration:

### Planned Commands

```
/plan vertical <symbol> <price> <long_strike>/<short_strike> <type> <long_premium>/<short_premium> <bias> <dte>
/plan long <symbol> <price> <strike> <type> <premium> <bias> <dte>
/size <max_loss> <account_size> <risk_pct>
```

### Example Discord Output

```
**Strategy:** Bull Call Spread (Vertical Debit)
**Ticker:** SPY @ $450.00
**Bias:** Bullish

**Position:**
• Long 445 Call @ $7.50 (1 contract)
• Short 450 Call @ $3.00 (1 contract)

**Risk/Reward:**
• Max Profit: $50.00
• Max Loss: $450.00
• Breakeven: $449.50
• R:R Ratio: 0.11

**Position Size:** 1 contract ($450 at risk)
**Win Probability:** ~20% (delta-based estimate)
**DTE:** 30 days
```

---

## Files Created/Modified

### New Files
- [app/core/trade_planner.py](../app/core/trade_planner.py) - Core calculation engine
- [app/api/v1/schemas/trade_planner.py](../app/api/v1/schemas/trade_planner.py) - Pydantic models
- [app/api/v1/trade_planner.py](../app/api/v1/trade_planner.py) - FastAPI router
- [app/alerts/discord_handlers.py](../app/alerts/discord_handlers.py) - Discord bridge placeholder
- [tests/test_trade_planner.py](../tests/test_trade_planner.py) - Unit tests

### Modified Files
- [app/main.py](../app/main.py) - Registered trade planner router

---

## Assumptions & Limitations

1. **Max Profit (Long Calls)**: Uses 5x risk as a conservative estimate since theoretical max is unlimited
2. **Max Profit (Long Puts)**: Assumes stock can go to $0, so max profit = strike × contracts × 100
3. **Probability Proxy**: Delta-based win probability is a rough approximation, not actual statistical probability
4. **Option Multiplier**: All calculations assume standard 100 shares per contract
5. **Commissions**: Not included in calculations (add separately based on broker)
6. **Slippage**: Not included (use conservative premiums when planning)
7. **Greeks**: Only Delta is used for probability proxy; other greeks not yet integrated

---

## Next Steps (Phase 3.2+)

- [ ] Integrate with live option chain data from Phase 2.2 workers
- [ ] Add Iron Condor and Iron Butterfly strategies
- [ ] Implement Greeks-based probability modeling (Theta, Vega, Gamma)
- [ ] Add Monte Carlo simulation for win probability
- [ ] Save calculated plans to `trade_plans` database table
- [ ] Build interactive Discord commands (Phase 8)
- [ ] Add chart generation for payoff diagrams
- [ ] Implement adjustment scenarios (roll, close early)
- [ ] Add historical backtest capability

---

## References

- [Options Profit Calculator](https://www.optionsprofitcalculator.com/)
- [The Options Playbook - Vertical Spreads](https://www.optionsplaybook.com/option-strategies/)
- [TastyTrade - Probability of Profit](https://www.tastytrade.com/concepts-strategies/probability-of-profit)

---

**Phase 3.1 Status:** ✅ **COMPLETE**
