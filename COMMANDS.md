# Volaris - Quick Command Reference

## Development Commands

### Virtual Environment

```bash
# Activate virtual environment
source venv/bin/activate

# Deactivate
deactivate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker Commands

```bash
# Build and run with Docker Compose
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop all services
docker-compose down

# Remove volumes
docker-compose down -v

# Build Docker image only
docker build -t volaris:latest .

# Run Docker container
docker run -p 8000:8000 --env-file .env volaris:latest
```

### Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_config.py

# Run with coverage
pytest --cov=app --cov-report=html

# Run with coverage (terminal report)
pytest --cov=app --cov-report=term-missing

# Open coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Code Quality

```bash
# Format code with Black
black app/ tests/

# Check formatting (no changes)
black --check app/ tests/

# Lint with Ruff
ruff check app/ tests/

# Fix auto-fixable issues
ruff check --fix app/ tests/

# Type checking with MyPy
mypy app/ --ignore-missing-imports
```

### Database Commands

```bash
# Initialize Alembic (first time only)
alembic init alembic

# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Run migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View current version
alembic current

# View migration history
alembic history
```

### Git Commands

```bash
# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit changes
git commit -m "Phase 1.1 complete: Project setup"

# Create and push to GitHub
git remote add origin https://github.com/yourusername/volaris.git
git branch -M main
git push -u origin main

# Create a new branch
git checkout -b feature/api-integrations
```

### Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit environment variables
nano .env  # or vim, code, etc.

# Load environment variables
source .env  # bash/zsh
set -a; source .env; set +a  # export all variables
```

### Useful Checks

```bash
# Check Python version
python --version

# Check installed packages
pip list

# Check for outdated packages
pip list --outdated

# Verify FastAPI import
python -c "from app.main import app; print('✅ OK')"

# Check database connection
python -c "from app.config import settings; print(settings.DATABASE_URL)"

# Test Redis connection (requires running server)
python -c "from app.utils.cache import cache; import asyncio; asyncio.run(cache.set('test', 'value'))"
```

### API Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Root endpoint
curl http://localhost:8000/

# Interactive docs
open http://localhost:8000/docs  # macOS
xdg-open http://localhost:8000/docs  # Linux
```

### Development Workflow

```bash
# 1. Create feature branch
git checkout -b feature/my-feature

# 2. Make changes
# ... edit files ...

# 3. Format and lint
black app/ tests/
ruff check --fix app/ tests/

# 4. Run tests
pytest -v

# 5. Commit changes
git add .
git commit -m "feat: Add my feature"

# 6. Push to GitHub
git push origin feature/my-feature

# 7. Create Pull Request on GitHub
```

### Troubleshooting

```bash
# Clear Python cache
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Reset database (CAUTION: deletes all data)
alembic downgrade base
alembic upgrade head

# Clear Redis cache (if using local Redis)
redis-cli FLUSHALL

# Rebuild Docker containers
docker-compose down -v
docker-compose build --no-cache
docker-compose up

# Check for port conflicts
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows
```

### Performance Profiling

```bash
# Profile with py-spy (install: pip install py-spy)
py-spy record -o profile.svg -- python -m uvicorn app.main:app

# Memory profiling (install: pip install memory_profiler)
python -m memory_profiler app/main.py
```

### Logs & Monitoring

```bash
# View application logs
tail -f logs/volaris.log

# Docker logs
docker-compose logs -f api

# Follow logs for specific service
docker logs -f volaris-api

# Export logs
docker-compose logs > logs.txt
```

---

## CI/CD Commands

### GitHub Actions

```bash
# Trigger CI manually (if configured)
gh workflow run ci.yml

# View workflow runs
gh run list

# View specific run
gh run view <run-id>

# Download artifacts
gh run download <run-id>
```

### Deployment (Render/Fly.io)

```bash
# Render - trigger deployment
curl -X POST https://api.render.com/v1/services/$SERVICE_ID/deploys \
  -H "Authorization: Bearer $RENDER_API_KEY"

# Fly.io - deploy
flyctl deploy

# Fly.io - view logs
flyctl logs

# Fly.io - ssh into container
flyctl ssh console
```

---

## Useful Scripts

### Create Test Data

```bash
# Run Python script to seed database
python scripts/seed_db.py

# Or use interactive Python
python
>>> from app.db.database import async_session_maker
>>> # ... add test data
```

### Backup Database

```bash
# Export Postgres dump (if using local DB)
docker-compose exec db-local pg_dump -U volaris volaris_dev > backup.sql

# Restore
docker-compose exec -T db-local psql -U volaris volaris_dev < backup.sql
```

---

## Quick Links

- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Neon Dashboard**: https://console.neon.tech
- **Upstash Console**: https://console.upstash.com
- **Sentry Dashboard**: https://sentry.io
- **GitHub Actions**: https://github.com/yourusername/volaris/actions

---

## Environment-Specific Commands

### Development

```bash
export ENVIRONMENT=development
uvicorn app.main:app --reload
```

### Staging

```bash
export ENVIRONMENT=staging
uvicorn app.main:app --workers 2
```

### Production

```bash
export ENVIRONMENT=production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```
