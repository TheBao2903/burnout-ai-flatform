"""
==============================================================
File: burnout.py

Burnout Models - Kết quả đánh giá Burnout.

CLEAN ARCHITECTURE - Theo thiết kế:
- BurnoutEngine là nơi DUY NHẤT tính burnout_score
- KHÔNG có risk_score (dùng burnout_score)
- Thêm engine_version để track algorithm
- Thêm confidence (tách khỏi score)
- Recommendation structure phân biệt type

Updated:
- Issue #5: Missing data handling
- Clean architecture: Survey chỉ lưu raw answers
==============================================================
"""

from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


# ==========================================
# Factor Models
# ==========================================

class BurnoutFactor(BaseModel):
    """Một yếu tố ảnh hưởng đến Burnout."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "factor": "sleep",
                "score": 95.0,
                "weight": 0.30,
                "contribution": 28.5,
                "details": {
                    "sleep_hours": 4.5,
                    "label": "Thiếu ngủ"
                }
            }
        }
    )

    factor: str = Field(..., description="Tên factor: sleep, workload, stress, emotion, behavior")
    score: float = Field(..., ge=0.0, le=100.0, description="Điểm số của factor (0-100)")
    weight: float = Field(..., ge=0.0, le=1.0, description="Trọng số gốc của factor")
    contribution: float = Field(..., ge=0.0, le=100.0, description="Đóng góp vào burnout_score (%)")
    details: Optional[dict] = Field(default=None, description="Chi tiết bổ sung")


# ==========================================
# Recommendation Models
# ==========================================

class Recommendation(BaseModel):
    """Một recommendation cho user.

    Phân biệt:
    - type: behavior, place, professional_support, etc.
    - Place recommendation chỉ lưu tối thiểu (place_id, name, category, distance)
    - Full place data lấy từ Place Service khi cần
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "rec_001",
                "type": "behavior",
                "priority": "high",
                "title": "Cải thiện giấc ngủ",
                "description": "Ngủ đủ 7-8 tiếng mỗi đêm để phục hồi năng lượng",
                "reason": "Sleep score cao (90/100) - Thiếu ngủ nghiêm trọng",
                "action": "Đặt báo thức sớm hơn 1 tiếng, tránh màn hình trước khi ngủ",
                "target_factor": "sleep",
                "metadata": {}
            }
        }
    )

    id: str = Field(default="", description="Recommendation ID")
    type: Literal["behavior", "place", "professional_support", "lifestyle"] = Field(
        ..., description="Loại recommendation"
    )
    priority: Literal["high", "medium", "low"] = Field(
        ..., description="Độ ưu tiên"
    )
    title: str = Field(..., description="Tiêu đề")
    description: str = Field(..., description="Mô tả chi tiết")
    reason: Optional[str] = Field(
        default=None, description="Lý do đề xuất (dựa trên factor nào)"
    )
    action: Optional[str] = Field(
        default=None, description="Hành động cụ thể user nên làm"
    )
    target_factor: Optional[str] = Field(
        default=None, description="Factor mà recommendation này nhắm đến"
    )

    # Place-specific fields (optional, chỉ khi type="place")
    place_id: Optional[str] = Field(
        default=None, description="Place ID (nếu type=place)"
    )
    name: Optional[str] = Field(
        default=None, description="Tên địa điểm (snapshot)"
    )
    category: Optional[str] = Field(
        default=None, description="Loại: park, cafe, gym..."
    )
    distance_meters: Optional[int] = Field(
        default=None, description="Khoảng cách tại thời điểm recommend (m)"
    )

    # Generic metadata
    metadata: dict = Field(default_factory=dict, description="Metadata bổ sung")


# ==========================================
# Insight Models
# ==========================================

