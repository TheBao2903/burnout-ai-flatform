"""
==============================================================
File: chat_session.py

Emotion Chat Session Models - Quản lý session cho Emotion Chat.

Session policy:
- Max duration: 5 hours
- Idle timeout: 60 minutes
- Auto-close when expired
- Summary generated on close
==============================================================
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class ChatSessionStatus(str):
    ACTIVE = "active"
    CLOSED = "closed"
    EXPIRED = "expired"


class ChatSession(BaseModel):
    """Một phiên chat Emotion."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "sess_abc123",
                "assessment_id": "asm_xyz789",
                "user_id": "user_123",
                "status": "active",
                "started_at": "2026-08-30T10:00:00Z",
                "last_activity_at": "2026-08-30T10:30:00Z",
                "summary": None,
            }
        }
    )

    id: str = Field(..., description="Session ID (auto Firestore document ID)")
    assessment_id: str = Field(..., description="Assessment ID (FK)")
    user_id: str = Field(..., description="User ID (denormalized)")
    status: Literal["active", "closed", "expired"] = Field(
        default="active",
        description="Session status"
    )

    # Timestamps
    started_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm bắt đầu session"
    )
    last_activity_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm activity cuối"
    )
    closed_at: Optional[datetime] = Field(
        default=None,
        description="Thời điểm đóng session"
    )

    # Summary (generated when session closes)
    summary: Optional[str] = Field(
        default=None,
        description="Tóm tắt session (tạo khi đóng)"
    )

    # Metadata
    message_count: int = Field(
        default=0,
        ge=0,
        description="Số tin nhắn trong session"
    )
    closed_reason: Optional[Literal["idle_timeout", "max_duration", "manual", None]] = Field(
        default=None,
        description="Lý do đóng session"
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatSessionCreate(BaseModel):
    """Request model để tạo session mới."""
    assessment_id: str
    user_id: str


class ChatSessionResponse(BaseModel):
    """Response model cho session."""
    session_id: str
    assessment_id: str
    status: str
    is_new: bool = Field(description="True nếu session mới được tạo")
    message: Optional[str] = Field(
        default=None,
        description="Thông báo nếu có (VD: session cũ đã đóng)"
    )
