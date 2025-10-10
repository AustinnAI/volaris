"""
Database Connection & Session Management
Handles PostgreSQL connection using SQLAlchemy async engine.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings


# Convert psycopg2 URL to async driver (asyncpg)
# Neon uses standard PostgreSQL, so we use asyncpg driver
def get_async_database_url(url: str) -> str:
    """
    Convert standard PostgreSQL URL to async URL.
    postgresql:// -> postgresql+asyncpg://
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


DATABASE_URL = get_async_database_url(settings.DATABASE_URL)


# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections before using
    # For serverless databases like Neon, consider using NullPool in production
    poolclass=NullPool if settings.is_production else None,
)


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
