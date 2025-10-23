"""
Workers package - V1 cleanup.

APScheduler removed in V1 Core MVP. Use GitHub Actions for batch refresh instead.
See legacy/workers/ for removed scheduler implementation.
"""

# No exports - scheduler moved to legacy/
__all__ = []
