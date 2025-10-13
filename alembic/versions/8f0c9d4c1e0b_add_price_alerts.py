"""add price alerts table

Revision ID: 8f0c9d4c1e0b
Revises: 73a17d6b8fc7
Create Date: 2025-10-13 18:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f0c9d4c1e0b"
down_revision: Union[str, None] = "73a17d6b8fc7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    price_alert_direction = sa.Enum(
        "ABOVE",
        "BELOW",
        name="pricealertdirection",
        native_enum=False,
        length=16,
    )
    price_alert_direction.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "price_alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker_id", sa.Integer(), nullable=False),
        sa.Column("direction", price_alert_direction, nullable=False),
        sa.Column("target_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("channel_id", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index(
        op.f("ix_price_alerts_ticker_id"), "price_alerts", ["ticker_id"], unique=False
    )
    op.create_index(
        "ix_price_alerts_ticker_direction",
        "price_alerts",
        ["ticker_id", "direction"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_price_alerts_ticker_direction", table_name="price_alerts")
    op.drop_index(op.f("ix_price_alerts_ticker_id"), table_name="price_alerts")
    op.drop_table("price_alerts")
    sa.Enum(
        "ABOVE",
        "BELOW",
        name="pricealertdirection",
        native_enum=False,
        length=16,
    ).drop(op.get_bind(), checkfirst=True)
