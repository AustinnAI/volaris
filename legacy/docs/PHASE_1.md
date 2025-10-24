## Phase 1: Foundation & Core Infrastructure

**Status**: ✅ Complete

This document covers all of Phase 1 including sub-phases 1.1 (Project Setup) and 1.2 (API Integrations).

---

## Phase 1.1: Project Setup ✅

### Completed Tasks

- [x] FastAPI application structure with async lifecycle management
- [x] Pydantic-based configuration management with environment validation
- [x] PostgreSQL (Neon) with async SQLAlchemy + asyncpg driver
- [x] Redis cache (Upstash) with REST API client
- [x] Docker & docker-compose for local development
- [x] GitHub Actions CI/CD pipelines (lint, test, security scan, deploy)
- [x] Sentry monitoring integration
- [x] Structured logging with rate limiting
- [x] Base test suite with pytest

### Key Files

```
app/
├── main.py                 # FastAPI entrypoint with lifespan management
├── config.py               # Pydantic settings with validation
├── db/
│   ├── database.py         # Async SQLAlchemy setup
│   └── models.py           # Base models with timestamp mixin
└── utils/
    ├── cache.py            # Redis client (Upstash REST API)
    ├── logger.py           # Structured logging + Sentry
    └── rate_limiter.py     # Token bucket rate limiter

.github/workflows/
├── ci.yml                  # CI pipeline
└── deploy.yml              # Deployment workflow

Dockerfile
docker-compose.yml
requirements.txt
```

---

## Phase 1.2: API Integrations ✅

### Overview

Complete API integration layer for 5 market data providers with health monitoring, fallback logic, OAuth 2.0 PKCE for Schwab, and comprehensive error handling.

### Provider Hierarchy (from spec)

1. **Schwab** (Primary) - Real-time 1m/5m OHLC via OAuth 2.0
2. **Alpaca** (Fallback) - Minute-delayed historical bars
3. **Databento** - Historical backfills
4. **Tiingo** - EOD data + IEX real-time quotes
5. **Finnhub** - Fundamentals, news, sentiment

### Implemented Clients

#### 1. Schwab Client (`app/services/schwab.py`)

**OAuth 2.0 PKCE Flow**:
- Authorization URL generation with PKCE challenge
- Code exchange for access/refresh tokens
- Automatic token refresh (cached in Redis)
- Callback endpoint: `/api/v1/auth/schwab/callback`

**Market Data APIs**:
- Real-time quotes (bid/ask/last)
- 1-minute & 5-minute price history
- Options chains
- Market hours

**Usage**:
```python
from app.services.schwab import schwab_client

# Get authorization URL
auth_url, verifier = schwab_client.get_authorization_url()
# User visits URL, we exchange code for tokens

# Get quote
quote = await schwab_client.get_quote("SPY")
print(quote['quote']['lastPrice'])

# Get 1m bars
history = await schwab_client.get_price_history(
    "SPY", period_type="day", period=1,
    frequency_type="minute", frequency=1
)
```

**OAuth Setup**:
```bash
# Visit authorization endpoint
curl http://localhost:8000/api/v1/auth/schwab/authorize

# After approval, callback receives code and returns refresh token
# Add to .env: SCHWAB_REFRESH_TOKEN=...
```

#### 2. Tiingo Client (`app/services/tiingo.py`)

**APIs**:
- EOD price data (daily OHLCV with adjustments)
- Real-time IEX quotes
- Intraday bars (1min, 5min, 15min, 30min, 1hour)
- Ticker metadata

**Usage**:
```python
from app.services.tiingo import tiingo_client
from datetime import date, timedelta

# EOD prices
prices = await tiingo_client.get_eod_prices(
    "SPY",
    start_date=date.today() - timedelta(days=30)
)

# Real-time IEX quote
quote = await tiingo_client.get_iex_realtime_price("AAPL")
print(f"${quote['last']} | Bid: ${quote['bidPrice']}")
```

**cURL**:
```bash
curl -H "Authorization: Token YOUR_KEY" \
  "https://api.tiingo.com/tiingo/daily/SPY/prices?startDate=2024-10-01"
```

#### 3. Alpaca Client (`app/services/alpaca.py`)

**APIs**:
- 1-minute delayed bars (1Min, 5Min, 15Min, 1Hour, 1Day)
- Latest quotes (bid/ask)
- Market snapshots
- Multi-symbol batch requests

