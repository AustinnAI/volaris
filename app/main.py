"""
FastAPI Application Entrypoint
Main entry point for the Volaris trading intelligence platform.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.config import settings
from app.db.database import init_db, close_db
from app.workers import create_scheduler


# Initialize Sentry for error tracking
SENTRY_DSN = (settings.SENTRY_DSN or "").strip()

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=1.0 if settings.ENVIRONMENT == "development" else 0.1,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    scheduler = None
    await init_db()
    try:
        if settings.SCHEDULER_ENABLED:
            scheduler = create_scheduler()
            scheduler.start()
        yield
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)
        await close_db()


# Initialize FastAPI application
app = FastAPI(
    title="Volaris Trading Intelligence Platform",
    description="Modular trading intelligence and decision-support system for short-dated options trades",
    version="0.1.0",
    lifespan=lifespan,
)


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint - API health check"""
    return {
        "status": "online",
        "service": "Volaris Trading Intelligence Platform",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    Returns system status and component health.
    """
    from app.db.database import engine
    from sqlalchemy import text

    health_status = {
        "status": "healthy",
        "database": "disconnected",
        "cache": "unknown"
    }

    # Check database connection
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"error: {str(e)[:50]}"
        health_status["status"] = "degraded"

    # Check Redis (if configured)
    try:
        from app.config import settings
        if hasattr(settings, 'REDIS_URL') and settings.REDIS_URL:
            import redis.asyncio as aioredis
            redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await redis_client.ping()
            health_status["cache"] = "connected"
            await redis_client.close()
        else:
            health_status["cache"] = "not_configured"
    except Exception as e:
        health_status["cache"] = f"error: {str(e)[:50]}"
        # Redis is optional, don't degrade status

    return health_status


# Register API routers
from app.api.v1.providers import router as providers_router
from app.api.v1.auth import router as auth_router
from app.api.v1.trade_planner import router as trade_planner_router
from app.api.v1.strike_selection import router as strike_selection_router
from app.api.v1.strategy_recommendation import router as strategy_router

app.include_router(providers_router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(trade_planner_router, prefix=settings.API_V1_PREFIX)
app.include_router(strike_selection_router, prefix=settings.API_V1_PREFIX)
app.include_router(strategy_router, prefix=settings.API_V1_PREFIX)
