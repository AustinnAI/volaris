"""
Discord UI components shared by cogs.
"""

from __future__ import annotations

from typing import Any

import discord

from .embeds import create_recommendation_embed


class MoreCandidatesView(discord.ui.View):
    """Interactive view that surfaces additional recommendation candidates."""

    def __init__(
        self,
        all_recommendations: list[dict[str, Any]],
        symbol: str,
        underlying_price: float,
        iv_regime: str | None,
        strategy: str,
    ) -> None:
        super().__init__(timeout=300)
        self._recommendations = all_recommendations
        self._symbol = symbol
        self._underlying_price = underlying_price
        self._iv_regime = iv_regime
        self._strategy = strategy

    @discord.ui.button(label="Show More Candidates", style=discord.ButtonStyle.primary, emoji="📋")
    async def show_more(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,  # pylint: disable=unused-argument
    ) -> None:
        """Send the next set of recommendation embeds as an ephemeral response."""
        if len(self._recommendations) <= 1:
            await interaction.response.send_message("No additional candidates available.", ephemeral=True)
            return

        embeds = [
            create_recommendation_embed(
                recommendation,
                self._symbol,
                self._underlying_price,
                self._iv_regime,
                self._strategy,
            )
            for recommendation in self._recommendations[1:3]
        ]
        await interaction.response.send_message(embeds=embeds, ephemeral=True)
