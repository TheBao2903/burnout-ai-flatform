"""
==============================================================
File: survey_history.py

Survey History Models - Lưu lịch sử survey theo chuẩn khoa học (STA).

MÔ HÌNH THIẾT KẾ:
1. Daily Check-in (Tối đa ~12 câu/ngày):
   - Exhaustion (OLBI): E1 - E3 (Thang 1-5)
   - Disengagement (OLBI): D1 - D3 (Thang 1-5)
   - Job Demands (JD-R): JD1 - JD3 (Thang 1-5)
   - Sleep: Số giờ ngủ đêm qua (float)
   - Recovery: Cảm nhận hồi phục sau khi ngủ/nghỉ ngơi (Thang 1-5)
   - Quick Overload: Đánh giá quá tải hôm nay (Thang 1-5) + lý do nếu chọn 4-5
   - Daily Work Changes: Làm thêm hôm nay (giờ) + Áp lực deadline hôm nay

2. Periodic Survey (Khảo sát định kỳ môi trường làm việc - Không làm mỗi ngày):
   - Job Resources (JD-R): JR1 - JR4 (Thang 1-5)
   - Six Areas of Worklife: Workload, Control, Reward, Community, Fairness, Values (Thang 1-5)

Collection:
- surveys: Daily check-in records gắn với assessment_id & user_id
- periodic_surveys: Periodic survey records gắn với user_id
==============================================================
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ==========================================
# Daily Check-in Dimension Groups
# ==========================================

class ExhaustionGroup(BaseModel):
    """Exhaustion dimension (OLBI core) - Thang 1-5."""
    e1: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="E1. Hôm nay tôi cảm thấy khó duy trì năng lượng để tiếp tục công việc."
    )
    e2: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="E2. Hôm nay công việc khiến tôi cảm thấy mình đã tiêu hao rất nhiều năng lượng."
    )
    e3: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="E3. Sau khi kết thúc công việc hôm nay, tôi vẫn khó lấy lại sức."
    )

    def mean_score(self) -> Optional[float]:
        vals = [v for v in [self.e1, self.e2, self.e3] if v is not None]
        return sum(vals) / len(vals) if vals else None


class DisengagementGroup(BaseModel):
    """Disengagement dimension (OLBI core) - Thang 1-5."""
    d1: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="D1. Hôm nay tôi muốn tránh hoặc hạn chế những việc liên quan đến công việc."
    )
    d2: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="D2. Hôm nay tôi cảm thấy mình ít quan tâm đến công việc hơn bình thường."
    )
    d3: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="D3. Hôm nay tôi cảm thấy công việc của mình ít có ý nghĩa hơn bình thường."
    )

    def mean_score(self) -> Optional[float]:
        vals = [v for v in [self.d1, self.d2, self.d3] if v is not None]
        return sum(vals) / len(vals) if vals else None


class JobDemandsGroup(BaseModel):
    """Job Demands dimension (JD-R) - Thang 1-5."""
    jd1: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="JD1. Hôm nay tôi có quá nhiều việc phải hoàn thành."
    )
    jd2: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="JD2. Hôm nay tôi phải hoàn thành công việc trong thời gian quá ngắn."
    )
    jd3: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="JD3. Hôm nay tôi phải xử lý nhiều việc cùng lúc."
    )

    def mean_score(self) -> Optional[float]:
        vals = [v for v in [self.jd1, self.jd2, self.jd3] if v is not None]
        return sum(vals) / len(vals) if vals else None


class RecoveryGroup(BaseModel):
    """Recovery dimension - Sleep hours & recovery perception."""
    sleep_hours: Optional[float] = Field(
        default=None, ge=0.0, le=24.0,
        description="Đêm qua bạn ngủ khoảng bao nhiêu giờ?"
    )
    recovery_score: Optional[int] = Field(
        default=None, ge=1, le=5,
        description="Hôm nay bạn cảm thấy mình đã hồi phục như thế nào? (1: Chưa hồi phục -> 5: Hồi phục tốt)"
    )


class QuickOverloadGroup(BaseModel):
    """Quick Overload check-in."""
    quick_overload: Optional[int] = Field(
        default=None, ge=1, le=5,
        description="Hôm nay công việc có khiến bạn cảm thấy quá tải không? (1-5)"
    )
    overload_reasons: List[str] = Field(
        default_factory=list,
        description="Lý do quá tải nếu quick_overload >= 4 (Quá nhiều việc, Áp lực deadline, v.v.)"
    )


class DailyWorkChangesGroup(BaseModel):
    """Biến động công việc trong ngày."""
    has_overtime_today: Optional[bool] = Field(
        default=None,
        description="Hôm nay bạn có làm thêm giờ không?"
    )
    overtime_hours_today: Optional[float] = Field(
        default=None, ge=0.0, le=24.0,
        description="Số giờ tăng ca hôm nay"
    )
    current_deadline_pressure: Optional[Literal["low", "medium", "high", "extreme"]] = Field(
        default=None,
        description="Áp lực deadline hiện tại (low, medium, high, extreme)"
    )


# ==========================================
# Main Daily Survey Data Model
# ==========================================

class SurveyData(BaseModel):
    """Dữ liệu Daily Check-in chuẩn STA và backward-compatible."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "exhaustion": {"e1": 4.0, "e2": 4.0, "e3": 3.0},
                "disengagement": {"d1": 2.0, "d2": 3.0, "d3": 2.0},
                "job_demands": {"jd1": 4.0, "jd2": 5.0, "jd3": 4.0},
                "sleep_hours": 6.0,
                "recovery_score": 2,
                "quick_overload": 4,
                "overload_reasons": ["Quá nhiều việc", "Áp lực deadline"],
                "has_overtime_today": True,
                "overtime_hours_today": 2.0,
                "current_deadline_pressure": "high"
            }
        }
    )

    # 1. Structured groups (STA Model)
    exhaustion: Optional[ExhaustionGroup] = Field(
        default_factory=ExhaustionGroup,
        description="Nhóm câu hỏi Kiệt sức (OLBI: E1-E3)"
    )
    disengagement: Optional[DisengagementGroup] = Field(
        default_factory=DisengagementGroup,
        description="Nhóm câu hỏi Xa cách công việc (OLBI: D1-D3)"
    )
    job_demands: Optional[JobDemandsGroup] = Field(
        default_factory=JobDemandsGroup,
        description="Nhóm câu hỏi Yêu cầu công việc (JD-R: JD1-JD3)"
    )
    recovery: Optional[RecoveryGroup] = Field(
        default_factory=RecoveryGroup,
        description="Nhóm hồi phục (Giấc ngủ + Cảm nhận hồi phục)"
    )
    quick_overload_data: Optional[QuickOverloadGroup] = Field(
        default_factory=QuickOverloadGroup,
        description="Đánh giá quá tải nhanh"
    )
    work_changes: Optional[DailyWorkChangesGroup] = Field(
        default_factory=DailyWorkChangesGroup,
        description="Biến động làm việc trong ngày"
    )

    # 2. Flattened & Legacy fields (for backward compatibility & direct access)
    sleep_hours: Optional[float] = Field(
        default=None, ge=0.0, le=24.0,
        description="Số giờ ngủ đêm qua"
    )
    recovery_score: Optional[int] = Field(
        default=None, ge=1, le=5,
        description="Cảm nhận hồi phục (1-5)"
    )
    quick_overload: Optional[int] = Field(
        default=None, ge=1, le=5,
        description="Mức độ quá tải hôm nay (1-5)"
    )
    overload_reasons: List[str] = Field(
        default_factory=list,
        description="Lý do quá tải"
    )
    has_overtime_today: Optional[bool] = Field(
        default=None,
        description="Có làm thêm hôm nay không"
    )
    overtime_hours_today: Optional[float] = Field(
        default=None, ge=0.0, le=24.0,
        description="Số giờ làm thêm hôm nay"
    )
    current_deadline_pressure: Optional[Literal["low", "medium", "high", "extreme"]] = Field(
        default=None,
        description="Áp lực deadline"
    )

    # Legacy attributes for compatibility with older code/tests
    working_hours: Optional[float] = Field(default=None, ge=0.0, le=24.0)
    overtime_hours: Optional[int] = Field(default=None, ge=0, le=24)
    work_days_per_week: Optional[int] = Field(default=None, ge=1, le=7)
    consecutive_work_days: Optional[int] = Field(default=None, ge=0, le=30)
    rest_days: Optional[int] = Field(default=None, ge=0, le=7)
    stress_level: Optional[int] = Field(default=None, ge=1, le=10)
    motivation_level: Optional[int] = Field(default=None, ge=1, le=10)
    work_satisfaction: Optional[int] = Field(default=None, ge=1, le=10)
    has_deadline: Optional[Literal["low", "medium", "high", "extreme"]] = Field(default=None)
    heart_rate: Optional[int] = Field(default=None, ge=30, le=220)

    # Metadata
    survey_version: str = Field(default="v3.0", description="Phiên bản survey schema")
    submitted_at: Optional[datetime] = Field(default=None, description="Thời điểm submit")

    def model_post_init(self, __context: Any) -> None:
        """Sync flattened fields with structured groups if provided."""
        # Sync sleep_hours
        if self.sleep_hours is None and self.recovery and self.recovery.sleep_hours is not None:
            self.sleep_hours = self.recovery.sleep_hours
        elif self.sleep_hours is not None and self.recovery and self.recovery.sleep_hours is None:
            self.recovery.sleep_hours = self.sleep_hours

        # Sync recovery_score
        if self.recovery_score is None and self.recovery and self.recovery.recovery_score is not None:
            self.recovery_score = self.recovery.recovery_score
        elif self.recovery_score is not None and self.recovery and self.recovery.recovery_score is None:
            self.recovery.recovery_score = self.recovery_score

        # Sync quick_overload
        if self.quick_overload is None and self.quick_overload_data and self.quick_overload_data.quick_overload is not None:
            self.quick_overload = self.quick_overload_data.quick_overload
        elif self.quick_overload is not None and self.quick_overload_data and self.quick_overload_data.quick_overload is None:
            self.quick_overload_data.quick_overload = self.quick_overload

        # Sync overload reasons
        if not self.overload_reasons and self.quick_overload_data and self.quick_overload_data.overload_reasons:
            self.overload_reasons = self.quick_overload_data.overload_reasons
        elif self.overload_reasons and self.quick_overload_data and not self.quick_overload_data.overload_reasons:
            self.quick_overload_data.overload_reasons = self.overload_reasons

        # Sync deadline
        if self.current_deadline_pressure is None and self.has_deadline is not None:
            self.current_deadline_pressure = self.has_deadline
        elif self.has_deadline is None and self.current_deadline_pressure is not None:
            self.has_deadline = self.current_deadline_pressure

    def has_burnout_core(self) -> bool:
        """Kiểm tra có đủ dữ liệu lõi (Exhaustion & Disengagement) hay không."""
        has_e = self.exhaustion and self.exhaustion.mean_score() is not None
        has_d = self.disengagement and self.disengagement.mean_score() is not None
        return bool(has_e and has_d)

    def has_recovery(self) -> bool:
        """Kiểm tra có dữ liệu hồi phục (ngủ hoặc cảm nhận hồi phục) hay không."""
        return self.sleep_hours is not None or (self.recovery and self.recovery.recovery_score is not None)

    def has_any_data(self) -> bool:
        """Check if any useful data is present."""
        return self.has_burnout_core() or self.has_recovery() or self.quick_overload is not None or self.working_hours is not None


