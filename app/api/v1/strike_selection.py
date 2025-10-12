"""
Strike Selection API Endpoints
Provides intelligent strike and spread recommendations.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.strike_data_service import StrikeDataService
from app.core.strike_selection import (
    recommend_vertical_spreads,
    recommend_long_options,
    determine_iv_regime,
    get_spread_width_for_price,
    IVRegime,
)
from app.api.v1.schemas.strike_selection import (
    StrikeRecommendationRequest,
    StrikeRecommendationResponse,
    SpreadCandidateResponse,
    LongOptionCandidateResponse,
)

router = APIRouter(prefix="/strike-selection", tags=["strike-selection"])


@router.post("/recommend", response_model=StrikeRecommendationResponse)
async def recommend_strikes(
    request: StrikeRecommendationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Recommend optimal strikes and spreads based on stored option data.

    Analyzes option chains and IV metrics to suggest ITM, ATM, and OTM candidates
    for vertical spreads or long options based on directional bias and IV regime.

    **Strategy Type:**
    - `vertical_spread`: Recommend bull/bear call/put spreads
    - `long_call`: Recommend long call strikes
    - `long_put`: Recommend long put strikes
    - `auto`: Auto-select strategy based on bias and IV regime

    **Example Request:**
    ```json
    {
        "underlying_symbol": "SPY",
        "bias": "bullish",
        "strategy_type": "vertical_spread",
        "target_dte": 30,
        "dte_tolerance": 3,
        "min_credit_pct": 25.0,
        "max_spread_width": 5
    }
    ```

    **Returns:**
    - 2-3 spread/option candidates (ITM, ATM, OTM)
    - Key metrics: strikes, premiums, breakevens, P/L, POP proxy
    - IV context and data timestamps
    - Warnings if data is missing or stale
    """
    try:
        # Validate and fetch data
        ticker, underlying_price, snapshot, iv_metric, warnings = (
            await StrikeDataService.validate_and_fetch_data(
                db,
                request.underlying_symbol,
                request.target_dte,
                request.dte_tolerance,
            )
        )

        # Check for critical errors
        if not ticker:
            raise HTTPException(
                status_code=404,
                detail=f"Ticker {request.underlying_symbol} not found"
            )

        if not underlying_price:
            raise HTTPException(
                status_code=404,
                detail=f"No price data available for {request.underlying_symbol}"
            )

        if not snapshot or not snapshot.contracts:
            raise HTTPException(
                status_code=404,
                detail=f"No option chain data for {request.underlying_symbol} at DTE {request.target_dte}"
            )

        # Determine IV regime
        iv_rank = iv_metric.iv_rank if iv_metric else None
        if request.iv_regime_override:
            iv_regime_str = request.iv_regime_override
        else:
            iv_regime = determine_iv_regime(iv_rank)
            iv_regime_str = iv_regime.value if iv_regime else None

        # Auto-select strategy based on IV regime with explicit debit/credit determination
        strategy_type = request.strategy_type
        force_credit = False  # Explicit credit/debit flag
        force_debit = False

        if strategy_type == "auto":
            if iv_regime_str == "high":
                # High IV → sell premium (credit spreads)
                strategy_type = "vertical_spread"
                force_credit = True
                warnings.append("Auto-selected credit spread strategy (high IV regime)")
            elif iv_regime_str == "low":
                # Low IV → buy premium (long options preferred)
                if request.bias == "bullish":
                    strategy_type = "long_call"
                    warnings.append("Auto-selected long call strategy (low IV regime)")
                elif request.bias == "bearish":
                    strategy_type = "long_put"
                    warnings.append("Auto-selected long put strategy (low IV regime)")
                else:
                    strategy_type = "vertical_spread"
                    force_debit = True
                    warnings.append("Auto-selected debit spread strategy (low IV regime)")
            else:
                # Neutral IV → use debit spreads for defined risk
                strategy_type = "vertical_spread"
                force_debit = True
                warnings.append("Auto-selected debit spread strategy (neutral IV regime)")

        # Convert contracts to data objects
        contract_data = StrikeDataService.contracts_to_data(snapshot.contracts)

        # Determine spread width
        spread_width = get_spread_width_for_price(
            underlying_price,
            min_width=2,
            max_width=request.max_spread_width,
        )

        # Generate recommendations
        spread_candidates = None
        long_option_candidates = None

        if strategy_type == "vertical_spread":
            # Determine option type based on bias and explicit credit/debit preference
            if request.bias == "bullish":
                # Bull call spread (debit) or bull put spread (credit)
                if force_credit:
                    option_type = "put"  # Bull put credit
                else:
                    option_type = "call"  # Bull call debit
            elif request.bias == "bearish":
                # Bear put spread (debit) or bear call spread (credit)
                if force_credit:
                    option_type = "call"  # Bear call credit
                else:
                    option_type = "put"  # Bear put debit
            else:  # neutral
                # Default to call spreads (debit)
                option_type = "call"

            # Get IV regime object for quality scoring
            iv_regime_obj = determine_iv_regime(iv_rank) if iv_rank else None

            candidates = recommend_vertical_spreads(
                contract_data,
                underlying_price,
                option_type,
                request.bias,
                spread_width,
                request.min_credit_pct,
                iv_regime=iv_regime_obj,
                apply_liquidity_filter=True,
            )

            if not candidates:
                warnings.append(f"No suitable {option_type} spreads found - try different width or credit threshold")

            spread_candidates = [
                SpreadCandidateResponse(
                    position=c.position.value,
                    long_strike=c.long_strike,
                    short_strike=c.short_strike,
                    long_premium=c.long_premium,
                    short_premium=c.short_premium,
                    net_premium=c.net_premium,
                    is_credit=c.is_credit,
                    net_credit=c.net_credit,
                    net_debit=c.net_debit,
                    width_points=c.width_points,
                    width_dollars=c.width_dollars,
                    spread_width=c.spread_width,  # DEPRECATED
                    breakeven=c.breakeven,
                    max_profit=c.max_profit,
                    max_loss=c.max_loss,
                    risk_reward_ratio=c.risk_reward_ratio,
                    pop_proxy=c.pop_proxy,
                    long_delta=c.long_delta,
                    short_delta=c.short_delta,
                    quality_score=c.quality_score,
                    notes=c.notes,
                )
                for c in candidates
            ]

        elif strategy_type == "long_call":
            candidates = recommend_long_options(
                contract_data,
                underlying_price,
                "call",
            )

            long_option_candidates = [
                LongOptionCandidateResponse(
                    position=c.position.value,
                    strike=c.strike,
                    premium=c.premium,
                    breakeven=c.breakeven,
                    max_loss=c.max_loss,
                    max_profit=c.max_profit,
                    delta=c.delta,
                    pop_proxy=c.pop_proxy,
                    notes=c.notes,
                )
                for c in candidates
            ]

        elif strategy_type == "long_put":
            candidates = recommend_long_options(
                contract_data,
                underlying_price,
                "put",
            )

            long_option_candidates = [
                LongOptionCandidateResponse(
                    position=c.position.value,
                    strike=c.strike,
                    premium=c.premium,
                    breakeven=c.breakeven,
                    max_loss=c.max_loss,
                    max_profit=c.max_profit,
                    delta=c.delta,
                    pop_proxy=c.pop_proxy,
                    notes=c.notes,
                )
                for c in candidates
            ]

        return StrikeRecommendationResponse(
            underlying_symbol=request.underlying_symbol.upper(),
            underlying_price=underlying_price,
            strategy_type=strategy_type,
            bias=request.bias,
            dte=snapshot.dte,
            iv_rank=iv_rank,
            iv_regime=iv_regime_str,
            spread_candidates=spread_candidates,
            long_option_candidates=long_option_candidates,
            data_timestamp=snapshot.as_of,
            warnings=warnings,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating recommendations: {str(e)}"
        )
