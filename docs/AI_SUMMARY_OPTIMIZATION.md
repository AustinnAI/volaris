# AI Summary Optimization Guide

**Status:** Phase 1 (Production Baseline)
**Last Updated:** 2025-11-06
**Current Config:** `SUMMARY_TOP_K=5`, `LLM_TIMEOUT_SECONDS=25`

---

## Overview

This document outlines article selection, ranking, and summarization optimization strategies for the AI-powered news summary feature (`/summary` command and `/api/v1/news/{ticker}/summary` endpoint).

### Current Implementation

**Article Selection Strategy:**
- Fetch recent articles (last 7 days)
- Sort by **recency** (most recent first)
- Apply **source diversity** (limit consecutive articles from same source)
- Take top `SUMMARY_TOP_K` articles (default: 5, range: 1-10)
- Send to LLM for structured summarization

**Performance Characteristics:**
- **Cold start:** 22-25 seconds (OpenAI API call)
- **Cached:** <1 second (Redis, 20-min TTL)
- **Expected cache hit rate:** 60-80% during market hours
- **Cost per summary:** ~$0.001 (gpt-4o-mini)

**Example:**
- AAPL has 10 articles in database
- Only 5 most recent (with diversity) sent to LLM
- Remaining 5 articles ignored

---

## Questions & Optimization Options

### 1. Can we rank articles by relevance to reduce LLM processing time?

#### Option A: **Sentiment-Weighted Ranking** ⭐ Recommended Quick Win

**Description:**
Prioritize articles with stronger sentiment signals and recency.

**Algorithm:**
```python
# Scoring function
score = abs(sentiment_compound) * 2.0 + recency_boost
# Where recency_boost = 1.0 if < 24h old, else 0.5

# Example scores:
# Article 1: |0.8| * 2 + 1.0 = 2.6 (strong sentiment, recent)
# Article 2: |0.2| * 2 + 1.0 = 1.4 (weak sentiment, recent)
# Article 3: |0.6| * 2 + 0.5 = 1.7 (moderate sentiment, older)
```

**Implementation:**
```python
# In ai_summary_service.py
from datetime import UTC, datetime, timedelta

# Fetch 2x articles
articles = await get_recent_news(db, ticker, limit=settings.SUMMARY_TOP_K * 2, days=7)

# Rank by sentiment magnitude + recency
ranked_articles = sorted(
    articles,
    key=lambda a: (
        abs(a.sentiment_compound or 0) * 2.0 +
        (1.0 if a.published_at > (datetime.now(UTC) - timedelta(hours=24)) else 0.5)
    ),
    reverse=True
)[:settings.SUMMARY_TOP_K]
```

**Pros:**
- ✅ Simple to implement (5 lines of code)
- ✅ No external dependencies
- ✅ Focuses LLM on high-signal articles
- ✅ ~20-30% latency reduction for high-activity tickers
- ✅ Free (no additional API costs)

**Cons:**
- ⚠️ May miss important neutral-sentiment news (e.g., routine guidance updates)
- ⚠️ Requires testing to validate quality doesn't degrade

**When to use:** If median LLM latency > 20s or OpenAI costs > $5/month

---

#### Option B: **Headline Similarity Clustering** (Advanced)

**Description:**
Use embeddings to cluster similar headlines and select diverse representatives.

**Algorithm:**
1. Generate embeddings for all headlines (OpenAI `text-embedding-3-small` or local `sentence-transformers`)
2. Cluster using cosine similarity (threshold: 0.85)
3. Select 1 article from each cluster (prioritize recency + sentiment)
4. Fill remaining slots with unclustered articles

