"""
AI Summarization Module (Phase 2 Enhancement).

Provides LLM-powered news summaries with Redis caching and deterministic fallback.
"""

from app.core.ai.formatters import create_fallback_summary, render_discord_markdown
from app.core.ai.llm_client import LLMError, get_llm_client
from app.core.ai.prompts import (
    build_cache_key,
    build_narrative_cache_key,
    build_news_narrative_prompt,
    build_single_ticker_prompt,
)
from app.core.ai.schema import (
    AISummaryAPIResponse,
    BatchSummaryItem,
    BatchSummaryRequest,
    BatchSummaryResponse,
    SummaryResponse,
)

__all__ = [
    # Schema
    "SummaryResponse",
    "AISummaryAPIResponse",
    "BatchSummaryRequest",
    "BatchSummaryResponse",
    "BatchSummaryItem",
    # Client
    "get_llm_client",
    "LLMError",
    # Prompts
    "build_single_ticker_prompt",
    "build_cache_key",
    "build_news_narrative_prompt",
    "build_narrative_cache_key",
    # Formatters
    "render_discord_markdown",
    "create_fallback_summary",
]
