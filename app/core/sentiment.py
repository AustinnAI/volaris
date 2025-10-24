"""VADER sentiment analysis for financial news articles.

Uses VADER (Valence Aware Dictionary and sEntiment Reasoner) for lightweight,
rule-based sentiment analysis optimized for social media and short texts.

Chosen for V1 due to:
- No model downloads (instant startup)
- Fast processing (~1000 articles/sec)
- 70% accuracy (sufficient for V1)
- Zero GPU/memory overhead
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.utils.logger import app_logger

# Initialize VADER analyzer (singleton)
_vader_analyzer = SentimentIntensityAnalyzer()


def analyze_sentiment(text: str) -> dict[str, float | str]:
    """
    Analyze sentiment of text using VADER.

    Args:
        text: News headline or article text

    Returns:
        Dict with keys:
        - score: Positive sentiment score (0.0 - 1.0)
        - label: "positive", "neutral", or "negative"
        - compound: VADER compound score (-1.0 to 1.0)

    Example:
        >>> analyze_sentiment("Stock rallies on strong earnings")
        {
            "score": 0.8,
            "label": "positive",
            "compound": 0.6369
        }
    """
    if not text or not text.strip():
        return {"score": 0.5, "label": "neutral", "compound": 0.0}

    # Get VADER scores
    scores = _vader_analyzer.polarity_scores(text)
    compound = scores["compound"]

    # Classify using VADER thresholds
    if compound >= 0.05:
        label = "positive"
        score = (compound + 1) / 2  # Map [-1, 1] -> [0, 1], bias toward positive
    elif compound <= -0.05:
        label = "negative"
        score = (compound + 1) / 2  # Map [-1, 1] -> [0, 1], bias toward negative
    else:
        label = "neutral"
        score = 0.5

    app_logger.debug(
        "VADER sentiment analysis",
        extra={
            "text_preview": text[:100],
            "compound": compound,
            "label": label,
            "score": score,
        },
    )

    return {
        "score": round(score, 4),
        "label": label,
        "compound": round(compound, 4),
    }


def aggregate_sentiment(
    articles: list[dict],
    decay_hours: float = 24.0,
) -> dict[str, float | int | str]:
    """
    Aggregate sentiment across multiple articles with exponential recency weighting.

    Applies exponential decay: weight = exp(-age_hours / decay_hours)
    More recent articles have higher influence on aggregate sentiment.

    Args:
        articles: List of dicts with keys:
            - sentiment_compound: float (-1.0 to 1.0)
            - published_at: datetime
        decay_hours: Half-life for exponential decay (default: 24 hours)

    Returns:
        Dict with keys:
        - weighted_score: Weighted average sentiment (0.0 - 1.0)
        - compound: Weighted compound score (-1.0 to 1.0)
        - label: "positive", "neutral", or "negative"
        - article_count: Number of articles analyzed
        - bullish_percent: % of positive articles (unweighted)
        - bearish_percent: % of negative articles (unweighted)

    Example:
        >>> articles = [
        ...     {"sentiment_compound": 0.5, "published_at": datetime.now(UTC)},
        ...     {"sentiment_compound": -0.3, "published_at": datetime.now(UTC) - timedelta(hours=12)},
        ... ]
        >>> aggregate_sentiment(articles)
        {
            "weighted_score": 0.65,
            "compound": 0.28,
            "label": "positive",
            "article_count": 2,
            "bullish_percent": 50,
            "bearish_percent": 50
        }
    """
    if not articles:
        return {
            "weighted_score": 0.5,
            "compound": 0.0,
            "label": "neutral",
            "article_count": 0,
            "bullish_percent": 0,
            "bearish_percent": 0,
        }

    now = datetime.now(UTC)
    weighted_sum = 0.0
    weight_total = 0.0
    bullish_count = 0
    bearish_count = 0
    neutral_count = 0

    for article in articles:
        compound = float(article.get("sentiment_compound", 0.0))
        published_at = article.get("published_at")

        if not published_at:
            continue

        # Ensure timezone-aware datetime
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)

        # Calculate exponential decay weight
        age_hours = (now - published_at).total_seconds() / 3600
        weight = math.exp(-age_hours / decay_hours)

        weighted_sum += compound * weight
        weight_total += weight

        # Count sentiment distribution (unweighted)
        if compound >= 0.05:
            bullish_count += 1
        elif compound <= -0.05:
            bearish_count += 1
        else:
            neutral_count += 1

    # Calculate weighted compound score
    if weight_total == 0:
        weighted_compound = 0.0
    else:
        weighted_compound = weighted_sum / weight_total

    # Convert compound to 0-1 score and classify
    if weighted_compound >= 0.05:
        label = "positive"
        weighted_score = (weighted_compound + 1) / 2
    elif weighted_compound <= -0.05:
        label = "negative"
        weighted_score = (weighted_compound + 1) / 2
    else:
        label = "neutral"
        weighted_score = 0.5

    total_articles = len(articles)
    bullish_percent = round((bullish_count / total_articles) * 100) if total_articles > 0 else 0
    bearish_percent = round((bearish_count / total_articles) * 100) if total_articles > 0 else 0

    app_logger.debug(
        "Sentiment aggregation",
        extra={
            "article_count": total_articles,
            "weighted_compound": weighted_compound,
            "label": label,
            "bullish_percent": bullish_percent,
            "bearish_percent": bearish_percent,
        },
    )

    return {
        "weighted_score": round(weighted_score, 4),
        "compound": round(weighted_compound, 4),
        "label": label,
        "article_count": total_articles,
        "bullish_percent": bullish_percent,
        "bearish_percent": bearish_percent,
    }


def batch_analyze_sentiment(texts: list[str]) -> list[dict[str, float | str]]:
    """
    Batch analyze sentiment for multiple texts.

    Args:
        texts: List of news headlines or article texts

    Returns:
        List of sentiment dicts (see analyze_sentiment)

    Example:
        >>> texts = ["Stock soars on earnings beat", "Company misses revenue targets"]
        >>> batch_analyze_sentiment(texts)
        [
            {"score": 0.8, "label": "positive", "compound": 0.6},
            {"score": 0.2, "label": "negative", "compound": -0.5}
        ]
    """
    return [analyze_sentiment(text) for text in texts]
