"""Seed basic ticker data into database."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.db.database import engine, async_session_maker
from app.db.models import Ticker


async def seed_tickers():
    """Seed essential tickers for testing."""
    tickers_data = [
        {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "sector": "ETF"},
        {"symbol": "QQQ", "name": "Invesco QQQ Trust", "sector": "ETF"},
        {"symbol": "IWM", "name": "iShares Russell 2000 ETF", "sector": "ETF"},
        {"symbol": "DIA", "name": "SPDR Dow Jones Industrial Average ETF", "sector": "ETF"},
        {"symbol": "AAPL", "name": "Apple Inc.", "sector": "Technology"},
        {"symbol": "MSFT", "name": "Microsoft Corporation", "sector": "Technology"},
        {"symbol": "NVDA", "name": "NVIDIA Corporation", "sector": "Technology"},
        {"symbol": "TSLA", "name": "Tesla Inc.", "sector": "Automotive"},
        {"symbol": "AMZN", "name": "Amazon.com Inc.", "sector": "Consumer Cyclical"},
        {"symbol": "GOOGL", "name": "Alphabet Inc.", "sector": "Technology"},
        {"symbol": "META", "name": "Meta Platforms Inc.", "sector": "Technology"},
        {"symbol": "JPM", "name": "JPMorgan Chase & Co.", "sector": "Financial"},
    ]

    async with async_session_maker() as session:
        added = 0
        skipped = 0

        for ticker_data in tickers_data:
            # Check if exists
            stmt = select(Ticker).where(Ticker.symbol == ticker_data["symbol"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if not existing:
                ticker = Ticker(**ticker_data, is_active=True)
                session.add(ticker)
                print(f"✅ Added {ticker_data['symbol']} - {ticker_data['name']}")
                added += 1
            else:
                print(f"⏭️  {ticker_data['symbol']} already exists")
                skipped += 1

        await session.commit()
        print(f"\n{'='*60}")
        print(f"✅ Ticker seeding complete!")
        print(f"   Added: {added}")
        print(f"   Skipped: {skipped}")
        print(f"   Total: {added + skipped}")
        print(f"{'='*60}")


if __name__ == "__main__":
    print("Starting ticker seeding...\n")
    asyncio.run(seed_tickers())
