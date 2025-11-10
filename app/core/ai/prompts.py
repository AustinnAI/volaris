"""
Prompt Engineering for AI Summaries.

Builds grounded prompts from article context and VADER sentiment data.
"""

from datetime import datetime

from app.config import settings
from app.db.models import NewsArticle


def build_single_ticker_prompt(
    ticker: str,
    articles: list[NewsArticle],
    sentiment_data: dict,
    prompt_version: str | None = None,
) -> str:
    """
    Build grounded prompt for single-ticker summary.

    Args:
        ticker: Ticker symbol (e.g., SPY).
        articles: Top K recent articles (already sorted by recency).
        sentiment_data: Dict with keys: compound, positive, neutral, negative, trend.
        prompt_version: Prompt template version (defaults to settings.PROMPT_VERSION).

    Returns:
        Complete prompt string with system instructions and article context.
    """
    if prompt_version is None:
        prompt_version = settings.PROMPT_VERSION

    # Format articles with 1-indexed citations
    articles_text = ""
    sources_json = []

    for idx, article in enumerate(articles, start=1):
        articles_text += f"\n[{idx}] {article.headline}\n"
        articles_text += f"    Source: {article.source}\n"
        articles_text += f"    Published: {article.published_at.strftime('%Y-%m-%d %H:%M UTC')}\n"

        # Include article summary for richer context (truncate to ~150 words to control tokens)
        if article.summary:
            # Truncate to ~600 chars (roughly 150 words) to balance cost vs quality
            summary_text = article.summary[:600].strip()
            if len(article.summary) > 600:
                summary_text += "..."
            articles_text += f"    Summary: {summary_text}\n"

        sources_json.append(
            {
                "idx": idx,
                "title": article.headline,
                "url": article.url,
                "published_at": article.published_at.isoformat(),
            }
        )

    # Extract sentiment metrics
    compound = sentiment_data.get("compound", 0.0)
    positive = sentiment_data.get("positive", 0.0)
    neutral = sentiment_data.get("neutral", 0.0)
    negative = sentiment_data.get("negative", 0.0)
    trend = sentiment_data.get("trend", "stable")

    # Determine dispersion
    sentiment_values = [positive, neutral, negative]
    max_val = max(sentiment_values)
    min_val = min(sentiment_values)
    dispersion_range = max_val - min_val

    if dispersion_range < 0.3:
        dispersion = "low"
    elif dispersion_range < 0.6:
        dispersion = "medium"
    else:
        dispersion = "high"

    # Current timestamp
    now = datetime.utcnow().isoformat()

    prompt = f"""You are analyzing market sentiment for **{ticker}** based on recent news articles.

**Articles** (most recent first):
{articles_text}

**Current Sentiment Metrics** (VADER analysis):
- Compound Score: {compound:.2f} (-1.0 to +1.0)
- Positive: {positive:.2f}
- Neutral: {neutral:.2f}
- Negative: {negative:.2f}
- Recent Trend: {trend}

**Your Task:**
Generate a structured market intelligence summary in **valid JSON format** following this exact schema:

{{
  "ticker": "{ticker}",
  "executive_summary": "2-3 sentence overview of market conditions and key themes. Be concise and actionable.",
  "key_drivers": [
    {{
      "theme": "Brief theme description (e.g., 'Tech earnings beats')",
      "supporting_articles": [1, 2]
    }}
  ],
  "sentiment_snapshot": {{
    "net_score": {compound},
    "dispersion": "{dispersion}",
    "recent_change": "{trend}"
  }},
  "risk_flags": [
    {{
      "concern": "Brief risk description",
      "severity": "low|medium|high"
    }}
  ],
  "follow_ups": [
    {{
      "question": "Actionable question or monitoring item",
      "rationale": "Why this matters"
    }}
  ],
  "sources": {sources_json},
  "generated_at": "{now}",
  "prompt_version": "{prompt_version}"
}}

**Instructions:**
1. **Executive Summary**: 2-3 sentences summarizing market conditions, key themes, and directional bias.
2. **Key Drivers** (2-4 items): Identify main themes across articles. Cite article indices [1], [2], etc.
3. **Sentiment Snapshot**: Use provided VADER metrics exactly as shown above.
4. **Risk Flags** (0-3 items): Notable concerns, regulatory issues, or headwinds. Leave empty array if none.
5. **Follow-ups** (0-3 items): Suggested monitoring items, data releases, or events to watch.
6. **Sources**: Use the exact sources array provided above.

**Constraints:**
- Output **only valid JSON** - no markdown, no explanations
- Ground all claims in provided articles (cite indices)
- Do NOT speculate beyond article content
- Keep themes concise (< 10 words each)
- Prioritize actionable insights over description
"""

    return prompt


def build_cache_key(ticker: str, article_urls: list[str]) -> str:
    """
    Build Redis cache key for AI summary.

    Args:
        ticker: Ticker symbol.
        article_urls: List of article URLs used in summary (for invalidation).

    Returns:
        Cache key string.
    """
    import hashlib

    # Hash URL list for compact key
    urls_string = "|".join(sorted(article_urls))
    urls_hash = hashlib.md5(urls_string.encode()).hexdigest()[:12]

    provider = settings.LLM_PROVIDER
    model = settings.LLM_MODEL
    version = settings.PROMPT_VERSION

    return f"ai:sum:{provider}:{model}:{version}:{ticker.upper()}:{urls_hash}"
