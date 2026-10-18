"""
==============================================================
File: scoring.py

Scoring helpers - Tính toán các chỉ số theo chuẩn khoa học (STA).

NGUYÊN TẮC KHOA HỌC:
1. Burnout Core: Tính điểm trung bình (Mean) cho Exhaustion (E1-E3) và Disengagement (D1-D3) thang 1-5.
2. Job Demands & Job Resources: Tính điểm trung bình Likert 1-5.
3. Recovery Status: Đối chiếu số giờ ngủ thực tế và cảm nhận hồi phục (Recovery perception 1-5).
4. Trend: Chỉ quan sát biến thiên (tăng / ổn định / giảm). TUYỆT ĐỐI KHÔNG CỘNG/TRỪ ĐIỂM (+15 / -10).
5. Facial & Chat: Là tín hiệu hỗ trợ (supporting signals), không tính điểm trực tiếp vào burnout score.
==============================================================
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from app.modules.burnout.helpers.models import (
        ChatAnalysisAggregate,
        EmotionAggregate,
        SurveyData,
        HistoricalTrend,
    )


# ==========================================
# Scientific Scoring Helpers (STA)
# ==========================================

def calculate_mean_score(scores: List[Optional[float]]) -> Optional[float]:
    """Tính điểm trung bình của một nhóm câu hỏi Likert 1-5.

    Bỏ qua các giá trị None. Không chuyển missing thành 0.
    """
    valid = [float(s) for s in scores if s is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 2)


def calculate_recovery_status(
    sleep_hours: Optional[float],
    recovery_score: Optional[int],
) -> Dict[str, Any]:
    """Đối chiếu số giờ ngủ và cảm nhận hồi phục.

    Không đưa ra kết luận phiến diện ('Ngủ ít nên bị burnout').
    Chỉ phản ánh bối cảnh khả năng hồi phục.
    """
    if sleep_hours is None and recovery_score is None:
        return {
            "status": "insufficient_data",
            "sleep_hours": None,
            "recovery_score": None,
            "description": "Chưa có thông tin hồi phục",
        }

    # Recovery perception is dominant subjective feeling
    # Sleep hours is physiological duration
    status = "medium"
    desc = "Khả năng hồi phục ở mức trung bình"

    low_sleep = sleep_hours is not None and sleep_hours < 6.0
    good_sleep = sleep_hours is not None and sleep_hours >= 7.0
    low_perception = recovery_score is not None and recovery_score <= 2
    good_perception = recovery_score is not None and recovery_score >= 4

    if low_perception or (low_sleep and (recovery_score is None or recovery_score <= 3)):
        status = "low"
        desc = "Khả năng hồi phục thấp"
    elif good_perception and (sleep_hours is None or good_sleep):
        status = "good"
        desc = "Khả năng hồi phục tốt"

    return {
        "status": status,
        "sleep_hours": sleep_hours,
        "recovery_score": recovery_score,
        "description": desc,
    }


def calculate_dimension_trend(history_values: List[float]) -> str:
    """Theo dõi chiều hướng diễn tiến của một dimension (Exhaustion/Disengagement).

    KHÔNG cộng/trừ điểm vào score tổng.
    Chỉ phân loại: 'increasing', 'stable', 'decreasing', 'insufficient_data'.
    """
    if len(history_values) < 2:
        return "insufficient_data"

    # Compare recent average vs older average
    mid = len(history_values) // 2
    older = history_values[:mid]
    recent = history_values[mid:]

    avg_older = sum(older) / len(older)
    avg_recent = sum(recent) / len(recent)
    diff = avg_recent - avg_older

    # Thang Likert 1-5: Thay đổi >= 0.3 điểm là có ý nghĩa thống kê
    if diff >= 0.3:
        return "increasing"
    elif diff <= -0.3:
        return "decreasing"
    return "stable"


# ==========================================
# Legacy Factor Scoring (Kept for tests)
# ==========================================

DEADLINE_TO_SCORE = {
    "low": 0.0,
    "medium": 25.0,
    "high": 75.0,
    "extreme": 100.0,
}

# Trend bonus deprecated - kept at 0 to avoid magic numbers
TREND_BONUS = {
    "increasing": 0.0,
    "decreasing": 0.0,
    "stable": 0.0,
}


def calculate_sleep_score(survey: Optional[Any]) -> Optional[float]:
    """Legacy sleep score (0-100)."""
    if survey is None or not hasattr(survey, "sleep_hours") or survey.sleep_hours is None:
        return None
    hours = survey.sleep_hours
    if hours >= 8:
        return 0.0
    if hours >= 7:
        return max(0.0, (7 - hours) * 50)
    if hours >= 4:
        return 50 + (7 - hours) * 16.67
    return min(100.0, 50 + (4 - hours) * 25)


def calculate_workload_score(survey: Optional[Any]) -> Optional[float]:
    """Legacy workload score (0-100)."""
    if survey is None:
        return None
    hours = getattr(survey, "working_hours", None)
    deadline = getattr(survey, "has_deadline", None)
    if hours is None and deadline is None:
        return None
    hours_score = 0.0
    if hours is not None:
        if hours <= 8:
            hours_score = 0.0
        elif hours >= 12:
            hours_score = 100.0
        else:
            hours_score = ((hours - 8) / 4) * 100
    deadline_score = DEADLINE_TO_SCORE.get(deadline, 50.0) if deadline else hours_score
    if hours is None:
        return deadline_score
    return round(hours_score * 0.7 + deadline_score * 0.3, 1)


def calculate_stress_score(
    survey: Optional[Any],
    chat: Optional[Any] = None,
) -> Optional[float]:
    """Legacy stress score."""
    survey_stress = getattr(survey, "stress_level", None) if survey else None
    chat_stress = getattr(chat, "stress_level", None) if chat else None
    if survey_stress is None and chat_stress is None:
        return None
    if survey_stress is not None and chat_stress is not None:
        return round((survey_stress / 10.0 * 100) * 0.6 + chat_stress * 0.4, 1)
    if survey_stress is not None:
        return round((survey_stress / 10.0) * 100, 1)
    return round(float(chat_stress), 1)


def calculate_emotion_score(emotion: Optional[Any]) -> Optional[float]:
    """Legacy emotion score."""
    if emotion is None:
        return None
    neg = getattr(emotion, "negative_ratio", None)
    if neg is not None:
        return round(neg * 100, 1)
    return None


def calculate_behavior_score(
    trend: Optional[Any],
    chat: Optional[Any] = None,
) -> Optional[float]:
    """Legacy behavior score."""
    return 50.0
