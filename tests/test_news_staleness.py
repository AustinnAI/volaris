"""Unit tests for news staleness logic."""

from datetime import UTC, datetime, timedelta

from app.services.news_service import is_stale
from app.utils.market_hours import is_market_hours


class TestMarketHours:
    """Test market hours detection."""

    def test_market_hours_weekday_open(self):
        """Market hours on weekday during trading (10 AM ET = 2 PM UTC)."""
        # Tuesday Nov 5, 2025, 10:00 AM ET = 3:00 PM UTC (daylight saving)
        dt = datetime(2025, 11, 5, 15, 0, tzinfo=UTC)
        assert is_market_hours(dt) is True

    def test_market_hours_weekday_closed_before(self):
        """Before market hours on weekday (8 AM ET = 12 PM UTC)."""
        # Tuesday Nov 5, 2025, 8:00 AM ET = 1:00 PM UTC
        dt = datetime(2025, 11, 5, 13, 0, tzinfo=UTC)
        assert is_market_hours(dt) is False

    def test_market_hours_weekday_closed_after(self):
        """After market hours on weekday (5 PM ET = 9 PM UTC)."""
        # Tuesday Nov 5, 2025, 5:00 PM ET = 10:00 PM UTC
        dt = datetime(2025, 11, 5, 22, 0, tzinfo=UTC)
        assert is_market_hours(dt) is False

    def test_market_hours_weekend(self):
        """Market closed on weekend."""
        # Saturday Nov 9, 2025, 10:00 AM ET = 3:00 PM UTC
        dt = datetime(2025, 11, 9, 15, 0, tzinfo=UTC)
        assert is_market_hours(dt) is False

    def test_market_hours_opening(self):
        """Market hours at opening bell (9:30 AM ET = 2:30 PM UTC)."""
        # Tuesday Nov 5, 2025, 9:30 AM ET = 2:30 PM UTC
        dt = datetime(2025, 11, 5, 14, 30, tzinfo=UTC)
        assert is_market_hours(dt) is True

    def test_market_hours_closing(self):
        """Market hours just before close (3:59 PM ET = 8:59 PM UTC)."""
        # Tuesday Nov 5, 2025, 3:59 PM ET = 8:59 PM UTC
        dt = datetime(2025, 11, 5, 20, 59, tzinfo=UTC)
        assert is_market_hours(dt) is True


class TestIsStale:
    """Test news staleness detection."""

    def test_no_articles_not_stale(self):
        """No articles (None) should not be stale."""
        assert is_stale(None) is False

    def test_fresh_articles_market_hours(self):
        """Fresh articles during market hours (< 6h) not stale."""
        # Latest article: 2 hours ago
        now = datetime(2025, 11, 5, 15, 0, tzinfo=UTC)  # 10 AM ET (market hours)
        latest = now - timedelta(hours=2)

        assert is_stale(latest, now) is False

    def test_stale_articles_market_hours(self):
        """Stale articles during market hours (> 6h) are stale."""
        # Latest article: 7 hours ago (exceeds 6h threshold)
        now = datetime(2025, 11, 5, 15, 0, tzinfo=UTC)  # 10 AM ET (market hours)
        latest = now - timedelta(hours=7)

        assert is_stale(latest, now) is True

    def test_fresh_articles_off_hours(self):
        """Fresh articles outside market hours (< 12h) not stale."""
        # Latest article: 10 hours ago
        now = datetime(2025, 11, 5, 22, 0, tzinfo=UTC)  # 5 PM ET (after hours)
        latest = now - timedelta(hours=10)

        assert is_stale(latest, now) is False

    def test_stale_articles_off_hours(self):
        """Stale articles outside market hours (> 12h) are stale."""
        # Latest article: 13 hours ago (exceeds 12h threshold)
        now = datetime(2025, 11, 5, 22, 0, tzinfo=UTC)  # 5 PM ET (after hours)
        latest = now - timedelta(hours=13)

        assert is_stale(latest, now) is True

    def test_boundary_case_market_hours_exact_threshold(self):
        """Exactly 6 hours old during market hours (not stale)."""
        now = datetime(2025, 11, 5, 15, 0, tzinfo=UTC)
        latest = now - timedelta(hours=6)

        # Should NOT be stale (not exceeding threshold)
        assert is_stale(latest, now) is False

    def test_boundary_case_market_hours_just_over_threshold(self):
        """Just over 6 hours during market hours (stale)."""
        now = datetime(2025, 11, 5, 15, 0, tzinfo=UTC)
        latest = now - timedelta(hours=6, seconds=1)

        # Should be stale (exceeds threshold)
        assert is_stale(latest, now) is True

    def test_boundary_case_off_hours_exact_threshold(self):
        """Exactly 12 hours old outside market hours (not stale)."""
        now = datetime(2025, 11, 5, 22, 0, tzinfo=UTC)  # After hours
        latest = now - timedelta(hours=12)

        # Should NOT be stale (not exceeding threshold)
        assert is_stale(latest, now) is False

    def test_boundary_case_off_hours_just_over_threshold(self):
        """Just over 12 hours outside market hours (stale)."""
        now = datetime(2025, 11, 5, 22, 0, tzinfo=UTC)  # After hours
        latest = now - timedelta(hours=12, seconds=1)

        # Should be stale (exceeds threshold)
        assert is_stale(latest, now) is True

    def test_weekend_uses_off_hours_threshold(self):
        """Weekend should use 12h threshold (off-hours)."""
        # Saturday 10 AM ET (market closed)
        now = datetime(2025, 11, 9, 15, 0, tzinfo=UTC)
        latest = now - timedelta(hours=10)

        # 10 hours on weekend < 12h threshold → not stale
        assert is_stale(latest, now) is False

        # 13 hours on weekend > 12h threshold → stale
        latest_stale = now - timedelta(hours=13)
        assert is_stale(latest_stale, now) is True
