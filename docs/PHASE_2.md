# Phase 2: Data Layer & Pipeline

**Status:** ✅ In Progress (2.1 & 2.2 complete)

This document summarizes the implementation work for Phase 2:

- **2.1 Database Models** – relational schema to persist price data, option chains, IV metrics, trade plans, and journaling primitives.
- **2.2 Data Fetchers** – APScheduler-backed workers that hydrate the database from external providers and derive IV stats.

---

## Phase 2.1 – Database Models ✅

### Completed Tasks
- [x] Core entities: `Ticker`, `Watchlist`, `WatchlistItem`
- [x] OHLC price storage (`PriceBar`) with per-timeframe uniqueness
- [x] Option-chain storage (`OptionChainSnapshot`, `OptionContract`)
- [x] IV metrics (`IVMetric`) tracked per term horizon
- [x] Market structure levels scaffold (`MarketStructureLevel`)
- [x] Trade lifecycle tables (`TradePlan`, `TradeExecution`, `TradeJournalEntry`)
- [x] Enum taxonomies for timeframes, providers, strategies, biases, etc.

### Key Files
- `app/db/models.py` – full ORM definitions with relationships, constraints, and enums
- `tests/test_models.py` – metadata assertions covering critical uniqueness/index rules

### Usage Notes
```python
from app.db.models import Ticker, Timeframe, PriceBar
from app.db.database import async_session_maker

async with async_session_maker() as session:
    spy = Ticker(symbol="SPY", name="SPDR S&P 500", is_active=True)
    session.add(spy)
    await session.commit()
```

### Configuration
No new environment variables required for schema usage.

### Testing
```bash
venv/bin/pytest tests/test_models.py -q
```

### Migrations
```bash
# Generate (already committed)
ALEMBIC_DATABASE_URL=sqlite:///tmp_migration.db venv/bin/alembic revision --autogenerate -m "create core tables"

# Apply to target database
venv/bin/alembic upgrade head
```

### Next
- Auto-generate Alembic migrations for the new schema (Phase 2 rollout)
- Seed baseline ticker/watchlist data for live environments
    ```bash
    # After applying migrations
    venv/bin/python scripts/seed_baseline.py
    ```

---

## Phase 2.2 – Data Fetchers ✅

### Completed Tasks
- [x] Real-time minute & 5-minute price ingestion (`fetch_realtime_prices`)
- [x] Historical backfill worker leveraging Databento/Alpaca
- [x] Tiingo EOD synchronisation
- [x] Option-chain snapshot pull + contract persistence
- [x] IV/IVR calculator deriving metrics from latest chain
- [x] APScheduler wiring with interval/cron triggers

### Key Files
- `app/workers/utils.py` – shared parsing helpers for timestamps, decimals, and payload normalisation
- `app/workers/tasks.py` – core async ingestion routines operating on an `AsyncSession`
- `app/workers/jobs.py` – thin wrappers that acquire sessions for scheduler execution
- `app/workers/scheduler.py` – `AsyncIOScheduler` factory with configured jobs
- `app/main.py` – scheduler lifecycle hook (guarded by `SCHEDULER_ENABLED`)
- `tests/test_workers_tasks.py` – mocks provider payloads to exercise ingestion logic end-to-end

### Usage Examples

**Manual price sync (1m bars)**
```python
from app.db.database import async_session_maker
from app.workers.tasks import fetch_realtime_prices
from app.db.models import Timeframe

async with async_session_maker() as session:
    await fetch_realtime_prices(session, timeframe=Timeframe.ONE_MINUTE)
```

**Kick off option-chain refresh**
```python
from app.db.database import async_session_maker
from app.workers.tasks import fetch_option_chains

async with async_session_maker() as session:
    await fetch_option_chains(session)
```

**Enable scheduler in production**
```bash
# .env / Render environment
SCHEDULER_ENABLED=true
SCHEDULER_TIMEZONE=US/Eastern  # optional override
```

Once enabled, FastAPI’s lifespan will boot APScheduler and run the following jobs:

| Job | Trigger | Purpose |
| --- | --- | --- |
| `prices_1m` | every `REALTIME_JOB_INTERVAL_SECONDS` | Schwab minute bars |
| `prices_5m` | every `FIVE_MINUTE_JOB_INTERVAL_SECONDS` | Aggregated 5m bars |
| `options_refresh` | every `OPTION_CHAIN_JOB_INTERVAL_MINUTES` | Option chain snapshot |
| `iv_metrics` | every `IV_METRICS_JOB_INTERVAL_MINUTES` | IV/IVR derivation |
| `eod_sync` | daily Cron (`EOD_SYNC_CRON_HOUR`/`MINUTE`) | Tiingo EOD close |
| `historical_backfill` | daily Cron (`HISTORICAL_BACKFILL_CRON_HOUR`) | Deep historical update |

### Configuration

New environment variables (defaults shown in `app/config.py`):

```
SCHEDULER_ENABLED=false
SCHEDULER_TIMEZONE=UTC
REALTIME_JOB_INTERVAL_SECONDS=60
FIVE_MINUTE_JOB_INTERVAL_SECONDS=300
OPTION_CHAIN_JOB_INTERVAL_MINUTES=15
IV_METRICS_JOB_INTERVAL_MINUTES=30
EOD_SYNC_CRON_HOUR=22
EOD_SYNC_CRON_MINUTE=15
HISTORICAL_BACKFILL_CRON_HOUR=3
HISTORICAL_BACKFILL_LOOKBACK_DAYS=30
```

### Testing
```bash
venv/bin/pytest tests/test_workers_tasks.py -q
```

### Next
- Integrate live provider credentials (Alpaca/Databento) and monitor `providers/health`
- Wire Phase 3 trade planner logic to the newly-populated tables
- Add Alembic migrations + seeds to bootstrap production data

---

## Overall Next Steps
- Generate migrations for the Phase 2 schema additions
- Stand up nightly jobs in production once Alpaca/Databento credentials are validated
- Proceed to **Phase 3 – Trade Planner & Strategy Engine**
