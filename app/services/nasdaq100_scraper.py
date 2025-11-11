"""
Utilities for fetching the NASDAQ-100 constituent list from Wikipedia.
"""

from __future__ import annotations

import csv
from pathlib import Path

import aiohttp
from bs4 import BeautifulSoup

from app.utils.logger import app_logger

WIKIPEDIA_NASDAQ100_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"
USER_AGENT = "VolarisBot/1.0 (+https://github.com/volaris-trading)"


def parse_nasdaq100_table(html: str) -> list[str]:
    """Parse the NASDAQ-100 HTML table and return the constituent symbols."""
    soup = BeautifulSoup(html, "html.parser")

    # Find the constituents table
    table = soup.find("table", {"id": "constituents"})
    if table is None:
        # Try finding by class
        tables = soup.find_all("table", class_="wikitable")
        for t in tables:
            # Look for table with "Ticker" column
            if t.find("th", string=lambda s: s and "ticker" in s.lower()):
                table = t
                break

    if table is None:
        return []

    symbols: list[str] = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if not cells or len(cells) < 2:
            continue

        # NASDAQ-100 table usually has Company | Ticker | ...
        # Try to find ticker in first or second column
        symbol = None
        for i in range(min(2, len(cells))):
            text = cells[i].get_text(strip=True).upper()
            # Ticker symbols are usually short and alphanumeric
            if text and len(text) <= 5 and text.replace(".", "").isalnum():
                symbol = text
                break

        if symbol and symbol not in symbols:
            symbols.append(symbol)

    return symbols


async def fetch_nasdaq100_symbols_wikipedia() -> list[str]:
    """Fetch the NASDAQ-100 constituent list from Wikipedia asynchronously."""
    timeout = aiohttp.ClientTimeout(total=30)
    headers = {"User-Agent": USER_AGENT}

    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(WIKIPEDIA_NASDAQ100_URL) as response:
                if response.status != 200:
                    app_logger.warning(
                        "Wikipedia NASDAQ-100 request failed",
                        extra={"status": response.status},
                    )
                    return []
                html = await response.text()
    except Exception as exc:  # pylint: disable=broad-except
        app_logger.warning(
            "Unable to fetch NASDAQ-100 constituents from Wikipedia",
            extra={"error": str(exc)},
        )
        return []

    symbols = parse_nasdaq100_table(html)
    app_logger.info(
        "Fetched %s NASDAQ-100 symbols from Wikipedia",
        len(symbols),
    )
    return symbols


def load_nasdaq100_from_csv() -> list[str]:
    """Load NASDAQ-100 constituents from CSV fallback."""
    csv_path = Path(__file__).parent.parent / "NASDAQ100.csv"
    if not csv_path.exists():
        app_logger.warning("NASDAQ100.csv not found")
        return []

    symbols: list[str] = []
    try:
        with csv_path.open("r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Try common column names
                symbol = (
                    row.get("Symbol")
                    or row.get("Ticker")
                    or row.get("ticker")
                    or row.get("symbol")
                    or ""
                ).strip().upper()
                if symbol and symbol not in symbols:
                    symbols.append(symbol)

        app_logger.info(
            "Loaded %s NASDAQ-100 symbols from CSV",
            len(symbols),
        )
    except Exception as exc:  # pylint: disable=broad-except
        app_logger.error(
            "Failed to load NASDAQ100.csv",
            extra={"error": str(exc)},
        )
        return []

    return symbols


__all__ = [
    "WIKIPEDIA_NASDAQ100_URL",
    "fetch_nasdaq100_symbols_wikipedia",
    "parse_nasdaq100_table",
    "load_nasdaq100_from_csv",
]
