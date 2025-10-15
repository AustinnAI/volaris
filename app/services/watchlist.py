"""
Watchlist Service
Manage server-side watchlist storage backed by Redis (primary) with Postgres fallback.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.models import Ticker, Watchlist, WatchlistItem
from app.utils.logger import app_logger

WATCHLIST_KEY = "watchlist:symbols"
WATCHLIST_NAME = "server_watchlist"
DEFAULT_SYMBOLS = ["SPY", "QQQ"]
SYMBOL_PATTERN = re.compile(r"^[A-Z.\-]{1,10}$")


class WatchlistValidationError(ValueError):
    """Raised when an invalid watchlist payload is provided."""


class WatchlistService:
    """Coordinate watchlist persistence across Redis and Postgres."""

    _redis_async_client: httpx.AsyncClient | None = None

    @classmethod
    def normalize_symbols(cls, symbols: Sequence[str]) -> list[str]:
        """
        Normalize and validate incoming symbol list.

        Args:
            symbols: Raw symbol strings.

        Returns:
            Cleaned list of uppercase symbols.

        Raises:
            WatchlistValidationError: When validation fails.
        """
        if not symbols:
            raise WatchlistValidationError("Watchlist must contain at least one symbol.")

        cleaned: list[str] = []
        seen: set[str] = set()

        for raw in symbols:
            symbol = (raw or "").strip().upper()
            if not symbol:
                continue
            if not SYMBOL_PATTERN.fullmatch(symbol):
                raise WatchlistValidationError(
                    f"Invalid symbol '{raw}'. Symbols must match [A-Z.-] and be <=10 characters."
                )
            if symbol not in seen:
                cleaned.append(symbol)
                seen.add(symbol)

        if not cleaned:
            raise WatchlistValidationError("Watchlist must contain at least one valid symbol.")
        if len(cleaned) > 8:
            raise WatchlistValidationError("Watchlist cannot exceed 8 symbols.")
        return cleaned

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    async def get_symbols(cls, session: AsyncSession) -> list[str]:
        """
        Return the current watchlist symbols.

        Order of precedence:
            1. Redis cache (if configured)
            2. Postgres fallback (watchlists table)
            3. Default list ["SPY", "QQQ"]
        """
        symbols = await cls._get_from_redis()
        if symbols:
            return symbols

        symbols = await cls._get_from_db(session)
        if symbols:
            return symbols

        return DEFAULT_SYMBOLS.copy()

    @classmethod
    async def set_symbols(cls, session: AsyncSession, symbols: Sequence[str]) -> list[str]:
        """
        Validate and persist watchlist symbols.

        Args:
            session: Database session for fallback persistence.
            symbols: Incoming symbol list.

        Returns:
            Persisted symbol list.
        """
        cleaned = cls.normalize_symbols(symbols)
        stored = False

        try:
            stored = await cls._set_in_redis(cleaned)
        except Exception as exc:  # pylint: disable=broad-except
            app_logger.warning("Failed to persist watchlist to Redis", extra={"error": str(exc)})

        await cls._set_in_db(session, cleaned)
        await session.commit()

        backend = "redis" if stored else "postgres"
        app_logger.info(
            "Updated server watchlist",
            extra={"symbols": cleaned, "backend": backend},
        )
        return cleaned

    # ------------------------------------------------------------------
    # Redis helpers
    # ------------------------------------------------------------------

    @classmethod
    def _redis_enabled(cls) -> bool:
        return bool(settings.UPSTASH_REDIS_REST_URL and settings.UPSTASH_REDIS_REST_TOKEN)

    @classmethod
    async def _get_from_redis(cls) -> list[str]:
        if not cls._redis_enabled():
            return []
        client = await cls._get_redis_client()
        try:
            response = await client.get(f"/get/{WATCHLIST_KEY}", headers=cls._redis_headers())
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return []
            app_logger.debug("Redis get failed", extra={"status": exc.response.status_code})
            return []
        except Exception as exc:  # pylint: disable=broad-except
            app_logger.debug("Redis get error", extra={"error": str(exc)})
            return []

        result = payload.get("result")
        if not result:
            return []
        try:
            parsed = json.loads(result)
        except json.JSONDecodeError:
            return []

        return [str(symbol).upper() for symbol in parsed if isinstance(symbol, str)]

    @classmethod
    async def _set_in_redis(cls, symbols: Sequence[str]) -> bool:
        if not cls._redis_enabled():
            return False
        client = await cls._get_redis_client()
        body = {"value": json.dumps(list(symbols))}
        response = await client.post(
            f"/set/{WATCHLIST_KEY}", headers=cls._redis_headers(), json=body
        )
        response.raise_for_status()
        return True

    @classmethod
    async def _get_redis_client(cls) -> httpx.AsyncClient:
        if cls._redis_async_client is None:
            cls._redis_async_client = httpx.AsyncClient(
                base_url=settings.UPSTASH_REDIS_REST_URL.rstrip("/"),
                timeout=10.0,
            )
        return cls._redis_async_client

    @staticmethod
    def _redis_headers() -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.UPSTASH_REDIS_REST_TOKEN}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Postgres helpers
    # ------------------------------------------------------------------

    @classmethod
    async def _get_from_db(cls, session: AsyncSession) -> list[str]:
        stmt = (
            select(Watchlist)
            .where(Watchlist.name == WATCHLIST_NAME)
            .options(selectinload(Watchlist.items).selectinload(WatchlistItem.ticker))
        )
        result = await session.execute(stmt)
        watchlist = result.scalar_one_or_none()
        if not watchlist:
            return []

        ordered_items = sorted(
            watchlist.items,
            key=lambda item: item.rank if item.rank is not None else 0,
        )
        symbols = [
            item.ticker.symbol
            for item in ordered_items
            if item.ticker and item.ticker.symbol  # type: ignore[truthy-function]
        ]
        return symbols

    @classmethod
    async def _set_in_db(cls, session: AsyncSession, symbols: Sequence[str]) -> None:
        stmt = (
            select(Watchlist)
            .where(Watchlist.name == WATCHLIST_NAME)
            .options(selectinload(Watchlist.items).selectinload(WatchlistItem.ticker))
        )
        result = await session.execute(stmt)
        watchlist = result.scalar_one_or_none()

        if watchlist is None:
            watchlist = Watchlist(name=WATCHLIST_NAME, description="Server-managed watchlist")
            session.add(watchlist)
            await session.flush()

        existing = {item.ticker.symbol: item for item in watchlist.items if item.ticker}  # type: ignore[index]
        desired = list(symbols)

        # Remove stale items
        for symbol, item in list(existing.items()):
            if symbol not in desired:
                await session.delete(item)
                existing.pop(symbol, None)

        for index, symbol in enumerate(desired):
            if symbol in existing:
                existing[symbol].rank = index
                continue
            ticker = await cls._get_or_create_ticker(session, symbol)
            session.add(WatchlistItem(watchlist_id=watchlist.id, ticker_id=ticker.id, rank=index))

    @staticmethod
    async def _get_or_create_ticker(session: AsyncSession, symbol: str) -> Ticker:
        stmt = select(Ticker).where(Ticker.symbol == symbol)
        result = await session.execute(stmt)
        ticker = result.scalar_one_or_none()
        if ticker:
            return ticker

        ticker = Ticker(symbol=symbol, is_active=True)
        session.add(ticker)
        await session.flush()
        return ticker
