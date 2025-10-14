"""
Database Connection & Session Management
Handles PostgreSQL connection using SQLAlchemy async engine.
"""

from typing import AsyncGenerator, Dict, Tuple
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings


# Convert psycopg2 URL to async driver (asyncpg)
# Neon uses standard PostgreSQL, so we use asyncpg driver
def _parse_ssl_from_url(url: str) -> Tuple[str, Dict]:
    """Translate libpq-style sslmode to asyncpg-friendly settings.

    - Rewrites scheme to postgresql+asyncpg
    - Strips unsupported "sslmode" query param
    - Returns (rewritten_url, connect_args)
    """
    parsed = urlparse(url)

    # Normalize scheme to asyncpg
    scheme = parsed.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"

    # Parse and adjust query params
    query_params = dict(parse_qsl(parsed.query))
    connect_args: Dict = {}

    # Remove parameters unsupported by asyncpg
    query_params.pop("channel_binding", None)

    sslmode = query_params.pop("sslmode", None)
    if sslmode:
        sslmode = sslmode.lower()
        if sslmode in ("require", "verify-ca", "verify-full"):
            # asyncpg expects 'ssl' True or an SSLContext; True uses default context
            connect_args["ssl"] = True
        elif sslmode == "disable":
            connect_args["ssl"] = False
        else:
            # prefer/prefer-like modes: leave to default (no explicit arg)
            pass

    rebuilt = urlunparse(
        (
            scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(query_params),
            parsed.fragment,
        )
    )
    return rebuilt, connect_args


def get_async_database_url(url: str) -> str:
    """Convert standard PostgreSQL URL to asyncpg URL and strip sslmode."""
    rewritten, _ = _parse_ssl_from_url(url)
    return rewritten


DATABASE_URL, CONNECT_ARGS = _parse_ssl_from_url(settings.DATABASE_URL)
CONNECT_ARGS = CONNECT_ARGS or None


def _build_engine() -> AsyncEngine:
    """Construct async engine with production-aware pooling."""
    base_kwargs = {
        "echo": settings.DB_ECHO,
        "pool_pre_ping": True,
        "connect_args": CONNECT_ARGS,
    }

    if settings.is_production:
        return create_async_engine(
            DATABASE_URL,
            poolclass=NullPool,
            **base_kwargs,
        )

    return create_async_engine(
        DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        **base_kwargs,
    )


# Create async engine
engine = _build_engine()


# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# Base class for SQLAlchemy models
class Base(DeclarativeBase):
    """Base class for all database models"""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.
    Use in FastAPI route dependencies.

    Example:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database.
    Creates all tables if they don't exist.
    Called on application startup.
    """
    async with engine.begin() as conn:
        # Import all models here to ensure they're registered with Base
        # from app.db.models import ticker, ohlc, options, ...

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    Close database connection.
    Called on application shutdown.
    """
    await engine.dispose()
