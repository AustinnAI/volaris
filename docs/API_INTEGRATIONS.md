# API Integrations Overview

**Last Updated:** October 12, 2025
**Project Phase:** Phase 3 Complete (Discord Bot Live)

## External APIs (Market Data & Services)

### 1. Schwab API (Primary - Real-time Options Data)
- **Purpose:** Real-time 1m/5m price data, options chains, OAuth authentication
- **Usage:** Primary data source for live options analysis and strategy recommendations
- **Status:** ✅ Configured (requires OAuth refresh token)
- **Endpoint:** `https://api.schwabapi.com`
- **Client:** [app/services/schwab.py](../app/services/schwab.py)
- **Auth:** OAuth 2.0 with PKCE flow
- **Environment Variables:**
  - `SCHWAB_APP_KEY`
  - `SCHWAB_SECRET_KEY`
  - `SCHWAB_REDIRECT_URI`
  - `SCHWAB_REFRESH_TOKEN`

### 2. Tiingo API (EOD Data)
- **Purpose:** End-of-day historical price data
- **Usage:** Historical backtesting, EOD sync jobs
- **Status:** ✅ Configured
- **Endpoint:** `https://api.tiingo.com`
- **Client:** [app/services/tiingo.py](../app/services/tiingo.py)
- **Auth:** API Key
- **Environment Variables:**
  - `TIINGO_API_KEY`

### 3. Alpaca API (Historical Data)
- **Purpose:** Minute-delayed historical bars
- **Usage:** Historical backfills, alternative data source
- **Status:** ✅ Configured (paper trading endpoint)
- **Endpoint:** `https://paper-api.alpaca.markets`
- **Client:** [app/services/alpaca.py](../app/services/alpaca.py)
- **Auth:** API Key + Secret
- **Environment Variables:**
  - `ALPACA_API_KEY`
  - `ALPACA_API_SECRET`

### 4. Databento API (Historical Backfills)
- **Purpose:** High-quality historical options and equity data
- **Usage:** Deep historical analysis, backtesting
- **Status:** ✅ Configured
- **Endpoint:** `https://hist.databento.com`
- **Client:** [app/services/databento.py](../app/services/databento.py)
- **Auth:** API Key
- **Environment Variables:**
  - `DATABENTO_API_KEY`

### 5. Finnhub API (Fundamentals & News)
- **Purpose:** Company fundamentals, earnings, news sentiment
- **Usage:** Fundamental analysis layer (future phases)
- **Status:** ✅ Configured
- **Endpoint:** `https://finnhub.io/api/v1`
- **Client:** [app/services/finnhub.py](../app/services/finnhub.py)
- **Auth:** API Key
- **Environment Variables:**
  - `FINNHUB_API_KEY`
  - `FINNHUB_WEBHOOK_SECRET` (optional)

### 6. Discord API (Bot Integration)
- **Purpose:** Slash commands, interactive embeds, user interface
- **Usage:** `/plan` command for live strategy recommendations
- **Status:** ✅ **LIVE** on Render (deployed as background worker)
- **Library:** `discord.py==2.4.0`
- **Client:** [app/alerts/discord_bot.py](../app/alerts/discord_bot.py)
- **Features:**
  - `/plan` slash command with 6 parameters
  - Symbol autocomplete (515 S&P 500 + ETF tickers)
  - Rich embeds with trade details
  - Interactive "Show More Candidates" button
  - Rate limiting (3 commands/minute per user)
- **Environment Variables:**
  - `DISCORD_BOT_TOKEN`
  - `DISCORD_SERVER_ID` (Guild ID: 1413243234569818346)
  - `DISCORD_BOT_ENABLED`
  - `API_BASE_URL` (points to Volaris API)

---

## Infrastructure APIs