class SurveyHistoryRecord(BaseModel):
    """Lịch sử Daily Check-in theo assessment."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Document id")
    assessment_id: str = Field(..., description="FK -> assessment")
    user_id: str = Field(..., description="User id")
    survey: SurveyData = Field(..., description="Dữ liệu survey")
    status: Literal["in_progress", "completed"] = Field(default="completed")
    completed_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================
# Periodic Survey Models (Khảo sát định kỳ)
# ==========================================

class PeriodicJobResources(BaseModel):
    """Job Resources dimension (JD-R) - Thang 1-5."""
    jr1: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="JR1. Tôi nhận được sự hỗ trợ cần thiết để hoàn thành công việc."
    )
    jr2: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="JR2. Tôi có đủ quyền chủ động trong cách thực hiện công việc của mình."
    )
    jr3: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="JR3. Khi gặp khó khăn, tôi nhận được hướng dẫn hoặc phản hồi cần thiết."
    )
    jr4: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="JR4. Những nỗ lực của tôi trong công việc được ghi nhận."
    )

    def mean_score(self) -> Optional[float]:
        vals = [v for v in [self.jr1, self.jr2, self.jr3, self.jr4] if v is not None]
        return sum(vals) / len(vals) if vals else None


class PeriodicSixAreas(BaseModel):
    """Six Areas of Worklife - Thang 1-5."""
    workload: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="Workload: Khối lượng công việc hiện tại phù hợp với khả năng của tôi."
    )
    control: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="Control: Tôi có đủ quyền chủ động trong những việc liên quan đến công việc của mình."
    )
    reward: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="Reward: Công sức và đóng góp của tôi được ghi nhận xứng đáng."
    )
    community: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="Community: Tôi nhận được sự hỗ trợ và tôn trọng cần thiết từ những người làm việc cùng mình."
    )
    fairness: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="Fairness: Tôi cảm thấy các quyết định liên quan đến công việc của mình được thực hiện công bằng."
    )
    values: Optional[float] = Field(
        default=None, ge=1.0, le=5.0,
        description="Values: Công việc hiện tại phù hợp với những điều tôi coi trọng."
    )

    def to_dict(self) -> Dict[str, Optional[float]]:
        return {
            "workload": self.workload,
            "control": self.control,
            "reward": self.reward,
            "community": self.community,
            "fairness": self.fairness,
            "values": self.values,
        }


class PeriodicSurveyRecord(BaseModel):
    """Record khảo sát định kỳ môi trường làm việc của user."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default="", description="Document id")
    user_id: str = Field(..., description="User ID")
    job_resources: PeriodicJobResources = Field(default_factory=PeriodicJobResources)
    six_areas: PeriodicSixAreas = Field(default_factory=PeriodicSixAreas)
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================
# Survey Questions Definitions (Static UI Definition)
# ==========================================

