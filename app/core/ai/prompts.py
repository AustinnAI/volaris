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


def build_news_narrative_prompt(
    ticker: str,
    articles: list[NewsArticle],
    sentiment_data: dict,
) -> str:
    """
    Build prompt for news narrative (Phase 2.2).

    Args:
        ticker: Ticker symbol.
        articles: Recent articles (top 10).
        sentiment_data: VADER sentiment metrics.

    Returns:
        Prompt for generating 2-3 sentence "Story of the Day" narrative.
    """
    # Format recent articles with summaries (top 5 for richer context)
    articles_text = ""
    for idx, article in enumerate(articles[:5], start=1):
        articles_text += f"{idx}. {article.headline}\n"

        # Include article summary if available (truncate to ~400 chars for cost control)
        if article.summary:
            summary_text = article.summary[:400].strip()
            if len(article.summary) > 400:
                summary_text += "..."
            articles_text += f"   Summary: {summary_text}\n"

        articles_text += "\n"

    compound = sentiment_data.get("compound", 0.0)
    trend = sentiment_data.get("trend", "stable")

    prompt = f"""You are analyzing news for **{ticker}**.

**Recent Articles:**
{articles_text}

**Sentiment:** {compound:.2f} (compound score), Trend: {trend}

**Task:** Write a concise "Story of the Day" narrative (2-3 sentences max) explaining what's driving **{ticker}** today. Focus on the main theme connecting the articles and market implications.

**Output:** Respond with ONLY a JSON object:
{{
  "narrative": "Your 2-3 sentence story here"
}}

**Instructions:**
- **ONLY discuss {ticker}** - ignore mentions of other companies unless directly relevant to {ticker}'s story
- Be concise and actionable
- Connect themes across articles that relate to {ticker}
- Ground claims in provided article content
- No speculation beyond article content
- If articles don't contain meaningful {ticker}-specific information, provide a brief factual summary
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


def build_narrative_cache_key(ticker: str, article_urls: list[str]) -> str:
    """
    Build Redis cache key for news narrative (Phase 2.2).

    Args:
        ticker: Ticker symbol.
        article_urls: List of article URLs.

    Returns:
        Cache key string.
    """
    import hashlib

    urls_string = "|".join(sorted(article_urls))
    urls_hash = hashlib.md5(urls_string.encode()).hexdigest()[:12]

    provider = settings.LLM_PROVIDER
    model = settings.LLM_MODEL

    return f"ai:narrative:{provider}:{model}:{ticker.upper()}:{urls_hash}"


def build_top_movers_prompt(
    gainers: list[dict],
    losers: list[dict],
) -> str:
    """
    Build prompt for top movers market narrative (Phase 2.2).

    Args:
        gainers: List of top gainers with {symbol, weighted_score, article_count}.
        losers: List of top losers with {symbol, weighted_score, article_count}.

    Returns:
        Prompt for generating 3-4 sentence market narrative.
    """
    gainers_text = "\n".join(
        [f"- {g['symbol']}: {g['weighted_score']:.2f} sentiment ({g['article_count']} articles)"
         for g in gainers[:5]]
    )
    losers_text = "\n".join(
        [f"- {l['symbol']}: {l['weighted_score']:.2f} sentiment ({l['article_count']} articles)"
         for l in losers[:5]]
    )

    prompt = f"""You are analyzing market sentiment across the S&P 500.

**Top Gainers (by sentiment):**
{gainers_text}

**Top Losers (by sentiment):**
{losers_text}

**Task:** Write a "Market Pulse" narrative (3-4 sentences max) explaining what's driving the market today. Connect themes across sectors and explain the rotation/sentiment shift.

**Output:** Respond with ONLY a JSON object:
{{
  "narrative": "Your 3-4 sentence market pulse here"
}}

**Instructions:**
- Explain broader market themes (sector rotation, risk-on/off, etc.)
- Connect top movers to macro trends
- Be concise and actionable
- No speculation beyond sentiment data provided
"""
    return prompt


def build_top_movers_cache_key(ticker_symbols: list[str]) -> str:
    """
    Build Redis cache key for top movers narrative.

    Args:
        ticker_symbols: List of tickers in the analysis.

    Returns:
        Cache key string.
    """
    import hashlib

    symbols_string = "|".join(sorted(ticker_symbols))
    symbols_hash = hashlib.md5(symbols_string.encode()).hexdigest()[:12]

    provider = settings.LLM_PROVIDER
    model = settings.LLM_MODEL

    return f"ai:top:{provider}:{model}:{symbols_hash}"


def build_watchlist_insights_prompt(watchlist_data: list[dict]) -> str:
    """
    Build prompt for watchlist portfolio insights (Phase 2.2).

    Args:
        watchlist_data: List of {symbol, weighted_score, article_count, label}.

    Returns:
        Prompt for portfolio-level insights.
    """
    holdings_text = "\n".join([
        f"- {h['symbol']}: {h['weighted_score']:.2f} ({h['label']}) • {h['article_count']} articles"
        for h in watchlist_data
    ])

    prompt = f"""Analyze this portfolio watchlist.

**Holdings:**
{holdings_text}

**Task:** Provide "Portfolio Insights" (3-4 sentences) covering:
1. Overall sentiment and risk assessment
2. Sector concentration or correlation warnings
3. Notable themes across holdings

**Output:** JSON only:
{{
  "insights": "Your 3-4 sentence analysis"
}}

**Instructions:**
- Focus on portfolio-level risks/opportunities
- Identify concentration issues
- Be actionable and concise
"""
    return prompt


def build_watchlist_cache_key(ticker_symbols: list[str]) -> str:
    """Build Redis cache key for watchlist insights."""
    import hashlib

    symbols_string = "|".join(sorted(ticker_symbols))
    symbols_hash = hashlib.md5(symbols_string.encode()).hexdigest()[:12]

    return f"ai:watchlist:{settings.LLM_PROVIDER}:{settings.LLM_MODEL}:{symbols_hash}"
