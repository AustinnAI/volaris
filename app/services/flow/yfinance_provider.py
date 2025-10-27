"""
yfinance provider for options flow detection.

Uses Yahoo Finance API (via yfinance library) to fetch option chains
and applies custom anomaly detection logic to identify unusual activity.
"""

import asyncio
from datetime import datetime
from decimal import Decimal

import yfinance as yf

from app.core.flow_detection import (
    compute_anomaly_score,
    compute_volume_oi_ratio,
    estimate_premium,
)
from app.utils.logger import app_logger

from .base_provider import FlowProvider, OptionChain, OptionContract, UnusualTrade


class YFinanceFlowProvider(FlowProvider):
    """
    Options flow provider using yfinance.

    Fetches raw option chains from Yahoo Finance and applies custom
    anomaly detection to identify unusual activity.

    Limitations:
    - 15-20 minute delay
    - Unofficial API (may break occasionally)
    - No historical volume data (uses current volume as proxy)
    """

    def __init__(self, avg_volume_lookback_days: int = 30):
        """
        Initialize yfinance provider.

        Args:
            avg_volume_lookback_days: Days to use for volume average calculation.
                                      Note: yfinance doesn't provide historical
                                      option volume, so we estimate from OI.
        """
        self.avg_volume_lookback_days = avg_volume_lookback_days

    async def get_option_chain(
        self, symbol: str, expiration: datetime | None = None
    ) -> OptionChain:
        """
        Fetch raw option chain data from yfinance.

        Args:
            symbol: Ticker symbol (e.g., SPY, AAPL).
            expiration: Optional specific expiration date (YYYY-MM-DD).

        Returns:
            OptionChain with calls and puts.

        Raises:
            ValueError: If ticker not found or no options available.
        """
        # Run yfinance in thread pool (it's blocking I/O)
        loop = asyncio.get_event_loop()
        ticker = await loop.run_in_executor(None, yf.Ticker, symbol)

        try:
            # Get available expiration dates
            expirations = await loop.run_in_executor(None, lambda: ticker.options)
            if not expirations:
                raise ValueError(f"No options available for {symbol}")

            # Use first expiration if not specified
            if expiration is None:
                exp_str = expirations[0]
            else:
                exp_str = expiration.strftime("%Y-%m-%d")
                if exp_str not in expirations:
                    raise ValueError(
                        f"Expiration {exp_str} not found for {symbol}. "
                        f"Available: {expirations[:3]}"
                    )

            # Fetch option chain for this expiration
            chain = await loop.run_in_executor(None, ticker.option_chain, exp_str)

            # Parse calls and puts
            calls = self._parse_contracts(chain.calls, "call", exp_str, symbol)
            puts = self._parse_contracts(chain.puts, "put", exp_str, symbol)

            return OptionChain(
                symbol=symbol.upper(),
                timestamp=datetime.now(),
                expirations=[datetime.strptime(e, "%Y-%m-%d") for e in expirations],
                calls=calls,
                puts=puts,
            )

        except Exception as e:
            app_logger.error(f"Failed to fetch option chain for {symbol}: {e}", exc_info=True)
            raise ValueError(f"Failed to fetch options for {symbol}: {e}") from e

    def _parse_contracts(
        self, df, option_type: str, exp_str: str, symbol: str
    ) -> list[OptionContract]:
        """
        Parse yfinance DataFrame into OptionContract list.

        Args:
            df: Pandas DataFrame from yfinance (chain.calls or chain.puts).
            option_type: "call" or "put".
            exp_str: Expiration date string (YYYY-MM-DD).
            symbol: Underlying ticker symbol.

        Returns:
            List of OptionContract dicts.
        """
        contracts = []
        expiration = datetime.strptime(exp_str, "%Y-%m-%d")

        for _, row in df.iterrows():
            try:
                # Build contract symbol (yfinance format)
                contract_symbol = row.get("contractSymbol", "")
                if not contract_symbol:
                    continue

                contracts.append(
                    OptionContract(
                        contract_symbol=contract_symbol,
                        strike=Decimal(str(row.get("strike", 0))),
                        expiration=expiration,
                        option_type=option_type,
                        last_price=Decimal(str(row.get("lastPrice", 0))),
                        bid=Decimal(str(row.get("bid", 0))),
                        ask=Decimal(str(row.get("ask", 0))),
                        volume=int(row.get("volume", 0)),
                        open_interest=int(row.get("openInterest", 0)),
                        implied_volatility=float(row.get("impliedVolatility", 0)),
                    )
                )
            except Exception as e:
                app_logger.warning(
                    f"Failed to parse contract {row.get('contractSymbol', 'unknown')}: {e}"
                )
                continue

        return contracts

    async def get_unusual_activity(
        self,
        symbol: str,
        min_score: float = 0.7,
        lookback_minutes: int = 60,
    ) -> list[UnusualTrade]:
        """
        Detect unusual options activity using custom anomaly logic.

        Args:
            symbol: Ticker symbol (e.g., SPY, AAPL).
            min_score: Minimum anomaly score (0-1) to return.
            lookback_minutes: Not used by yfinance (current snapshot only).

        Returns:
            List of unusual trades sorted by anomaly_score descending.

        Raises:
            ValueError: If ticker not found or data unavailable.
        """
        # Get current option chain
        chain = await self.get_option_chain(symbol)

        unusual_trades = []

        # Analyze all contracts (calls + puts)
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

            # Estimate 30-day average volume (use OI as proxy since no historical data)
            # Assumption: avg daily volume = OI / 30
            avg_volume_30d = max(open_interest / self.avg_volume_lookback_days, 1.0)

            # Calculate bid-ask spread percentage
            if ask > 0:
                bid_ask_spread_pct = float((ask - bid) / ask)
            else:
                bid_ask_spread_pct = 1.0  # Wide spread if ask is 0

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
        return unusual_trades[:50]  # Top 50 unusual contracts
