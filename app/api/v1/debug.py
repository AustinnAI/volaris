"""Debug and diagnostics endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
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
