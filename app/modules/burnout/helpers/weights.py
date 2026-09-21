"""
==============================================================
File: weights.py

Weight constants và normalization helpers.

Pure functions, deterministic.
==============================================================
"""

from typing import Dict, List, Tuple

# ==========================================
# Burnout Weights (Base)
# ==========================================

BURNOUT_WEIGHTS = {
    "sleep": 0.30,
    "workload": 0.25,
    "stress": 0.20,
    "emotion": 0.15,
    "behavior": 0.10,
}

assert abs(sum(BURNOUT_WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"


# ==========================================
# Risk Thresholds
# ==========================================

RISK_THRESHOLDS = {
    "low": 40.0,
    "medium": 60.0,
    "high": 80.0,
}


def get_risk_level(score: float) -> str:
    """Determine risk level from burnout score.

    Args:
        score: Burnout score (0-100).

    Returns:
        Risk level: low/medium/high/critical.
    """
    if score < RISK_THRESHOLDS["low"]:
        return "low"
    if score < RISK_THRESHOLDS["medium"]:
        return "medium"
    if score < RISK_THRESHOLDS["high"]:
        return "high"
    return "critical"


def get_risk_level_from_score(score: float) -> str:
    """Alias for get_risk_level."""
    return get_risk_level(score)


# ==========================================
# Weight Normalization
# ==========================================

def normalize_weights(
    available_factors: List[str],
    base_weights: Dict[str, float] = BURNOUT_WEIGHTS,
) -> Dict[str, float]:
    """Normalize weights cho available factors.

    Khi một số factors không có data, cần redistribute weights
    để tổng vẫn = 1.0.

    Args:
        available_factors: List of factor names that have data.
        base_weights: Base weights dict.

    Returns:
        Normalized weights dict (tổng = 1.0).
    """
    if not available_factors:
        return {}

    # Tính tổng weight của available factors
    available_weight = sum(
        base_weights.get(f, 0.0) for f in available_factors
    )

    if available_weight == 0:
        return {}

    # Normalize
    return {
        f: round(base_weights.get(f, 0.0) / available_weight, 4)
        for f in available_factors
    }


def normalize_weights_tuple(
    contributions: List[Tuple[str, float, float]],
) -> List[Tuple[str, float, float]]:
    """Normalize weights từ contributions list.

    Args:
        contributions: List of (factor, score, weight) tuples.

    Returns:
        List of (factor, score, normalized_weight) tuples.
    """
    if not contributions:
        return []

    # Tính tổng weights gốc
    total_weight = sum(w for _, _, w in contributions)
    if total_weight == 0:
        return []

    # Normalize
    return [
        (factor, score, round(weight / total_weight, 4))
        for factor, score, weight in contributions
    ]
