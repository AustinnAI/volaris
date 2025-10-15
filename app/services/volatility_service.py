"""
Volatility Service
Coordinates database access and volatility analytics computations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Sequence

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.volatility import (
    ExpectedMoveEstimate,
    IVMetricSnapshot,
    IVSummary,
    OptionSkew,
    TermStructurePoint,
    build_term_structure,
    compute_expected_move,
    compute_skew,
    summarize_iv,
)
from app.db.models import IVMetric, IVTerm, OptionChainSnapshot, Ticker
from app.services.exceptions import DataNotFoundError
from app.services.strike_data_service import StrikeDataService


@dataclass(slots=True)
class VolatilitySnapshot:
    """Aggregated volatility analytics for a ticker."""

    symbol: str
    underlying_price: Decimal | None
    iv_summary: IVSummary
    term_structure: list[TermStructurePoint]
    expected_moves: list[ExpectedMoveEstimate]
    skew: OptionSkew | None
    warnings: list[str] = field(default_factory=list)


class VolatilityService:
    """Facade that gathers volatility analytics for downstream consumers."""

    SHORT_WINDOW_LABEL = "1-7d"
    SHORT_WINDOW_RANGE = (1, 7)
    SHORT_WINDOW_TARGET = 5

    MEDIUM_WINDOW_LABEL = "14-45d"
    MEDIUM_WINDOW_RANGE = (14, 45)
    MEDIUM_WINDOW_TARGET = 30

    @classmethod
    async def get_snapshot(cls, db: AsyncSession, symbol: str) -> VolatilitySnapshot:
        """
        Return a fully composed volatility snapshot for the requested ticker.

        Args:
            db: Async session.
            symbol: Requested ticker symbol.

        Raises:
            DataNotFoundError: When the ticker does not exist.
        """
        ticker = await cls._require_ticker(db, symbol)
        underlying_price = await cls._resolve_underlying_price(db, ticker.id)

        iv_metrics = await cls._load_iv_metrics(db, ticker.id)
        iv_summary = summarize_iv(
            metrics=iv_metrics,
            high_threshold=float(settings.IV_HIGH_THRESHOLD),
            low_threshold=float(settings.IV_LOW_THRESHOLD),
        )
        term_structure = build_term_structure(iv_metrics)

        snapshots = await cls._load_recent_option_snapshots(db, ticker.id)
        warnings: list[str] = []

        short_snapshot = cls._select_snapshot(
            snapshots,
            target=cls.SHORT_WINDOW_TARGET,
            window=cls.SHORT_WINDOW_RANGE,
        )
        medium_snapshot = cls._select_snapshot(
            snapshots,
            target=cls.MEDIUM_WINDOW_TARGET,
            window=cls.MEDIUM_WINDOW_RANGE,
        )

        if underlying_price is None:
            for candidate in (short_snapshot, medium_snapshot):
                if candidate and candidate.underlying_price is not None:
                    underlying_price = candidate.underlying_price
                    break

        expected_moves: list[ExpectedMoveEstimate] = []

        if short_snapshot:
            contracts = StrikeDataService.contracts_to_data(short_snapshot.contracts)
            estimate = compute_expected_move(
                label=cls.SHORT_WINDOW_LABEL,
                contracts=contracts,
                underlying_price=underlying_price or short_snapshot.underlying_price,
                dte=short_snapshot.dte,
                as_of=short_snapshot.as_of,
            )
            if estimate:
                expected_moves.append(estimate)
            else:
                warnings.append("Insufficient option liquidity for 1-7d expected move.")
        else:
            warnings.append("No recent option snapshot covering 1-7 DTE.")

        if medium_snapshot:
            contracts = StrikeDataService.contracts_to_data(medium_snapshot.contracts)
            estimate = compute_expected_move(
                label=cls.MEDIUM_WINDOW_LABEL,
                contracts=contracts,
                underlying_price=underlying_price or medium_snapshot.underlying_price,
                dte=medium_snapshot.dte,
                as_of=medium_snapshot.as_of,
            )
            if estimate:
                expected_moves.append(estimate)
            else:
                warnings.append("Insufficient option liquidity for 14-45d expected move.")
        else:
            warnings.append("No recent option snapshot covering 14-45 DTE.")

        skew_snapshot = medium_snapshot or short_snapshot
        skew = None
        if skew_snapshot:
            contracts = StrikeDataService.contracts_to_data(skew_snapshot.contracts)
            skew = compute_skew(
                contracts=contracts,
                underlying_price=underlying_price or skew_snapshot.underlying_price,
                dte=skew_snapshot.dte,
            )
            if skew is None:
                warnings.append("Unable to compute skew (missing delta/IV data).")
        else:
            warnings.append("No option snapshot available to compute skew.")

        if not iv_metrics:
            warnings.append("IV metrics unavailable. Enable IV worker or manual refresh.")

        return VolatilitySnapshot(
            symbol=ticker.symbol,
            underlying_price=underlying_price,
            iv_summary=iv_summary,
            term_structure=term_structure,
            expected_moves=expected_moves,
            skew=skew,
            warnings=warnings,
        )

    @staticmethod
    async def _require_ticker(db: AsyncSession, symbol: str) -> Ticker:
        ticker = await StrikeDataService.get_ticker_by_symbol(db, symbol)
        if ticker is None:
            raise DataNotFoundError(f"Ticker {symbol.upper()} not found")
        return ticker

    @staticmethod
    async def _resolve_underlying_price(db: AsyncSession, ticker_id: int) -> Decimal | None:
        return await StrikeDataService.get_latest_price(db, ticker_id)

    @classmethod
    async def _load_iv_metrics(cls, db: AsyncSession, ticker_id: int) -> list[IVMetricSnapshot]:
        stmt = (
            select(IVMetric)
            .where(IVMetric.ticker_id == ticker_id)
            .order_by(IVMetric.term, desc(IVMetric.as_of))
        )
        result = await db.execute(stmt)
        rows: Sequence[IVMetric] = result.scalars().all()

        latest_by_term: dict[IVTerm, IVMetric] = {}
        for metric in rows:
            if metric.term not in latest_by_term:
                latest_by_term[metric.term] = metric

        return [
            IVMetricSnapshot(
                term=term,
                as_of=metric.as_of,
                implied_vol=metric.implied_vol,
                iv_rank=metric.iv_rank,
                iv_percentile=metric.iv_percentile,
            )
            for term, metric in latest_by_term.items()
        ]

    @classmethod
    async def _load_recent_option_snapshots(
        cls,
        db: AsyncSession,
        ticker_id: int,
        limit: int = 10,
    ) -> list[OptionChainSnapshot]:
        stmt = (
            select(OptionChainSnapshot)
            .where(OptionChainSnapshot.ticker_id == ticker_id)
            .order_by(desc(OptionChainSnapshot.as_of))
            .limit(limit)
            .options(selectinload(OptionChainSnapshot.contracts))
        )
        result = await db.execute(stmt)
        snapshots: Sequence[OptionChainSnapshot] = result.scalars().all()
        return list(snapshots)

    @classmethod
    def _select_snapshot(
        cls,
        snapshots: Iterable[OptionChainSnapshot],
        target: int,
        window: tuple[int, int],
    ) -> OptionChainSnapshot | None:
        min_dte, max_dte = window
        candidates = [
            snapshot
            for snapshot in snapshots
            if snapshot.dte is not None
            and min_dte <= snapshot.dte <= max_dte
            and snapshot.contracts
        ]
        if not candidates:
            return None

        return min(candidates, key=lambda snapshot: abs(snapshot.dte - target))
