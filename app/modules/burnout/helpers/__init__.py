"""
==============================================================
Helpers Package

Chứa các pure functions, constants và models dùng chung cho Burnout Engine.
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
    calculate_mean_score,
    calculate_recovery_status,
    calculate_dimension_trend,
    calculate_sleep_score,
    calculate_workload_score,
    calculate_stress_score,
    calculate_emotion_score,
    calculate_behavior_score,
    DEADLINE_TO_SCORE,
    TREND_BONUS,
)

# Completeness & Sufficiency
from app.modules.burnout.helpers.completeness import (
    evaluate_data_sufficiency,
    evaluate_data_quality,
    calculate_data_completeness,
    calculate_data_completeness_from_analysis,
    calculate_evidence_coverage,
    DATA_COMPLETENESS_WEIGHTS,
)

# Weights & Thresholds
from app.modules.burnout.helpers.weights import (
    LIKERT_CUTOFFS,
    get_dimension_level,
    get_burnout_signal_status,
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
    # STA Scoring
    "calculate_mean_score",
    "calculate_recovery_status",
    "calculate_dimension_trend",
    "evaluate_data_sufficiency",
    "evaluate_data_quality",
    "LIKERT_CUTOFFS",
    "get_dimension_level",
    "get_burnout_signal_status",
    # Legacy Scoring
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