**Usage**:
```python
from app.services.alpaca import alpaca_client
from datetime import datetime, timedelta

# Get 1m bars
bars = await alpaca_client.get_bars(
    "SPY", timeframe="1Min",
    start=datetime.now() - timedelta(hours=1)
)

# Latest quote
quote = await alpaca_client.get_latest_quote("QQQ")
print(f"Bid: ${quote['bp']} x {quote['bs']}")

# Snapshot
snapshot = await alpaca_client.get_snapshot("AAPL")
```

**cURL**:
```bash
curl -H "APCA-API-KEY-ID: YOUR_KEY" \
     -H "APCA-API-SECRET-KEY: YOUR_SECRET" \
  "https://paper-api.alpaca.markets/v2/stocks/SPY/bars?timeframe=1Min&limit=10"
```

#### 4. Databento Client (`app/services/databento.py`)

**APIs**:
- Historical OHLCV bars (1m, 5m, 1h, 1d)
- Trade and quote (MBO/MBP) data
- Dataset listing & range queries
- Cost estimation before fetching

**Usage**:
```python
from app.services.databento import databento_client
from datetime import date

# List datasets
datasets = await databento_client.list_datasets()

# Get cost estimate
cost = await databento_client.get_cost_estimate(
    dataset="XNAS.ITCH", symbols=["SPY"],
    schema="ohlcv-1m", start=date(2024, 1, 1), end=date(2024, 1, 31)
)
print(f"Cost: ${cost['cost']}")

# Fetch data
bars = await databento_client.get_ohlcv_bars(
    "SPY", start=date(2024, 1, 1), timeframe="1m"
)
```

#### 5. Finnhub Client (`app/services/finnhub.py`)

**APIs**:
- Company profiles & fundamentals
- Real-time quotes
- Company & market news
- Earnings calendar
- Analyst recommendations
- Insider transactions

**Usage**:
```python
from app.services.finnhub import finnhub_client
from datetime import date, timedelta

# Company profile
profile = await finnhub_client.get_company_profile("AAPL")
print(f"{profile['name']} - ${profile['marketCapitalization']}M")

# Quote
quote = await finnhub_client.get_quote("SPY")
print(f"${quote['c']} ({quote['dp']}%)")

# News
news = await finnhub_client.get_company_news(
    "TSLA", from_date=date.today() - timedelta(days=7)
)

# Financials
financials = await finnhub_client.get_basic_financials("AAPL")
metrics = financials['metric']
print(f"P/E: {metrics['peNormalizedAnnual']}")
```

### Infrastructure

#### Base Client (`app/services/base_client.py`)

**Features**:
- Automatic retry with exponential backoff (2-10s)
- Rate limit handling (429 errors)
- Server error retry (5xx errors)
- Timeout handling (30s default)
- Network error recovery

**Retry Strategy**:
- Max retries: 3
- Multiplier: 1
- Min wait: 2s
- Max wait: 10s
- Retries on: `NetworkError`, `ProviderError`

#### Exception Taxonomy (`app/services/exceptions.py`)

```python
APIClientError               # Base exception
├── AuthenticationError      # 401, 403
├── RateLimitError          # 429 (includes retry_after)
├── QuotaExceededError      # Quota exhausted
├── InvalidRequestError     # 4xx (except 401, 403, 429)
├── ProviderError           # 5xx
├── DataNotFoundError       # Data unavailable
├── NetworkError            # Connection issues
├── TimeoutError            # Request timeout
└── ValidationError         # Response validation failed
```

**Usage**:
```python
from app.services.exceptions import RateLimitError, DataNotFoundError

try:
    data = await client.get_data()
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
    await asyncio.sleep(e.retry_after)
except DataNotFoundError:
    print("Data not found for ticker")
```

#### Provider Manager (`app/services/provider_manager.py`)

**Fallback Hierarchy**:
```python
from app.services.provider_manager import provider_manager, DataType

# Automatic provider selection
provider = provider_manager.get_provider(DataType.REALTIME_MINUTE)
# Returns: schwab_client (primary) or alpaca_client (fallback)

provider = provider_manager.get_provider(DataType.EOD)
# Returns: tiingo_client

# Manual selection
provider = provider_manager.get_provider(
    DataType.REALTIME_MINUTE, preferred="alpaca"
)
```

**Data Types**:
- `REALTIME_MINUTE` → Schwab (primary), Alpaca (fallback)
- `MINUTE_DELAYED` → Alpaca, Schwab
- `EOD` → Tiingo
- `HISTORICAL` → Databento, Alpaca
- `FUNDAMENTALS` → Finnhub
- `NEWS` → Finnhub
- `QUOTE` → Schwab, Alpaca, Tiingo
- `OPTIONS` → Schwab