class SurveyQuestions:
    """Static definitions of Daily and Periodic survey questions."""

    DAILY_QUESTIONS = [
        # Exhaustion (OLBI)
        {"id": "e1", "group": "exhaustion", "text": "Hôm nay tôi cảm thấy khó duy trì năng lượng để tiếp tục công việc.", "type": "scale_1_5"},
        {"id": "e2", "group": "exhaustion", "text": "Hôm nay công việc khiến tôi cảm thấy mình đã tiêu hao rất nhiều năng lượng.", "type": "scale_1_5"},
        {"id": "e3", "group": "exhaustion", "text": "Sau khi kết thúc công việc hôm nay, tôi vẫn khó lấy lại sức.", "type": "scale_1_5"},
        # Disengagement (OLBI)
        {"id": "d1", "group": "disengagement", "text": "Hôm nay tôi muốn tránh hoặc hạn chế những việc liên quan đến công việc.", "type": "scale_1_5"},
        {"id": "d2", "group": "disengagement", "text": "Hôm nay tôi cảm thấy mình ít quan tâm đến công việc hơn bình thường.", "type": "scale_1_5"},
        {"id": "d3", "group": "disengagement", "text": "Hôm nay tôi cảm thấy công việc của mình ít có ý nghĩa hơn bình thường.", "type": "scale_1_5"},
        # Job Demands (JD-R)
        {"id": "jd1", "group": "job_demands", "text": "Hôm nay tôi có quá nhiều việc phải hoàn thành.", "type": "scale_1_5"},
        {"id": "jd2", "group": "job_demands", "text": "Hôm nay tôi phải hoàn thành công việc trong thời gian quá ngắn.", "type": "scale_1_5"},
        {"id": "jd3", "group": "job_demands", "text": "Hôm nay tôi phải xử lý nhiều việc cùng lúc.", "type": "scale_1_5"},
        # Recovery
        {"id": "sleep_hours", "group": "recovery", "text": "Đêm qua bạn ngủ khoảng bao nhiêu giờ?", "type": "number", "min": 0, "max": 24, "step": 0.5},
        {"id": "recovery_score", "group": "recovery", "text": "Sau khi ngủ hoặc nghỉ ngơi, hôm nay bạn cảm thấy mình đã hồi phục như thế nào?", "type": "scale_1_5", "labels": {"1": "Chưa hồi phục", "2": "Hồi phục rất ít", "3": "Hồi phục một phần", "4": "Khá hồi phục", "5": "Hồi phục tốt"}},
        # Quick Overload
        {"id": "quick_overload", "group": "quick_overload", "text": "Hôm nay công việc có khiến bạn cảm thấy quá tải không?", "type": "scale_1_5", "labels": {"1": "Hoàn toàn không", "2": "Ít", "3": "Khá nhiều", "4": "Rất nhiều", "5": "Cực kỳ nhiều"}, "conditional_reasons_on": [4, 5]},
    ]

    PERIODIC_QUESTIONS = [
        # Job Resources
        {"id": "jr1", "group": "job_resources", "text": "Tôi nhận được sự hỗ trợ cần thiết để hoàn thành công việc.", "type": "scale_1_5"},
        {"id": "jr2", "group": "job_resources", "text": "Tôi có đủ quyền chủ động trong cách thực hiện công việc của mình.", "type": "scale_1_5"},
        {"id": "jr3", "group": "job_resources", "text": "Khi gặp khó khăn, tôi nhận được hướng dẫn hoặc phản hồi cần thiết.", "type": "scale_1_5"},
        {"id": "jr4", "group": "job_resources", "text": "Những nỗ lực của tôi trong công việc được ghi nhận.", "type": "scale_1_5"},
        # Six Areas of Worklife
        {"id": "workload", "group": "six_areas", "text": "Khối lượng công việc hiện tại phù hợp với khả năng của tôi.", "type": "scale_1_5"},
        {"id": "control", "group": "six_areas", "text": "Tôi có đủ quyền chủ động trong những việc liên quan đến công việc của mình.", "type": "scale_1_5"},
        {"id": "reward", "group": "six_areas", "text": "Công sức và đóng góp của tôi được ghi nhận xứng đáng.", "type": "scale_1_5"},
        {"id": "community", "group": "six_areas", "text": "Tôi nhận được sự hỗ trợ và tôn trọng cần thiết từ những người làm việc cùng mình.", "type": "scale_1_5"},
        {"id": "fairness", "group": "six_areas", "text": "Tôi cảm thấy các quyết định liên quan đến công việc của mình được thực hiện công bằng.", "type": "scale_1_5"},
        {"id": "values", "group": "six_areas", "text": "Công việc hiện tại phù hợp với những điều tôi coi trọng.", "type": "scale_1_5"},
    ]


# Legacy aliases for compatibility
SurveyAnalysisResult = None
SurveyRecommendation = None