### 7. PostgreSQL Database (Neon/Supabase)
- **Purpose:** Persistent storage for tickers, prices, trades, IV metrics
- **Status:** ✅ Active
- **Connection:** Async SQLAlchemy with asyncpg driver
- **Models:** [app/db/models.py](../app/db/models.py)
- **Environment Variables:**
  - `DATABASE_URL`
  - `DB_POOL_SIZE` (default: 5)
  - `DB_MAX_OVERFLOW` (default: 10)

### 8. Redis Cache (Upstash)
- **Purpose:** Rate limiting, caching, session management
- **Status:** ✅ Active
- **Connection:** Upstash REST API
- **Environment Variables:**
  - `UPSTASH_REDIS_REST_URL`
  - `UPSTASH_REDIS_REST_TOKEN`
  - `REDIS_TTL_DEFAULT` (default: 300 seconds)

### 9. Sentry (Optional - Error Tracking)
- **Purpose:** Production error monitoring and alerting
- **Status:** ⚠️ Optional (controlled by `SENTRY_DSN` env var)
- **Integration:** `sentry-sdk[fastapi]==2.17.0`
- **Environment Variables:**
  - `SENTRY_DSN` (optional)

---

## Internal APIs (Volaris FastAPI Application)

### 10. Volaris REST API
- **Production URL:** `https://volaris-yz19.onrender.com`
- **Local URL:** `http://localhost:8000`
- **Deployment:** Render (Web Service + Background Worker)

#### Current Endpoints

**Phase 3.3 - Strategy Recommendation**
```
POST /api/v1/strategy/recommend
```
- Returns ranked strategy recommendations based on IV regime, bias, and constraints
- Used by Discord bot `/plan` command
- Request: `{underlying_symbol, bias, target_dte, dte_tolerance, objectives, constraints}`
- Response: `{recommendations[], underlying_symbol, underlying_price, iv_regime, chosen_strategy_family}`

**Phase 3.2 - Strike Selection**
```
POST /api/v1/strike-selection/select
```
- Selects optimal strikes and spread width for vertical spreads
- Returns strike prices, width, premiums, and quality scores
- Request: `{underlying_symbol, strategy_type, target_dte, ...}`
- Response: `{long_strike, short_strike, width_points, width_dollars, ...}`

**Phase 3.1 - Trade Planning**
```
POST /api/v1/trade-planner/calculate/vertical-spread
POST /api/v1/trade-planner/calculate/long-option
POST /api/v1/trade-planner/position-size
```
- Calculate P/L, breakeven, R:R for strategies
- Position sizing based on account size and max risk
- Returns max profit/loss, breakeven points, recommended contracts

**Health Check**
```
GET /health
```
- Database and Redis connectivity check
- Returns service status and version

---

## Architecture Flow

### Discord Bot → Volaris API → Schwab API

```
Discord User (in server 1413243234569818346)
         ↓
    /plan SPY bullish 30
         ↓
Discord Bot (Render Background Worker)
         ↓
POST https://volaris-yz19.onrender.com/api/v1/strategy/recommend
         ↓
Volaris API (Render Web Service)
         ↓
    Strategy Recommender (Phase 3.3)
         ↓
    Strike Selection Engine (Phase 3.2)
         ↓
Schwab API (Options Chain Data)
         ↓
    Trade Planner (Phase 3.1)
         ↓
Discord Embed Response with 3 ranked recommendations
```

---

## API Status Summary

| API | Status | Purpose | Phase | Rate Limits |
|-----|--------|---------|-------|-------------|
| **Schwab** | ✅ Configured | Real-time options data | 1.2 | TBD (OAuth refresh) |
| **Tiingo** | ✅ Configured | EOD historical data | 1.2 | Free tier limits |
| **Alpaca** | ✅ Configured | Minute historical bars | 1.2 | Free tier limits |
| **Databento** | ✅ Configured | Deep historical data | 1.2 | Pay-per-use |
| **Finnhub** | ✅ Configured | Fundamentals & news | 1.2 | 60 calls/min (free) |
| **Discord** | ✅ **LIVE** | User interface (bot) | 3.x | Global rate limits |
| **Postgres** | ✅ Active | Database | 1.1 | Connection pooling |
| **Redis** | ✅ Active | Cache & rate limiting | 1.1 | Upstash limits |
| **Sentry** | ⚠️ Optional | Error tracking | 1.1 | Event-based limits |

