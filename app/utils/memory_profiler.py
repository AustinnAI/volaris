"""Memory profiling utilities for diagnosing memory usage."""

import gc
import sys
from collections import defaultdict
from typing import Any

import psutil


def get_memory_usage() -> dict[str, float]:
    """Get current process memory usage in MB.

    Returns:
        Dictionary with memory metrics:
        - rss: Resident Set Size (physical memory)
        - vms: Virtual Memory Size
        - percent: Percentage of total system memory
        - available: Available system memory
    """
    process = psutil.Process()
    memory_info = process.memory_info()

    return {
        "rss_mb": round(memory_info.rss / 1024 / 1024, 2),
        "vms_mb": round(memory_info.vms / 1024 / 1024, 2),
        "percent": round(process.memory_percent(), 2),
        "available_mb": round(psutil.virtual_memory().available / 1024 / 1024, 2),
        "total_mb": round(psutil.virtual_memory().total / 1024 / 1024, 2),
    }


def get_object_memory_breakdown(limit: int = 20) -> list[dict[str, Any]]:
    """Get memory usage breakdown by object type.

    Args:
        limit: Number of top object types to return

    Returns:
        List of dictionaries with object type, count, and estimated size
    """
    gc.collect()  # Force garbage collection first

    # Count objects by type
    type_counts: dict[str, int] = defaultdict(int)
    for obj in gc.get_objects():
        type_name = type(obj).__name__
        type_counts[type_name] += 1

    # Sort by count and get top N
    sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

    return [
        {
            "type": type_name,
            "count": count,
            "avg_size_bytes": sys.getsizeof(type_name),
        }
        for type_name, count in sorted_types
    ]


def get_large_objects(threshold_mb: float = 1.0, limit: int = 10) -> list[dict[str, Any]]:
    """Find large objects in memory.

    Args:
        threshold_mb: Minimum size in MB to include
        limit: Maximum number of objects to return

    Returns:
        List of large objects with type, size, and representation
    """
    gc.collect()
    threshold_bytes = threshold_mb * 1024 * 1024

    large_objects = []
    for obj in gc.get_objects():
        size = sys.getsizeof(obj)
        if size >= threshold_bytes:
            large_objects.append(
                {
                    "type": type(obj).__name__,
                    "size_mb": round(size / 1024 / 1024, 2),
                    "repr": str(obj)[:100] if hasattr(obj, "__str__") else "N/A",
                }
            )

    # Sort by size descending
    large_objects.sort(key=lambda x: x["size_mb"], reverse=True)
    return large_objects[:limit]


def get_memory_summary() -> dict[str, Any]:
    """Get comprehensive memory usage summary.

    Returns:
        Dictionary with:
        - current_usage: Current process memory metrics
        - top_objects: Top 20 object types by count
        - large_objects: Objects over 1MB
        - gc_stats: Garbage collection statistics
    """
    return {
        "current_usage": get_memory_usage(),
        "top_objects": get_object_memory_breakdown(limit=20),
        "large_objects": get_large_objects(threshold_mb=1.0, limit=10),
        "gc_stats": {
            "collections": gc.get_count(),
            "threshold": gc.get_threshold(),
            "tracked_objects": len(gc.get_objects()),
        },
    }
