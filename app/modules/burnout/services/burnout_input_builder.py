"""
==============================================================
File: burnout_input_builder.py

BurnoutInputBuilder - Load và normalize dữ liệu từ Firestore
thành BurnoutInput cho BurnoutEngine.

Nhiệm vụ:
1. Load assessment data
2. Load survey data
3. Load emotion data (aggregate nếu có nhiều frames)
4. Load chat analysis data
5. Load historical burnout results (cho trend)
6. Tính data_completeness
7. Build BurnoutInput

BurnoutInputBuilder KHÔNG tính Burnout.
BurnoutInputBuilder KHÔNG gọi AI.
BurnoutInputBuilder KHÔNG biết Firestore trực tiếp.
==============================================================
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.modules.burnout.helpers import (
    calculate_data_completeness,
    SurveyData,
    HistoricalTrend,
)

# Import helpers models
from app.modules.burnout.helpers.models import (
    EmotionAggregate,
    ChatAnalysisAggregate,
    HistoricalTrend as TrendModel,
)

logger = logging.getLogger("burnout.input_builder")


# ==========================================
# Aggregators
# ==========================================

class EmotionAggregator:
    """Aggregate nhiều emotion frames thành một."""

    NEGATIVE_EMOTIONS = {"sad", "angry", "fear", "disgust"}
    POSITIVE_EMOTIONS = {"happy"}
    NEUTRAL_EMOTIONS = {"neutral"}

    @staticmethod
    def aggregate(emotion_records: List[Dict[str, Any]]) -> Optional[EmotionAggregate]:
        """Aggregate list of emotion records.

        Args:
            emotion_records: List of emotion dicts từ Firestore.

        Returns:
            EmotionAggregate hoặc None nếu empty.
        """
        if not emotion_records:
            return None

        frame_count = len(emotion_records)

        # Sum all emotion scores
        total_happy = 0.0
        total_sad = 0.0
        total_neutral = 0.0
        total_fear = 0.0
        total_angry = 0.0
        total_surprise = 0.0
        total_disgust = 0.0
        total_confidence = 0.0
        dominant_emotions: Dict[str, int] = {}

        for record in emotion_records:
            emotions = record.get("emotions", {})
            if isinstance(emotions, dict):
                total_happy += emotions.get("happy", 0.0)
                total_sad += emotions.get("sad", 0.0)
                total_neutral += emotions.get("neutral", 0.0)
                total_fear += emotions.get("fear", 0.0)
                total_angry += emotions.get("angry", 0.0)
                total_surprise += emotions.get("surprise", 0.0)
                total_disgust += emotions.get("disgust", 0.0)

            total_confidence += float(record.get("confidence", 0.0))

            dom = str(record.get("dominant_emotion", "neutral")).lower()
            dominant_emotions[dom] = dominant_emotions.get(dom, 0) + 1

        # Calculate averages
        avg_happy = total_happy / frame_count
        avg_sad = total_sad / frame_count
        avg_neutral = total_neutral / frame_count
        avg_fear = total_fear / frame_count
        avg_angry = total_angry / frame_count
        avg_surprise = total_surprise / frame_count
        avg_disgust = total_disgust / frame_count
        avg_confidence = total_confidence / frame_count

        # Calculate ratios
        total_score = avg_happy + avg_sad + avg_neutral + avg_fear + avg_angry + avg_surprise + avg_disgust
        if total_score > 0:
            negative_ratio = (avg_sad + avg_fear + avg_angry + avg_disgust) / total_score
            positive_ratio = (avg_happy) / total_score
            neutral_ratio = (avg_neutral) / total_score
        else:
            negative_ratio = 0.0
            positive_ratio = 0.0
            neutral_ratio = 1.0

        # Find most common dominant emotion
        most_common_dom = max(dominant_emotions.items(), key=lambda x: x[1])[0] if dominant_emotions else "neutral"

        return EmotionAggregate(
            dominant_emotion=most_common_dom,
            confidence=avg_confidence,
            negative_ratio=negative_ratio,
            positive_ratio=positive_ratio,
            neutral_ratio=neutral_ratio,
            happy=avg_happy,
            sad=avg_sad,
            neutral=avg_neutral,
            fear=avg_fear,
            angry=avg_angry,
            surprise=avg_surprise,
            disgust=avg_disgust,
            frame_count=frame_count,
        )


class ChatAggregator:
    """Aggregate chat analysis từ nhiều messages."""

    @staticmethod
    def aggregate(chat_records: List[Dict[str, Any]]) -> Optional[ChatAnalysisAggregate]:
        """Aggregate list of chat records with analysis.

        Args:
            chat_records: List of chat records từ Firestore (user messages with analysis).

        Returns:
            ChatAnalysisAggregate hoặc None nếu empty.
        """
        # Filter chỉ lấy user messages với analysis
        analyzed_messages = [
            r for r in chat_records
            if r.get("role") == "user" and r.get("analysis")
        ]

        if not analyzed_messages:
            return None

        message_count = len(analyzed_messages)

        # Sum all signals
        total_stress = 0.0
        total_fatigue = 0.0
        total_motivation = 0.0
        total_work_avoidance = 0.0
        total_sleep_problem = 0.0
        total_emotional_negative = 0.0
        total_workload = 0.0
        total_burnout = 0.0
        total_uncertainty = 0.0

        all_detected_signals: set = set()
        all_keywords: set = set()

        for record in analyzed_messages:
            analysis = record.get("analysis", {})
            if isinstance(analysis, dict):
                # Extract scores (handle both nested and flat structure)
                stress_data = analysis.get("stress_level", {})
                if isinstance(stress_data, dict):
                    total_stress += float(stress_data.get("score", 0))
                else:
                    total_stress += float(stress_data or 0)

                fatigue_data = analysis.get("fatigue_signal", {})
                if isinstance(fatigue_data, dict):
                    total_fatigue += float(fatigue_data.get("score", 0))
                else:
                    total_fatigue += float(fatigue_data or 0)

                motivation_data = analysis.get("motivation_level", {})
                if isinstance(motivation_data, dict):
                    total_motivation += float(motivation_data.get("score", 0))
                else:
                    total_motivation += float(motivation_data or 0)

                avoidance_data = analysis.get("work_avoidance_signal", {})
                if isinstance(avoidance_data, dict):
                    total_work_avoidance += float(avoidance_data.get("score", 0))
                else:
                    total_work_avoidance += float(avoidance_data or 0)

                sleep_data = analysis.get("sleep_problem_signal", {})
                if isinstance(sleep_data, dict):
                    total_sleep_problem += float(sleep_data.get("score", 0))
                else:
                    total_sleep_problem += float(sleep_data or 0)

                emotional_data = analysis.get("emotional_negative_signal", {})
                if isinstance(emotional_data, dict):
                    total_emotional_negative += float(emotional_data.get("score", 0))
                else:
                    total_emotional_negative += float(emotional_data or 0)

                workload_data = analysis.get("workload_signal", {})
                if isinstance(workload_data, dict):
                    total_workload += float(workload_data.get("score", 0))
                else:
                    total_workload += float(workload_data or 0)

                burnout_data = analysis.get("burnout_related_signal", {})
                if isinstance(burnout_data, dict):
                    total_burnout += float(burnout_data.get("score", 0))
                else:
                    total_burnout += float(burnout_data or 0)

                total_uncertainty += float(analysis.get("uncertainty", 0.5))

                # Union detected signals
                signals = analysis.get("detected_signals", [])
                if isinstance(signals, list):
                    all_detected_signals.update(signals)

                # Union keywords
                keywords = analysis.get("important_phrases", [])
                if isinstance(keywords, list):
                    all_keywords.update(keywords)

        # Calculate averages
        count = message_count
        return ChatAnalysisAggregate(
            stress_level=total_stress / count if count else 50.0,
            fatigue_signal=total_fatigue / count if count else 0.0,
            motivation_level=total_motivation / count if count else 50.0,
            work_avoidance_signal=total_work_avoidance / count if count else 0.0,
            sleep_problem_signal=total_sleep_problem / count if count else 0.0,
            emotional_negative_signal=total_emotional_negative / count if count else 0.0,
            workload_signal=total_workload / count if count else 0.0,
            burnout_related_signal=total_burnout / count if count else 0.0,
            detected_signals=list(all_detected_signals),
            keywords=list(all_keywords)[:20],  # Limit
            uncertainty=total_uncertainty / count if count else 0.5,
            message_count=message_count,
        )


class TrendAnalyzer:
    """Analyze historical trend từ previous burnout results."""

    @staticmethod
    def analyze(historical_results: List[Dict[str, Any]]) -> TrendModel:
        """Analyze trend from historical results.

        Args:
            historical_results: List of burnout results, sorted newest first.

        Returns:
            TrendModel.
        """
        if len(historical_results) < 2:
            return TrendModel(
                trend="insufficient_data",
                assessment_count=len(historical_results),
            )

        # Extract scores (newest first)
        scores = []
        for r in historical_results:
            score = r.get("burnout_score") or r.get("score")
            if score is not None:
                scores.append(float(score))

        if len(scores) < 2:
            return TrendModel(
                previous_scores=scores,
                trend="insufficient_data",
                assessment_count=len(scores),
            )

        # Calculate trend
        # Compare first 1/3 vs last 1/3 averages
        n = len(scores)
        early_scores = scores[:max(1, n // 3)]
        late_scores = scores[-max(1, n // 3):]

        early_avg = sum(early_scores) / len(early_scores)
        late_avg = sum(late_scores) / len(late_scores)

        diff = late_avg - early_avg

        if diff > 10:
            trend = "increasing"
        elif diff < -10:
            trend = "decreasing"
        else:
            trend = "stable"

        return TrendModel(
            previous_scores=scores,
            trend=trend,
            assessment_count=len(scores),
        )


# ==========================================
# Survey Normalizer
# ==========================================

class SurveyNormalizer:
    """Normalize survey data từ Firestore."""

    @staticmethod
    def normalize(survey_record: Optional[Dict[str, Any]]) -> Optional[SurveyData]:
        """Normalize survey record.

        Args:
            survey_record: Survey dict từ Firestore.

        Returns:
            SurveyData hoặc None.
        """
        if not survey_record:
            return None

        survey = survey_record.get("survey", {})
        if not survey:
            # Fallback: survey_record có thể là survey trực tiếp
            survey = survey_record

        if isinstance(survey, dict):
            return SurveyData(
                sleep_hours=survey.get("sleep_hours") or survey.get("sleep_hour"),
                working_hours=survey.get("working_hours") or survey.get("working_hour"),
                overtime_hours=survey.get("overtime_hours") or survey.get("overtime"),
                has_deadline=survey.get("has_deadline") or survey.get("deadline"),
                work_days_per_week=survey.get("work_days_per_week") or survey.get("work_day"),
                stress_level=survey.get("stress_level"),
                motivation_level=survey.get("motivation_level"),
                consecutive_work_days=survey.get("consecutive_work_days"),
                rest_days=survey.get("rest_days"),
                work_satisfaction=survey.get("work_satisfaction"),
            )

        return None


# ==========================================
# Data Completeness Calculator
# ==========================================

DATA_COMPLETENESS_WEIGHTS = {
    "emotion": 0.30,
    "survey": 0.30,
    "chat": 0.20,
    "trend": 0.20,
}


# Keep class for backward compatibility
class DataCompletenessCalculator:
    """Tính data completeness dựa trên available data.

    DEPRECATED: Dùng calculate_data_completeness() function thay thế.
    """

    WEIGHTS = DATA_COMPLETENESS_WEIGHTS

    @staticmethod
    def calculate(
        has_emotion: bool = False,
        emotion_count: int = 0,
        has_survey: bool = False,
        has_chat: bool = False,
        has_chat_analysis: bool = False,
        has_trend: bool = False,
    ) -> float:
        """Tính data completeness (0-1)."""
        # Normalize: nếu có chat thì tính là có chat analysis
        actual_has_chat = has_chat or has_chat_analysis
        return calculate_data_completeness(
            has_emotion=has_emotion,
            emotion_count=emotion_count,
            has_survey=has_survey,
            has_chat=actual_has_chat,
            has_trend=has_trend,
        )


# ==========================================
# Burnout Input Builder
# ==========================================

@dataclass
class BurnoutInput:
    """Input chuẩn cho BurnoutEngine."""

    assessment_id: str
    user_id: str
    survey: Optional[SurveyData] = None
    emotion: Optional[EmotionAggregate] = None
    chat: Optional[ChatAnalysisAggregate] = None
    trend: Optional[TrendModel] = None
    data_completeness: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "user_id": self.user_id,
            "survey": self.survey.to_dict() if self.survey else None,
            "emotion": self.emotion if isinstance(self.emotion, dict) else None,
            "chat": self.chat if isinstance(self.chat, dict) else None,
            "trend": self.trend if isinstance(self.trend, dict) else None,
            "data_completeness": self.data_completeness,
            "created_at": self.created_at.isoformat(),
        }


class BurnoutInputBuilder:
    """Build BurnoutInput từ raw Firestore data.

    Usage:
        builder = BurnoutInputBuilder(
            assessment=assessment_doc,
            survey=survey_doc,
            emotions=list_of_emotion_docs,
            chats=list_of_chat_docs,
            historical_results=list_of_burnout_results,
        )
        burnout_input = builder.build()
    """

    def __init__(
        self,
        assessment_id: str,
        user_id: str,
        assessment: Optional[Dict[str, Any]] = None,
        survey: Optional[Dict[str, Any]] = None,
        emotions: Optional[List[Dict[str, Any]]] = None,
        chats: Optional[List[Dict[str, Any]]] = None,
        historical_results: Optional[List[Dict[str, Any]]] = None,
    ):
        self.assessment_id = assessment_id
        self.user_id = user_id
        self.assessment = assessment
        self.survey = survey
        self.emotions = emotions or []
        self.chats = chats or []
        self.historical_results = historical_results or []

    def build(self) -> BurnoutInput:
        """Build BurnoutInput.

        Returns:
            BurnoutInput ready for BurnoutEngine.
        """
        # 1. Normalize survey
        survey_data = SurveyNormalizer.normalize(self.survey)

        # 2. Aggregate emotions
        emotion_agg = EmotionAggregator.aggregate(self.emotions)

        # 3. Aggregate chat analysis
        chat_agg = ChatAggregator.aggregate(self.chats)

        # 4. Analyze trend
        trend = TrendAnalyzer.analyze(self.historical_results)

        # 5. Calculate data completeness
        has_survey = survey_data is not None
        has_emotion = emotion_agg is not None and emotion_agg.frame_count > 0
        emotion_count = emotion_agg.frame_count if emotion_agg else 0
        has_chat = chat_agg is not None and chat_agg.message_count > 0
        has_trend = trend.assessment_count >= 2

        completeness = calculate_data_completeness(
            has_emotion=has_emotion,
            emotion_count=emotion_count,
            has_survey=has_survey,
            has_chat=has_chat,
            has_trend=has_trend,
        )

        # 6. Get created_at from assessment or now
        created_at = datetime.utcnow()
        if self.assessment:
            created_at_str = self.assessment.get("created_at")
            if created_at_str:
                try:
                    if isinstance(created_at_str, str):
                        created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    else:
                        created_at = created_at_str
                except Exception:
                    pass

        return BurnoutInput(
            assessment_id=self.assessment_id,
            user_id=self.user_id,
            survey=survey_data,
            emotion=emotion_agg,
            chat=chat_agg,
            trend=trend,
            data_completeness=completeness,
            created_at=created_at,
        )