### API Endpoints

#### Health & Status

```bash
# All providers health
GET /api/v1/providers/health

# Specific provider
GET /api/v1/providers/{name}/health

# Configured providers
GET /api/v1/providers/configured

# Available data types
GET /api/v1/providers/capabilities

# Provider hierarchy
GET /api/v1/providers/hierarchy
```

**Response Example**:
```json
{
  "timestamp": "2024-10-10T10:30:00Z",
  "providers": {
    "schwab": {"configured": true, "healthy": true},
    "tiingo": {"configured": true, "healthy": true},
    "alpaca": {"configured": true, "healthy": true},
    "databento": {"configured": true, "healthy": true},
    "finnhub": {"configured": true, "healthy": true}
  },
  "summary": {
    "total": 5,
    "healthy": 5,
    "unhealthy": 0
  }
}
```

#### OAuth Authentication

```bash
# Schwab authorization (browser)
GET /api/v1/auth/schwab/authorize

# OAuth callback (automatic)
GET /api/v1/auth/schwab/callback?code=...&code_verifier=...
```

### Configuration

**Environment Variables** (`.env`):
```bash
# Schwab
SCHWAB_APP_KEY=your_app_key
SCHWAB_SECRET_KEY=your_secret_key
SCHWAB_REDIRECT_URI=https://volaris.onrender.com/auth/schwab/callback
SCHWAB_REFRESH_TOKEN=  # Obtained after OAuth

# Tiingo
TIINGO_API_KEY=your_api_key

# Alpaca
ALPACA_API_KEY=your_key_id
ALPACA_API_SECRET=your_secret_key

# Databento
DATABENTO_API_KEY=your_api_key

# Finnhub
FINNHUB_API_KEY=your_api_key
```

### Testing

**Unit Tests** (`tests/test_providers.py`):
```bash
# Run all tests
pytest tests/test_providers.py -v

# With coverage
pytest tests/test_providers.py --cov=app/services --cov-report=term-missing

# Specific test
pytest tests/test_providers.py::test_tiingo_get_eod_prices -v
```

**Mock-based tests** for:
- All 5 provider clients
- OAuth PKCE generation
- Error handling (rate limits, server errors, timeouts)
- Provider manager selection
- Base client retry logic

**Manual Testing**:
```bash
# Start app
uvicorn app.main:app --reload

# Check health
curl http://localhost:8000/api/v1/providers/health | jq

# Test Tiingo
curl -H "Authorization: Token YOUR_KEY" \
  "https://api.tiingo.com/tiingo/daily/SPY/prices?startDate=2024-10-01" | jq

# Test Finnhub
curl "https://finnhub.io/api/v1/quote?symbol=SPY&token=YOUR_KEY" | jq
```

### OAuth Flow (Schwab)

**Step 1: Visit Authorization Endpoint**
```
http://localhost:8000/api/v1/auth/schwab/authorize
```

**Step 2: Click "Authorize with Schwab"**
- Browser redirects to Schwab login
- User approves application

**Step 3: Callback Receives Code**
- Schwab redirects to: `https://volaris.onrender.com/auth/schwab/callback?code=...&state=code_verifier`
- Callback exchanges code for tokens
- Displays refresh token

**Step 4: Save Refresh Token**
```bash
# Add to .env
SCHWAB_REFRESH_TOKEN=your_refresh_token_here

# Restart app
uvicorn app.main:app --reload
```

**Step 5: Automatic Token Refresh**
- Access tokens cached in Redis (30min TTL)
- Refresh tokens cached in Redis (7 days TTL)
- Auto-refresh when access token expires

### Complete Workflow Example

