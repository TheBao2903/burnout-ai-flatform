"""
==============================================================
File: chat_history.py

Chat History Models - Lưu lịch sử chat và analysis cho user.

Đây là collection riêng để lưu lịch sử chat theo assessment,
phân biệt với ChatResult (dùng cho session-level).
==============================================================
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class ChatAnalysisSignal(BaseModel):
    """Signal từ GPT analysis."""

    score: float = Field(..., ge=0, le=100, description="Điểm signal (0-100)")
    evidence: str = Field(default="", description="Bằng chứng từ text")


class ChatAnalysis(BaseModel):
    """Kết quả phân tích chat từ GPT."""

    stress_level: ChatAnalysisSignal = Field(..., description="Mức độ stress")
    fatigue_signal: ChatAnalysisSignal = Field(..., description="Tín hiệu mệt mỏi")
    motivation_level: ChatAnalysisSignal = Field(..., description="Mức độ động lực")
    work_avoidance_signal: ChatAnalysisSignal = Field(..., description="Tín hiệu tránh việc")
    sleep_problem_signal: ChatAnalysisSignal = Field(..., description="Tín hiệu vấn đề giấc ngủ")
    emotional_negative_signal: ChatAnalysisSignal = Field(..., description="Tín hiệu tiêu cực")
    workload_signal: ChatAnalysisSignal = Field(..., description="Tín hiệu khối lượng công việc")
    burnout_related_signal: ChatAnalysisSignal = Field(..., description="Tín hiệu liên quan burnout")

    detected_signals: List[str] = Field(default_factory=list, description="Các signals phát hiện được")
    important_phrases: List[str] = Field(default_factory=list, description="Các cụm từ quan trọng")
    uncertainty: float = Field(default=0.0, ge=0.0, le=1.0, description="Độ không chắc chắn")

    # Audit fields
    ai_model: Optional[str] = Field(default=None, description="Model AI sử dụng")
    analyzed_at: datetime = Field(default_factory=datetime.utcnow, description="Thời điểm phân tích")


class ChatHistoryRecord(BaseModel):
    """Lịch sử một tin nhắn chat trong assessment."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "chat_abc123",
                "assessment_id": "asm_xyz789",
                "user_id": "user_123",
                "role": "user",
                "content": "Em rất mệt, không muốn đi làm nữa.",
                "analysis": {
                    "stress_level": {"score": 85, "evidence": "..."},
                    "fatigue_signal": {"score": 90, "evidence": "..."},
                    "motivation_level": {"score": 80, "evidence": "..."},
                    "work_avoidance_signal": {"score": 85, "evidence": "..."},
                    "sleep_problem_signal": {"score": 0, "evidence": "..."},
                    "emotional_negative_signal": {"score": 70, "evidence": "..."},
                    "workload_signal": {"score": 90, "evidence": "..."},
                    "burnout_related_signal": {"score": 85, "evidence": "..."},
                    "detected_signals": ["fatigue", "high_workload"],
                    "important_phrases": ["rất mệt", "không muốn đi làm"],
                    "uncertainty": 0.08,
                    "ai_model": "gemini-3.5-flash",
                    "analyzed_at": "2026-08-24T10:30:00Z"
                },
                "created_at": "2026-08-24T10:29:55Z"
            }
        }
    )

    id: str = Field(..., description="Document id (auto)")
    assessment_id: str = Field(..., description="FK -> assessment")
    user_id: str = Field(..., description="User id (denormalized)")

    role: Literal["user", "assistant"] = Field(..., description="Vai trò: user hoặc assistant")
    content: str = Field(..., min_length=1, description="Nội dung tin nhắn")

    # GPT Analysis (null cho assistant message hoặc nếu analyze fail)
    analysis: Optional[ChatAnalysis] = Field(default=None, description="Kết quả phân tích từ GPT")

    # Client-side idempotency key (Q5). Nếu client retry cùng ID,
    # backend sẽ trả response cũ thay vì xử lý lại.
    client_message_id: Optional[str] = Field(
        default=None,
        description="Idempotency key từ client (UUID)",
    )

    created_at: datetime = Field(default_factory=datetime.utcnow, description="Thời điểm gửi")


class ChatSessionSummary(BaseModel):
    """Tóm tắt một phiên chat trong assessment."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "assessment_id": "asm_xyz789",
                "user_id": "user_123",
                "message_count": 5,
                "last_message_at": "2026-08-24T10:45:00Z",
                "has_analysis": True,
                "aggregated_stress_level": 75.0,
                "detected_signals": ["fatigue", "high_workload", "work_avoidance"]
            }
        }
    )

    assessment_id: str = Field(..., description="Assessment ID")
    user_id: str = Field(..., description="User id")

    message_count: int = Field(default=0, ge=0, description="Số tin nhắn")
    last_message_at: Optional[datetime] = Field(default=None, description="Tin nhắn cuối")

    has_analysis: bool = Field(default=False, description="Có ít nhất 1 message có analysis")

    # Aggregated from all analyses in session
    aggregated_stress_level: Optional[float] = Field(default=None, ge=0, le=100)
    aggregated_burnout_signal: Optional[float] = Field(default=None, ge=0, le=100)

    detected_signals: List[str] = Field(default_factory=list, description="Tất cả signals phát hiện")
    keywords: List[str] = Field(default_factory=list, description="Từ khóa quan trọng")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
