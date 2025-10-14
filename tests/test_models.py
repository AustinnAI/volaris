"""Tests covering SQLAlchemy model metadata for Phase 2.1."""

from sqlalchemy import UniqueConstraint

from app.db.models import (
    IVMetric,
    MarketStructureLevel,
    OptionChainSnapshot,
    OptionContract,
    PriceBar,
    Ticker,
    TradePlan,
    WatchlistItem,
)


def _has_unique_constraint(table, columns: set[str]) -> bool:
    """Return True if the SQLAlchemy table defines the expected unique constraint."""

    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint):
            if {col.name for col in constraint.columns} == columns:
                return True
    return False


def test_ticker_symbol_unique_constraint() -> None:
    """Ticker symbols must be unique to avoid duplicates across data providers."""

    assert Ticker.__table__.c.symbol.unique is True


def test_price_bar_unique_key() -> None:
    """Each price bar is uniquely identified by ticker, timeframe, and timestamp."""

    assert _has_unique_constraint(PriceBar.__table__, {"ticker_id", "timestamp", "timeframe"})


def test_watchlist_item_prevents_duplicate_membership() -> None:
    """A ticker can only appear once per watchlist."""

    assert _has_unique_constraint(WatchlistItem.__table__, {"watchlist_id", "ticker_id"})


def test_option_contract_unique_per_snapshot() -> None:
    """Contracts of the same snapshot/strike/side should not duplicate rows."""

    assert _has_unique_constraint(
        OptionContract.__table__, {"snapshot_id", "option_type", "strike"}
    )


def test_iv_metrics_unique_time_bucket() -> None:
    """There should be only one IV metric per ticker/term/as_of combination."""

    assert _has_unique_constraint(IVMetric.__table__, {"ticker_id", "as_of", "term"})


def test_option_snapshot_indexes_defined() -> None:
    """Snapshots should expose foreign key indexes for performant lookups."""

    columns = {col.name for col in OptionChainSnapshot.__table__.columns}
    assert {"ticker_id", "expiration"}.issubset(columns)


def test_market_structure_level_columns_present() -> None:
    """Ensure critical columns exist for downstream analytics."""

    table = MarketStructureLevel.__table__
    for expected in ("ticker_id", "level_type", "price", "detected_at"):
        assert expected in table.columns


def test_trade_plan_relationship_fields_exist() -> None:
    """Trade plans should support strategy, bias, and status fields."""

    table = TradePlan.__table__
    for expected in ("strategy", "bias", "status"):
        assert expected in table.columns