```python
import asyncio
from datetime import date, timedelta
from app.services.provider_manager import provider_manager, DataType

async def analyze_ticker(ticker: str):
    """Fetch all available data for a ticker using provider hierarchy"""

    # 1. Fundamentals
    fundamentals_provider = provider_manager.get_provider(DataType.FUNDAMENTALS)
    if fundamentals_provider:
        profile = await fundamentals_provider.get_company_profile(ticker)
        print(f"Company: {profile['name']}")
        print(f"Market Cap: ${profile['marketCapitalization']}M")

    # 2. News (last 7 days)
    news_provider = provider_manager.get_provider(DataType.NEWS)
    if news_provider:
        news = await news_provider.get_company_news(
            ticker, from_date=date.today() - timedelta(days=7)
        )
        print(f"News articles: {len(news)}")

    # 3. EOD data (last 30 days)
    eod_provider = provider_manager.get_provider(DataType.EOD)
    if eod_provider:
        prices = await eod_provider.get_eod_prices(
            ticker, start_date=date.today() - timedelta(days=30)
        )
        print(f"EOD data points: {len(prices)}")
        if prices:
            latest = prices[-1]
            print(f"Latest close: ${latest['close']}")

    # 4. Real-time quote
    quote_provider = provider_manager.get_provider(DataType.QUOTE)
    if quote_provider:
        if hasattr(quote_provider, 'get_iex_realtime_price'):
            # Tiingo
            quote = await quote_provider.get_iex_realtime_price(ticker)
            print(f"Current price: ${quote['last']}")
        elif hasattr(quote_provider, 'get_quote'):
            # Schwab
            quote_data = await quote_provider.get_quote(ticker)
            quote = quote_data['quote']
            print(f"Last: ${quote['lastPrice']}")

    # 5. Intraday minute data
    minute_provider = provider_manager.get_provider(DataType.REALTIME_MINUTE)
    if minute_provider:
        try:
            if hasattr(minute_provider, 'get_price_history'):
                # Schwab
                history = await minute_provider.get_price_history(
                    ticker, period_type="day", period=1,
                    frequency_type="minute", frequency=1
                )
                candles = history.get('candles', [])
                print(f"Intraday candles: {len(candles)}")
            elif hasattr(minute_provider, 'get_bars'):
                # Alpaca
                bars = await minute_provider.get_bars(
                    ticker, timeframe="1Min", limit=100
                )
                print(f"Intraday bars: {len(bars)}")
        except Exception as e:
            print(f"Intraday error: {e}")

asyncio.run(analyze_ticker("SPY"))
```

### Error Handling Pattern

```python
from app.services.exceptions import (
    RateLimitError, DataNotFoundError, ProviderError
)
from app.services.tiingo import tiingo_client
import asyncio

async def fetch_with_retry(ticker: str, max_retries: int = 3):
    """Fetch data with custom retry logic"""
    for attempt in range(max_retries):
        try:
            return await tiingo_client.get_eod_prices(ticker)

        except RateLimitError as e:
            print(f"Rate limited. Waiting {e.retry_after}s...")
            await asyncio.sleep(e.retry_after)

        except DataNotFoundError:
            print(f"No data found for {ticker}")
            return None

        except ProviderError as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt  # Exponential backoff
                print(f"Provider error. Retry {attempt+1}/{max_retries} in {wait}s")
                await asyncio.sleep(wait)
            else:
                print(f"Failed after {max_retries} attempts")
                raise
```

### Files Created

```
app/services/
├── base_client.py          # HTTP client with retry (273 lines)
├── exceptions.py           # 9 exception types (63 lines)
├── tiingo.py              # Tiingo client (243 lines)
├── alpaca.py              # Alpaca client (210 lines)
├── databento.py           # Databento client (184 lines)
├── finnhub.py             # Finnhub client (298 lines)
├── schwab.py              # Schwab OAuth + API (372 lines)
└── provider_manager.py    # Fallback manager (157 lines)

app/api/v1/
├── providers.py           # Health endpoints (162 lines)
└── auth.py                # OAuth callback (202 lines)

tests/
└── test_providers.py      # Provider tests (262 lines)

Total: ~2,426 lines of code
```

### Success Criteria

- [x] All 5 provider clients implemented
- [x] OAuth 2.0 PKCE for Schwab with callback endpoint
- [x] Retry logic with exponential backoff
- [x] 9 exception types for error handling
- [x] Provider manager with fallback hierarchy
- [x] Health check endpoints
- [x] Token caching in Redis
- [x] Unit tests with mocks (~85% coverage)
- [x] All credentials configured
- [x] Documentation consolidated into single file

### Next Steps

1. **Schwab OAuth**: Visit `/api/v1/auth/schwab/authorize` to complete OAuth and obtain refresh token
2. **Phase 2.1**: Implement database models for storing fetched data
3. **Phase 2.2**: Implement data fetchers and APScheduler jobs

---

## Quick Reference

**Start App**:
```bash
source venv/bin/activate
uvicorn app.main:app --reload
```

**Check Health**:
```bash
curl http://localhost:8000/api/v1/providers/health | jq
```

**Run Tests**:
```bash
pytest tests/test_providers.py -v
```

**Schwab OAuth**:
```
http://localhost:8000/api/v1/auth/schwab/authorize
```

**API Docs**:
```
http://localhost:8000/docs
```

---

**Phase 1 Status**: ✅ **COMPLETE** (Both 1.1 and 1.2)

**Next**: Phase 2.1 - Database Models
