"""
AI Summary Formatters.

Renders structured summaries as Discord markdown and creates deterministic fallbacks.
"""

from datetime import datetime

from app.core.ai.schema import SummaryResponse
from app.db.models import NewsArticle


def render_discord_markdown(summary: SummaryResponse, fallback_used: bool = False) -> str:
    """
    Convert SummaryResponse to Discord-optimized markdown.

    Args:
        summary: Structured summary data.
        fallback_used: Whether deterministic fallback was used.

    Returns:
        Formatted markdown string for Discord embed.
    """
    lines = []

    # Header with ticker and fallback indicator
    header = f"📊 **{summary.ticker} Market Intelligence**"
    if fallback_used:
        header += " ⚙️ (Fallback Mode)"
    lines.append(header)
    lines.append("")

    # Executive Summary
    lines.append("**Executive Summary:**")
    lines.append(summary.executive_summary)
    lines.append("")

    # Key Drivers
    if summary.key_drivers:
        lines.append("**Key Drivers:**")
        for driver in summary.key_drivers:
            article_refs = ", ".join([f"[{idx}]" for idx in driver.supporting_articles])
            lines.append(f"• {driver.theme} ({article_refs})")
        lines.append("")

    # Sentiment Snapshot
    sentiment = summary.sentiment_snapshot
    sentiment_emoji = (
        "🟢" if sentiment.net_score > 0.05 else "🔴" if sentiment.net_score < -0.05 else "🟡"
    )
    sentiment_label = (
        "Positive"
        if sentiment.net_score > 0.05
        else "Negative" if sentiment.net_score < -0.05 else "Neutral"
    )

    lines.append("**Sentiment:**")
    lines.append(
        f"{sentiment_emoji} {sentiment_label} ({sentiment.net_score:+.2f}) • "
        f"{sentiment.recent_change.capitalize()} • Dispersion: {sentiment.dispersion}"
    )
    lines.append("")

    # Risk Flags
    if summary.risk_flags:
        lines.append("**Risk Flags:**")
        for risk in summary.risk_flags:
            severity_emoji = (
                "⚠️" if risk.severity == "high" else "⚡" if risk.severity == "medium" else "ℹ️"
            )
            lines.append(f"{severity_emoji} {risk.concern}")
        lines.append("")

    # Follow-ups
    if summary.follow_ups:
        lines.append("**Follow-ups:**")
        for followup in summary.follow_ups[:2]:  # Limit to 2 for Discord brevity
            lines.append(f"• {followup.question}")
        lines.append("")

    # Sources (compact format)
    lines.append("**Sources:**")
    for source in summary.sources[:5]:  # Limit to 5 for Discord
        # Truncate title if too long
        title = source.title if len(source.title) <= 60 else source.title[:57] + "..."
        lines.append(f"[{source.idx}] {title}")

    if len(summary.sources) > 5:
        lines.append(f"_...and {len(summary.sources) - 5} more_")

    lines.append("")
    lines.append(f"_Generated: {summary.generated_at}_")

    return "\n".join(lines)


def create_fallback_summary(
    ticker: str,
    articles: list[NewsArticle],
    sentiment_data: dict,
    reason: str = "LLM unavailable",
) -> SummaryResponse:
    """
    Create deterministic fallback summary when LLM fails or is disabled.

    Args:
        ticker: Ticker symbol.
        articles: Recent articles.
        sentiment_data: VADER sentiment metrics.
        reason: Reason for fallback.

    Returns:
        SummaryResponse with deterministic content.
    """
    from app.core.ai.schema import (
        KeyDriver,
        SentimentSnapshot,
        Source,
    )

    # Build executive summary from headlines (more readable format)
    if not articles:
        executive_summary = f"No recent news articles found for {ticker}. Market intelligence is limited without recent news coverage."
    elif len(articles) == 1:
        executive_summary = f"{ticker} has limited recent news coverage with 1 article: \"{articles[0].headline}\""
    else:
        # Create conversational summary with top headlines
        top_headline = articles[0].headline
        article_count = len(articles)

        # Truncate first headline if too long
        if len(top_headline) > 120:
            top_headline = top_headline[:117] + "..."

        executive_summary = (
            f"{ticker} has {article_count} recent articles. "
            f"Most recent: \"{top_headline}\""
        )

    # Create key drivers from top headlines (use full titles, truncate if needed)
    key_drivers = []
    for idx, article in enumerate(articles[:3], start=1):
        # Use full headline, truncate only if very long
        theme = article.headline
        if len(theme) > 100:
            theme = theme[:97] + "..."

        key_drivers.append(KeyDriver(theme=theme, supporting_articles=[idx]))

    # Sentiment snapshot
    compound = sentiment_data.get("compound", 0.0)
    positive = sentiment_data.get("positive", 0.0)
    neutral = sentiment_data.get("neutral", 0.0)
    negative = sentiment_data.get("negative", 0.0)
    trend = sentiment_data.get("trend", "stable")

    # Calculate dispersion
    sentiment_values = [positive, neutral, negative]
    max_val = max(sentiment_values) if sentiment_values else 0.0
    min_val = min(sentiment_values) if sentiment_values else 0.0
    dispersion_range = max_val - min_val

    if dispersion_range < 0.3:
        dispersion = "low"
    elif dispersion_range < 0.6:
        dispersion = "medium"
    else:
        dispersion = "high"

    sentiment_snapshot = SentimentSnapshot(
        net_score=compound, dispersion=dispersion, recent_change=trend
    )

    # Sources
    sources = []
    for idx, article in enumerate(articles, start=1):
        sources.append(
            Source(
                idx=idx,
                title=article.headline,
                url=article.url,
                published_at=article.published_at.isoformat(),
            )
        )

    # Build summary
    summary = SummaryResponse(
        ticker=ticker.upper(),
        executive_summary=executive_summary,
        key_drivers=key_drivers,
        sentiment_snapshot=sentiment_snapshot,
        risk_flags=[],  # No risk detection in fallback
        follow_ups=[],  # No follow-ups in fallback
        sources=sources,
        generated_at=datetime.utcnow().isoformat(),
        prompt_version="fallback",
    )

    return summary
