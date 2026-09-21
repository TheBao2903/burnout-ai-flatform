"""
==============================================================
File: models.py

Core models/dataclasses dùng chung cho burnout system.

Tách riêng để tránh circular imports và tái sử dụng.
==============================================================
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EmotionAggregate:
    """Kết quả aggregate từ nhiều emotion frames."""

    dominant_emotion: str = "neutral"
    confidence: float = 0.0
    negative_ratio: float = 0.0
    positive_ratio: float = 0.0
    neutral_ratio: float = 0.0
    happy: float = 0.0
    sad: float = 0.0
    neutral: float = 0.0
    fear: float = 0.0
    angry: float = 0.0
    surprise: float = 0.0
    disgust: float = 0.0
    frame_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dominant_emotion": self.dominant_emotion,
            "confidence": self.confidence,
            "negative_ratio": self.negative_ratio,
            "positive_ratio": self.positive_ratio,
            "neutral_ratio": self.neutral_ratio,
            "emotions": {
                "happy": self.happy,
                "sad": self.sad,
                "neutral": self.neutral,
                "fear": self.fear,
                "angry": self.angry,
                "surprise": self.surprise,
                "disgust": self.disgust,
            },
            "frame_count": self.frame_count,
        }


@dataclass
class ChatAnalysisAggregate:
    """Kết quả aggregate từ chat analysis."""

    stress_level: float = 50.0
    fatigue_signal: float = 0.0
    motivation_level: float = 50.0
    work_avoidance_signal: float = 0.0
    sleep_problem_signal: float = 0.0
    emotional_negative_signal: float = 0.0
    workload_signal: float = 0.0
    burnout_related_signal: float = 0.0
    detected_signals: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    uncertainty: float = 0.5
    message_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stress_level": self.stress_level,
            "fatigue_signal": self.fatigue_signal,
            "motivation_level": self.motivation_level,
            "work_avoidance_signal": self.work_avoidance_signal,
            "sleep_problem_signal": self.sleep_problem_signal,
            "emotional_negative_signal": self.emotional_negative_signal,
            "workload_signal": self.workload_signal,
            "burnout_related_signal": self.burnout_related_signal,
            "detected_signals": self.detected_signals,
            "keywords": self.keywords,
            "uncertainty": self.uncertainty,
            "message_count": self.message_count,
        }


@dataclass
class SurveyData:
    """Survey data đã normalize."""

    sleep_hours: Optional[float] = None
    working_hours: Optional[float] = None
    overtime_hours: Optional[int] = None
    has_deadline: Optional[str] = None  # low, medium, high, extreme
    work_days_per_week: Optional[int] = None
    stress_level: Optional[int] = None  # 1-10
    motivation_level: Optional[int] = None  # 1-10
    consecutive_work_days: Optional[int] = None
    rest_days: Optional[int] = None
    work_satisfaction: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sleep_hours": self.sleep_hours,
            "working_hours": self.working_hours,
            "overtime_hours": self.overtime_hours,
            "has_deadline": self.has_deadline,
            "work_days_per_week": self.work_days_per_week,
            "stress_level": self.stress_level,
            "motivation_level": self.motivation_level,
            "consecutive_work_days": self.consecutive_work_days,
            "rest_days": self.rest_days,
            "work_satisfaction": self.work_satisfaction,
        }


@dataclass
class HistoricalTrend:
    """Historical trend data."""

    previous_scores: List[float] = field(default_factory=list)
    trend: str = "insufficient_data"  # increasing, decreasing, stable, insufficient_data
    assessment_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "previous_scores": self.previous_scores,
            "trend": self.trend,
            "assessment_count": self.assessment_count,
        }


@dataclass
class FactorContribution:
    """Một factor contribution cho burnout score."""
    factor: str
    score: float  # 0-100
    weight: float  # original weight (e.g., 0.30)
    percentage: float  # score * weight
    available: bool = True


@dataclass
class FactorAnalysis:
    """Kết quả phân tích các factors."""
    contributions: List[FactorContribution]
    burnout_score: Optional[float]  # None if no factors available
    evidence_coverage: float  # 0-1, based on available weights
    available_factors: List[str]
    missing_factors: List[str]
