# Database Seeding Guide

Complete guide to populate the Volaris database with option chain data for `/plan` and automated `/calc` lookups.

## Overview

The database needs 4 types of data:
1. **Tickers** - Basic ticker information (symbol, name, sector)
2. **Price History** - Historical price data for backtesting
3. **Option Chains** - Current option strikes, prices, greeks
4. **IV Metrics** - Implied volatility rank/percentile

## Prerequisites

### 1. Database Setup
```bash
# Ensure PostgreSQL is running
# Check DATABASE_URL in .env
DATABASE_URL=postgresql://user:password@host:5432/volaris
```

### 2. Required API Keys

Add these to `.env`:

```bash
# Schwab (Primary - Real-time options data)
SCHWAB_APP_KEY=your_schwab_app_key
SCHWAB_SECRET_KEY=your_schwab_secret_key
SCHWAB_REFRESH_TOKEN=your_refresh_token

# Tiingo (EOD price data)
TIINGO_API_KEY=your_tiingo_key

# Alpaca (Alternative minute data)
ALPACA_API_KEY=your_alpaca_key
ALPACA_API_SECRET=your_alpaca_secret
```

**Getting API Keys:**
- **Schwab:** https://developer.schwab.com/ (Individual Developer Account)
- **Tiingo:** https://www.tiingo.com/ (Free tier available)
- **Alpaca:** https://alpaca.markets/ (Free paper trading account)

### 3. Run Database Migrations

```bash
source venv/bin/activate

# Initialize Alembic (if not done)
alembic init alembic

# Generate migration from models
alembic revision --autogenerate -m "Initial schema"

# Apply migrations
alembic upgrade head
```

## Quick Start: Seed Basic Data

### Option 1: Manual SQL Seeding (Fastest)

Create a SQL file to seed tickers:

```sql
-- seed_tickers.sql
INSERT INTO tickers (symbol, name, sector, is_active) VALUES
('SPY', 'SPDR S&P 500 ETF', 'ETF', true),
('QQQ', 'Invesco QQQ Trust', 'ETF', true),
('IWM', 'iShares Russell 2000 ETF', 'ETF', true),
('AAPL', 'Apple Inc.', 'Technology', true),
('MSFT', 'Microsoft Corporation', 'Technology', true),
('NVDA', 'NVIDIA Corporation', 'Technology', true),
('TSLA', 'Tesla Inc.', 'Automotive', true),
('AMZN', 'Amazon.com Inc.', 'Consumer Cyclical', true)
ON CONFLICT (symbol) DO NOTHING;
```

Run it:
```bash
psql $DATABASE_URL -f seed_tickers.sql
```

### Option 2: Python Seeding Script

Create `scripts/seed_tickers.py`:

```python
"""Seed basic ticker data."""
import asyncio
from sqlalchemy import select
from app.db.database import get_async_session
from app.db.models import Ticker

async def seed_tickers():
    """Seed essential tickers."""
    tickers_data = [
        {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "sector": "ETF"},
        {"symbol": "QQQ", "name": "Invesco QQQ Trust", "sector": "ETF"},
        {"symbol": "IWM", "name": "iShares Russell 2000 ETF", "sector": "ETF"},
        {"symbol": "AAPL", "name": "Apple Inc.", "sector": "Technology"},
        {"symbol": "MSFT", "name": "Microsoft Corporation", "sector": "Technology"},
        {"symbol": "NVDA", "name": "NVIDIA Corporation", "sector": "Technology"},
        {"symbol": "TSLA", "name": "Tesla Inc.", "sector": "Automotive"},
        {"symbol": "AMZN", "name": "Amazon.com Inc.", "sector": "Consumer Cyclical"},
    ]

    async with get_async_session() as session:
        for ticker_data in tickers_data:
            # Check if exists
            stmt = select(Ticker).where(Ticker.symbol == ticker_data["symbol"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if not existing:
                ticker = Ticker(**ticker_data, is_active=True)
                session.add(ticker)
                print(f"✅ Added {ticker_data['symbol']}")
            else:
                print(f"⏭️  {ticker_data['symbol']} already exists")

        await session.commit()
        print("\n✅ Ticker seeding complete!")

if __name__ == "__main__":
    asyncio.run(seed_tickers())
```

Run it:
```bash
python scripts/seed_tickers.py
```

## Full Data Pipeline: Phase 2 Workers

### Step 1: Enable Scheduler

In `.env`:
```bash
SCHEDULER_ENABLED=true
SCHEDULER_TIMEZONE=America/New_York

# Job intervals
REALTIME_JOB_INTERVAL_SECONDS=60
OPTION_CHAIN_JOB_INTERVAL_MINUTES=15
IV_METRICS_JOB_INTERVAL_MINUTES=30
EOD_SYNC_CRON_HOUR=22
EOD_SYNC_CRON_MINUTE=15
```

### Step 2: Start Background Workers

```bash
source venv/bin/activate
python -m app.workers.scheduler
```

**What it does:**
- Fetches real-time prices every 60 seconds (Schwab)
- Fetches option chains every 15 minutes (Schwab)
- Calculates IV metrics every 30 minutes
- Syncs EOD data daily at 10:15 PM ET (Tiingo)

**Expected output:**
```
INFO - Starting scheduler...
INFO - Job 'realtime_price_sync' scheduled
INFO - Job 'option_chain_refresh' scheduled
INFO - Job 'iv_metrics_calculation' scheduled
INFO - Job 'eod_data_sync' scheduled
INFO - Scheduler started
```

### Step 3: Verify Data

