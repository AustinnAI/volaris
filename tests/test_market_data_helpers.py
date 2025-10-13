"""Tests for helper functions powering market data endpoints."""

from typing import Any, Dict

from app.api.v1.market_data import (
    _extract_finnhub_earnings,
    _extract_schwab_quote,
)


def test_extract_schwab_quote_handles_nested_structure() -> None:
    """Schwab quote helper should unwrap nested payloads keyed by symbol."""
    payload: Dict[str, Any] = {
        "quotes": {
            "AAPL": {
                "quote": {
                    "lastPrice": 190.25,
                    "previousClose": 188.15,
                }
            }
        }
    }

    result = _extract_schwab_quote(payload, "AAPL")

    assert result["lastPrice"] == 190.25
    assert result["previousClose"] == 188.15


def test_extract_schwab_quote_handles_direct_quote() -> None:
    """Schwab quote helper should support direct `quote` payloads."""
    payload = {
        "quote": {
            "lastPrice": 402.1,
            "totalVolume": 123456,
        }
    }

    result = _extract_schwab_quote(payload, "SPY")

    assert result["lastPrice"] == 402.1
    assert result["totalVolume"] == 123456


def test_extract_finnhub_earnings_prefers_matching_symbol() -> None:
    """Finnhub earnings helper should choose entries for the requested ticker."""
    payload = {
        "earningsCalendar": [
            {
                "symbol": "MSFT",
                "date": "2024-05-01",
            },
            {
                "symbol": "AAPL",
                "date": "2024-05-02",
                "hour": "amc",
            },
        ]
    }

    record = _extract_finnhub_earnings(payload, "AAPL")

    assert record is not None
    assert record["symbol"] == "AAPL"
    assert record["date"] == "2024-05-02"
    assert record["hour"] == "amc"


def test_extract_finnhub_earnings_returns_none_when_empty() -> None:
    """Finnhub earnings helper should return None when payload lacks data."""
    payload = {"earningsCalendar": []}

    record = _extract_finnhub_earnings(payload, "TSLA")

    assert record is None
