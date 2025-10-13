"""add price streams and index constituents

Revision ID: f3f6f2d64d2c
Revises: 8f0c9d4c1e0b
Create Date: 2025-10-13 19:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3f6f2d64d2c"
down_revision: Union[str, None] = "8f0c9d4c1e0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "index_constituents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("index_symbol", sa.String(length=32), nullable=False),
        sa.Column("ticker_id", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Numeric(10, 6), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ticker_id"], ["tickers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("index_symbol", "ticker_id", name="uq_index_constituent"),
    )
    op.create_index(
        "ix_index_constituents_symbol",
        "index_constituents",
        ["index_symbol"],
        unique=False,
    )

    op.create_table(
        "price_streams",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.String(length=64), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("last_price", sa.Numeric(18, 6), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ticker_id"], ["tickers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker_id", "channel_id", name="uq_price_stream_channel"),
    )
    op.create_index(
        "ix_price_streams_next_run",
        "price_streams",
        ["next_run_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_price_streams_next_run", table_name="price_streams")
    op.drop_table("price_streams")
    op.drop_index("ix_index_constituents_symbol", table_name="index_constituents")
    op.drop_table("index_constituents")
