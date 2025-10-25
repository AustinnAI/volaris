"""Debug and diagnostics endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.utils.memory_profiler import get_memory_summary

router = APIRouter(prefix="/debug", tags=["debug"])


class MemoryUsageResponse(BaseModel):
    """Memory usage response model."""

    current_usage: dict
    top_objects: list[dict]
    large_objects: list[dict]
    gc_stats: dict


@router.get("/memory", response_model=MemoryUsageResponse)
async def get_memory_diagnostics() -> dict:
    """Get detailed memory usage diagnostics.

    Returns:
        Memory usage breakdown including:
        - Current process memory (RSS, VMS, %)
        - Top 20 object types by count
        - Objects over 1MB
        - Garbage collection stats

    Note:
        This endpoint is only available in development/staging.
        Disable in production for security.
    """
    if settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=403,
            detail="Memory diagnostics disabled in production",
        )

    return get_memory_summary()


@router.get("/health")
async def debug_health() -> dict:
    """Debug health check with environment info.

    Returns:
        Environment, memory usage, and configuration status
    """
    memory = get_memory_summary()["current_usage"]

    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "memory_mb": memory["rss_mb"],
        "memory_percent": memory["percent"],
        "scheduler_enabled": settings.SCHEDULER_ENABLED,
    }


@router.get("/db-tables")
async def check_db_tables(db: AsyncSession = Depends(get_db)) -> dict:
    """Check which tables exist in the database.

    Returns:
        List of all tables and their row counts
    """
    # Get all tables
    result = await db.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """
        )
    )
    tables = [row[0] for row in result.fetchall()]

    # Check if news_articles exists
    news_table_exists = "news_articles" in tables

    # Get alembic version
    alembic_version = None
    if "alembic_version" in tables:
        result = await db.execute(text("SELECT version_num FROM alembic_version"))
        row = result.fetchone()
        if row:
            alembic_version = row[0]

    # Get row counts for key tables
    table_counts = {}
    for table in ["news_articles", "tickers", "price_bars"]:
        if table in tables:
            result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            table_counts[table] = count

    return {
        "all_tables": tables,
        "news_articles_exists": news_table_exists,
        "alembic_version": alembic_version,
        "table_counts": table_counts,
    }
