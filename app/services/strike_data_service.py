"""
Strike Data Service
Retrieves option chain and IV data from database for strike selection.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.strike_selection import OptionContractData
from app.db.models import (
    IVMetric,
    IVTerm,
    OptionChainSnapshot,
    OptionContract,
    PriceBar,
    Ticker,
    Timeframe,
)


class StrikeDataService:
    """Service for retrieving option chain and market data."""

    @staticmethod
    async def get_ticker_by_symbol(
        db: AsyncSession,
        symbol: str,
    ) -> Ticker | None:
        """
        Get ticker by symbol.

        Args:
            db: Database session
            symbol: Ticker symbol

        Returns:
            Ticker object or None if not found
        """
        stmt = select(Ticker).where(Ticker.symbol == symbol.upper())
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_latest_price(
        db: AsyncSession,
        ticker_id: int,
        timeframe: Timeframe = Timeframe.ONE_MINUTE,
    ) -> Decimal | None:
        """
        Get the latest price for a ticker.

        Args:
            db: Database session
            ticker_id: Ticker ID
            timeframe: Price bar timeframe (default 1m)

        Returns:
            Latest close price or None
        """
        stmt = (
            select(PriceBar)
            .where(
                and_(
                    PriceBar.ticker_id == ticker_id,
                    PriceBar.timeframe == timeframe,
                )
            )
            .order_by(desc(PriceBar.timestamp))
            .limit(1)
        )
        result = await db.execute(stmt)
        bar = result.scalar_one_or_none()
        return bar.close if bar else None

    @staticmethod
    async def get_option_chain_by_dte(
        db: AsyncSession,
        ticker_id: int,
        target_dte: int,
        dte_tolerance: int = 3,
    ) -> OptionChainSnapshot | None:
        """
        Get option chain snapshot closest to target DTE.

        Args:
            db: Database session
            ticker_id: Ticker ID
            target_dte: Desired days to expiration
            dte_tolerance: Max days difference from target (default ±3)

        Returns:
            OptionChainSnapshot with contracts loaded, or None
        """
        min_dte = target_dte - dte_tolerance
        max_dte = target_dte + dte_tolerance

        stmt = (
            select(OptionChainSnapshot)
            .options(selectinload(OptionChainSnapshot.contracts))
            .where(
                and_(
                    OptionChainSnapshot.ticker_id == ticker_id,
                    OptionChainSnapshot.dte >= min_dte,
                    OptionChainSnapshot.dte <= max_dte,
                )
            )
            .order_by(desc(OptionChainSnapshot.as_of))
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_iv_metrics(
        db: AsyncSession,
        ticker_id: int,
        term: IVTerm = IVTerm.D30,
        max_age_hours: int = 24,
    ) -> IVMetric | None:
        """
        Get latest IV metrics for a ticker.

        Args:
            db: Database session
            ticker_id: Ticker ID
            term: IV term (default 30d)
            max_age_hours: Max age of data in hours

        Returns:
            IVMetric or None
        """
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

        stmt = (
            select(IVMetric)
            .where(
                and_(
                    IVMetric.ticker_id == ticker_id,
                    IVMetric.term == term,
                    IVMetric.as_of >= cutoff,
                )
            )
            .order_by(desc(IVMetric.as_of))
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def contracts_to_data(
        contracts: list[OptionContract],
    ) -> list[OptionContractData]:
        """
        Convert SQLAlchemy OptionContract objects to OptionContractData.

        Args:
            contracts: List of OptionContract from database

        Returns:
            List of OptionContractData for calculations
        """
        return [
            OptionContractData(
                strike=c.strike,
                option_type=c.option_type.value,
                bid=c.bid,
                ask=c.ask,
                mark=c.mark,
                delta=c.delta,
                implied_vol=c.implied_vol,
                volume=c.volume,
                open_interest=c.open_interest,
            )
            for c in contracts
        ]

    @staticmethod
    async def validate_and_fetch_data(
        db: AsyncSession,
        symbol: str,
        target_dte: int,
        dte_tolerance: int = 3,
    ) -> tuple[
        Ticker | None,
        Decimal | None,
        OptionChainSnapshot | None,
        IVMetric | None,
        list[str],
    ]:
        """
        Validate symbol and fetch all required data for strike selection.

        Args:
            db: Database session
            symbol: Ticker symbol
            target_dte: Target days to expiration
            dte_tolerance: DTE tolerance window

        Returns:
            (ticker, underlying_price, snapshot, iv_metric, warnings)
        """
        warnings = []

        # Get ticker
        ticker = await StrikeDataService.get_ticker_by_symbol(db, symbol)
        if not ticker:
            return None, None, None, None, [f"Ticker {symbol} not found"]

        # Get latest price
        underlying_price = await StrikeDataService.get_latest_price(db, ticker.id)
        if not underlying_price:
            # Try daily timeframe
            underlying_price = await StrikeDataService.get_latest_price(
                db, ticker.id, Timeframe.DAILY
            )

        if not underlying_price:
            warnings.append(f"No recent price data for {symbol}")

        # Get option chain
        snapshot = await StrikeDataService.get_option_chain_by_dte(
            db, ticker.id, target_dte, dte_tolerance
        )

        if not snapshot:
            warnings.append(
                f"No option chain data for {symbol} with DTE {target_dte} ±{dte_tolerance}"
            )
        elif not snapshot.contracts:
            warnings.append(f"Option chain for {symbol} has no contracts")

        # Get IV metrics
        iv_metric = await StrikeDataService.get_iv_metrics(db, ticker.id)
        if not iv_metric:
            warnings.append(f"No recent IV metrics for {symbol}")

        return ticker, underlying_price, snapshot, iv_metric, warnings
