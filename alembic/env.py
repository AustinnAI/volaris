from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

import os

from app.db.database import Base, CONNECT_ARGS, DATABASE_URL  # noqa: E402
from app.db import models  # noqa: F401  # ensure models are imported

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

alembic_database_url = os.environ.get("ALEMBIC_DATABASE_URL")
effective_database_url = alembic_database_url or DATABASE_URL

config.set_main_option("sqlalchemy.url", effective_database_url)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using async engine."""

    if alembic_database_url and effective_database_url.startswith("sqlite"):
        engine = create_engine(effective_database_url, poolclass=pool.NullPool)
        with engine.connect() as connection:
            run_migrations_with_connection(connection)
        engine.dispose()
        return

    connect_args = {} if alembic_database_url else (CONNECT_ARGS or {})

    connectable: AsyncEngine = create_async_engine(
        effective_database_url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async def do_run_migrations() -> None:
        async with connectable.connect() as connection:
            await connection.run_sync(run_migrations_with_connection)
        await connectable.dispose()

    asyncio.run(do_run_migrations())


def run_migrations_with_connection(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
