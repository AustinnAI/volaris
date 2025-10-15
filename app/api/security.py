"""
Shared API security utilities.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.config import settings


def require_bearer_token(request: Request) -> None:
    """
    Enforce a simple bearer token check when VOLARIS_API_TOKEN is configured.

    Raises:
        HTTPException: When token missing or invalid.
    """
    expected = (settings.VOLARIS_API_TOKEN or "").strip()
    if not expected:
        return

    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )
    token = auth_header[7:].strip()
    if token != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid bearer token.",
        )
