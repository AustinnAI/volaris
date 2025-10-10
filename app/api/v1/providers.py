"""
Provider Health & Status Endpoints
Check provider availability and health status.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, List
from datetime import datetime

from app.services.provider_manager import provider_manager, DataType

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/health")
async def get_providers_health() -> Dict:
    """
    Check health status of all configured providers.

    Returns:
        Health status for each provider

    Example response:
        {
            "timestamp": "2024-01-15T10:30:00Z",
            "providers": {
                "schwab": {
                    "configured": true,
                    "healthy": true
                },
                "alpaca": {
                    "configured": true,
                    "healthy": true
                },
                "tiingo": {
                    "configured": true,
                    "healthy": true
                },
                "databento": {
                    "configured": true,
                    "healthy": false
                },
                "finnhub": {
                    "configured": true,
                    "healthy": true
                }
            },
            "summary": {
                "total": 5,
                "healthy": 4,
                "unhealthy": 1
            }
        }
    """
    health_status = await provider_manager.get_provider_health()

    providers_detail = {}
    for name, status in health_status.items():
        is_configured = provider_manager.providers.get(name) is not None
        providers_detail[name] = {
            "configured": is_configured,
            "healthy": status if is_configured else False,
        }

    healthy_count = sum(
        1
        for name, status in health_status.items()
        if provider_manager.providers.get(name) is not None and status is True
    )
    total_count = len(providers_detail)

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "providers": providers_detail,
        "summary": {
            "total": total_count,
            "healthy": healthy_count,
            "unhealthy": total_count - healthy_count,
        },
    }


@router.get("/configured")
async def get_configured_providers() -> Dict:
    """
    Get list of configured providers.

    Returns:
        List of configured provider names

    Example response:
        {
            "configured": ["schwab", "tiingo", "alpaca", "finnhub"],
            "count": 4
        }
    """
    configured = provider_manager.get_configured_providers()

    return {
        "configured": configured,
        "count": len(configured),
    }


@router.get("/capabilities")
async def get_provider_capabilities() -> Dict:
    """
    Get available data types and their providers.

    Returns:
        Data types with available providers

    Example response:
        {
            "capabilities": {
                "realtime_minute": ["schwab", "alpaca"],
                "eod": ["tiingo"],
                "historical": ["databento", "alpaca"],
                "fundamentals": ["finnhub"],
                "news": ["finnhub"],
                "quote": ["schwab", "alpaca", "tiingo"],
                "options": ["schwab"]
            }
        }
    """
    available = provider_manager.get_available_data_types()

    # Convert enum keys to strings
    capabilities = {
        data_type.value: providers for data_type, providers in available.items()
    }

    return {"capabilities": capabilities}


@router.get("/hierarchy")
async def get_provider_hierarchy() -> Dict:
    """
    Get the complete provider hierarchy by data type.

    Returns:
        Full hierarchy configuration

    Example response:
        {
            "hierarchy": {
                "realtime_minute": {
                    "primary": "schwab",
                    "fallback": ["alpaca"]
                },
                "eod": {
                    "primary": "tiingo",
                    "fallback": []
                },
                ...
            }
        }
    """
    hierarchy = {}

    for data_type, provider_list in provider_manager.hierarchy.items():
        hierarchy[data_type.value] = {
            "primary": provider_list[0] if provider_list else None,
            "fallback": provider_list[1:] if len(provider_list) > 1 else [],
        }

    return {"hierarchy": hierarchy}


@router.get("/{provider_name}/health")
async def check_provider_health(provider_name: str) -> Dict:
    """
    Check health of a specific provider.

    Args:
        provider_name: Provider name (schwab, alpaca, tiingo, etc.)

    Returns:
        Provider health status

    Example response:
        {
            "provider": "schwab",
            "configured": true,
            "healthy": true,
            "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    provider_name = provider_name.lower()

    if provider_name not in provider_manager.providers:
        raise HTTPException(
            status_code=404, detail=f"Provider '{provider_name}' not found"
        )

    client = provider_manager.providers[provider_name]

    if client is None:
        return {
            "provider": provider_name,
            "configured": False,
            "healthy": False,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "message": "Provider not configured",
        }

    try:
        is_healthy = await client.health_check()
        return {
            "provider": provider_name,
            "configured": True,
            "healthy": is_healthy,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        return {
            "provider": provider_name,
            "configured": True,
            "healthy": False,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "error": str(e),
        }
