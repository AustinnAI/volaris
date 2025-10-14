"""
Trade Planner API Endpoints
Provides strategy calculation and position sizing endpoints.
"""

from decimal import Decimal

from fastapi import APIRouter, HTTPException

from app.api.v1.schemas.trade_planner import (
    CalculationResponse,
    LegResponse,
    LongOptionRequest,
    PositionSizeRequest,
    PositionSizeResponse,
    StrategyCalculateRequest,
    VerticalSpreadRequest,
)
from app.core.trade_planner import (
    TradeBias,
    calculate_long_option,
    calculate_position_size,
    calculate_vertical_spread,
)

router = APIRouter(prefix="/trade-planner", tags=["trade-planner"])


@router.post("/calculate/vertical-spread", response_model=CalculationResponse)
async def calculate_vertical_spread_endpoint(
    request: VerticalSpreadRequest,
) -> dict:
    """
    Calculate risk/reward metrics for a vertical spread.

    Supports both debit and credit spreads (determined automatically from premiums).

    Example request:
        ```json
        {
            "underlying_symbol": "SPY",
            "underlying_price": 450.00,
            "long_strike": 445.00,
            "short_strike": 450.00,
            "long_premium": 7.50,
            "short_premium": 3.00,
            "option_type": "call",
            "bias": "bullish",
            "contracts": 1,
            "dte": 30,
            "long_delta": 0.60,
            "short_delta": 0.40
        }
        ```

    Returns:
        Calculation result with max profit, max loss, breakeven, and position sizing
    """
    try:
        result = calculate_vertical_spread(
            underlying_symbol=request.underlying_symbol.upper(),
            underlying_price=request.underlying_price,
            long_strike=request.long_strike,
            short_strike=request.short_strike,
            long_premium=request.long_premium,
            short_premium=request.short_premium,
            option_type=request.option_type,
            bias=TradeBias(request.bias),
            contracts=request.contracts,
            dte=request.dte,
            long_delta=request.long_delta,
            short_delta=request.short_delta,
            account_size=request.account_size,
            risk_percentage=request.risk_percentage,
        )

        # Convert to response format
        return {
            "strategy_type": result.strategy_type,
            "bias": result.bias,
            "underlying_symbol": result.underlying_symbol,
            "underlying_price": result.underlying_price,
            "legs": [LegResponse(**leg) for leg in result.legs],
            "max_profit": result.max_profit,
            "max_loss": result.max_loss,
            "breakeven_prices": result.breakeven_prices,
            "risk_reward_ratio": result.risk_reward_ratio,
            "win_probability": result.win_probability,
            "recommended_contracts": result.recommended_contracts,
            "position_size_dollars": result.position_size_dollars,
            "net_premium": result.net_premium,
            "net_credit": result.net_credit,
            "dte": result.dte,
            "total_delta": result.total_delta,
            "assumptions": result.assumptions,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Calculation error: {str(e)}")


@router.post("/calculate/long-option", response_model=CalculationResponse)
async def calculate_long_option_endpoint(
    request: LongOptionRequest,
) -> dict:
    """
    Calculate risk/reward metrics for a long call or long put.

    Example request:
        ```json
        {
            "underlying_symbol": "AAPL",
            "underlying_price": 175.00,
            "strike": 180.00,
            "premium": 3.50,
            "option_type": "call",
            "bias": "bullish",
            "contracts": 2,
            "dte": 45,
            "delta": 0.35
        }
        ```

    Returns:
        Calculation result with max profit, max loss, breakeven, and position sizing
    """
    try:
        result = calculate_long_option(
            underlying_symbol=request.underlying_symbol.upper(),
            underlying_price=request.underlying_price,
            strike=request.strike,
            premium=request.premium,
            option_type=request.option_type,
            bias=TradeBias(request.bias),
            contracts=request.contracts,
            dte=request.dte,
            delta=request.delta,
            account_size=request.account_size,
            risk_percentage=request.risk_percentage,
        )

        # Convert to response format
        return {
            "strategy_type": result.strategy_type,
            "bias": result.bias,
            "underlying_symbol": result.underlying_symbol,
            "underlying_price": result.underlying_price,
            "legs": [LegResponse(**leg) for leg in result.legs],
            "max_profit": result.max_profit,
            "max_loss": result.max_loss,
            "breakeven_prices": result.breakeven_prices,
            "risk_reward_ratio": result.risk_reward_ratio,
            "win_probability": result.win_probability,
            "recommended_contracts": result.recommended_contracts,
            "position_size_dollars": result.position_size_dollars,
            "net_premium": result.net_premium,
            "net_credit": result.net_credit,
            "dte": result.dte,
            "total_delta": result.total_delta,
            "assumptions": result.assumptions,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Calculation error: {str(e)}")


@router.post("/calculate", response_model=CalculationResponse)
async def calculate_strategy_unified(
    request: StrategyCalculateRequest,
) -> dict:
    """
    Unified endpoint for calculating any supported strategy.

    Strategy types:
    - `vertical_spread`: Requires long_strike, short_strike, long_premium, short_premium
    - `long_call`: Requires strike, premium, option_type="call"
    - `long_put`: Requires strike, premium, option_type="put"

    Example request (vertical spread):
        ```json
        {
            "strategy_type": "vertical_spread",
            "underlying_symbol": "SPY",
            "underlying_price": 450.00,
            "long_strike": 445.00,
            "short_strike": 450.00,
            "long_premium": 7.50,
            "short_premium": 3.00,
            "option_type": "call",
            "bias": "bullish",
            "contracts": 1,
            "dte": 30
        }
        ```

    Returns:
        Calculation result with max profit, max loss, breakeven, and position sizing
    """
    try:
        if request.strategy_type == "vertical_spread":
            # Validate required fields
            if not all(
                [
                    request.long_strike,
                    request.short_strike,
                    request.long_premium,
                    request.short_premium,
                ]
            ):
                raise HTTPException(
                    status_code=400,
                    detail="vertical_spread requires long_strike, short_strike, long_premium, short_premium",
                )

            result = calculate_vertical_spread(
                underlying_symbol=request.underlying_symbol.upper(),
                underlying_price=request.underlying_price,
                long_strike=request.long_strike,
                short_strike=request.short_strike,
                long_premium=request.long_premium,
                short_premium=request.short_premium,
                option_type=request.option_type,
                bias=TradeBias(request.bias),
                contracts=request.contracts,
                dte=request.dte,
                long_delta=request.long_delta,
                short_delta=request.short_delta,
            )
        elif request.strategy_type in ["long_call", "long_put"]:
            # Validate required fields
            if not all([request.strike, request.premium]):
                raise HTTPException(
                    status_code=400,
                    detail=f"{request.strategy_type} requires strike and premium",
                )

            result = calculate_long_option(
                underlying_symbol=request.underlying_symbol.upper(),
                underlying_price=request.underlying_price,
                strike=request.strike,
                premium=request.premium,
                option_type=request.option_type,
                bias=TradeBias(request.bias),
                contracts=request.contracts,
                dte=request.dte,
                delta=request.delta,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported strategy_type: {request.strategy_type}",
            )

        # Convert to response format
        return {
            "strategy_type": result.strategy_type,
            "bias": result.bias,
            "underlying_symbol": result.underlying_symbol,
            "underlying_price": result.underlying_price,
            "legs": [LegResponse(**leg) for leg in result.legs],
            "max_profit": result.max_profit,
            "max_loss": result.max_loss,
            "breakeven_prices": result.breakeven_prices,
            "risk_reward_ratio": result.risk_reward_ratio,
            "win_probability": result.win_probability,
            "recommended_contracts": result.recommended_contracts,
            "position_size_dollars": result.position_size_dollars,
            "net_premium": result.net_premium,
            "net_credit": result.net_credit,
            "dte": result.dte,
            "total_delta": result.total_delta,
            "assumptions": result.assumptions,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Calculation error: {str(e)}")


@router.post("/position-size", response_model=PositionSizeResponse)
async def calculate_position_size_endpoint(
    request: PositionSizeRequest,
) -> dict:
    """
    Calculate position size based on risk management rules.

    Example request:
        ```json
        {
            "max_loss_per_contract": 450.00,
            "account_size": 25000.00,
            "risk_percentage": 2.0
        }
        ```

    Returns:
        Recommended number of contracts and risk metrics
    """
    try:
        contracts = calculate_position_size(
            max_loss=request.max_loss_per_contract,
            account_size=request.account_size,
            risk_percentage=request.risk_percentage,
        )

        total_risk = request.max_loss_per_contract * Decimal(contracts)
        risk_percent = (total_risk / request.account_size) * Decimal(100)

        return {
            "contracts": contracts,
            "max_loss_per_contract": request.max_loss_per_contract,
            "account_size": request.account_size,
            "risk_percentage": request.risk_percentage,
            "total_risk_dollars": total_risk,
            "risk_as_percent_of_account": risk_percent,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Calculation error: {str(e)}")
