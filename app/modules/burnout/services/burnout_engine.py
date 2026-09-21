"""
==============================================================
File: burnout_engine.py

BurnoutEngine - Composite score theo clean architecture.

Weights (bắt buộc):
    sleep       = 30%
    workload    = 25%
    stress      = 20%
    emotion     = 15%
    behavior    = 10%

Total = 100%

CLEAN ARCHITECTURE:
- Helpers được tách ra helpers/ folder
- Scoring functions: helpers/scoring.py
- Completeness functions: helpers/completeness.py
- Weight constants: helpers/weights.py
- Models: helpers/models.py

Burnout Engine KHÔNG:
- Gọi Firestore
- Gọi AI
- Gọi DeepFace
- Gọi R2
- Biết HTTP

Burnout Engine CHỈ:
- Nhận BurnoutInput (từ BurnoutInputBuilder)
- Gọi helpers để tính scores
- Trả BurnoutEngineOutput
==============================================================
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from app.modules.burnout.models.burnout import (
    BurnoutEngineOutput,
    BurnoutFactor,
    BurnoutInsight,
    BurnoutResult,
)

# Import helpers (singleton source of truth)
from app.modules.burnout.helpers import (
    BURNOUT_WEIGHTS,
    RISK_THRESHOLDS,
    calculate_sleep_score,
    calculate_workload_score,
    calculate_stress_score,
    calculate_emotion_score,
    calculate_behavior_score,
    calculate_data_completeness,
    calculate_data_completeness_from_analysis,
    normalize_weights,
    DEADLINE_TO_SCORE,
    TREND_BONUS,
    # Models
    EmotionAggregate,
    ChatAnalysisAggregate,
    SurveyData,
    HistoricalTrend,
    FactorContribution,
    FactorAnalysis,
)

logger = logging.getLogger("burnout.engine")


# ==========================================
# Engine Version & Constants
# ==========================================

ENGINE_VERSION = "v2.1"

DEFAULT_DISCLAIMER = (
    "Chi so AI khong thay the chan doan y khoa. "
    "Neu cam thay qua tai hay tu sat, hay gap chuyen gia."
)

FACTOR_LABELS = {
    "sleep": "Thiếu ngủ",
    "workload": "Công việc quá tải",
    "stress": "Stress cao",
    "emotion": "Cảm xúc tiêu cực",
    "behavior": "Xu hướng burnout tăng",
}


# ==========================================
# Factor Analysis
# ==========================================

def analyze_factors(
    survey: Optional[SurveyData],
    emotion: Optional[EmotionAggregate],
    chat: Optional[ChatAnalysisAggregate],
    trend: Optional[HistoricalTrend],
) -> FactorAnalysis:
    """Phân tích tất cả factors và tính burnout score.

    Args:
        survey: Survey data.
        emotion: Aggregated emotion data.
        chat: Chat analysis data.
        trend: Historical trend data.

    Returns:
        FactorAnalysis với contributions và burnout_score.
    """
    # Calculate individual scores
    sleep_score = calculate_sleep_score(survey)
    workload_score = calculate_workload_score(survey)
    stress_score = calculate_stress_score(survey, chat)
    emotion_score = calculate_emotion_score(emotion)
    behavior_score = calculate_behavior_score(trend, chat)  # Pass chat as fallback

    # Build contributions list
    contributions = []
    available_factors = []
    missing_factors = []

    # Sleep
    if sleep_score is not None:
        contributions.append(FactorContribution(
            factor="sleep",
            score=sleep_score,
            weight=BURNOUT_WEIGHTS["sleep"],
            percentage=sleep_score * BURNOUT_WEIGHTS["sleep"],
            available=True,
        ))
        available_factors.append("sleep")
    else:
        missing_factors.append("sleep")

    # Workload
    if workload_score is not None:
        contributions.append(FactorContribution(
            factor="workload",
            score=workload_score,
            weight=BURNOUT_WEIGHTS["workload"],
            percentage=workload_score * BURNOUT_WEIGHTS["workload"],
            available=True,
        ))
        available_factors.append("workload")
    else:
        missing_factors.append("workload")

    # Stress
    if stress_score is not None:
        contributions.append(FactorContribution(
            factor="stress",
            score=stress_score,
            weight=BURNOUT_WEIGHTS["stress"],
            percentage=stress_score * BURNOUT_WEIGHTS["stress"],
            available=True,
        ))
        available_factors.append("stress")
    else:
        missing_factors.append("stress")

    # Emotion
    if emotion_score is not None:
        contributions.append(FactorContribution(
            factor="emotion",
            score=emotion_score,
            weight=BURNOUT_WEIGHTS["emotion"],
            percentage=emotion_score * BURNOUT_WEIGHTS["emotion"],
            available=True,
        ))
        available_factors.append("emotion")
    else:
        missing_factors.append("emotion")

    # Behavior
    if behavior_score is not None:
        contributions.append(FactorContribution(
            factor="behavior",
            score=behavior_score,
            weight=BURNOUT_WEIGHTS["behavior"],
            percentage=behavior_score * BURNOUT_WEIGHTS["behavior"],
            available=True,
        ))
        available_factors.append("behavior")
    else:
        missing_factors.append("behavior")

    # Calculate burnout score với dynamic weight normalization
    burnout_score: Optional[float] = None
    evidence_coverage = 0.0

    if contributions:
        # Normalize weights cho available factors
        norm_weights = normalize_weights(available_factors, BURNOUT_WEIGHTS)

        # Recalculate percentages với normalized weights
        total_score = 0.0
        total_weight = 0.0
        for contrib in contributions:
            norm_w = norm_weights.get(contrib.factor, contrib.weight)
            contrib.weight = norm_w
            contrib.percentage = contrib.score * norm_w
            total_score += contrib.percentage
            total_weight += norm_w

        burnout_score = round(total_score, 2)
        evidence_coverage = total_weight

    return FactorAnalysis(
        contributions=contributions,
        burnout_score=burnout_score,
        evidence_coverage=round(evidence_coverage, 2),
        available_factors=available_factors,
        missing_factors=missing_factors,
    )


# ==========================================
# BurnoutInput (from BurnoutInputBuilder)
# ==========================================

@dataclass
class BurnoutInput:
    """Input chuẩn cho BurnoutEngine."""
    assessment_id: str
    user_id: str
    survey: Optional[SurveyData] = None
    emotion: Optional[EmotionAggregate] = None
    chat: Optional[ChatAnalysisAggregate] = None
    trend: Optional[HistoricalTrend] = None


# ==========================================
# Engine
# ==========================================

class BurnoutEngine:
    """Composite burnout score engine.

    Usage:
        input_data = BurnoutInput(...)
        output = engine.analyze(input_data)
        # output.burnout: BurnoutResult
        # output.insight: BurnoutInsight
    """

    def __init__(self, weights: Optional[dict] = None):
        self._weights = weights or dict(BURNOUT_WEIGHTS)

    @property
    def weights(self) -> dict:
        return dict(self._weights)

    @staticmethod
    def _risk_level(score: Optional[float]) -> str:
        """Determine risk level from score."""
        if score is None:
            return "insufficient_data"

        if score < RISK_THRESHOLDS["low"]:
            return "low"
        if score < RISK_THRESHOLDS["medium"]:
            return "medium"
        if score < RISK_THRESHOLDS["high"]:
            return "high"
        return "critical"

    @staticmethod
    def _get_label(factor: str) -> str:
        """Get Vietnamese label for factor."""
        return FACTOR_LABELS.get(factor, factor)

    def analyze(self, input_data: BurnoutInput) -> BurnoutEngineOutput:
        """Tính burnout score từ BurnoutInput.

        Pure function - deterministic, không gọi API, không IO.

        Args:
            input_data: BurnoutInput từ BurnoutInputBuilder.

        Returns:
            BurnoutEngineOutput với BurnoutResult + insight.
        """
        # Extract data
        survey = input_data.survey
        emotion = input_data.emotion
        chat = input_data.chat
        trend = input_data.trend

        # Analyze all factors with dynamic weight normalization
        factor_analysis = analyze_factors(survey, emotion, chat, trend)

        # Build factors list for BurnoutResult
        factors = []
        for contrib in factor_analysis.contributions:
            if contrib.available and contrib.score is not None:
                details = self._build_factor_details(contrib.factor, survey, chat, emotion, trend)
                factors.append(BurnoutFactor(
                    factor=contrib.factor,
                    score=contrib.score,
                    weight=contrib.weight,
                    contribution=contrib.percentage,
                    details=details,
                ))

        # Calculate total score
        burnout_score = factor_analysis.burnout_score
        if burnout_score is None:
            burnout_score = 0.0

        # Risk level
        risk = self._risk_level(burnout_score)

        # Data completeness
        has_survey = survey is not None
        has_emotion = emotion is not None and emotion.frame_count > 0
        has_chat = chat is not None and chat.message_count > 0
        has_trend = trend is not None and trend.trend != "insufficient_data"

        completeness = calculate_data_completeness(
            has_survey=has_survey,
            has_emotion=has_emotion,
            emotion_count=emotion.frame_count if emotion else 0,
            has_chat=has_chat,
            has_trend=has_trend,
        )

        # Trend
        trend_str = trend.trend if trend else "insufficient_data"

        # Build BurnoutInsight
        insight = self._build_insight(input_data, burnout_score, factor_analysis)

        # Build BurnoutResult với đầy đủ fields
        burnout = BurnoutResult(
            assessment_id=input_data.assessment_id,
            user_id=input_data.user_id,
            engine_version=ENGINE_VERSION,
            burnout_score=burnout_score,
            risk_level=risk,
            confidence=1.0,
            data_completeness=completeness,
            trend=trend_str,
            factors=factors,
            insight=insight,
            recommendations=[],
            analyzed_at=datetime.utcnow(),
        )

        # Log
        logger.info(
            "Burnout analyze done: assessment=%s score=%s risk=%s completeness=%.2f "
            "available=%s missing=%s coverage=%.2f",
            input_data.assessment_id,
            f"{burnout_score:.1f}" if burnout_score else "None",
            risk,
            completeness,
            factor_analysis.available_factors,
            factor_analysis.missing_factors,
            factor_analysis.evidence_coverage,
        )

        return BurnoutEngineOutput(
            burnout=burnout,
            insight=insight,
        )

    def _build_factor_details(
        self,
        factor: str,
        survey: Optional[SurveyData],
        chat: Optional[ChatAnalysisAggregate],
        emotion: Optional[EmotionAggregate],
        trend: Optional[HistoricalTrend],
    ) -> dict:
        """Build details dict for a factor."""
        if factor == "sleep":
            return {
                "sub_score": calculate_sleep_score(survey),
                "sleep_hours": survey.sleep_hours if survey else None,
                "label": self._get_label("sleep"),
            }
        elif factor == "workload":
            return {
                "sub_score": calculate_workload_score(survey),
                "working_hours": survey.working_hours if survey else None,
                "deadline": survey.has_deadline if survey else None,
                "label": self._get_label("workload"),
            }
        elif factor == "stress":
            return {
                "sub_score": calculate_stress_score(survey, chat),
                "survey_stress": survey.stress_level if survey else None,
                "chat_stress": chat.stress_level if chat else None,
                "label": self._get_label("stress"),
            }
        elif factor == "emotion":
            return {
                "sub_score": calculate_emotion_score(emotion),
                "dominant_emotion": emotion.dominant_emotion if emotion else None,
                "negative_ratio": emotion.negative_ratio if emotion else None,
                "frame_count": emotion.frame_count if emotion else 0,
                "label": self._get_label("emotion"),
            }
        elif factor == "behavior":
            return {
                "sub_score": calculate_behavior_score(trend, chat),
                "trend": trend.trend if trend else "insufficient_data",
                "previous_scores": trend.previous_scores if trend else [],
                "chat_message_count": chat.message_count if chat else 0,
                "burnout_signal": chat.burnout_related_signal if chat else None,
                "label": self._get_label("behavior"),
            }
        return {"label": self._get_label(factor)}

    def _build_insight(
        self,
        input_data: BurnoutInput,
        burnout_score: float,
        factor_analysis: FactorAnalysis,
    ) -> BurnoutInsight:
        """Build BurnoutInsight model."""
        # Sort factors by contribution
        sorted_f = sorted(
            factor_analysis.contributions,
            key=lambda c: c.percentage,
            reverse=True
        )
        sorted_f = [f for f in sorted_f if f.available and f.score is not None]

        primary = sorted_f[0].factor if sorted_f else None
        secondary = sorted_f[1].factor if len(sorted_f) >= 2 else None

        # Generate key observations
        key_observations = []
        for contrib in sorted_f[:3]:
            if contrib.factor == "sleep" and contrib.score > 60:
                key_observations.append(f"Ngủ trung bình ít hơn khuyến nghị (score: {contrib.score:.0f}/100)")
            elif contrib.factor == "workload" and contrib.score > 60:
                key_observations.append(f"Quá tải công việc (score: {contrib.score:.0f}/100)")
            elif contrib.factor == "stress" and contrib.score > 60:
                key_observations.append(f"Stress ở mức cao (score: {contrib.score:.0f}/100)")
            elif contrib.factor == "emotion" and contrib.score > 60:
                key_observations.append(f"Cảm xúc tiêu cực chiếm đa số (score: {contrib.score:.0f}/100)")

        # Determine summary
        risk = self._risk_level(burnout_score)
        if risk == "insufficient_data":
            summary = "Không đủ dữ liệu để đánh giá burnout. Vui lòng cung cấp thêm thông tin."
        elif risk == "critical":
            summary = f"Nguy cơ burnout nghiêm trọng ({burnout_score:.0f}/100). Cần hành động ngay."
        elif risk == "high":
            summary = f"Nguy cơ burnout ở mức cao ({burnout_score:.0f}/100). Cần có hành động cải thiện."
        elif risk == "medium":
            summary = f"Có dấu hiệu burnout ở mức trung bình ({burnout_score:.0f}/100). Nên chú ý nghỉ ngơi."
        else:
            summary = f"Tình trạng burnout ở mức thấp ({burnout_score:.0f}/100). Tiếp tục duy trì sức khỏe."

        return BurnoutInsight(
            assessment_id=input_data.assessment_id,
            user_id=input_data.user_id,
            primary_factor=primary,
            secondary_factor=secondary,
            key_observations=key_observations,
            summary=summary,
            data_completeness=calculate_data_completeness_from_analysis(factor_analysis.contributions),
            evidence_coverage=factor_analysis.evidence_coverage,
            available_factors=factor_analysis.available_factors,
            missing_factors=factor_analysis.missing_factors,
        )


# ==========================================
# Singleton
# ==========================================

_engine: Optional[BurnoutEngine] = None


def get_burnout_engine() -> BurnoutEngine:
    """Lay BurnoutEngine singleton."""
    global _engine
    if _engine is None:
        _engine = BurnoutEngine()
    return _engine