**Implementation:**
```python
# Using OpenAI embeddings
import openai
from sklearn.metrics.pairwise import cosine_similarity

async def cluster_articles(articles: list[NewsArticle]) -> list[NewsArticle]:
    """Cluster articles by headline similarity and select diverse representatives."""
    headlines = [a.headline for a in articles]

    # Get embeddings
    response = await openai.Embedding.acreate(
        model="text-embedding-3-small",
        input=headlines
    )
    embeddings = [e.embedding for e in response.data]

    # Cluster (simple greedy approach)
    selected = []
    used = set()

    for i, article in enumerate(articles):
        if i in used:
            continue
        selected.append(article)

        # Mark similar articles as used
        for j in range(i + 1, len(articles)):
            if j not in used:
                sim = cosine_similarity([embeddings[i]], [embeddings[j]])[0][0]
                if sim > 0.85:
                    used.add(j)

        if len(selected) >= settings.SUMMARY_TOP_K:
            break

    return selected
```

**Pros:**
- ✅ Better theme coverage (avoids redundant articles)
- ✅ More comprehensive summaries
- ✅ Reduces "X company reports earnings" duplicates

**Cons:**
- ❌ Additional latency (~200-300ms for embeddings)
- ❌ Additional cost (~$0.0001 per request)
- ❌ External dependency (OpenAI or local model)
- ❌ More complex to maintain

**When to use:** If sentiment-weighted ranking isn't sufficient or if users report repetitive summaries

---

#### Option C: **Reduce SUMMARY_TOP_K** (Immediate)

**Description:**
Lower the article count from 5 to 3 globally.

**Configuration:**
```python
# In .env
SUMMARY_TOP_K=3  # Down from 5
```

**Pros:**
- ✅ Zero code changes
- ✅ ~30-40% faster LLM calls
- ✅ Lower OpenAI costs (~40% reduction)
- ✅ Still sufficient context for meaningful summaries

**Cons:**
- ⚠️ Less comprehensive for high-activity tickers
- ⚠️ Might miss important secondary themes
- ⚠️ Requires user testing to validate quality

**When to use:** As emergency measure if timeouts become frequent (>5% of requests)

---

### 2. Is optimization needed now, or should we wait?

**Recommendation: Wait and monitor** 📊

**Reasoning:**
1. **Current performance is acceptable:**
   - 22-25s cold start is within Discord's 60s timeout
   - <1s cached response meets user expectations
   - High cache hit rate (60-80%) means most requests are fast

2. **No production data yet:**
   - Don't know which tickers users will query most
   - Don't know actual cache hit rates
   - Don't know if timeouts will be an issue

3. **Premature optimization risks:**
   - May optimize for wrong metrics
   - Could degrade summary quality
   - Adds complexity without proven need

**Monitoring Plan:**

Track these metrics in production for 1-2 weeks:

```python
# Log structure
{
    "event": "ai_summary_generated",
    "ticker": "AAPL",
    "total_articles": 10,
    "top_k_used": 5,
    "llm_latency_ms": 23456,
    "cache_hit": false,
    "fallback_used": false,
    "tokens_used": 1250,
    "provider": "openai",
    "model": "gpt-4o-mini"
}
```

**Trigger optimization if:**
- Median LLM latency > 30s
- Timeout rate > 5%
- OpenAI costs > $10/month
- User complaints about speed

---

### 3. How to handle high-activity tickers (NVDA, TSLA, etc.)?

#### Strategy A: **Dynamic Timeout Based on Article Count**

**Implementation:**
```python
def calculate_timeout(article_count: int) -> int:
    """Calculate LLM timeout based on article count."""
    base_timeout = 15  # Minimum timeout
    per_article = 2    # 2 seconds per article
    max_timeout = 40   # Safety cap

    return min(base_timeout + (article_count * per_article), max_timeout)

# Examples:
# 3 articles: 15 + 6 = 21s
# 5 articles: 15 + 10 = 25s
# 10 articles: 15 + 20 = 35s (if we sent all 10)
```

**Pros:** Flexible, prevents unnecessary long timeouts for simple tickers
**Cons:** Adds complexity, still doesn't solve root cause (too many articles)

---

#### Strategy B: **Adaptive SUMMARY_TOP_K** ⭐ Recommended

**Description:**
Automatically reduce article count for high-activity tickers.