class BurnoutInsight(BaseModel):
    """Insight từ burnout analysis."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "assessment_id": "asm_abc123",
                "user_id": "user_123",
                "primary_factor": "sleep",
                "secondary_factor": "workload",
                "key_observations": [
                    "Ngủ trung bình chỉ 4.5 tiếng/đêm",
                    "Làm việc 12 tiếng/ngày"
                ],
                "summary": "Nguy cơ burnout ở mức cao. Thiếu ngủ và quá tải công việc là hai vấn đề chính.",
                "data_completeness": 0.85,
                "evidence_coverage": 0.75,
                "available_factors": ["sleep", "workload", "stress"],
                "missing_factors": ["emotion", "behavior"]
            }
        }
    )

    assessment_id: str = Field(..., description="Assessment ID")
    user_id: str = Field(..., description="User ID")

    # Factor analysis
    primary_factor: Optional[str] = Field(
        default=None, description="Factor đóng góp cao nhất"
    )
    secondary_factor: Optional[str] = Field(
        default=None, description="Factor đóng góp cao thứ 2"
    )
    key_observations: List[str] = Field(
        default_factory=list, description="Các quan sát chính"
    )

    # Summary
    summary: str = Field(..., description="Tóm tắt tình trạng")

    # Evidence
    data_completeness: float = Field(
        ..., ge=0.0, le=1.0,
        description="Mức độ hoàn thiện dữ liệu (0-1)"
    )
    evidence_coverage: float = Field(
        ..., ge=0.0, le=1.0,
        description="Tỷ lệ evidence có sẵn so với tổng (0-1)"
    )
    available_factors: List[str] = Field(
        default_factory=list, description="Các factors có dữ liệu"
    )
    missing_factors: List[str] = Field(
        default_factory=list, description="Các factors thiếu dữ liệu"
    )


# ==========================================
# Main Burnout Result Model
# ==========================================

class BurnoutResult(BaseModel):
    """Kết quả đánh giá Burnout CUỐI CÙNG.

    ĐÂY LÀ NƠI DUY NHẤT LƯU:
    - burnout_score (KHÔNG có risk_score riêng)
    - risk_level (từ burnout_score)
    - factors (từ BurnoutEngine)
    - data_completeness (evidence coverage)
    - confidence (AI confidence, tách khỏi score)
    - insight (AI summary + observations)
    - recommendations (từ RecommendationEngine)
    - engine_version (để track algorithm changes)
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "burnout_result_001",
                "assessment_id": "asm_xyz789",
                "user_id": "user_123",
                "engine_version": "v2.1",
                "burnout_score": 72.5,
                "risk_level": "high",
                "confidence": 0.85,
                "data_completeness": 0.92,
                "trend": "increasing",
                "factors": [
                    {
                        "factor": "sleep",
                        "score": 95.0,
                        "weight": 0.30,
                        "contribution": 28.5,
                        "details": {"sleep_hours": 4.5, "label": "Thiếu ngủ"}
                    },
                    {
                        "factor": "workload",
                        "score": 75.0,
                        "weight": 0.25,
                        "contribution": 18.75,
                        "details": {"working_hours": 11.0, "label": "Công việc quá tải"}
                    }
                ],
                "insight": {
                    "primary_factor": "sleep",
                    "secondary_factor": "workload",
                    "key_observations": [
                        "Ngủ trung bình chỉ 4.5 tiếng/đêm",
                        "Làm việc 11 tiếng/ngày"
                    ],
                    "summary": "Nguy cơ burnout ở mức cao. Thiếu ngủ và quá tải công việc là hai vấn đề chính."
                },
                "recommendations": [
                    {
                        "type": "behavior",
                        "priority": "high",
                        "title": "Cải thiện giấc ngủ",
                        "description": "Ngủ đủ 7-8 tiếng mỗi đêm",
                        "reason": "Sleep score cao (95/100)",
                        "target_factor": "sleep"
                    }
                ],
                "analyzed_at": "2024-01-20T10:15:00Z",
                "created_at": "2024-01-20T10:15:00Z"
            }
        }
    )

    # IDs
    id: str = Field(default="", description="Document ID (auto)")
    assessment_id: str = Field(..., description="FK -> assessment session")
    user_id: str = Field(..., description="User ID (denormalized)")

    # Engine metadata
    engine_version: str = Field(
        default="v2.1",
        description="Phiên bản BurnoutEngine sử dụng"
    )

    # Core scores
    burnout_score: float = Field(
        ..., ge=0.0, le=100.0,
        description="Điểm burnout (0-100). ĐÂY LÀ ĐIỂM SỐ CHÍNH - KHÔNG dùng risk_score"
    )
    risk_level: Literal["low", "medium", "high", "critical", "insufficient_data"] = Field(
        ...,
        description="Mức độ rủi ro: low(<40), medium(40-59), high(60-79), critical(>=80), insufficient_data(không đủ dữ liệu)"
    )

    # Confidence & Completeness (TÁCH BIỆT)
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Độ tin cậy của kết quả (từ AI/emotion confidence). KHÔNG phải data_completeness"
    )
    data_completeness: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Mức độ hoàn thiện của evidence (0-1). Đây là evidence coverage"
    )

    # Trend
    trend: Literal["increasing", "decreasing", "stable", "insufficient_data"] = Field(
        default="insufficient_data",
        description="Xu hướng so với các lần đánh giá trước"
    )

    # Factors breakdown
    factors: List[BurnoutFactor] = Field(
        default_factory=list,
        description="Danh sách factors với scores và contributions"
    )

    # Insight (AI-generated summary)
    insight: Optional[BurnoutInsight] = Field(
        default=None,
        description="Insight chi tiết từ burnout analysis"
    )

    # Recommendations (từ RecommendationEngine)
    recommendations: List[Recommendation] = Field(
        default_factory=list,
        description="Danh sách recommendations"
    )

    # Disclaimer
    disclaimer: str = Field(
        default="Chỉ số AI không thay thế chẩn đoán y khoa. Nếu cảm thấy quá tải hay tự sát, hãy gặp chuyên gia.",
        description="Tuyên bố từ chối trách nhiệm"
    )

    # Timestamps
    analyzed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm phân tích"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm tạo record"
    )

    # ==========================================
    # Computed Properties
    # ==========================================

    def get_primary_factor(self) -> Optional[str]:
        """Lấy factor đóng góp cao nhất."""
        if not self.factors:
            return None
        return max(self.factors, key=lambda f: f.contribution).factor

    def get_top_recommendations(self, limit: int = 3) -> List[Recommendation]:
        """Lấy top N recommendations theo priority."""
        priority_order = {"high": 0, "medium": 1, "low": 2}
        sorted_recs = sorted(
            self.recommendations,
            key=lambda r: priority_order.get(r.priority, 3)
        )
        return sorted_recs[:limit]


# ==========================================
# Engine Output Model
# ==========================================

class BurnoutEngineOutput(BaseModel):
    """Output từ BurnoutEngine."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "burnout": {
                    "assessment_id": "asm_abc123",
                    "user_id": "user_123",
                    "burnout_score": 72.5,
                    "risk_level": "high",
                    "confidence": 0.85,
                    "data_completeness": 0.92,
                    "trend": "increasing",
                    "factors": [],
                    "recommendations": []
                },
                "insight": {}
            }
        }
    )

    burnout: BurnoutResult = Field(..., description="Kết quả burnout")
    insight: BurnoutInsight = Field(..., description="Insight chi tiết")


# ==========================================
# Legacy Support (Deprecated)
# ==========================================

# Old field names for backward compatibility
BurnoutEngineInput = None  # Deprecated, use BurnoutInput from burnout_input_builder.py
