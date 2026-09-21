"""
==============================================================
File: survey_history.py

Survey History Models - Lưu lịch sử survey theo assessment.

CLEAN ARCHITECTURE - Theo thiết kế:
- Survey CHỉ lưu raw answers (user input)
- KHÔNG lưu analysis_result (thuộc BurnoutResult)
- KHÔNG lưu recommendations (thuộc Recommendation Engine)

Collection: FirestoreCollections.SURVEY_HISTORY ("survey_history").
Mỗi assessment chỉ có một survey record.
==============================================================
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


# ==========================================
# Survey Data Groups (Logical Organization)
# ==========================================

class SleepGroup(BaseModel):
    """Sleep-related survey fields."""
    sleep_hours: Optional[float] = Field(
        default=None, ge=0.0, le=24.0,
        description="Số giờ ngủ trung bình"
    )


class WorkloadGroup(BaseModel):
    """Workload-related survey fields."""
    working_hours: Optional[float] = Field(
        default=None, ge=0.0, le=24.0,
        description="Số giờ làm việc/ngày"
    )
    overtime_hours: Optional[int] = Field(
        default=None, ge=0, le=24,
        description="Số giờ tăng ca/tuần"
    )
    work_days_per_week: Optional[int] = Field(
        default=None, ge=1, le=7,
        description="Số ngày làm việc/tuần"
    )
    consecutive_work_days: Optional[int] = Field(
        default=None, ge=0, le=30,
        description="Số ngày làm việc liên tục"
    )
    rest_days: Optional[int] = Field(
        default=None, ge=0, le=7,
        description="Số ngày nghỉ/tuần"
    )


class PsychologicalGroup(BaseModel):
    """Psychological-related survey fields."""
    stress_level: Optional[int] = Field(
        default=None, ge=1, le=10,
        description="Mức độ stress tự đánh giá (1-10)"
    )
    motivation_level: Optional[int] = Field(
        default=None, ge=1, le=10,
        description="Mức độ động lực (1-10)"
    )
    work_satisfaction: Optional[int] = Field(
        default=None, ge=1, le=10,
        description="Mức độ hài lòng công việc (1-10)"
    )


class WorkPressureGroup(BaseModel):
    """Work pressure-related survey fields."""
    has_deadline: Optional[Literal["low", "medium", "high", "extreme"]] = Field(
        default=None,
        description="Mức độ deadline: low/medium/high/extreme"
    )


class PhysiologicalGroup(BaseModel):
    """Physiological-related survey fields."""
    heart_rate: Optional[int] = Field(
        default=None, ge=30, le=220,
        description="Nhịp tim (bpm)"
    )


# ==========================================
# Main Survey Data Model
# ==========================================

class SurveyData(BaseModel):
    """Dữ liệu survey chuẩn - CHỈ raw answers.

    KHÔNG chứa:
    - analysis_result (thuộc BurnoutResult)
    - recommendations (thuộc Recommendation Engine)

    Fields được nhóm theo domain logic:
    - Sleep: sleep_hours
    - Workload: working_hours, overtime_hours, work_days_per_week, consecutive_work_days, rest_days
    - Psychological: stress_level, motivation_level, work_satisfaction
    - Work Pressure: has_deadline
    - Physiological: heart_rate
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sleep_hours": 5.5,
                "working_hours": 10.0,
                "overtime_hours": 3,
                "has_deadline": "high",
                "work_days_per_week": 6,
                "stress_level": 8,
                "motivation_level": 3
            }
        }
    )

    # Sleep Group
    sleep_hours: Optional[float] = Field(
        default=None, ge=0.0, le=24.0,
        description="Số giờ ngủ trung bình"
    )

    # Workload Group
    working_hours: Optional[float] = Field(
        default=None, ge=0.0, le=24.0,
        description="Số giờ làm việc/ngày"
    )
    overtime_hours: Optional[int] = Field(
        default=None, ge=0, le=24,
        description="Số giờ tăng ca/tuần"
    )
    work_days_per_week: Optional[int] = Field(
        default=None, ge=1, le=7,
        description="Số ngày làm việc/tuần"
    )
    consecutive_work_days: Optional[int] = Field(
        default=None, ge=0, le=30,
        description="Số ngày làm việc liên tục"
    )
    rest_days: Optional[int] = Field(
        default=None, ge=0, le=7,
        description="Số ngày nghỉ/tuần"
    )

    # Psychological Group
    stress_level: Optional[int] = Field(
        default=None, ge=1, le=10,
        description="Mức độ stress tự đánh giá (1-10)"
    )
    motivation_level: Optional[int] = Field(
        default=None, ge=1, le=10,
        description="Mức độ động lực (1-10)"
    )
    work_satisfaction: Optional[int] = Field(
        default=None, ge=1, le=10,
        description="Mức độ hài lòng công việc (1-10)"
    )

    # Work Pressure Group
    has_deadline: Optional[Literal["low", "medium", "high", "extreme"]] = Field(
        default=None,
        description="Mức độ deadline: low/medium/high/extreme"
    )

    # Physiological Group
    heart_rate: Optional[int] = Field(
        default=None, ge=30, le=220,
        description="Nhịp tim (bpm)"
    )

    # Metadata
    survey_version: str = Field(
        default="v1.0",
        description="Phiên bản survey schema"
    )
    submitted_at: Optional[datetime] = Field(
        default=None,
        description="Thời điểm submit"
    )

    # ==========================================
    # Field Availability Checkers
    # ==========================================

    def has_sleep_data(self) -> bool:
        """Check if sleep data is available."""
        return self.sleep_hours is not None

    def has_workload_data(self) -> bool:
        """Check if workload data is available (any workload field)."""
        return any([
            self.working_hours is not None,
            self.overtime_hours is not None,
            self.work_days_per_week is not None,
            self.has_deadline is not None,
        ])

    def has_stress_data(self) -> bool:
        """Check if stress data is available."""
        return self.stress_level is not None

    def has_psychological_data(self) -> bool:
        """Check if any psychological data is available."""
        return any([
            self.stress_level is not None,
            self.motivation_level is not None,
            self.work_satisfaction is not None,
        ])

    def has_physiological_data(self) -> bool:
        """Check if physiological data is available."""
        return self.heart_rate is not None

    def has_any_data(self) -> bool:
        """Check if any survey data is available."""
        return any([
            self.has_sleep_data(),
            self.has_workload_data(),
            self.has_psychological_data(),
            self.has_physiological_data(),
        ])

    def get_available_fields(self) -> list[str]:
        """Get list of available field names."""
        fields = []
        for field_name, value in self.model_dump(exclude_none=True).items():
            if value is not None and field_name not in ['survey_version', 'submitted_at']:
                fields.append(field_name)
        return fields


