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

    # Metadata & State Management (STA Compact 3-Turn Protocol)
    message_count: int = Field(
        default=0,
        ge=0,
        description="Số tin nhắn trong session"
    )
    user_turn_count: int = Field(
        default=0,
        ge=0,
        description="Số lượt tin nhắn hợp lệ của user (Chuẩn 3, Trần 4 với 1 mở rộng)"
    )
    current_stage: str = Field(
        default="greeting_and_probe",
        description=(
            "Trạng thái hội thoại hiện tại: "
            "greeting_and_probe | clarifying_cause | reflect_and_support | "
            "wrapping_up | crisis_support"
        )
    )
    is_extended: bool = Field(
        default=False,
        description="True nếu phiên đã dùng lượt mở rộng clarifying_cause (Turn 2.5)"
    )
    is_crisis_active: bool = Field(
        default=False,
        description="True nếu phiên chuyển sang luồng hỗ trợ an toàn khẩn cấp"
    )
    was_fatigued_turn1: bool = Field(
        default=False,
        description="True nếu lượt 1 user trả lời cực ngắn thể hiện kiệt sức (kích hoạt Turn 2.5)"
    )
    user_extended: bool = Field(
        default=False,
        description="True nếu user chủ động gia hạn phiên thêm +3 lượt (STA User-Driven Extension)"
    )
    closed_reason: Optional[Literal["idle_timeout", "max_duration", "manual", "completed_wrap_up", "max_turns_completed", None]] = Field(
        default=None,
        description="Lý do đóng session"
    )

    # STA Compact: Context Tagging (lưu khi đóng session để dashboard phân tích)
    used_topics: list = Field(
        default_factory=list,
        description="Danh sách topic đã dùng trong session (workload, deadline, ...)"
    )
    primary_cause: Optional[str] = Field(
        default=None,
        description="Nguyên nhân chính được xác định: workload | deadline | task_switching | support | autonomy | recovery | disengagement"
    )
    micro_action_offered: Optional[str] = Field(
        default=None,
        description="Micro-action 5 phút đã khuyến nghị cho user"
    )

    # PR 2: Mở rộng context analysis (tương thích ngược - default = None/[])
    detected_stressors: list = Field(
        default_factory=list,
        description="PR 2: Danh sách stressor phát hiện được từ session (workload, priority_conflict, ...)"
    )
    detected_emotions: list = Field(
        default_factory=list,
        description="PR 2: Cảm xúc được thể hiện trực tiếp (frustration, anxiety, ...)"
    )
    behavioral_signals: list = Field(
        default_factory=list,
        description="PR 2: Tín hiệu hành vi (hard_to_focus, rumination, avoidance, ...)"
    )
    context_facts: list = Field(
        default_factory=list,
        description="PR 2: Facts user đã nói cụ thể (số người, deadline, hành động đã thử, ...)"
    )
    evidence_spans: list = Field(
        default_factory=list,
        description="PR 2: Bằng chứng trích từ user message [{turn: N, span: '...'}]"
    )
    support_need: Optional[str] = Field(
        default=None,
        description="PR 2: Nhu cầu hỗ trợ: prioritization | clarity | resources | listening | action | none"
    )
    last_analysis_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="PR 2: Độ chắc chắn của phân tích gần nhất (0-1)"
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
    current_stage: str = "greeting_and_probe"
    user_turn_count: int = 0
    is_extended: bool = False
    user_extended: bool = False
    is_crisis_active: bool = False
    can_extend: bool = False
    is_new: bool = Field(description="True nếu session mới được tạo")
    message: Optional[str] = Field(
        default=None,
        description="Thông báo nếu có (VD: session cũ đã đóng)"
    )
