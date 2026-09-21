"""
==============================================================
Helpers Package

Chứa các pure functions, constants và models dùng chung.
==============================================================
"""

# Models
from app.modules.burnout.helpers.models import (
    EmotionAggregate,
    ChatAnalysisAggregate,
    SurveyData,
    HistoricalTrend,
    FactorContribution,
    FactorAnalysis,
)

# Scoring
from app.modules.burnout.helpers.scoring import (
    calculate_sleep_score,
    calculate_workload_score,
    calculate_stress_score,
    calculate_emotion_score,
    calculate_behavior_score,
    DEADLINE_TO_SCORE,
    TREND_BONUS,
)

# Completeness
from app.modules.burnout.helpers.completeness import (
    calculate_data_completeness,
    calculate_data_completeness_from_analysis,
    calculate_evidence_coverage,
    DATA_COMPLETENESS_WEIGHTS,
)

# Weights
from app.modules.burnout.helpers.weights import (
    BURNOUT_WEIGHTS,
    RISK_THRESHOLDS,
    get_risk_level,
    get_risk_level_from_score,
    normalize_weights,
    normalize_weights_tuple,
)

__all__ = [
    # Models
    "EmotionAggregate",
    "ChatAnalysisAggregate",
    "SurveyData",
    "HistoricalTrend",
    "FactorContribution",
    "FactorAnalysis",
    # Scoring
    "calculate_sleep_score",
    "calculate_workload_score",
    "calculate_stress_score",
    "calculate_emotion_score",
    "calculate_behavior_score",
    "DEADLINE_TO_SCORE",
    "TREND_BONUS",
    # Completeness
    "calculate_data_completeness",
    "calculate_data_completeness_from_analysis",
    "calculate_evidence_coverage",
    "DATA_COMPLETENESS_WEIGHTS",
    # Weights
    "BURNOUT_WEIGHTS",
    "RISK_THRESHOLDS",
    "get_risk_level",
    "get_risk_level_from_score",
    "normalize_weights",
    "normalize_weights_tuple",
]
