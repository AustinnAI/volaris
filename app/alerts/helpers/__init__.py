"""
Helper utilities for the Volaris Discord bot.

This package exposes reusable building blocks shared across cog modules,
including API clients, embed builders, and autocomplete helpers.
"""

from .api_client import (
    StrategyRecommendationAPI,
    PriceAlertAPI,
    PriceStreamAPI,
    MarketInsightsAPI,
)
from .autocomplete import SymbolService, PRIORITY_SYMBOLS
from .embeds import (
    create_recommendation_embed,
    build_top_movers_embed,
)
from .views import MoreCandidatesView

__all__ = [
    "StrategyRecommendationAPI",
    "PriceAlertAPI",
    "PriceStreamAPI",
    "MarketInsightsAPI",
    "SymbolService",
    "PRIORITY_SYMBOLS",
    "create_recommendation_embed",
    "build_top_movers_embed",
    "MoreCandidatesView",
]