**Implementation:**
```python
def get_optimal_top_k(total_articles: int) -> int:
    """
    Determine optimal number of articles based on total count.
    High-activity tickers get fewer articles to prevent timeout.
    """
    if total_articles >= 20:
        return 3  # Popular stocks: focus on most recent
    elif total_articles >= 10:
        return 4  # Moderate activity
    else:
        return 5  # Default (low activity)

# In ai_summary_service.py
async def generate_ai_summary(db, ticker, force_refresh):
    # Get all recent articles to determine count
    all_articles = await get_recent_news(db, ticker, limit=50, days=7)

    # Determine optimal top_k
    top_k = get_optimal_top_k(len(all_articles))

    # Select articles
    articles = all_articles[:top_k]
    # ... rest of logic
```

**Pros:**
- ✅ Automatically adapts to ticker activity
- ✅ Prevents timeouts without sacrificing quality for low-activity tickers
- ✅ No global config changes needed

**Cons:**
- ⚠️ Adds query overhead (need to fetch more articles initially)
- ⚠️ More complex logic

**When to use:** If >10% of tickers with 10+ articles experience timeouts

---

## Recommended Phased Approach

### Phase 1: **Immediate** (Pre-Production) ✅ CURRENT

**Actions:**
- ✅ Set `LLM_TIMEOUT_SECONDS=25`
- ✅ Keep `SUMMARY_TOP_K=5`
- ✅ Deploy to production
- ✅ Add logging for LLM latency, article counts, cache hits

**Success Criteria:**
- Timeout rate < 5%
- Cache hit rate > 60%
- User satisfaction (no complaints)

**Duration:** 1-2 weeks

---

### Phase 2: **Short-term** (If Issues Arise)

**Trigger Conditions:**
- Median LLM latency > 30s
- Timeout rate > 5%
- User complaints about speed

**Actions (in order):**
1. **Implement sentiment-weighted ranking** (Option A)
   - Quick win, low risk
   - Expected: 20-30% latency reduction

2. **Reduce SUMMARY_TOP_K to 3** (if ranking insufficient)
   - Emergency measure
   - Test quality impact first

3. **Add enhanced logging:**
   ```python
   # Track per-ticker performance
   {
       "ticker": "NVDA",
       "p50_latency": 28000,
       "p95_latency": 35000,
       "timeout_rate": 0.08,
       "avg_articles": 15
   }
   ```

**Success Criteria:**
- Timeout rate < 2%
- Median latency < 25s
- No quality degradation (manual review of 20 summaries)

---

### Phase 3: **Long-term** (If Further Optimization Needed)

**Trigger Conditions:**
- Persistent timeout issues after Phase 2
- OpenAI costs > $20/month
- User requests for faster responses

**Actions:**
1. **Implement adaptive SUMMARY_TOP_K**
   - Automatically scale article count by ticker activity

2. **Add headline clustering** (Option B)
   - For high-activity tickers only
   - If redundancy is confirmed issue

3. **Consider streaming responses:**
   ```python
   # Show partial results while LLM generates
   await interaction.edit(content="📊 Fetching articles...")
   await interaction.edit(content="🤖 Generating summary...")
   await interaction.edit(content="✅ Complete!")
   ```

4. **Explore model alternatives:**
   - Test `gpt-4o-mini` vs `gpt-3.5-turbo` (faster, cheaper)
   - Consider Claude Haiku for speed-critical cases

---

## Additional Optimization Ideas

### Keyword Boosting

**Description:**
Prioritize articles containing material event keywords.

**Keywords:**
- Earnings-related: "earnings", "revenue", "guidance", "EPS", "quarter"
- Corporate actions: "merger", "acquisition", "buyback", "dividend"
- Regulatory: "SEC", "investigation", "lawsuit", "settlement"
- Product: "product launch", "recall", "FDA approval"

**Implementation:**
```python
MATERIAL_KEYWORDS = ["earnings", "guidance", "merger", "sec", "lawsuit"]

def has_material_keyword(headline: str) -> bool:
    headline_lower = headline.lower()
    return any(kw in headline_lower for kw in MATERIAL_KEYWORDS)

# Boost score for material articles
score = base_score + (1.0 if has_material_keyword(article.headline) else 0.0)
```

**Pros:** Ensures critical news isn't filtered out
**Cons:** Requires maintaining keyword list

