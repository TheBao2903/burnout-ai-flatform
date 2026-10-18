"""
==============================================================
File: burnout.py

Burnout Models - Kết quả đánh giá Burnout theo chuẩn khoa học (STA).

MÔ HÌNH THIẾT KẾ (STA):
- Burnout Core: Exhaustion + Disengagement (OLBI) thang 1-5
- Context: Job Demands + Job Resources (JD-R) + Six Areas + Recovery
- Supporting Signals: AI Chat (context tags) + DeepFace Facial Emotion
- Data Sufficiency & Data Quality: Thay thế trọng số data completeness tùy tiện
- Confidence: Mặc định null vì chưa có kiểm định lâm sàng
- Tương thích ngược: Duy trì burnout_score, risk_level, factors, insight cho các API cũ
==============================================================
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ==========================================
# Legacy / Factor Models
# ==========================================

class BurnoutFactor(BaseModel):
    """Một yếu tố ảnh hưởng đến Burnout (Legacy support)."""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    factor: str = Field(..., description="Tên factor: sleep, workload, stress, emotion, behavior")
    score: float = Field(default=0.0, ge=0.0, le=100.0, description="Điểm số của factor (0-100)")
    weight: float = Field(default=0.0, ge=0.0, le=1.0, description="Trọng số gốc của factor")
    contribution: float = Field(default=0.0, ge=0.0, le=100.0, description="Đóng góp vào burnout_score (%)")
    percentage: float = Field(default=0.0, description="Alias cho contribution")
    details: Optional[dict] = Field(default_factory=dict, description="Chi tiết bổ sung")

    def model_post_init(self, __context: Any) -> None:
        if self.percentage and not self.contribution:
            self.contribution = self.percentage
        elif self.contribution and not self.percentage:
            self.percentage = self.contribution
        if self.details and "sub_score" in self.details and not self.score:
            self.score = float(self.details["sub_score"])


# ==========================================
# Recommendation Models
# ==========================================

class Recommendation(BaseModel):
    """Gợi ý cải thiện cho người dùng."""

    model_config = ConfigDict(from_attributes=True)

    type: Literal["immediate", "short_term", "long_term", "medical", "lifestyle", "workplace", "behavior", "activity"] = Field(
        default="behavior",
        description="Phân loại gợi ý"
    )
    priority: Literal["low", "medium", "high", "urgent"] = Field(
        default="medium",
        description="Mức độ ưu tiên"
    )
    title: str = Field(..., description="Tiêu đề gợi ý ngắn gọn")
    description: str = Field(..., description="Nội dung chi tiết và hành động cụ thể")
    reason: Optional[str] = Field(default=None, description="Lý do đưa ra gợi ý")
    target_factor: Optional[str] = Field(default=None, description="Factor cần cải thiện")
    place_id: Optional[str] = Field(default=None, description="Place ID nếu là gợi ý địa điểm")
    metadata: Optional[dict] = Field(default=None, description="Metadata bổ sung")


# ==========================================
# STA Scientific Architecture Sub-models
# ==========================================

class DimensionDetail(BaseModel):
    """Chi tiết một khía cạnh (Likert 1-5)."""

    model_config = ConfigDict(from_attributes=True)

    score: Optional[float] = Field(default=None, description="Điểm trung bình (1.00 - 5.00)")
    level: str = Field(default="insufficient_data", description="Mức độ: low, medium, high, insufficient_data")
    trend: str = Field(default="stable", description="Diễn biến: increasing, stable, decreasing, insufficient_data")
    indicator: str = Field(default="→", description="Ký hiệu hiển thị: ↑, →, ↓")


class BurnoutCoreResult(BaseModel):
    """Burnout Core theo OLBI: Exhaustion + Disengagement."""

    model_config = ConfigDict(from_attributes=True)

    exhaustion: DimensionDetail = Field(default_factory=DimensionDetail, description="Chỉ số Kiệt sức")
    disengagement: DimensionDetail = Field(default_factory=DimensionDetail, description="Chỉ số Xa cách công việc")
    status: str = Field(
        default="Tín hiệu burnout ổn định ở mức thấp",
        description="Trạng thái tín hiệu tổng quát"
    )


class RecoveryResult(BaseModel):
    """Khả năng hồi phục: Đối chiếu thời lượng ngủ và cảm nhận hồi phục."""

    model_config = ConfigDict(from_attributes=True)

    sleep_hours: Optional[float] = Field(default=None, description="Số giờ ngủ đêm qua")
    recovery_perception: Optional[float] = Field(default=None, description="Cảm nhận hồi phục (1-5)")
    status: str = Field(default="medium", description="Mức độ hồi phục: low, medium, good, insufficient_data")
    description: str = Field(default="", description="Mô tả bối cảnh hồi phục")


class ContextResult(BaseModel):
    """Bối cảnh công việc và hồi phục (JD-R, Six Areas, Recovery)."""

    model_config = ConfigDict(from_attributes=True)

    job_demands: DimensionDetail = Field(default_factory=DimensionDetail, description="Yêu cầu công việc (JD-R)")
    job_resources: DimensionDetail = Field(default_factory=DimensionDetail, description="Nguồn lực công việc (JD-R)")
    worklife_areas: Dict[str, Optional[float]] = Field(
        default_factory=dict,
        description="Six Areas of Worklife: workload, control, reward, community, fairness, values"
    )
    recovery: RecoveryResult = Field(default_factory=RecoveryResult, description="Khả năng hồi phục")
    overload_signals: Optional[Dict[str, Any]] = Field(default=None, description="Tín hiệu quá tải nhanh")


class SupportingSignalsResult(BaseModel):
    """Tín hiệu hỗ trợ từ AI Chat & DeepFace."""

    model_config = ConfigDict(from_attributes=True)

    chat: Dict[str, Any] = Field(
        default_factory=dict,
        description="Context tags từ AI Chat (workload, deadline, lack of support...)"
    )
    facial: Dict[str, Any] = Field(
        default_factory=dict,
        description="Phân bố cảm xúc từ DeepFace (dominant emotion, negative ratio)"
    )


# ==========================================
# Insight Model
# ==========================================

class BurnoutInsight(BaseModel):
    """Tóm tắt phân tích định tính."""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    session_id: Optional[str] = None
    assessment_id: Optional[str] = None
    user_id: Optional[str] = None
    primary_factor: Optional[str] = None
    secondary_factor: Optional[str] = None
    key_observations: List[str] = Field(default_factory=list)
    summary: str = ""
    data_completeness: float = 1.0
    evidence_coverage: float = 1.0
    available_factors: List[str] = Field(default_factory=list)
    missing_factors: List[str] = Field(default_factory=list)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item, None)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


# ==========================================
# Main Burnout Result Model
# ==========================================

class BurnoutResult(BaseModel):
    """Kết quả đánh giá Burnout theo mô hình STA."""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    id: str = Field(default="", description="Document ID")
    assessment_id: str = Field(default="test", description="FK -> assessment session")
    user_id: str = Field(default="test", description="User ID")
    engine_version: str = Field(default="v2.5_sta", description="Phiên bản thuật toán")

    # STA Output Fields
    burnout_core: BurnoutCoreResult = Field(default_factory=BurnoutCoreResult)
    context: ContextResult = Field(default_factory=ContextResult)
    supporting_signals: SupportingSignalsResult = Field(default_factory=SupportingSignalsResult)
    data_quality: str = Field(default="valid", description="Chất lượng dữ liệu: valid, partial, invalid")
    data_sufficiency: str = Field(default="sufficient", description="Độ đủ dữ liệu: sufficient, insufficient_data")
    interpretation: str = Field(default="", description="Nhận định khoa học tổng hợp")

    # Confidence (Item 15: null nếu chưa kiểm định)
    confidence: Optional[float] = Field(default=None, description="Độ tin cậy kiểm định lâm sàng")

    # Recommendations (Accepts Recommendation objects or legacy string lists)
    recommendations: List[Any] = Field(default_factory=list)

    # Disclaimer (Item 16: Không phán 'Bạn bị burnout', chỉ là tín hiệu hệ thống mẫu)
    disclaimer: str = Field(
        default="Chỉ số AI không thay thế chẩn đoán y khoa. Đây là kết quả nghiên cứu/nguyên mẫu hệ thống nhằm hỗ trợ tự theo dõi."
    )

    # Backward compatibility fields (cho các API/màn hình admin cũ)
    burnout_score: float = Field(default=0.0, description="Điểm quy đổi tham khảo (0-100)")
    risk_level: str = Field(default="low", description="Mức độ: low, medium, high, critical, insufficient_data")
    data_completeness: float = Field(default=1.0)
    trend: str = Field(default="stable")
    factors: List[BurnoutFactor] = Field(default_factory=list)
    insight: Optional[BurnoutInsight] = None

    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def get_top_recommendations(self, limit: int = 3) -> List[Recommendation]:
        """Lấy top N recommendations theo priority."""
        priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        return sorted(self.recommendations, key=lambda r: priority_order.get(r.priority, 4))[:limit]


# ==========================================
# Engine Input & Output Models
# ==========================================

class BurnoutInput(BaseModel):
    """Input chuẩn cho BurnoutEngine."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    assessment_id: str = ""
    user_id: str = ""
    survey: Optional[Any] = None
    emotion: Optional[Any] = None
    chat: Optional[Any] = None
    trend: Optional[Any] = None
    data_completeness: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    session_id: Optional[str] = None
    periodic_survey: Optional[Any] = None

    def model_post_init(self, __context: Any) -> None:
        if self.session_id and not self.assessment_id:
            self.assessment_id = self.session_id
        elif self.assessment_id and not self.session_id:
            self.session_id = self.assessment_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "user_id": self.user_id,
            "survey": self.survey.model_dump() if hasattr(self.survey, "model_dump") else self.survey,
            "data_completeness": self.data_completeness,
            "created_at": self.created_at.isoformat(),
        }


class BurnoutEngineOutput(BaseModel):
    """Output từ BurnoutEngine."""

    model_config = ConfigDict(from_attributes=True)

    burnout: BurnoutResult = Field(..., description="Kết quả burnout")
    insight: BurnoutInsight = Field(..., description="Insight chi tiết")


# Alias for backward compatibility
BurnoutEngineInput = BurnoutInput
