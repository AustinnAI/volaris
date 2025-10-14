"""
Strategy Recommendation API Endpoints
Intelligent strategy recommendations combining IV regime, strike selection, and trade calculations.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.strategy_recommendation import (
    StrategyRecommendationRequest,
    StrategyRecommendationResponse,
    StrategyRecommendationResultResponse,
)
from app.core.strategy_recommender import (
    ScoringWeights,
    StrategyConstraints,
    StrategyObjectives,
    recommend_strategies,
)
from app.db.database import get_db
from app.services.strike_data_service import StrikeDataService

router = APIRouter(prefix="/strategy", tags=["strategy-recommendation"])


@router.post("/recommend", response_model=StrategyRecommendationResultResponse)
async def recommend_strategy(
    request: StrategyRecommendationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate intelligent strategy recommendations based on IV regime and market conditions.

    **How it works:**
    1. Analyzes IV regime (high/neutral/low) to select optimal strategy family
    2. Uses Phase 3.2 strike selection to find ITM/ATM/OTM candidates
    3. Applies Phase 3.1 calculations for risk metrics
    4. Filters by constraints and objectives
    5. Scores and ranks top 2-3 recommendations with reasoning

    **Strategy Selection Logic:**
    - **High IV (>50)**: Credit spreads (sell premium)
      - Bullish → Bull put credit spread
      - Bearish → Bear call credit spread
    - **Low IV (<25)**: Long options (cheap premium)
      - Bullish → Long calls
      - Bearish → Long puts
    - **Neutral IV (25-50)**: Debit spreads (defined risk)
      - Bullish → Bull call debit spread
      - Bearish → Bear put debit spread

    **Example Request:**
    ```json
    {
      "underlying_symbol": "SPY",
      "bias": "bullish",
      "target_dte": 30,
      "dte_tolerance": 3,
      "target_move_pct": 2.0,
      "objectives": {
        "max_risk_per_trade": 500,
        "min_pop_pct": 50,
        "account_size": 25000
      },
      "constraints": {
        "min_credit_pct": 25,
        "max_spread_width": 5
      }
    }
    ```

    **Returns:**
    - Ranked recommendations (1-3) with strikes, pricing, risk metrics
    - Reasoning bullets explaining selection
    - IV regime context and configuration used
    - Warnings for missing data or constraint violations
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
                status_code=404, detail=f"Ticker {request.underlying_symbol} not found"
            )

        if not underlying_price:
            raise HTTPException(
                status_code=404, detail=f"No price data available for {request.underlying_symbol}"
            )

        if not snapshot or not snapshot.contracts:
            raise HTTPException(
                status_code=404,
                detail=f"No option chain data for {request.underlying_symbol} at DTE {request.target_dte} (±{request.dte_tolerance} days)",
            )

        # Get IV rank
        iv_rank = iv_metric.iv_rank if iv_metric else None
        if iv_rank is None:
            warnings.append("IV rank unavailable - using neutral regime assumption")

        # Convert request objectives to core model
        objectives = None
        if request.objectives:
            objectives = StrategyObjectives(
                max_risk_per_trade=request.objectives.max_risk_per_trade,
                min_pop_pct=request.objectives.min_pop_pct,
                min_risk_reward=request.objectives.min_risk_reward,
                prefer_credit=request.objectives.prefer_credit,
                avoid_earnings=request.objectives.avoid_earnings,
                account_size=request.objectives.account_size,
                bias_reason=request.objectives.bias_reason,
            )

        # Convert request constraints to core model
        constraints = None
        if request.constraints:
            constraints = StrategyConstraints(
                min_credit_pct=request.constraints.min_credit_pct,
                max_spread_width=request.constraints.max_spread_width,
                iv_regime_override=request.constraints.iv_regime_override,
                min_open_interest=request.constraints.min_open_interest,
                min_volume=request.constraints.min_volume,
                min_mark_price=request.constraints.min_mark_price,
            )

        # Convert contracts to data objects
        contract_data = StrikeDataService.contracts_to_data(snapshot.contracts)

        # Generate recommendations
        result = recommend_strategies(
            contracts=contract_data,
            underlying_symbol=request.underlying_symbol,
            underlying_price=underlying_price,
            bias=request.bias,
            dte=snapshot.dte,
            iv_rank=iv_rank,
            target_move_pct=request.target_move_pct,
            objectives=objectives,
            constraints=constraints,
            scoring_weights=ScoringWeights(),  # Use defaults
            data_timestamp=snapshot.as_of,
        )

        # Add any data fetch warnings
        result.warnings.extend(warnings)

        # Convert to response model
        recommendations = [
            StrategyRecommendationResponse(
                rank=rec.rank,
                strategy_family=rec.strategy_family.value,
                option_type=rec.option_type,
                position=rec.position,
                strike=rec.strike,
                long_strike=rec.long_strike,
                short_strike=rec.short_strike,
                premium=rec.premium,
                long_premium=rec.long_premium,
                short_premium=rec.short_premium,
                net_premium=rec.net_premium,
                is_credit=rec.is_credit,
                net_credit=rec.net_credit,
                net_debit=rec.net_debit,
                width_points=rec.width_points,
                width_dollars=rec.width_dollars,
                breakeven=rec.breakeven,
                max_profit=rec.max_profit,
                max_loss=rec.max_loss,
                risk_reward_ratio=rec.risk_reward_ratio,
                pop_proxy=rec.pop_proxy,
                delta=rec.delta,
                long_delta=rec.long_delta,
                short_delta=rec.short_delta,
                recommended_contracts=rec.recommended_contracts,
                position_size_dollars=rec.position_size_dollars,
                composite_score=rec.composite_score,
                avg_open_interest=rec.avg_open_interest,
                avg_volume=rec.avg_volume,
                reasons=rec.reasons,
                warnings=rec.warnings,
            )
            for rec in result.recommendations
        ]

        return StrategyRecommendationResultResponse(
            underlying_symbol=result.underlying_symbol,
            underlying_price=result.underlying_price,
            chosen_strategy_family=result.chosen_strategy_family.value,
            iv_rank=result.iv_rank,
            iv_regime=result.iv_regime,
            dte=result.dte,
            expected_move_pct=result.expected_move_pct,
            data_timestamp=result.data_timestamp,
            recommendations=recommendations,
            config_used=result.config_used,
            warnings=result.warnings,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating strategy recommendations: {str(e)}"
        )
