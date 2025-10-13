"""
Tests for Wikipedia S&P 500 scraper utilities.
"""

from __future__ import annotations

from app.services.sp500_scraper import parse_sp500_table


def test_parse_sp500_table_extracts_symbols():
    """Ensure the parser extracts symbol column from Wikipedia table markup."""
    html = """
    <table id="constituents" class="wikitable">
        <tbody>
            <tr>
                <th>Symbol</th><th>Security</th>
            </tr>
            <tr>
                <td>AAPL</td><td>Apple Inc.</td>
            </tr>
            <tr>
                <td>MSFT</td><td>Microsoft Corp.</td>
            </tr>
        </tbody>
    </table>
    """
    symbols = parse_sp500_table(html)
    assert symbols == ["AAPL", "MSFT"]


def test_parse_sp500_table_handles_missing_table():
    """Parser returns empty list when no table present."""
    symbols = parse_sp500_table("<html><body>No table here</body></html>")
    assert symbols == []