```bash
# Check tickers
psql $DATABASE_URL -c "SELECT symbol, name FROM tickers LIMIT 10;"

# Check price data
psql $DATABASE_URL -c "SELECT symbol, timestamp, close FROM price_history ORDER BY timestamp DESC LIMIT 5;"

# Check option chains
psql $DATABASE_URL -c "SELECT COUNT(*) FROM option_contracts;"

# Check IV metrics
psql $DATABASE_URL -c "SELECT symbol, iv_rank, iv_percentile FROM iv_metrics ORDER BY updated_at DESC LIMIT 5;"
```

## Manual Data Fetching (Without Scheduler)

### Fetch Option Chain for Single Ticker

Create `scripts/fetch_option_chain.py`:

```python
"""Manually fetch option chain for a ticker."""
import asyncio
from app.services.schwab_client import SchwabClient
from app.db.database import get_async_session
from app.db.models import OptionContract, Ticker

async def fetch_chain(symbol: str):
    """Fetch and save option chain."""
    client = SchwabClient()

    # Fetch option chain
    chain_data = await client.get_option_chain(symbol)

    if not chain_data:
        print(f"❌ No data for {symbol}")
        return

    async with get_async_session() as session:
        # Get ticker
        ticker = await session.scalar(
            select(Ticker).where(Ticker.symbol == symbol)
        )

        if not ticker:
            print(f"❌ Ticker {symbol} not found in database")
            return

        # Save contracts
        for contract in chain_data['contracts']:
            opt = OptionContract(
                ticker_id=ticker.id,
                strike=contract['strike'],
                expiration=contract['expiration'],
                option_type=contract['type'],
                bid=contract['bid'],
                ask=contract['ask'],
                last=contract['last'],
                volume=contract['volume'],
                open_interest=contract['open_interest'],
                implied_volatility=contract['iv'],
                delta=contract.get('delta'),
                gamma=contract.get('gamma'),
                theta=contract.get('theta'),
                vega=contract.get('vega'),
            )
            session.add(opt)

        await session.commit()
        print(f"✅ Saved {len(chain_data['contracts'])} contracts for {symbol}")

if __name__ == "__main__":
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    asyncio.run(fetch_chain(symbol))
```

Run it:
```bash
python scripts/fetch_option_chain.py SPY
python scripts/fetch_option_chain.py QQQ
python scripts/fetch_option_chain.py AAPL
```

## Minimal Setup for Testing

If you just want to test locally without API keys:

### Create Mock Data

```sql
-- Mock option contracts for SPY
INSERT INTO option_contracts (
    ticker_id,
    strike,
    expiration,
    option_type,
    bid,
    ask,
    last,
    volume,
    open_interest,
    implied_volatility,
    delta
)
SELECT
    (SELECT id FROM tickers WHERE symbol = 'SPY'),
    strike_price,
    CURRENT_DATE + INTERVAL '7 days',
    'call',
    strike_price * 0.02,  -- Mock bid
    strike_price * 0.025, -- Mock ask
    strike_price * 0.0225, -- Mock last
    1000,
    5000,
    0.15,
    CASE
        WHEN strike_price < 540 THEN 0.60
        WHEN strike_price < 545 THEN 0.50
        ELSE 0.40
    END
FROM generate_series(535, 555, 5) AS strike_price;

-- Repeat for puts
INSERT INTO option_contracts (
    ticker_id,
    strike,
    expiration,
    option_type,
    bid,
    ask,
    last,
    volume,
    open_interest,
    implied_volatility,
    delta
)
SELECT
    (SELECT id FROM tickers WHERE symbol = 'SPY'),
    strike_price,
    CURRENT_DATE + INTERVAL '7 days',
    'put',
    strike_price * 0.02,
    strike_price * 0.025,
    strike_price * 0.0225,
    1000,
    5000,
    0.15,
    CASE
        WHEN strike_price > 545 THEN -0.60
        WHEN strike_price > 540 THEN -0.50
        ELSE -0.40
    END
FROM generate_series(535, 555, 5) AS strike_price;
```

## Troubleshooting

### "Option chain refresh failed"
**Cause:** API keys not configured or invalid
**Fix:** Check `.env` has valid `SCHWAB_APP_KEY` and `SCHWAB_REFRESH_TOKEN`

### "Ticker not found"
**Cause:** Ticker not in database
**Fix:** Run ticker seeding script first

### "No option contracts found"
**Cause:** Option chain data not fetched yet
**Fix:** Run `option_chain_refresh` job manually or wait 15 minutes

### "IV rank unavailable"
**Cause:** IV metrics not calculated yet
**Fix:** Run `iv_metrics_calculation` job manually

## Current Workaround

Until database is populated, use `/calc` with required parameters:

```
/calc
Strategy: Bull Put Spread (Credit)
Symbol: SPY
Strikes: 545/540
DTE: 7
Premium: 1.50
Underlying Price: 548.00
```

This bypasses database lookup and works immediately!

## Next Steps

1. ✅ Seed tickers (Option 1 or 2)
2. ⏰ Start background workers (Step 2)
3. ⏳ Wait 15 minutes for first option chain fetch
4. ✅ Test `/plan` command in Discord
5. 🎯 `/calc` will auto-fetch prices once DB populated

## Quick Reference

| Data Type | Update Frequency | Requires |
|-----------|-----------------|----------|
| Tickers | Once | Manual seed |
| Price History | 60s / EOD | Schwab/Tiingo |
| Option Chains | 15min | Schwab |
| IV Metrics | 30min | Price history |

## Production Deployment

For Render/production:
1. Add all API keys to Render environment variables
2. Enable scheduler: `SCHEDULER_ENABLED=true`
3. Workers run automatically via `app/main.py` lifespan
4. Monitor logs: `"Option chain refreshed"` every 15 min
