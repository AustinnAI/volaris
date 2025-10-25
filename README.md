# Volaris – Trading Intelligence & Alert Platform

> **Modular trading intelligence and decision-support system for short-dated (2-7 DTE) options trades**

[![CI/CD](https://github.com/yourusername/volaris/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/volaris/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## 🎯 Overview

Volaris combines multi-provider market data (Schwab, Tiingo, Alpaca, Databento, Finnhub) with rule-based and ML-driven analytics to generate trade setups, volatility insights, and Discord-delivered alerts for options trading.

### Core Capabilities

- **📊 Trade Planner**: Build 2-7 DTE trade plans with auto-computed breakevens, max P/L, risk-reward, and position sizing
- **📈 Volatility Analysis**: Track IV/IVR, term structure, and expected move with IV crush risk detection
- **🎯 Market Structure Alerts**: Identify BSL/SSL sweeps, FVG tags, VWAP & 200-EMA tests
- **🛡️ Risk Management**: PDT tracking, position monitoring, and event risk guardrails
- **🤖 Discord Integration**: Slash commands for trade execution and alerts

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (optional)
- PostgreSQL (or Neon/Supabase account)
- Redis (or Upstash account)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/volaris.git
   cd volaris
   ```

2. **Set up environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Install dependencies**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   uvicorn app.main:app --reload
   ```

   Or with Docker:
   ```bash
   docker-compose up --build
   ```

5. **Access the API**
   - API: http://localhost:8000
   - Docs: http://localhost:8000/docs
   - Health: http://localhost:8000/health

---

## 📁 Project Structure

```
volaris/
├── app/
│   ├── main.py              # FastAPI entrypoint
│   ├── config.py            # Configuration management
│   ├── db/                  # Database models & migrations
│   ├── services/            # API clients (Schwab, Tiingo, etc.)
│   ├── core/                # Business logic (trade planning, volatility)
│   ├── alerts/              # Discord integration
│   ├── workers/             # Background jobs (APScheduler)
│   └── utils/               # Utilities (cache, rate limiter, logger)
├── tests/                   # Test suite
├── docs/                    # Documentation
├── .github/workflows/       # CI/CD pipelines
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 🔧 Configuration

### Environment Variables

Key configuration options (see [.env.example](.env.example)):

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/volaris

# Redis Cache
UPSTASH_REDIS_REST_URL=https://your-redis.upstash.io
UPSTASH_REDIS_REST_TOKEN=your_token

# Monitoring
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id

# API Keys (Phase 1.2)
SCHWAB_CLIENT_ID=your_client_id
TIINGO_API_KEY=your_api_key
ALPACA_API_KEY=your_api_key
DATABENTO_API_KEY=your_api_key
FINNHUB_API_KEY=your_api_key

# Discord (Phase 8)
DISCORD_BOT_TOKEN=your_bot_token
DISCORD_WEBHOOK_URL=your_webhook_url
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_config.py
```

---

## 📦 Deployment

### Docker Production Build

```bash
docker build -t volaris:latest .
docker run -p 8000:8000 --env-file .env volaris:latest
```

### Render/Fly.io

The project includes GitHub Actions workflows for automated deployment:

- **CI Pipeline**: `.github/workflows/ci.yml` - Runs tests, linting, and security scans
- **Deploy Pipeline**: `.github/workflows/deploy.yml` - Deploys to production on push to main

Configure secrets in GitHub repository settings:
- `RENDER_API_KEY` / `FLY_API_TOKEN`
- `SENTRY_AUTH_TOKEN`
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`

---

## 🗺️ Roadmap

See [docs/roadmap.md](docs/roadmap.md) for detailed development roadmap.

### Current Phase: 1.1 - Project Setup ✅

- [x] FastAPI application structure
- [x] Environment management
- [x] Docker & docker-compose
- [x] PostgreSQL (Neon) configuration
- [x] Redis (Upstash) integration
- [x] GitHub Actions CI/CD
- [x] Sentry monitoring setup

### Next: Phase 1.2 - API Integrations

---

## 🛠️ Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Backend** | FastAPI, Python 3.11, SQLAlchemy (async) |
| **Database** | PostgreSQL (Neon/Supabase) |
| **Cache** | Redis (Upstash) |
| **Data Providers** | Schwab, Tiingo, Alpaca, Databento, Finnhub |
| **Analytics** | Pandas, NumPy |
| **Alerts** | Discord (Webhooks + Slash Commands) |
| **Monitoring** | Sentry |
| **Infrastructure** | Docker, GitHub Actions, Render/Fly.io |

---

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details

---

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines and code of conduct.

---

## 📧 Support

For issues and questions:
- GitHub Issues: [Create an issue](https://github.com/yourusername/volaris/issues)
- Documentation: [docs/](docs/)

---

**Built with ❤️ for options traders**
# Force redeploy
