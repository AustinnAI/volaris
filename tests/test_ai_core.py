"""
Basic tests for AI summarization core module (Phase 2 Enhancement).

Tests schema validation, prompt building, cache key generation, and formatters.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.core.ai import (
    SummaryResponse,
    build_cache_key,
    create_fallback_summary,
    render_discord_markdown,
)
from app.core.ai.schema import KeyDriver, SentimentSnapshot
from app.db.models import NewsArticle, Ticker


class TestAISchema:
    """Test Pydantic schema validation."""

    def test_summary_response_valid(self):
        """Valid SummaryResponse should parse correctly."""
        data = {
            "ticker": "SPY",
            "executive_summary": "Strong bullish momentum.",
            "key_drivers": [
                {"theme": "Tech earnings beats", "supporting_articles": [1, 2]},
            ],
            "sentiment_snapshot": {
                "net_score": 0.72,
                "dispersion": "low",
                "recent_change": "improving",
            },
            "risk_flags": [],
            "follow_ups": [],
            "sources": [
                {
                    "idx": 1,
                    "title": "Tech stocks rally",
                    "url": "https://example.com/1",
                    "published_at": "2025-01-01T12:00:00",
                }
            ],
            "generated_at": "2025-01-01T12:00:00",
            "prompt_version": "v1",
        }

        summary = SummaryResponse(**data)
        assert summary.ticker == "SPY"
        assert summary.sentiment_snapshot.net_score == 0.72

    def test_sentiment_snapshot_invalid_score(self):
        """Sentiment score outside [-1, 1] should raise validation error."""
        with pytest.raises(ValidationError):
            SentimentSnapshot(net_score=1.5, dispersion="low", recent_change="improving")

    def test_sentiment_snapshot_invalid_dispersion(self):
        """Invalid dispersion value should raise validation error."""
        with pytest.raises(ValidationError):
            SentimentSnapshot(net_score=0.5, dispersion="invalid", recent_change="improving")


class TestCacheKey:
    """Test cache key generation."""

    def test_cache_key_deterministic(self):
        """Same inputs should produce same cache key."""
        urls = ["https://example.com/1", "https://example.com/2"]
        key1 = build_cache_key("SPY", urls)
        key2 = build_cache_key("SPY", urls)
        assert key1 == key2

    def test_cache_key_different_urls(self):
        """Different URLs should produce different cache keys."""
        urls1 = ["https://example.com/1"]
        urls2 = ["https://example.com/2"]
        key1 = build_cache_key("SPY", urls1)
        key2 = build_cache_key("SPY", urls2)
        assert key1 != key2

    def test_cache_key_format(self):
        """Cache key should have expected format."""
        urls = ["https://example.com/1"]
        key = build_cache_key("SPY", urls)
        # Format: ai:sum:{provider}:{model}:{version}:{ticker}:{urls_hash}
        # Note: model can contain hyphens (e.g., gpt-4o-mini)
        assert key.startswith("ai:sum:")
        assert ":SPY:" in key
        parts = key.split(":")
        assert parts[0] == "ai"
        assert parts[1] == "sum"


class TestFallbackSummary:
    """Test deterministic fallback summary generation."""

    def test_fallback_with_articles(self):
        """Fallback should generate summary from article headlines."""
        ticker = Ticker(id=1, symbol="SPY", is_active=True)
        articles = [
            NewsArticle(
                id=1,
                ticker_id=1,
                ticker=ticker,
                headline="Tech stocks rally on strong earnings",
                url="https://example.com/1",
                source="Reuters",
                published_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            ),
            NewsArticle(
                id=2,
                ticker_id=1,
                ticker=ticker,
                headline="Fed signals dovish stance",
                url="https://example.com/2",
                source="Bloomberg",
                published_at=datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC),
            ),
        ]

        sentiment_data = {
            "compound": 0.65,
            "positive": 0.7,
            "neutral": 0.2,
            "negative": 0.1,
            "trend": "improving",
        }

        summary = create_fallback_summary("SPY", articles, sentiment_data)

        assert summary.ticker == "SPY"
        assert summary.prompt_version == "fallback"
        assert len(summary.key_drivers) == 2
        assert summary.sentiment_snapshot.net_score == 0.65
        assert summary.sentiment_snapshot.recent_change == "improving"
        assert len(summary.sources) == 2

    def test_fallback_no_articles(self):
        """Fallback with no articles should return empty summary."""
        sentiment_data = {"compound": 0.0, "trend": "stable"}
        summary = create_fallback_summary("SPY", [], sentiment_data)

        assert summary.ticker == "SPY"
        assert "No recent news" in summary.executive_summary
        assert len(summary.key_drivers) == 0
        assert len(summary.sources) == 0


class TestDiscordFormatter:
    """Test Discord markdown rendering."""

    def test_render_markdown_structure(self):
        """Rendered markdown should have expected sections."""
        summary = SummaryResponse(
            ticker="SPY",
            executive_summary="Strong bullish momentum driven by tech earnings.",
            key_drivers=[
                KeyDriver(theme="Tech earnings beats", supporting_articles=[1]),
            ],
            sentiment_snapshot=SentimentSnapshot(
                net_score=0.72, dispersion="low", recent_change="improving"
            ),
            risk_flags=[],
            follow_ups=[],
            sources=[
                {
                    "idx": 1,
                    "title": "Tech stocks rally",
                    "url": "https://example.com/1",
                    "published_at": "2025-01-01T12:00:00",
                }
            ],
            generated_at="2025-01-01T12:00:00",
            prompt_version="v1",
        )

        markdown = render_discord_markdown(summary)

        assert "**SPY Market Intelligence**" in markdown
        assert "**Executive Summary:**" in markdown
        assert "Strong bullish momentum" in markdown
        assert "**Key Drivers:**" in markdown
        assert "Tech earnings beats" in markdown
        assert "**Sentiment:**" in markdown
        assert "Positive" in markdown
        assert "**Sources:**" in markdown

    def test_render_markdown_fallback_indicator(self):
        """Fallback mode should show indicator."""
        summary = SummaryResponse(
            ticker="SPY",
            executive_summary="Test",
            key_drivers=[],
            sentiment_snapshot=SentimentSnapshot(
                net_score=0.0, dispersion="low", recent_change="stable"
            ),
            risk_flags=[],
            follow_ups=[],
            sources=[],
            generated_at="2025-01-01T12:00:00",
            prompt_version="fallback",
        )

        markdown = render_discord_markdown(summary, fallback_used=True)
        assert "Fallback Mode" in markdown
