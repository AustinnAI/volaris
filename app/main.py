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
    # Startup: Initialize database connection
    await init_db()
    yield
    # Shutdown: Close database connection
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
    return {
        "status": "healthy",
        "database": "connected",  # TODO: Add actual DB health check
        "cache": "connected",     # TODO: Add actual Redis health check
    }


# Register API routers
from app.api.v1.providers import router as providers_router
from app.api.v1.auth import router as auth_router

app.include_router(providers_router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
