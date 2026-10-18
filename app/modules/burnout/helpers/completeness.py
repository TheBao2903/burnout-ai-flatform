"""
==============================================================
File: completeness.py

Data Sufficiency & Data Quality helpers theo chuẩn khoa học (STA).

NGUYÊN TẮC:
- Bỏ trọng số tùy tiện (Emotion 30%, Survey 30%, Chat 20%, Trend 20%).
- Thay bằng 2 khái niệm khoa học:
  1. Data Sufficiency: Dữ liệu có đủ để đưa ra nhận định không?
     (Tối thiểu cần Burnout Core: Exhaustion + Disengagement).
     Nếu thiếu: Trả "insufficient_data", không cố chẩn đoán bừa, không ép về 0.
  2. Data Quality: Dữ liệu có hợp lệ / nhất quán về mặt logic không?
     (Kiểm tra range 1-5, số giờ ngủ thực tế, v.v.)
- Giữ calculate_data_completeness cho backward compatibility.
==============================================================
"""

from typing import Any, Dict, List, Optional


def evaluate_data_sufficiency(
    has_exhaustion: bool,
    has_disengagement: bool,
    has_recovery: bool = True,
) -> Dict[str, Any]:
    """Đánh giá Data Sufficiency cho kết luận Burnout.

    Quy tắc:
    - Burnout Core (Exhaustion + Disengagement) là điều kiện TIÊN QUYẾT.
    - Thiếu Core -> insufficient_data, KHÔNG đưa ra kết luận.
    """
    missing = []
    if not has_exhaustion:
        missing.append("exhaustion")
    if not has_disengagement:
        missing.append("disengagement")

    is_sufficient = len(missing) == 0
    return {
        "status": "sufficient" if is_sufficient else "insufficient_data",
        "is_sufficient": is_sufficient,
        "missing_elements": missing,
        "has_recovery": has_recovery,
    }


def evaluate_data_quality(
    survey_data: Optional[Dict[str, Any]] = None,
    emotion_count: int = 0,
    chat_message_count: int = 0,
) -> Dict[str, Any]:
    """Đánh giá chất lượng dữ liệu thu thập."""
    issues: List[str] = []

    if survey_data:
        # Check sleep hours sanity
        sleep = survey_data.get("sleep_hours")
        if sleep is not None:
            try:
                s_val = float(sleep)
                if s_val < 0 or s_val > 24:
                    issues.append("Giá trị số giờ ngủ không hợp lệ (0-24)")
            except (ValueError, TypeError):
                issues.append("Số giờ ngủ không phải số")

        # Check Likert ranges 1-5 if dict format
        for group in ["exhaustion", "disengagement", "job_demands"]:
            grp_data = survey_data.get(group)
            if isinstance(grp_data, dict):
                for k, v in grp_data.items():
                    if v is not None:
                        try:
                            fv = float(v)
                            if fv < 1.0 or fv > 5.0:
                                issues.append(f"{group}.{k} ngoài khoảng Likert 1-5 ({fv})")
                        except (ValueError, TypeError):
                            issues.append(f"{group}.{k} không hợp lệ")

    status = "valid"
    if issues:
        status = "invalid" if len(issues) > 2 else "partial"

    return {
        "status": status,
        "valid": len(issues) == 0,
        "issues": issues,
        "supporting_sources": {
            "has_facial": emotion_count > 0,
            "facial_frames": emotion_count,
            "has_chat": chat_message_count > 0,
            "chat_messages": chat_message_count,
        }
    }


# ==========================================
# Legacy Completeness (Backward Compatibility)
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
    """Legacy completeness calculation (0-1)."""
    total = 0.0
    if has_emotion and emotion_count > 0:
        total += DATA_COMPLETENESS_WEIGHTS["emotion"]
    if has_survey:
        total += DATA_COMPLETENESS_WEIGHTS["survey"]
    if has_chat:
        total += DATA_COMPLETENESS_WEIGHTS["chat"]
    if has_trend:
        total += DATA_COMPLETENESS_WEIGHTS["trend"]
    return round(min(1.0, total), 2)


def calculate_data_completeness_from_analysis(
    contributions: List[Any],
) -> float:
    """Legacy completeness helper."""
    from app.modules.burnout.helpers.weights import BURNOUT_WEIGHTS
    available_weight = 0.0
    for contrib in contributions:
        factor = contrib.factor if hasattr(contrib, 'factor') else contrib.get('factor')
        available = contrib.available if hasattr(contrib, 'available') else contrib.get('available', True)
        score = contrib.score if hasattr(contrib, 'score') else contrib.get('score')
        if available and score is not None:
            available_weight += BURNOUT_WEIGHTS.get(factor, 0.0)
    total_weight = sum(BURNOUT_WEIGHTS.values())
    return round(min(1.0, available_weight / total_weight), 2) if total_weight > 0 else 0.0


def calculate_evidence_coverage(
    available_factors: List[str],
    missing_factors: List[str],
) -> float:
    """Ratio của available factors so với tổng."""
    total = len(available_factors) + len(missing_factors)
    if total == 0:
        return 0.0
    return round(len(available_factors) / total, 2)
