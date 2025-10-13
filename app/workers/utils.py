"""Utility helpers for worker jobs."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional

from app.utils.logger import app_logger


def to_decimal(value: Any) -> Optional[Decimal]:
    """Convert generic numeric values to Decimal, tolerating None."""

    if value is None:
        return None

    try:
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str) and value.strip():

            return Decimal(value)
    except (InvalidOperation, TypeError):
        app_logger.debug("Failed to parse decimal value", extra={"value": value})
    return None


def parse_timestamp(raw: Any) -> Optional[datetime]:
    """Normalise provider timestamps (epoch milliseconds, seconds, ISO strings)."""

    if raw is None:
        return None

    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)

    try:
        if isinstance(raw, (int, float)):
            # Heuristic: assume milliseconds when value is large.
            if raw > 10_000_000_000:
                raw /= 1000
            return datetime.fromtimestamp(raw, tz=timezone.utc)

        if isinstance(raw, str):
            raw = raw.strip()
            if not raw:
                return None
            # Accept ISO-8601 strings.
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                # Fallback: treat as integer epoch value encoded as string.
                numeric = float(raw)
                if numeric > 10_000_000_000:
                    numeric /= 1000
                return datetime.fromtimestamp(numeric, tz=timezone.utc)
    except Exception as exc:  # pylint: disable=broad-except
        app_logger.debug("Failed to parse timestamp", extra={"value": raw, "error": str(exc)})
    return None


def normalize_price_points(raw: Any) -> List[Dict[str, Any]]:
    """Extract a list of OHLCV dictionaries from provider responses."""

    if raw is None:
        return []

    if isinstance(raw, dict):
        for key in ("candles", "bars", "data", "prices"):
            if key in raw and isinstance(raw[key], Iterable):
                raw = raw[key]
                break

    if not isinstance(raw, Iterable):
        return []

    normalized: List[Dict[str, Any]] = []

    for item in raw:
        if not isinstance(item, dict):
            continue

        timestamp = parse_timestamp(
            item.get("datetime")
            or item.get("timestamp")
            or item.get("time")
            or item.get("date")
            or item.get("t")
        )

        if timestamp is None:
            continue

        open_price = to_decimal(item.get("open") or item.get("o"))
        high_price = to_decimal(item.get("high") or item.get("h"))
        low_price = to_decimal(item.get("low") or item.get("l"))
        close_price = to_decimal(item.get("close") or item.get("c"))
        volume = item.get("volume") or item.get("v")
        if isinstance(volume, str) and volume.isdigit():
            volume = int(volume)

        if None in (open_price, high_price, low_price, close_price):
            continue

        normalized.append(
            {
                "timestamp": timestamp,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume if isinstance(volume, int) else None,
            }
        )

    return normalized


def normalize_option_contracts(raw: Any) -> List[Dict[str, Any]]:
    """Flatten provider option-chain payloads into a list of contracts."""

    contracts: List[Dict[str, Any]] = []

    if raw is None:
        return contracts

    if isinstance(raw, dict):
        if "contracts" in raw and isinstance(raw["contracts"], Iterable):
            raw_list = raw["contracts"]
        else:
            # Schwab/TD style callExpDateMap / putExpDateMap
            combined: List[Dict[str, Any]] = []
            for key in ("callExpDateMap", "putExpDateMap"):
                exp_map = raw.get(key, {})
                if isinstance(exp_map, dict):
                    for expiration_key, strikes in exp_map.items():
                        if isinstance(strikes, dict):
                            expiration_value = None
                            if isinstance(expiration_key, str):
                                expiration_value = expiration_key.split(":")[0]
                            elif expiration_key:
                                expiration_value = str(expiration_key)

                            for strike_list in strikes.values():
                                for contract in strike_list:
                                    if not isinstance(contract, dict):
                                        continue
                                    enriched = dict(contract)
                                    if "expirationDate" not in enriched and "expiration" not in enriched:
                                        enriched["expiration"] = expiration_value
                                    combined.append(enriched)
            raw_list = combined
    elif isinstance(raw, Iterable):
        raw_list = raw
    else:
        raw_list = []

    for item in raw_list:
        if not isinstance(item, dict):
            continue
        strike = to_decimal(item.get("strikePrice") or item.get("strike"))
        option_type = item.get("putCall") or item.get("optionType") or item.get("type")
        if strike is None or option_type is None:
            continue

        contracts.append(
            {
                "option_type": str(option_type).lower(),
                "strike": strike,
                "bid": to_decimal(item.get("bid") or item.get("bidPrice")),
                "ask": to_decimal(item.get("ask") or item.get("askPrice")),
                "last": to_decimal(item.get("last") or item.get("lastPrice")),
                "mark": to_decimal(item.get("mark") or item.get("midpoint")),
                "volume": item.get("totalVolume") or item.get("volume"),
                "open_interest": item.get("openInterest"),
                "implied_vol": to_decimal(item.get("impliedVolatility") or item.get("iv")),
                "delta": to_decimal(item.get("delta")),
                "gamma": to_decimal(item.get("gamma")),
                "theta": to_decimal(item.get("theta")),
                "vega": to_decimal(item.get("vega")),
                "rho": to_decimal(item.get("rho")),
                "days_to_expiration": item.get("daysToExpiration") or item.get("dte"),
                "expiration": item.get("expirationDate") or item.get("expiration"),
            }
        )

    return contracts


def parse_date(raw: Any) -> Optional[date]:
    """Parse date-like payloads returned by providers."""

    if raw is None:
        return None

    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw

    timestamp = parse_timestamp(raw)
    if timestamp:
        return timestamp.date()
    return None