class SurveyHistoryRecord(BaseModel):
    """Lịch sử survey của một assessment - CLEAN VERSION.

    CHỈ lưu:
    - assessment_id, user_id (FK)
    - survey data (raw answers)
    - status, timestamps

    KHÔNG lưu:
    - analysis_result (thuộc BurnoutResult)
    - recommendations (thuộc Recommendation Engine)
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "survey_abc123",
                "assessment_id": "asm_xyz789",
                "user_id": "user_123",
                "survey": {
                    "sleep_hours": 5.5,
                    "working_hours": 10.0,
                    "overtime_hours": 3,
                    "has_deadline": "high",
                    "work_days_per_week": 6,
                    "stress_level": 8,
                    "motivation_level": 3
                },
                "status": "completed",
                "completed_at": "2026-08-24T10:15:00Z",
                "created_at": "2026-08-24T10:14:00Z"
            }
        }
    )

    id: str = Field(..., description="Document id (auto)")
    assessment_id: str = Field(..., description="FK -> assessment")
    user_id: str = Field(..., description="User id (denormalized)")

    # CHỈ raw answers - KHÔNG có analysis_result hay recommendations
    survey: SurveyData = Field(..., description="Dữ liệu survey (raw answers)")

    # Status
    status: Literal["in_progress", "completed"] = Field(
        default="in_progress",
        description="Trạng thái survey"
    )

    # Timestamps
    completed_at: Optional[datetime] = Field(default=None, description="Thời điểm hoàn thành")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Thời điểm tạo")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Thời điểm cập nhật")


# ==========================================
# Survey Questions (Static Definition)
# ==========================================

class SurveyQuestions(BaseModel):
    """Câu hỏi survey chuẩn (static)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "questions": [
                    {
                        "id": "sleep_hours",
                        "text": "Trung bình bạn ngủ bao nhiêu giờ mỗi đêm?",
                        "type": "number",
                        "min": 0,
                        "max": 24,
                        "step": 0.5
                    }
                ]
            }
        }
    )

    questions: list = Field(
        default_factory=lambda: [
            {
                "id": "sleep_hours",
                "text": "Trung bình bạn ngủ bao nhiêu giờ mỗi đêm?",
                "type": "number",
                "min": 0,
                "max": 24,
                "step": 0.5,
                "required": True,
                "hint": "Khuyến nghị: 7-9 giờ cho người trưởng thành",
                "group": "sleep"
            },
            {
                "id": "working_hours",
                "text": "Trung bình bạn làm việc bao nhiêu giờ mỗi ngày?",
                "type": "number",
                "min": 0,
                "max": 24,
                "step": 0.5,
                "required": True,
                "hint": "Bao gồm giờ làm việc chính thức",
                "group": "workload"
            },
            {
                "id": "overtime_hours",
                "text": "Bạn tăng ca bao nhiêu giờ/tuần?",
                "type": "number",
                "min": 0,
                "max": 60,
                "step": 1,
                "required": False,
                "hint": "Số giờ làm thêm ngoài giờ làm chính thức",
                "group": "workload"
            },
            {
                "id": "has_deadline",
                "text": "Mức độ deadline hiện tại của bạn như thế nào?",
                "type": "select",
                "options": [
                    {"value": "low", "label": "Thấp - Không có deadline gấp"},
                    {"value": "medium", "label": "Vừa - Deadline có thể quản lý được"},
                    {"value": "high", "label": "Cao - Deadline sát và nhiều"},
                    {"value": "extreme", "label": "Rất cao - Deadline chồng chất, liên tục"}
                ],
                "required": True,
                "group": "work_pressure"
            },
            {
                "id": "work_days_per_week",
                "text": "Bạn làm việc bao nhiêu ngày/tuần?",
                "type": "number",
                "min": 1,
                "max": 7,
                "step": 1,
                "required": True,
                "group": "workload"
            },
            {
                "id": "stress_level",
                "text": "Trên thang 1-10, mức độ stress hiện tại của bạn là bao nhiêu?",
                "type": "scale",
                "min": 1,
                "max": 10,
                "labels": {"1": "Rất thấp", "5": "Trung bình", "10": "Cực kỳ cao"},
                "required": True,
                "group": "psychological"
            },
            {
                "id": "motivation_level",
                "text": "Trên thang 1-10, mức độ động lực làm việc của bạn hiện tại là bao nhiêu?",
                "type": "scale",
                "min": 1,
                "max": 10,
                "labels": {"1": "Không có động lực", "5": "Bình thường", "10": "Rất hăng hái"},
                "required": True,
                "group": "psychological"
            }
        ],
        description="Danh sách câu hỏi survey"
    )


