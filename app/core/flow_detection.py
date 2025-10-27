"""
Custom anomaly detection logic for unusual options activity.

Implements scoring algorithms to identify unusual trades based on:
- Volume/OI ratio
- Volume spikes vs. 30-day average
- Bid-ask spread (liquidity)
- Premium size (block trades)
"""

from decimal import Decimal


def compute_anomaly_score(
    volume: int,
    open_interest: int,
    avg_volume_30d: float,
    bid_ask_spread_pct: float,
    premium: Decimal,
) -> tuple[float, list[str]]:
    """
    Compute unusual activity score (0-1) and flags.

    Scoring Criteria:
    - Volume/OI > 3.0 → +0.3 points, "high_volume" flag
    - Volume > 3× 30-day avg → +0.4 points, "volume_spike" flag
    - Bid-ask spread < 10% → +0.2 points, "liquid" flag
    - Premium > $50,000 → +0.1 points, "block_trade" flag

    Args:
        volume: Current contract volume.
        open_interest: Open interest for contract.
        avg_volume_30d: 30-day rolling average volume.
        bid_ask_spread_pct: (ask - bid) / ask as decimal (e.g., 0.05 = 5%).
        premium: Total premium (volume × price × 100).

    Returns:
        Tuple of (anomaly_score, flags).
        - anomaly_score: 0.0 to 1.0, clamped
        - flags: List of condition names that triggered
    """
    score = 0.0
    flags = []

    # Criterion 1: Volume/OI Ratio (fresh interest indicator)
    vol_oi_ratio = volume / max(open_interest, 1)
    if vol_oi_ratio > 3.0:
        score += 0.3
        flags.append("high_volume")

    # Criterion 2: Volume Spike (vs. 30-day average)
    if avg_volume_30d > 0 and volume > avg_volume_30d * 3:
        score += 0.4
        flags.append("volume_spike")

    # Criterion 3: Liquidity Check (tight bid-ask spread)
    if bid_ask_spread_pct < 0.10:  # Less than 10% spread
        score += 0.2
        flags.append("liquid")

    # Criterion 4: Block Trade (large premium)
    if premium > Decimal("50000"):
        score += 0.1
        flags.append("block_trade")

    # Clamp score to [0, 1]
    return min(score, 1.0), flags


def filter_unusual_contracts(
    contracts: list[dict],
    min_score: float = 0.7,
    max_results: int = 50,
) -> list[dict]:
    """
    Filter and sort contracts by anomaly score.

    Args:
        contracts: List of contract dicts with 'anomaly_score' field.
        min_score: Minimum score to include (0-1).
        max_results: Maximum number of results to return.

    Returns:
        Sorted list (highest scores first), limited to max_results.
    """
    unusual = [c for c in contracts if c.get("anomaly_score", 0) >= min_score]
    unusual.sort(key=lambda x: x.get("anomaly_score", 0), reverse=True)
    return unusual[:max_results]


def compute_volume_oi_ratio(volume: int, open_interest: int) -> float:
    """
    Calculate volume-to-open-interest ratio.

    High ratios (>3.0) indicate fresh interest or unusual activity.

    Args:
        volume: Current volume.
        open_interest: Open interest.

    Returns:
        Ratio as float. Returns volume if OI is 0 (avoid division by zero).
    """
    if open_interest == 0:
        return float(volume) if volume > 0 else 0.0
    return volume / open_interest


def estimate_premium(volume: int, last_price: Decimal) -> Decimal:
    """
    Estimate total premium (volume × price × 100).

    Each option contract represents 100 shares.

    Args:
        volume: Contract volume.
        last_price: Last traded price per share.

    Returns:
        Total premium in dollars.
    """
    return Decimal(volume) * last_price * Decimal(100)
