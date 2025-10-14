import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_fetch_sentiment_aggregates_data(monkeypatch):
    from app.services import market_insights

    mock_cache = AsyncMock()
    mock_cache.get.return_value = None
    mock_cache.set.return_value = True
    monkeypatch.setattr(market_insights, "cache", mock_cache)

    class MockFinnhub:
        async def get_recommendation_trends(self, symbol: str):
            return [
                {
                    "symbol": symbol,
                    "period": "2025-10-01",
                    "strongBuy": 5,
                    "buy": 12,
                    "hold": 4,
                    "sell": 1,
                    "strongSell": 0,
                }
            ]

        async def get_company_news(self, symbol: str):
            return [
                {
                    "headline": "Solid earnings",
                    "datetime": 1700000000,
                    "source": "Finnhub",
                    "url": "https://example.com/earnings",
                }
            ]

    monkeypatch.setattr(market_insights, "finnhub_client", MockFinnhub())
    monkeypatch.setattr(market_insights, "polygon_client", None)

    result = await market_insights.fetch_sentiment("AAPL")

    assert result["symbol"] == "AAPL"
    assert result["bullish_percent"] == 65.0
    assert result["recommendation_trend"]["buy"] == 12
    mock_cache.set.assert_awaited()


@pytest.mark.asyncio
async def test_get_top_movers_filters_sp500(monkeypatch):
    from app.services import market_insights

    mock_polygon = AsyncMock()
    mock_polygon.get_top_movers.side_effect = [
        [
            {
                "ticker": "AAPL",
                "todaysChangePerc": 3.2,
                "todaysChange": 6.0,
                "lastTrade": {"p": 190.0},
                "day": {"v": 100000},
            },
            {
                "ticker": "XYZ",
                "todaysChangePerc": 15.0,
                "todaysChange": 1.5,
                "lastTrade": {"p": 10.0},
            },
        ],
        [
            {
                "ticker": "MSFT",
                "todaysChangePerc": -2.0,
                "todaysChange": -6.4,
                "lastTrade": {"p": 320.0},
            },
            {
                "ticker": "PENN",
                "todaysChangePerc": -5.0,
                "todaysChange": -1.0,
                "lastTrade": {"p": 20.0},
            },
        ],
    ]
    monkeypatch.setattr(market_insights, "polygon_client", mock_polygon)

    sp500_symbols = {"AAPL", "MSFT", "NVDA"}
    result = await market_insights.get_top_movers(limit=1, sp500_symbols=sp500_symbols)

    assert result["gainers"][0]["symbol"] == "AAPL"
    assert result["losers"][0]["symbol"] == "MSFT"
