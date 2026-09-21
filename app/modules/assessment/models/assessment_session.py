"""
==============================================================
File: assessment_session.py

Assessment Session Models - Quản lý lifecycle của một assessment.

Một Assessment Session = một lần user thực hiện đánh giá burnout.
Bao gồm: emotion frames, survey, chat, và kết quả cuối cùng.
==============================================================
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class AssessmentStatus(BaseModel):
    """Trạng thái chi tiết của một assessment."""

    has_emotion: bool = Field(default=False, description="Đã thu thập emotion")
    emotion_count: int = Field(default=0, ge=0, description="Số frame emotion")
    has_survey: bool = Field(default=False, description="Đã submit survey")
    has_chat: bool = Field(default=False, description="Đã có tin nhắn chat")
    has_result: bool = Field(default=False, description="Đã có kết quả burnout")
    is_completed: bool = Field(default=False, description="Assessment hoàn thành")


class AssessmentSession(BaseModel):
    """Assessment Session - một lần đánh giá burnout."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "asm_abc123",
                "user_id": "user_123",
                "status": "collecting",
                "status_detail": {
                    "has_emotion": True,
                    "emotion_count": 5,
                    "has_survey": True,
                    "has_chat": False,
                    "has_result": False,
                    "is_completed": False
                },
                "data_completeness": 0.65,
                "created_at": "2026-08-24T10:00:00Z",
                "updated_at": "2026-08-24T10:15:00Z",
                "completed_at": None
            }
        }
    )

    id: str = Field(..., description="Assessment ID (document id)")
    user_id: str = Field(..., description="User id")

    # Status: collecting / analyzing / completed / cancelled
    status: Literal["collecting", "analyzing", "completed", "cancelled"] = Field(
        default="collecting",
        description="Trạng thái chính"
    )

    # Chi tiết trạng thái
    status_detail: AssessmentStatus = Field(
        default_factory=AssessmentStatus,
        description="Trạng thái chi tiết"
    )

    # Độ hoàn thiện dữ liệu (0-1)
    data_completeness: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Độ hoàn thiện dữ liệu"
    )

    # Kết quả burnout (nếu đã có)
    burnout_result_id: Optional[str] = Field(
        default=None,
        description="FK -> burnout_result document"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)


class AssessmentCreateResponse(BaseModel):
    """Response khi tạo assessment mới."""

    assessment_id: str
    status: str
    message: str


class AssessmentInfoResponse(BaseModel):
    """Response khi lấy thông tin assessment."""

    id: str
    user_id: str
    status: str
    status_detail: dict
    data_completeness: float
    has_result: bool
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
