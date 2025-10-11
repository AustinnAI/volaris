# Volaris - Credentials & Configuration Summary

> **⚠️ IMPORTANT: This file contains credential information. Keep it secure and never commit to public repositories.**

---

## ✅ Configured Services

### 1. PostgreSQL Database (Neon)

**Status**: ✅ Active and configured

```
Host:     ep-holy-feather-adn3mcsp-pooler.c-2.us-east-1.aws.neon.tech
Database: neondb
User:     neondb_owner
Region:   us-east-1 (AWS)
SSL:      Required
Driver:   asyncpg (async)
```

**Connection String (in .env)**:
```
DATABASE_URL=postgresql://neondb_owner:npg_lSficVj7Ezu1@ep-holy-feather-adn3mcsp-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require
```

**Dashboard**: https://console.neon.tech

---

### 2. Redis Cache (Upstash)

**Status**: ✅ Active and configured

```
Instance: alert-hermit-21942
Region:   Global
Type:     REST API
Endpoint: https://alert-hermit-21942.upstash.io
```

**Configuration (in .env)**:
```
UPSTASH_REDIS_REST_URL=https://alert-hermit-21942.upstash.io
UPSTASH_REDIS_REST_TOKEN=AVW2AAIncDJiN2Q4MzA0Y2FkYzU0NTFkOWI4YmNjZDg5NTNiMjlmY3AyMjE5NDI
```

**Dashboard**: https://console.upstash.com

---

### 3. Sentry Monitoring

**Status**: ⏳ Ready to configure

Add Sentry DSN when you create a project:
```
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
```

**Setup Steps**:
1. Create account at https://sentry.io
2. Create new project (select FastAPI/Python)
3. Copy DSN to .env file
4. Restart application

---

## 🔐 Security Checklist

- [x] `.env` file excluded from git (.gitignore)
- [x] `.env.example` template created (no secrets)
- [x] SSL/TLS enabled for database connection
- [x] Connection pooling configured
- [x] Rate limiting enabled
- [ ] Sentry DSN configured (when ready)
- [ ] GitHub repository secrets configured (for CI/CD)

---

## 📝 GitHub Secrets (Required for CI/CD)

When you push to GitHub, configure these repository secrets:

**Settings → Secrets and variables → Actions → New repository secret**

```
Name: UPSTASH_REDIS_REST_URL
Value: https://alert-hermit-21942.upstash.io

Name: UPSTASH_REDIS_REST_TOKEN
Value: AVW2AAIncDJiN2Q4MzA0Y2FkYzU0NTFkOWI4YmNjZDg5NTNiMjlmY3AyMjE5NDI

Name: DATABASE_URL (optional, for CI tests)
Value: [Use test database or mock]

Name: SENTRY_DSN (when configured)
Value: [Your Sentry DSN]

Name: SENTRY_AUTH_TOKEN (for deployment tracking)
Value: [Your Sentry auth token]

Name: SENTRY_ORG
Value: [Your Sentry organization slug]

Name: SENTRY_PROJECT
Value: [Your Sentry project slug]
```

---

## 🚀 Deployment Credentials (Phase 10)

### Render

When deploying to Render:

```
Name: RENDER_API_KEY
Value: [Get from Render Dashboard → Account Settings → API Keys]

Name: RENDER_SERVICE_ID
Value: [Get from Render service URL]
```

### Fly.io

When deploying to Fly.io:

```
Name: FLY_API_TOKEN
Value: [Get via: flyctl auth token]
```

---

## 📡 API Keys (Phase 1.2 - To Be Configured)

### Schwab API
```
SCHWAB_CLIENT_ID=
SCHWAB_CLIENT_SECRET=
SCHWAB_REDIRECT_URI=https://localhost:8000/callback
```
**Get credentials**: https://developer.schwab.com

### Tiingo
```
TIINGO_API_KEY=
```
**Get API key**: https://www.tiingo.com/account/api/token

### Alpaca
```
ALPACA_API_KEY=
ALPACA_API_SECRET=
```
**Get credentials**: https://app.alpaca.markets/paper/dashboard/overview

### Databento
```
DATABENTO_API_KEY=
```
**Get API key**: https://databento.com/portal/keys

### Finnhub
```
FINNHUB_API_KEY=
```
**Get API key**: https://finnhub.io/dashboard

---

## 🤖 Discord Integration (Phase 8)

### Discord Bot
```
DISCORD_BOT_TOKEN=
DISCORD_SERVER_ID=
DISCORD_WEBHOOK_URL=
```

**Setup Steps**:
1. Go to https://discord.com/developers/applications
2. Create New Application → Name: "Volaris Trading Bot"
3. Bot tab → Create bot → Copy token
4. OAuth2 → URL Generator → Select bot + slash commands
5. Add bot to your server using generated URL

---

## 🔄 Credential Rotation

### When to Rotate
- Immediately if credentials are exposed
- Every 90 days for production (recommended)
- After team member departure
- After security incident

### How to Rotate

**Database (Neon)**:
1. Neon Console → Settings → Reset password
2. Update `.env` and GitHub secrets
3. Redeploy application

**Redis (Upstash)**:
1. Upstash Console → Database → Credentials → Rotate
2. Update `.env` and GitHub secrets
3. Redeploy application

**API Keys**:
1. Provider dashboard → Revoke old key → Generate new
2. Update `.env` immediately
3. Update GitHub secrets if used in CI/CD

---

## 📞 Support Contacts

- **Neon Support**: https://neon.tech/docs/introduction/support
- **Upstash Support**: https://upstash.com/docs
- **Sentry Support**: https://sentry.io/support/

---

## 🔍 Verification Commands

```bash
# Test database connection
python -c "from app.config import settings; print(settings.DATABASE_URL[:50] + '...')"

# Test Redis connection
python -c "import asyncio; from app.utils.cache import cache; asyncio.run(cache.set('test', 'ok')); print('✅ Redis OK')"

# Verify all settings
python -c "from app.config import settings; print(f'ENV: {settings.ENVIRONMENT}'); print(f'DB: {settings.DATABASE_URL[:30]}...'); print(f'Redis: {settings.UPSTASH_REDIS_REST_URL}')"
```

---

**Last Updated**: Phase 1.1 Complete
**Next Review**: Before Phase 1.2 API integration
