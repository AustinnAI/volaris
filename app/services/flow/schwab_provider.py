"""
Schwab provider for options flow detection.

Uses Schwab API (Phase 1 integration) to fetch option chains with
real-time data and applies custom anomaly detection logic.

Advantages over yfinance:
- Works on cloud platforms (no IP blocking)
- Real-time data (no 15-min delay)
- Official API (reliable)
"""

from datetime import datetime
from decimal import Decimal

from app.core.flow_detection import (
    compute_anomaly_score,
    compute_volume_oi_ratio,
    estimate_premium,
)
from app.services.schwab import SchwabClient
from app.utils.logger import app_logger

from .base_provider import FlowProvider, OptionChain, OptionContract, UnusualTrade


class SchwabFlowProvider(FlowProvider):
    """
    Options flow provider using Schwab API.

    Uses the existing Schwab client from Phase 1 to fetch option chains
    and applies custom anomaly detection.

    Advantages:
    - Real-time data
    - Works on cloud platforms
    - Official API
    """

    def __init__(self, avg_volume_lookback_days: int = 30):
        """
        Initialize Schwab provider.

        Args:
            avg_volume_lookback_days: Days to use for volume average calculation.
        """
        self.avg_volume_lookback_days = avg_volume_lookback_days
        self.schwab_client = SchwabClient()

    async def get_option_chain(
        self, symbol: str, expiration: datetime | None = None
    ) -> OptionChain:
        """
        Fetch option chain from Schwab API.

        Args:
            symbol: Ticker symbol (e.g., SPY, AAPL).
            expiration: Optional specific expiration date filter.

        Returns:
            OptionChain with calls and puts.

        Raises:
            ValueError: If ticker not found or no options available.
        """
        try:
            # Fetch option chain from Schwab
            chain_data = await self.schwab_client.get_option_chain(
                symbol=symbol,
                contract_type="ALL",  # Get both calls and puts
                strike_count=50,  # Get 50 strikes above/below current price
                include_quotes=True,
            )

            if not chain_data or "status" not in chain_data:
                raise ValueError(f"No options data returned for {symbol}")

            if chain_data["status"] != "SUCCESS":
                raise ValueError(f"Schwab API error: {chain_data.get('status', 'Unknown error')}")

            # Parse expirations
            expirations = []
            calls = []
            puts = []

            # Extract call options
            call_exp_map = chain_data.get("callExpDateMap", {})
            for exp_date_str, strikes in call_exp_map.items():
                exp_date = datetime.strptime(exp_date_str.split(":")[0], "%Y-%m-%d")
                if exp_date not in expirations:
                    expirations.append(exp_date)

                for _strike_str, contracts in strikes.items():
                    for contract in contracts:
                        calls.append(self._parse_contract(contract, "call", exp_date))

            # Extract put options
            put_exp_map = chain_data.get("putExpDateMap", {})
            for exp_date_str, strikes in put_exp_map.items():
                exp_date = datetime.strptime(exp_date_str.split(":")[0], "%Y-%m-%d")
                if exp_date not in expirations:
                    expirations.append(exp_date)

                for _strike_str, contracts in strikes.items():
                    for contract in contracts:
                        puts.append(self._parse_contract(contract, "put", exp_date))

            return OptionChain(
                symbol=symbol.upper(),
                timestamp=datetime.now(),
                expirations=sorted(expirations),
                calls=calls,
                puts=puts,
            )

        except Exception as e:
            app_logger.error(
                f"Failed to fetch option chain from Schwab for {symbol}: {e}",
                exc_info=True,
            )
            raise ValueError(f"Failed to fetch options for {symbol}: {e}") from e

    def _parse_contract(
        self, contract_data: dict, option_type: str, expiration: datetime
    ) -> OptionContract:
        """Parse Schwab contract data into OptionContract."""
        return OptionContract(
            contract_symbol=contract_data.get("symbol", ""),
            strike=Decimal(str(contract_data.get("strikePrice", 0))),
            expiration=expiration,
            option_type=option_type,
            last_price=Decimal(str(contract_data.get("last", 0))),
            bid=Decimal(str(contract_data.get("bid", 0))),
            ask=Decimal(str(contract_data.get("ask", 0))),
            volume=int(contract_data.get("totalVolume", 0)),
            open_interest=int(contract_data.get("openInterest", 0)),
            implied_volatility=float(contract_data.get("volatility", 0)) / 100.0,
        )

    async def get_unusual_activity(
        self,
        symbol: str,
        min_score: float = 0.7,
        lookback_minutes: int = 60,
    ) -> list[UnusualTrade]:
        """
        Detect unusual options activity using Schwab data.

        Args:
            symbol: Ticker symbol (e.g., SPY, AAPL).
            min_score: Minimum anomaly score (0-1) to return.
            lookback_minutes: Not applicable (current snapshot only).

        Returns:
            List of unusual trades sorted by anomaly_score descending.

        Raises:
            ValueError: If ticker not found or data unavailable.
        """
        # Get option chain
        chain = await self.get_option_chain(symbol)

        unusual_trades = []
        all_contracts = chain["calls"] + chain["puts"]

        for contract in all_contracts:
            volume = contract["volume"]
            open_interest = contract["open_interest"]
            last_price = contract["last_price"]
            bid = contract["bid"]
            ask = contract["ask"]

            # Skip if no volume
            if volume == 0:
                continue

            # Calculate metrics
            vol_oi_ratio = compute_volume_oi_ratio(volume, open_interest)
            premium = estimate_premium(volume, last_price)

            # Estimate 30-day average volume (use OI as proxy)
            avg_volume_30d = max(open_interest / self.avg_volume_lookback_days, 1.0)

            # Calculate bid-ask spread percentage
            if ask > 0:
                bid_ask_spread_pct = float((ask - bid) / ask)
            else:
                bid_ask_spread_pct = 1.0

            # Compute anomaly score
            score, flags = compute_anomaly_score(
                volume=volume,
                open_interest=open_interest,
                avg_volume_30d=avg_volume_30d,
                bid_ask_spread_pct=bid_ask_spread_pct,
                premium=premium,
            )

            # Only include if score meets threshold
            if score >= min_score:
                unusual_trades.append(
                    UnusualTrade(
                        symbol=symbol.upper(),
                        contract_symbol=contract["contract_symbol"],
                        option_type=contract["option_type"],
                        strike=contract["strike"],
                        expiration=contract["expiration"],
                        last_price=last_price,
                        volume=volume,
                        open_interest=open_interest,
                        volume_oi_ratio=round(vol_oi_ratio, 2),
                        premium=premium,
                        anomaly_score=round(score, 2),
                        flags=flags,
                        detected_at=datetime.now(),
                    )
                )

        # Sort by anomaly score descending and limit results
        unusual_trades.sort(key=lambda x: x["anomaly_score"], reverse=True)
        return unusual_trades[:50]
