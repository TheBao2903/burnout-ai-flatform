"""
==============================================================
File: assessment.py

Assessment Models - Cau hoi va ket qua danh gia.
==============================================================
"""

from datetime import datetime
from typing import List, Optional, Literal, Union

from pydantic import BaseModel, Field, ConfigDict


class QuestionOption(BaseModel):
    """Option cho cau hoi choice."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "value": "never",
                "label": "Khong bao gio",
                "score": 0
            }
        }
    )

    value: str = Field(..., description="Gia tri option")
    label: str = Field(..., description="Nhan hien thi")
    score: float = Field(default=0.0, description="Diem tuong ung")


class AssessmentTemplate(BaseModel):
    """Mot bo cau hoi danh gia."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "tmpl_burnout_v1",
                "title": "Burnout Assessment",
                "description": "Danh gia muc do kiet su",
                "version": "1.0.0",
                "category": "burnout",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00Z"
            }
        }
    )

    id: str = Field(..., description="Unique ID")
    title: str = Field(..., description="Tieu de")
    description: str = Field(..., description="Mo ta")
    version: str = Field(..., description="Phien ban: 1.0.0")
    category: Literal["burnout", "stress", "anxiety", "depression", "sleep", "mental_health"] = Field(..., description="Danh muc")
    is_active: bool = Field(default=True, description="Dang su dung")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Thoi diem tao")


class AssessmentQuestion(BaseModel):
    """Mot cau hoi trong bo danh gia."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "q_burnout_001",
                "template_id": "tmpl_burnout_v1",
                "question": "Ban ngu bao nhieu tieng moi dem?",
                "question_type": "number",
                "category": "sleep",
                "required": True,
                "order": 1,
                "weight": 1.5
            }
        }
    )

    id: str = Field(..., description="Unique ID")
    template_id: str = Field(..., description="ID cua template")
    question: str = Field(..., description="Noi dung cau hoi")
    description: Optional[str] = Field(default=None, description="Mo ta chi tiet")
    question_type: Literal["number", "boolean", "scale", "text", "multiple_choice", "single_choice"] = Field(..., description="Loai cau hoi")
    category: Literal["sleep", "workload", "stress", "emotion", "work_life", "support", "general"] = Field(..., description="Danh muc")
    required: bool = Field(default=True, description="Bat buoc tra loi")
    order: int = Field(..., ge=1, description="Thu tu hien thi")
    options: Optional[List[QuestionOption]] = Field(default=None, description="Options cho choice")
    min_value: Optional[float] = Field(default=None, description="Gia tri toi thieu")
    max_value: Optional[float] = Field(default=None, description="Gia tri toi da")
    weight: float = Field(default=1.0, ge=0.0, description="He so tinh diem")


class AssessmentAnswer(BaseModel):
    """Cau tra loi cua user cho mot cau hoi."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "ans_001",
                "session_id": "session_abc123",
                "question_id": "q_burnout_001",
                "answer": 5.0,
                "answered_at": "2024-01-20T10:05:00Z"
            }
        }
    )

    id: str = Field(..., description="Unique ID")
    session_id: str = Field(..., description="ID cua session")
    question_id: str = Field(..., description="ID cua cau hoi")
    answer: Union[float, bool, str, List[str], None] = Field(..., description="Gia tri tra loi")
    answered_at: datetime = Field(default_factory=datetime.utcnow, description="Thoi diem tra loi")


class AssessmentResult(BaseModel):
    """Ket qua hoan thanh bo danh gia."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "session_id": "session_abc123",
                "answers": [],
                "completed": True,
                "completed_at": "2024-01-20T10:10:00Z"
            }
        }
    )

    session_id: str = Field(..., description="ID cua session")
    answers: List[AssessmentAnswer] = Field(default_factory=list, description="Danh sach tra loi")
    completed: bool = Field(default=False, description="Da hoan thanh chua")
    completed_at: Optional[datetime] = Field(default=None, description="Thoi diem hoan thanh")
