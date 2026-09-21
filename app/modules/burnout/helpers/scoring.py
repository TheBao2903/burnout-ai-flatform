"""
==============================================================
File: scoring.py

Scoring helpers - Các hàm tính score cho từng factor.

Pure functions, deterministic, không IO.
==============================================================
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional

# Import models từ helpers/models (tránh circular import)
if TYPE_CHECKING:
    from app.modules.burnout.helpers.models import (
        ChatAnalysisAggregate,
        EmotionAggregate,
        SurveyData,
        HistoricalTrend,
    )

# Deadline mapping
DEADLINE_TO_SCORE = {
    "low": 0.0,
    "medium": 25.0,
    "high": 75.0,
    "extreme": 100.0,
}

# Trend bonus
TREND_BONUS = {
    "increasing": 15.0,  # Trend tăng -> thêm risk
    "decreasing": -10.0,  # Trend giảm -> giảm risk
    "stable": 0.0,  # Stable -> không đổi
}


def calculate_sleep_score(survey: Optional[SurveyData]) -> Optional[float]:
    """Tính sleep score (0-100).

    Logic:
    - 7-8h = 0 (optimal)
    - <4h = 100 (severe)
    - Linear interpolation giữa các điểm

    Returns:
        None nếu không có sleep data.
    """
    if survey is None or survey.sleep_hours is None:
        return None

    hours = survey.sleep_hours

    if hours >= 8:
        return 0.0
    if hours >= 7:
        return max(0.0, (7 - hours) * 50)
    if hours >= 4:
        return 50 + (7 - hours) * 16.67
    # <4h -> severe
    return min(100.0, 50 + (4 - hours) * 25)


def calculate_workload_score(survey: Optional[SurveyData]) -> Optional[float]:
    """Tính workload score (0-100).

    Logic:
    - Working hours: <=8h = 0, >=12h = 100
    - Deadline: low=0, extreme=100
    - Kết hợp cả hai với weights

    Returns:
        None nếu không có workload data.
    """
    if survey is None:
        return None

    hours = survey.working_hours
    deadline = survey.has_deadline

    # Working hours score (70% weight)
    hours_score: Optional[float] = None
    if hours is not None:
        if hours <= 8:
            hours_score = 0.0
        elif hours >= 12:
            hours_score = 100.0
        else:
            hours_score = ((hours - 8) / 4) * 100

    # Deadline score (30% weight)
    deadline_score: Optional[float] = None
    if deadline is not None:
        deadline_score = DEADLINE_TO_SCORE.get(deadline, 50.0)

    # Combine
    if hours_score is None and deadline_score is None:
        return None
    if hours_score is None:
        return deadline_score
    if deadline_score is None:
        return hours_score

    return hours_score * 0.7 + deadline_score * 0.3


def calculate_stress_score(
    survey: Optional[SurveyData],
    chat: Optional[ChatAnalysisAggregate],
) -> Optional[float]:
    """Tính stress score (0-100).

    Kết hợp:
    - Survey stress (60% weight)
    - Chat analysis stress (40% weight)

    Returns:
        None nếu không có stress data.
    """
    survey_stress_score: Optional[float] = None
    chat_stress_score: Optional[float] = None

    # Survey stress: 1-10 -> 0-100
    if survey is not None and survey.stress_level is not None:
        survey_stress_score = (survey.stress_level - 1) / 9 * 100

    # Chat stress
    if chat is not None and chat.stress_level is not None:
        chat_stress_score = chat.stress_level

    if survey_stress_score is None and chat_stress_score is None:
        return None
    if survey_stress_score is None:
        return chat_stress_score
    if chat_stress_score is None:
        return survey_stress_score

    return survey_stress_score * 0.6 + chat_stress_score * 0.4


def calculate_emotion_score(emotion: Optional[EmotionAggregate]) -> Optional[float]:
    """Tính emotion score (0-100).

    Dựa trên negative emotion ratio:
    - 0% negative = 0 (happy)
    - 100% negative = 100 (distressed)

    Returns:
        None nếu không có emotion data.
    """
    if emotion is None or emotion.frame_count == 0:
        return None

    negative_ratio = emotion.negative_ratio
    if negative_ratio is None:
        return None

    return negative_ratio * 100


def calculate_behavior_score(
    trend: Optional[HistoricalTrend],
    chat: Optional["ChatAnalysisAggregate"] = None,
) -> Optional[float]:
    """Tính behavior score từ historical trend HOẶC chat signals (0-100).

    Ưu tiên dùng historical trend (exact):
    - increasing -> thêm 15 điểm (worsening)
    - decreasing -> giảm 10 điểm (improving)
    - stable -> không đổi
    - insufficient_data -> dùng chat signals fallback

    Fallback: Dùng chat analysis signals:
    - work_avoidance_signal: né việc
    - burnout_related_signal: tín hiệu burnout từ chat
    - emotional_negative_signal: cảm xúc tiêu cực

    Returns:
        None nếu không có cả trend và chat data.
    """
    # Primary: Use historical trend if available
    if trend is not None:
        scores = trend.previous_scores
        if scores and len(scores) >= 2:
            base_score = sum(scores) / len(scores)
            trend_str = trend.trend
            bonus = TREND_BONUS.get(trend_str, 0.0)
            result = base_score + bonus
            return max(0.0, min(100.0, result))

    # Fallback: Use chat signals
    if chat is not None and chat.message_count > 0:
        # Combine chat signals related to behavior
        # Work avoidance + burnout signals + emotional negative
        avoidance = chat.work_avoidance_signal or 0
        burnout_signal = chat.burnout_related_signal or 0
        emotional = chat.emotional_negative_signal or 0

        # Calculate behavior score from chat signals
        # Higher values = worse behavior patterns
        behavior_score = (avoidance * 0.4 + burnout_signal * 0.4 + emotional * 0.2)
        return max(0.0, min(100.0, behavior_score))

    return None
