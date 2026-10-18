"""
==============================================================
File: weights.py

Cutoffs, Dimension Levels và Logic phân loại theo chuẩn khoa học (STA).

NGUYÊN TẮC:
- Không dùng trọng số % tùy ý (30% sleep, 25% workload...) vì chưa có kiểm định.
- Sử dụng ngưỡng chuẩn cho thang Likert 1-5 (OLBI, JD-R, Six Areas):
    * Low (Thấp): 1.00 - 2.33
    * Medium (Trung bình): 2.34 - 3.66
    * High (Cao): 3.67 - 5.00
- Phân loại tín hiệu thay vì phán xét chẩn đoán y khoa:
    * "Tín hiệu ổn định ở mức thấp"
    * "Tín hiệu burnout: Cần theo dõi"
    * "Tín hiệu kiệt sức đang tăng"
==============================================================
"""

from typing import Dict, List, Optional, Tuple

# ==========================================
# Likert 1-5 Standard Cutoffs (3-tier division)
# ==========================================

LIKERT_CUTOFFS = {
    "low_max": 2.33,
    "med_max": 3.66,
}


def get_dimension_level(score: Optional[float]) -> str:
    """Xác định mức độ (low, medium, high) cho chỉ số thang Likert 1-5.

    Args:
        score: Giá trị trung bình thang 1-5.

    Returns:
        "low", "medium", "high", hoặc "insufficient_data".
    """
    if score is None:
        return "insufficient_data"
    if score <= LIKERT_CUTOFFS["low_max"]:
        return "low"
    if score <= LIKERT_CUTOFFS["med_max"]:
        return "medium"
    return "high"


def get_burnout_signal_status(
    exhaustion_level: str,
    disengagement_level: str,
    trend: str = "stable",
) -> str:
    """Tạo thông điệp tình trạng tín hiệu Burnout Core chuẩn mực khoa học."""
    if exhaustion_level == "insufficient_data" or disengagement_level == "insufficient_data":
        return "Chưa đủ dữ liệu kết luận"

    if exhaustion_level == "high" and disengagement_level == "high":
        if trend == "increasing":
            return "Tín hiệu kiệt sức và xa cách công việc đang tăng cao (Cần chú ý)"
        return "Tín hiệu kiệt sức và xa cách công việc ở mức cao"

    if exhaustion_level == "high":
        if trend == "increasing":
            return "Tín hiệu kiệt sức đang tăng"
        return "Tín hiệu kiệt sức ở mức cao (Cần theo dõi)"

    if disengagement_level == "high":
        return "Tín hiệu xa cách công việc ở mức cao"

    if exhaustion_level == "medium" or disengagement_level == "medium":
        if trend == "increasing":
            return "Tín hiệu burnout: Cần theo dõi (Xu hướng gia tăng)"
        return "Tín hiệu burnout: Cần theo dõi"

    return "Tín hiệu burnout ổn định ở mức thấp"


# ==========================================
# Legacy Support (Giữ để tương thích tests cũ)
# ==========================================

BURNOUT_WEIGHTS = {
    "sleep": 0.30,
    "workload": 0.25,
    "stress": 0.20,
    "emotion": 0.15,
    "behavior": 0.10,
}

RISK_THRESHOLDS = {
    "low": 40.0,
    "medium": 60.0,
    "high": 80.0,
}


def get_risk_level(score: float) -> str:
    """Determine risk level from burnout score (Legacy 0-100 scale)."""
    if score < RISK_THRESHOLDS["low"]:
        return "low"
    if score < RISK_THRESHOLDS["medium"]:
        return "medium"
    if score < RISK_THRESHOLDS["high"]:
        return "high"
    return "critical"


def get_risk_level_from_score(score: float) -> str:
    return get_risk_level(score)


def normalize_weights(
    available_factors: List[str],
    base_weights: Dict[str, float] = BURNOUT_WEIGHTS,
) -> Dict[str, float]:
    """Legacy normalize weights."""
    if not available_factors:
        return {}
    available_weight = sum(base_weights.get(f, 0.0) for f in available_factors)
    if available_weight == 0:
        return {}
    return {
        f: round(base_weights.get(f, 0.0) / available_weight, 4)
        for f in available_factors
    }


def normalize_weights_tuple(
    contributions: List[Tuple[str, float, float]],
) -> List[Tuple[str, float, float]]:
    """Legacy normalize weights tuple."""
    if not contributions:
        return []
    total_weight = sum(w for _, _, w in contributions)
    if total_weight == 0:
        return []
    return [
        (factor, score, round(weight / total_weight, 4))
        for factor, score, weight in contributions
    ]
