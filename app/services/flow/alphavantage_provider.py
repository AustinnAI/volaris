"""
Alpha Vantage options flow provider (Phase 3.1).

Uses the free Alpha Vantage API to fetch options chains and detect unusual activity.
"""

import math
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.core.flow_detection import compute_anomaly_score
from app.services.flow.base_provider import FlowProvider, OptionChain, OptionContract, UnusualTrade
from app.utils.logger import app_logger


class AlphaVantageFlowProvider(FlowProvider):
    """
    Uses Alpha Vantage API for options data.

    - Free tier: 25 requests/day
    - No IP blocking (cloud-friendly)
    - Options chain endpoint: HISTORICAL_OPTIONS
    """

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str, avg_volume_lookback_days: int = 30):
        self.api_key = api_key
        self.avg_volume_lookback_days = avg_volume_lookback_days

    async def get_option_chain(
        self, symbol: str, expiration: datetime | None = None
    ) -> OptionChain:
        """Fetch options chain from Alpha Vantage."""
        try:
            # Alpha Vantage uses HISTORICAL_OPTIONS endpoint
            # We'll get the most recent date available
            params = {
                "function": "HISTORICAL_OPTIONS",
                "symbol": symbol,
                "apikey": self.api_key,
            }

            if expiration:
                params["date"] = expiration.strftime("%Y-%m-%d")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

            if "Error Message" in data:
                raise ValueError(f"Alpha Vantage API error: {data['Error Message']}")

            if "Note" in data:
                raise ValueError(f"Alpha Vantage rate limit: {data['Note']}")

            # Parse Alpha Vantage response
            contracts = []
            for option_data in data.get("data", []):
                contract = self._parse_contract(option_data)
                if contract:
                    contracts.append(contract)

            app_logger.info(f"Fetched {len(contracts)} options for {symbol} from Alpha Vantage")

            return OptionChain(symbol=symbol, contracts=contracts, timestamp=datetime.now(UTC))

        except Exception as e:
            app_logger.error(f"Failed to fetch option chain from Alpha Vantage for {symbol}: {e}")
            raise ValueError(f"Failed to fetch options for {symbol}: {e}") from e

    def _parse_contract(self, data: dict[str, Any]) -> OptionContract | None:
        """Parse a single Alpha Vantage option contract."""
        try:
            # Alpha Vantage response format:
            # {
            #   "contractID": "SPY250131C00600000",
            #   "symbol": "SPY",
            #   "expiration": "2025-01-31",
            #   "strike": "600",
            #   "type": "call",
            #   "last": "5.20",
            #   "bid": "5.15",
            #   "ask": "5.25",
            #   "volume": "1500",
            #   "open_interest": "5000",
            #   "implied_volatility": "0.25"
            # }

            # Handle missing/invalid values
            volume = int(data.get("volume", 0) or 0)
            open_interest = int(data.get("open_interest", 0) or 0)
            last_price = float(data.get("last", 0) or 0)
            bid = float(data.get("bid", 0) or 0)
            ask = float(data.get("ask", 0) or 0)
            iv = data.get("implied_volatility")

            # Skip if missing critical data
            if not data.get("contractID") or not data.get("expiration"):
                return None

            # Parse expiration date
            exp_date = datetime.strptime(data["expiration"], "%Y-%m-%d")
            exp_date = exp_date.replace(tzinfo=UTC)

            return OptionContract(
                contract_symbol=data["contractID"],
                strike=Decimal(str(data["strike"])),
                expiration=exp_date,
                option_type=data["type"],  # "call" or "put"
                last_price=Decimal(str(last_price)),
                bid=Decimal(str(bid)),
                ask=Decimal(str(ask)),
                volume=volume,
                open_interest=open_interest,
                implied_volatility=float(iv) if iv and not math.isnan(float(iv)) else None,
            )

        except Exception as e:
            app_logger.warning(f"Failed to parse Alpha Vantage contract: {e}")
            return None

    async def get_unusual_activity(
        self,
        symbol: str,
        min_score: float = 0.7,
        lookback_minutes: int = 60,
    ) -> list[UnusualTrade]:
        """
        Detect unusual options activity using Alpha Vantage data.

        NOTE: Alpha Vantage provides historical data, not real-time intraday volume.
        This is a limitation of the free tier.
        """
        app_logger.info(f"Detecting unusual activity for {symbol} from AlphaVantageFlowProvider")

        # Fetch option chain
        chain = await self.get_option_chain(symbol)

        # Get 30-day average volume (simplified: use current OI as proxy)
        # In a production system, you'd fetch historical data
        unusual_trades: list[UnusualTrade] = []
        detected_at = datetime.now(UTC)

        for contract in chain["contracts"]:
            # Skip if no volume or OI
            if contract["volume"] == 0 and contract["open_interest"] == 0:
                continue

            # Calculate metrics
            vol_oi_ratio = contract["volume"] / max(contract["open_interest"], 1)

            # Use OI as proxy for avg volume (limitation of free tier)
            avg_volume_30d = float(contract["open_interest"]) * 0.1  # Assume 10% turnover

            bid_ask_spread = float(contract["ask"] - contract["bid"])
            mid_price = (contract["bid"] + contract["ask"]) / 2
            bid_ask_spread_pct = bid_ask_spread / float(mid_price) if mid_price > 0 else 1.0

            premium = Decimal(str(contract["volume"])) * contract["last_price"] * 100

            # Compute anomaly score
            score, flags = compute_anomaly_score(
                volume=contract["volume"],
                open_interest=contract["open_interest"],
                avg_volume_30d=avg_volume_30d,
                bid_ask_spread_pct=bid_ask_spread_pct,
                premium=premium,
            )

            # Filter by minimum score
            if score >= min_score:
                unusual_trades.append(
                    UnusualTrade(
                        symbol=symbol,
                        contract_symbol=contract["contract_symbol"],
                        option_type=contract["option_type"],
                        strike=contract["strike"],
                        expiration=contract["expiration"],
                        last_price=contract["last_price"],
                        volume=contract["volume"],
                        open_interest=contract["open_interest"],
                        volume_oi_ratio=vol_oi_ratio,
                        premium=premium,
                        anomaly_score=score,
                        flags=flags,
                        detected_at=detected_at,
                    )
                )

        app_logger.info(
            f"Found {len(unusual_trades)} unusual trades for {symbol} (min_score={min_score})"
        )

        return unusual_trades