# ==========================================
# DEPRECATED MODELS - Kept for migration reference only
# ==========================================

class SurveyAnalysisResult(BaseModel):
    """DEPRECATED: Kết quả phân tích survey.

    ĐÃ LOẠI BỎ KHỎI SURVEY MODEL.
    Chuyển sang BurnoutResult cho:
    - risk_level
    - burnout_score (thay vì risk_score)
    - summary
    - factors

    Chỉ giữ lại để migration reference.
    """

    model_config = ConfigDict(
        deprecated=True,
        json_schema_extra={
            "example": {
                "risk_level": "high",
                "risk_score": 0,  # DEPRECATED - use burnout_score instead
                "summary": "Nguy cơ burnout cao. Cần thay đổi lối sống.",
                "suggestions": [
                    "Ngủ ít hơn 6 tiếng ảnh hưởng nghiêm trọng đến sức khỏe",
                    "Làm việc hơn 10 tiếng/ngày gây kiệt sức nghiêm trọng"
                ]
            }
        }
    )

    risk_level: str = Field(default="low", description="[DEPRECATED] Mức độ nguy cơ")
    risk_score: int = Field(default=0, description="[DEPRECATED] - Use burnout_score in BurnoutResult")
    summary: str = Field(default="", description="[DEPRECATED] - Use summary in BurnoutResult.insight")
    suggestions: list[str] = Field(default_factory=list, description="[DEPRECATED] - Use recommendations in BurnoutResult")


class SurveyRecommendation(BaseModel):
    """DEPRECATED: Một recommendation cho survey.

    ĐÃ LOẠI BỎ KHỎI SURVEY MODEL.
    Recommendations nên được lưu trong BurnoutResult.recommendations
    với Place Recommendation trong Recommendation Engine.
    """

    model_config = ConfigDict(
        deprecated=True,
        json_schema_extra={
            "example": {
                "place_id": "geoapify:abc123",
                "name": "Công viên Tao Đàn",
                "address": "Nguyễn Du, Q.1, TP.HCM",
                "distance_meters": 500,
                "category": "park",
                "phone": "02838221234",
                "website": "https://example.com"
            }
        }
    )

    place_id: Optional[str] = Field(default=None, description="[DEPRECATED] Place ID")
    name: str = Field(default="", description="[DEPRECATED] Tên địa điểm/hoạt động")
    address: Optional[str] = Field(default=None, description="[DEPRECATED] Địa chỉ")
    distance_meters: Optional[int] = Field(default=None, description="[DEPRECATED] Khoảng cách (m)")
    category: Optional[str] = Field(default=None, description="[DEPRECATED] Loại: park, cafe, gym...")
    phone: Optional[str] = Field(default=None, description="[DEPRECATED] Số điện thoại")
    website: Optional[str] = Field(default=None, description="[DEPRECATED] Website")