---

### Lightweight Deduplication

**Description:**
Drop near-duplicate headlines before sending to LLM.

**Algorithm:**
```python
def is_duplicate(h1: str, h2: str, threshold: float = 0.8) -> bool:
    """Check if headlines are duplicates using fuzzy matching."""
    from difflib import SequenceMatcher
    return SequenceMatcher(None, h1.lower(), h2.lower()).ratio() > threshold

# Filter duplicates
unique_articles = []
for article in articles:
    if not any(is_duplicate(article.headline, a.headline) for a in unique_articles):
        unique_articles.append(article)
```

**Pros:** Simple, no external dependencies
**Cons:** May miss semantically similar but differently worded headlines

---

## Logging & Monitoring

### Required Metrics

Add to all LLM calls:

```python
app_logger.info(
    "ai_summary_llm_call",
    extra={
        "ticker": ticker,
        "total_articles_available": total_count,
        "articles_sent_to_llm": len(articles),
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "llm_latency_ms": elapsed_ms,
        "llm_tokens_prompt": token_count_prompt,
        "llm_tokens_completion": token_count_completion,
        "cache_hit": cache_hit,
        "fallback_used": fallback_used,
    }
)
```

### Dashboards to Create

1. **Latency Distribution**
   - Histogram of LLM response times
   - P50, P95, P99 percentiles
   - Breakdown by ticker (top 20)

2. **Cache Performance**
   - Cache hit rate over time
   - TTL expiration patterns
   - Memory usage

3. **Cost Tracking**
   - Daily OpenAI API spend
   - Cost per ticker
   - Token usage trends

4. **Quality Metrics**
   - Fallback rate (should be <5%)
   - Timeout rate (should be <2%)
   - User-reported issues

---

## Testing Plan

### Before Implementing Any Optimization

1. **Baseline Test:**
   ```bash
   # Test 20 diverse tickers
   for ticker in SPY QQQ AAPL NVDA TSLA GOOGL MSFT AMZN META NFLX; do
       time curl "localhost:8000/api/v1/news/$ticker/summary?force_refresh=true"
       sleep 5
   done
   ```

2. **Quality Review:**
   - Manually review 20 summaries
   - Check for: coherence, relevance, citation accuracy, sentiment accuracy
   - Rate 1-5 scale

3. **After Optimization:**
   - Re-run baseline test
   - Compare latency (should improve 20-30%)
   - Compare quality scores (should not degrade)
   - A/B test if possible (50% old, 50% new)

---

## Decision Matrix

| Scenario | Recommended Action |
|----------|-------------------|
| Median latency < 25s, no complaints | ✅ No action needed |
| Median latency 25-35s | 🟡 Implement sentiment-weighted ranking |
| Median latency > 35s | 🔴 Reduce SUMMARY_TOP_K to 3 |
| Timeout rate > 5% | 🔴 Implement adaptive SUMMARY_TOP_K |
| Repetitive summaries reported | 🟡 Add headline clustering |
| OpenAI costs > $20/month | 🟡 Reduce SUMMARY_TOP_K or switch to gpt-3.5-turbo |

---

## Rollback Plan

If optimization degrades quality:

1. **Immediate:**
   ```bash
   # In .env and Render
   SUMMARY_TOP_K=5
   ```

2. **Code rollback:**
   ```bash
   git revert <optimization-commit-hash>
   git push
   ```

3. **Monitor for 24 hours:**
   - Verify quality returns to baseline
   - Check user feedback

---

## References

- [OpenAI API Pricing](https://openai.com/api/pricing/)
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
- [VADER Sentiment](https://github.com/cjhutto/vaderSentiment)
- [Sentence Transformers](https://www.sbert.net/)

---

## Changelog

| Date | Change | Reason |
|------|--------|--------|
| 2025-11-06 | Initial document created | Document optimization strategies before production |
| 2025-11-06 | Set `LLM_TIMEOUT_SECONDS=25` | Fixed AAPL timeout issue in testing |

---

**Next Review Date:** 2025-11-20 (after 2 weeks of production data)
