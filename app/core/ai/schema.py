"""
AI Summary Schema Models.

Pydantic models for structured LLM outputs with strict validation.
"""

from pydantic import BaseModel, Field


class SentimentSnapshot(BaseModel):
    """Sentiment analysis snapshot with VADER metrics."""

    net_score: float = Field(..., ge=-1.0, le=1.0, description="Compound sentiment score")
    dispersion: str = Field(
        ..., description="Sentiment spread: low | medium | high", pattern="^(low|medium|high)$"
    )
    recent_change: str = Field(
        ...,
        description="Trend direction: improving | stable | declining",
        pattern="^(improving|stable|declining)$",
    )


class KeyDriver(BaseModel):
    """Key market driver or theme."""

    theme: str = Field(..., description="Concise theme (e.g., 'Tech earnings beats')")
    supporting_articles: list[int] = Field(
        ..., description="Article indices (1-indexed) that support this theme"
    )


class RiskFlag(BaseModel):
    """Risk or concern identified in news."""

    concern: str = Field(..., description="Brief description of the risk")
    severity: str = Field(
        ..., description="Risk level: low | medium | high", pattern="^(low|medium|high)$"
    )


class FollowUp(BaseModel):
    """Suggested follow-up question or action."""

    question: str = Field(..., description="Actionable question or next step")
    rationale: str = Field(..., description="Why this matters")


class Source(BaseModel):
    """News article source citation."""

    idx: int = Field(..., ge=1, description="Article index (1-indexed)")
    title: str = Field(..., description="Article headline")
    url: str = Field(..., description="Article URL")
    published_at: str = Field(..., description="Publication timestamp (ISO format)")


class SummaryResponse(BaseModel):
    """Complete AI-generated market intelligence summary."""

    ticker: str = Field(..., description="Ticker symbol (e.g., SPY)")
    executive_summary: str = Field(
        ..., description="2-3 sentence overview of market conditions and key themes"
    )
    key_drivers: list[KeyDriver] = Field(..., description="Top 2-4 drivers with citations")
    sentiment_snapshot: SentimentSnapshot = Field(..., description="VADER sentiment metrics")
    risk_flags: list[RiskFlag] = Field(
        default_factory=list, description="Notable risks or concerns (0-3 items)"
    )
    follow_ups: list[FollowUp] = Field(
        default_factory=list, description="Suggested next steps or monitoring items (0-3)"
    )
    sources: list[Source] = Field(..., description="All articles used in summary")
    generated_at: str = Field(..., description="Summary generation timestamp (ISO format)")
    prompt_version: str = Field(..., description="Prompt template version (e.g., v1)")


class AISummaryAPIResponse(BaseModel):
    """API response wrapper for AI summary endpoints."""

    structured: SummaryResponse = Field(..., description="Structured summary data")
    markdown: str = Field(..., description="Discord-optimized markdown format")
    fallback_used: bool = Field(
        default=False, description="True if deterministic fallback was used instead of LLM"
    )
    cache_hit: bool = Field(default=False, description="True if result came from Redis cache")
