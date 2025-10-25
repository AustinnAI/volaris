"""
Helper utilities for the Volaris Discord bot.

This package exposes reusable building blocks shared across cog modules,
including API clients, embed builders, and autocomplete helpers.
"""

from .api_client import (
    MarketInsightsAPI,
    NewsAPI,
    PriceAlertAPI,
    PriceStreamAPI,
    StrategyRecommendationAPI,
    VolatilityAPI,
)
from .autocomplete import PRIORITY_SYMBOLS, SymbolService
from .embeds import (
    build_expected_move_embed,
    build_top_movers_embed,
    create_recommendation_embed,
)
from .views import MoreCandidatesView

__all__ = [
    "StrategyRecommendationAPI",
    "PriceAlertAPI",
    "PriceStreamAPI",
    "VolatilityAPI",
    "MarketInsightsAPI",
    "NewsAPI",
    "SymbolService",
    "PRIORITY_SYMBOLS",
    "create_recommendation_embed",
    "build_expected_move_embed",
    "build_top_movers_embed",
    "MoreCandidatesView",
]