---

## Active Data Sources (Current Usage)

**Most Actively Used:**
1. **Schwab API** - Options chain data for strike selection and strategy recommendations
2. **Discord API** - User interactions via `/plan` command
3. **Volaris Internal API** - Strategy logic, calculations, and recommendations
4. **PostgreSQL** - Data persistence (tickers, prices, IV metrics)
5. **Redis** - Rate limiting for Discord bot and API caching

**Configured but Less Active:**
- Tiingo, Alpaca, Databento - Historical data (for future backfilling jobs)
- Finnhub - Fundamentals (for future analysis features)

---

## Environment Variables Reference

### Required for Production
```bash
# Database & Cache
DATABASE_URL=postgresql://...
UPSTASH_REDIS_REST_URL=https://...
UPSTASH_REDIS_REST_TOKEN=...

# Primary Market Data
SCHWAB_APP_KEY=...
SCHWAB_SECRET_KEY=...
SCHWAB_REDIRECT_URI=https://volaris-yz19.onrender.com/auth/schwab/callback
SCHWAB_REFRESH_TOKEN=...

# Alternative Data Sources
TIINGO_API_KEY=...
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
DATABENTO_API_KEY=...
FINNHUB_API_KEY=...

# Discord Bot (Background Worker)
DISCORD_BOT_TOKEN=...
DISCORD_SERVER_ID=1413243234569818346
DISCORD_BOT_ENABLED=true
API_BASE_URL=https://volaris-yz19.onrender.com

# App Configuration
ENV=production
LOG_LEVEL=INFO
```

### Optional
```bash
SENTRY_DSN=https://...  # Error tracking
FINNHUB_WEBHOOK_SECRET=...  # Webhook validation
```

---

## Next Phase API Plans

### Phase 4 - Real-time Market Structure
- **Schwab WebSocket** - Real-time price streaming (1m/5m bars)
- **Redis Pub/Sub** - Real-time alert distribution

### Phase 5 - FinBERT Sentiment
- **HuggingFace Inference API** - FinBERT model for news sentiment
- Alternative: Local model deployment

### Phase 8 - Full Discord Integration
- **Discord Webhooks** - Proactive alerts and notifications
- **Discord Interactions** - More slash commands and buttons

---

## Configuration Files

- **API Configuration:** [app/config.py](../app/config.py)
- **Service Clients:** [app/services/](../app/services/)
- **API Routes:** [app/api/v1/](../app/api/v1/)
- **Discord Bot:** [app/alerts/discord_bot.py](../app/alerts/discord_bot.py)
- **Environment Template:** [.env.example](../.env.example)

---

## Troubleshooting

### Schwab API Issues
- Check `SCHWAB_REFRESH_TOKEN` is valid
- OAuth tokens expire; re-authenticate via `/auth/schwab/login` endpoint
- Rate limits: implement exponential backoff (handled in client)

### Discord Bot Issues
- Verify `DISCORD_BOT_TOKEN` and `DISCORD_SERVER_ID` are correct
- Check bot has application.commands scope in Discord Developer Portal
- Commands sync to guild instantly; global commands take up to 1 hour
- Rate limit: 3 commands/minute per user (configurable in bot code)

### API Connection Issues
- Health check endpoint: `GET https://volaris-yz19.onrender.com/health`
- Check Render service logs for database/Redis connectivity
- Verify all required environment variables are set

---

## Documentation

- [Roadmap](./roadmap.md) - Full project phases and status
- [Phase 3 Details](./PHASE_3.md) - Trade planner and options engine
- [Discord Bot Guide](./DISCORD_BOT.md) - Bot setup and usage
- [Credentials Guide](./CREDENTIALS.md) - API key setup instructions
