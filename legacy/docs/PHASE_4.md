# Phase 4 – Volatility & Expected-Move Module

## Overview & Status
- Status: 🚧 In Progress  
- Summary: Implemented the volatility core analytics layer, FastAPI endpoints, and supporting Discord helpers. Core IV/IVR/percentile calculations now surface through `/api/v1/vol/*`, expected-move estimates are fully straddle-based, and the Discord bot has pooled HTTP clients ready for a future `/em` command.

## Completed Tasks ✅
- [x] Added `app/core/volatility.py` with IV summaries, term structure, skew, and expected-move calculators.
- [x] Introduced `VolatilityService` facade with snapshot aggregation and graceful fallbacks.
- [x] Exposed new typed endpoints: `/api/v1/vol/iv`, `/api/v1/vol/term`, `/api/v1/vol/expected-move`, `/api/v1/vol/overview`.
- [x] Added optional batch refresh endpoint (`POST /api/v1/market/refresh/batch`) for price/options/IV hydration.
- [x] Wired Discord helpers with reusable `VolatilityAPI` client and expected-move embed builder.
- [x] Added unit tests covering volatility helpers, API responses, and batch refresh plumbing.
- [x] Updated roadmap Phase 4 checkboxes to reflect delivered scope.

## Key Files Created/Modified
- `app/core/volatility.py` – pure volatility analytics.
- `app/services/volatility_service.py` – snapshot orchestration and DB lookups.
- `app/api/v1/volatility.py` & `app/api/v1/schemas/volatility.py` – FastAPI layer + Pydantic models.
- `app/api/v1/market_data.py` – batch refresh request model + endpoint.
- `app/alerts/helpers/api_client.py`, `app/alerts/discord_bot.py`, `app/alerts/helpers/embeds.py` – Discord helpers for expected moves.
- Tests: `tests/test_volatility_core.py`, `tests/test_volatility_api.py`, `tests/test_market_refresh.py`.
- Docs: `docs/PHASE_4.md`, updated `docs/roadmap.md`.

## Usage Examples
```bash
# Fetch IV summary (FastAPI)
curl -s http://localhost:8000/api/v1/vol/iv/SPY | jq

# Expected moves (FastAPI)
curl -s http://localhost:8000/api/v1/vol/expected-move/QQQ | jq

# Batch refresh IV + options before requesting analytics
curl -s -X POST http://localhost:8000/api/v1/market/refresh/batch \
  -H "Content-Type: application/json" \
  -d '{"symbols":["SPY","QQQ"],"kinds":["price","options","iv"]}' | jq
```

```python
import httpx

async def fetch_overview(symbol: str) -> dict:
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        response = await client.get(f"/api/v1/vol/overview/{symbol}")
        response.raise_for_status()
        return response.json()

# Usage:
# overview = asyncio.run(fetch_overview("SPY"))
```

## Testing Procedures
```bash
# Focused tests for volatility module
pytest tests/test_volatility_core.py tests/test_volatility_api.py tests/test_market_refresh.py

# Full suite (optional before release)
pytest
```

## Configuration Details
- Uses existing `settings.IV_HIGH_THRESHOLD` / `IV_LOW_THRESHOLD` to classify regimes; adjust in `app/config.py` or via environment.
- No new environment variables required; relies on existing Postgres/Redis settings.
- Expected-move computations depend on option-chain snapshots—ensure `/api/v1/market/refresh/options/{symbol}` or the new batch endpoint is run periodically when the scheduler is disabled.

## Next Steps
- Wire expected-move context into strike selection and strategy reasoning (Phase 4.4, 4.3).
- Implement EM-based alerts (inside/outside move validation).
- Surface `/em` slash command using the new helpers and embed builder.
- Add automated data freshness checks (warnings currently surfaced when option data is stale).
