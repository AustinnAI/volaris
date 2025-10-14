"""
Utilities for fetching the S&P 500 constituent list from Wikipedia.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from urllib.request import Request, urlopen

import aiohttp
from bs4 import BeautifulSoup

from app.utils.logger import app_logger

WIKIPEDIA_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
USER_AGENT = "VolarisBot/1.0 (+https://github.com/volaris-trading)"


def parse_sp500_table(html: str) -> list[str]:
    """Parse the S&P 500 HTML table and return the constituent symbols."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"id": "constituents"})
    if table is None:
        table = soup.find("table", class_="wikitable")
    if table is None:
        return []

    symbols: list[str] = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if not cells:
            continue
        symbol = cells[0].get_text(strip=True)
        if symbol:
            symbol = symbol.upper()
            if symbol not in symbols:
                symbols.append(symbol)
    return symbols


async def fetch_sp500_symbols_wikipedia() -> list[str]:
    """Fetch the S&P 500 constituent list from Wikipedia asynchronously."""
    timeout = aiohttp.ClientTimeout(total=30)
    headers = {"User-Agent": USER_AGENT}

    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(WIKIPEDIA_SP500_URL) as response:
                if response.status != 200:
                    app_logger.warning(
                        "Wikipedia S&P 500 request failed",
                        extra={"status": response.status},
                    )
                    return []
                html = await response.text()
    except Exception as exc:  # pylint: disable=broad-except
        app_logger.warning(
            "Unable to fetch S&P 500 constituents from Wikipedia",
            extra={"error": str(exc)},
        )
        return []

    symbols = parse_sp500_table(html)
    app_logger.info(
        "Fetched %s S&P 500 symbols from Wikipedia",
        len(symbols),
    )
    return symbols


def fetch_sp500_symbols_wikipedia_sync() -> list[str]:
    """Fetch the S&P 500 list synchronously (used for startup fallbacks)."""
    request = Request(WIKIPEDIA_SP500_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=30) as response:  # nosec B310 - controlled URL
            html = response.read().decode("utf-8", errors="ignore")
    except Exception as exc:  # pylint: disable=broad-except
        app_logger.warning(
            "Unable to fetch S&P 500 constituents from Wikipedia (sync)",
            extra={"error": str(exc)},
        )
        return []

    symbols = parse_sp500_table(html)
    app_logger.info(
        "Fetched %s S&P 500 symbols from Wikipedia (sync)",
        len(symbols),
    )
    return symbols


async def ensure_sp500_symbols(fetchers: Iterable[callable]) -> list[str]:
    """Try multiple fetchers until one returns symbols."""
    for fetcher in fetchers:
        try:
            if asyncio.iscoroutinefunction(fetcher):
                symbols = await fetcher()
            else:
                symbols = fetcher()
        except Exception:  # pylint: disable=broad-except
            continue
        if symbols:
            return symbols
    return []


__all__ = [
    "WIKIPEDIA_SP500_URL",
    "fetch_sp500_symbols_wikipedia",
    "fetch_sp500_symbols_wikipedia_sync",
    "parse_sp500_table",
    "ensure_sp500_symbols",
]
