"""
Autocomplete helpers for Discord slash commands.

This module centralizes symbol loading logic so cogs can share a consistent
autocomplete experience without duplicating CSV loading or API merge logic.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterable, Sequence

from app.services.sp500_scraper import fetch_sp500_symbols_wikipedia_sync

logger = logging.getLogger("volaris.discord.autocomplete")

# Priority ETFs to surface before equities for better UX.
PRIORITY_SYMBOLS: list[str] = [
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "VOO",
    "VTI",
    "GLD",
    "SLV",
    "TLT",
    "EEM",
]


def load_sp500_symbols(csv_path: Path | None = None) -> list[str]:
    """Return the list of S&P 500 tickers from the bundled CSV.

    Args:
        csv_path: Optional override path for the CSV file.

    Returns:
        Combined list of priority ETFs followed by unique S&P 500 symbols.
        Falls back to a curated subset if the CSV cannot be read.
    """
    symbols: list[str] = []
    path = csv_path or Path(__file__).resolve().parents[2] / "SP500.csv"

    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    symbol = (row.get("Symbol") or "").strip()
                    if symbol:
                        symbols.append(symbol)
            logger.info("Loaded %s S&P 500 symbols from %s", len(symbols), path)
        else:
            logger.warning("SP500.csv not found at %s; fetching from Wikipedia", path)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Failed to load SP500.csv: %s", exc)

    if not symbols:
        symbols = fetch_sp500_symbols_wikipedia_sync()

    if not symbols:
        logger.warning("Falling back to static S&P 500 seed list")
        symbols = [
            "AAPL",
            "MSFT",
            "GOOGL",
            "AMZN",
            "NVDA",
            "META",
            "TSLA",
            "NFLX",
            "JPM",
            "BAC",
            "V",
            "MA",
            "WMT",
            "HD",
            "UNH",
            "JNJ",
        ]

    # Deduplicate while preserving priority ordering.
    merged = PRIORITY_SYMBOLS + [s for s in symbols if s not in PRIORITY_SYMBOLS]
    return merged


class SymbolService:
    """Manage cached ticker symbols for Discord autocomplete."""

    def __init__(self, initial_symbols: Sequence[str] | None = None) -> None:
        """
        Initialize the symbol cache.

        Args:
            initial_symbols: Optional seed list of symbols.
        """
        self._symbols: list[str] = list(initial_symbols) if initial_symbols else load_sp500_symbols()

    @property
    def symbols(self) -> list[str]:
        """Return the cached symbols."""
        return list(self._symbols)

    def update(self, api_symbols: Iterable[str]) -> None:
        """Merge API-provided symbols with the priority list.

        Args:
            api_symbols: Symbols returned from the Volaris API.
        """
        merged = PRIORITY_SYMBOLS + [s for s in api_symbols if s not in PRIORITY_SYMBOLS]
        self._symbols = merged
        logger.info("Updated symbol cache with %s entries", len(self._symbols))

    def matches(self, query: str, limit: int = 25) -> list[str]:
        """Return symbol matches for the current query.

        Args:
            query: Current user input.
            limit: Maximum number of matches to return (Discord hard limit is 25).

        Returns:
            List of symbol strings.
        """
        if not query:
            return self._symbols[:limit]

        prefix = query.upper()
        return [symbol for symbol in self._symbols if symbol.startswith(prefix)][:limit]
