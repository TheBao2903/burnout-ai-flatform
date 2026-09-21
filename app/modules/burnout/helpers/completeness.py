"""
==============================================================
File: completeness.py

Data completeness helpers - Tính data coverage.

Pure functions, deterministic.
==============================================================
"""

from typing import List, Any

# Import BURNOUT_WEIGHTS từ weights.py (tránh circular import)
from app.modules.burnout.helpers.weights import BURNOUT_WEIGHTS


# ==========================================
# Data Completeness Weights
# ==========================================

DATA_COMPLETENESS_WEIGHTS = {
    "emotion": 0.30,
    "survey": 0.30,
    "chat": 0.20,
    "trend": 0.20,
}


def calculate_data_completeness(
    has_emotion: bool = False,
    emotion_count: int = 0,
    has_survey: bool = False,
    has_chat: bool = False,
    has_trend: bool = False,
) -> float:
    """Tính data completeness (0-1).

    Args:
        has_emotion: Có emotion data (cần ít nhất 1 frame).
        emotion_count: Số emotion frames.
        has_survey: Có survey data.
        has_chat: Có chat messages.
        has_trend: Có historical trend/result.

    Returns:
        Float 0.0 - 1.0.
    """
    total = 0.0

    # Emotion: 30% (cần ít nhất 1 frame)
    if has_emotion and emotion_count > 0:
        total += DATA_COMPLETENESS_WEIGHTS["emotion"]

    # Survey: 30%
    if has_survey:
        total += DATA_COMPLETENESS_WEIGHTS["survey"]

    # Chat: 20%
    if has_chat:
        total += DATA_COMPLETENESS_WEIGHTS["chat"]

    # Trend: 20% bonus
    if has_trend:
        total += DATA_COMPLETENESS_WEIGHTS["trend"]

    return round(min(1.0, total), 2)


def calculate_data_completeness_from_analysis(
    contributions: List[Any],
) -> float:
    """Tính data completeness từ FactorAnalysis contributions.

    Args:
        contributions: List of FactorContribution objects or dicts.

    Helper để chuyển từ FactorAnalysis sang completeness score.
    """
    available_weight = 0.0

    for contrib in contributions:
        # Handle both object and dict
        factor = contrib.factor if hasattr(contrib, 'factor') else contrib.get('factor')
        available = contrib.available if hasattr(contrib, 'available') else contrib.get('available', True)
        score = contrib.score if hasattr(contrib, 'score') else contrib.get('score')

        if available and score is not None:
            available_weight += BURNOUT_WEIGHTS.get(factor, 0.0)

    total_weight = sum(BURNOUT_WEIGHTS.values())  # 1.0
    return round(min(1.0, available_weight / total_weight), 2) if total_weight > 0 else 0.0


def calculate_evidence_coverage(
    available_factors: List[str],
    missing_factors: List[str],
) -> float:
    """Tính evidence coverage (0-1).

    Ratio của available factors so với tổng.

    Args:
        available_factors: List of factors with data.
        missing_factors: List of factors without data.

    Returns:
        Float 0.0 - 1.0.
    """
    total = len(available_factors) + len(missing_factors)
    if total == 0:
        return 0.0
    return round(len(available_factors) / total, 2)
