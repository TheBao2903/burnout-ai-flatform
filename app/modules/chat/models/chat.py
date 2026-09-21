"""
==============================================================
File: chat.py

Chat Models - Tin nhan va ket qua hoi thoai.
==============================================================
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class ChatMessage(BaseModel):
    """Mot tin nhan trong cuoc hoi thoai."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "role": "user",
                "content": "Em met qua, khong biet sao ma luon căng thang.",
                "created_at": "2024-01-20T10:05:00Z"
            }
        }
    )

    role: Literal["user", "assistant"] = Field(..., description="Vai tro: user hoac assistant")
    content: str = Field(..., min_length=1, description="Noi dung tin nhan")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Thoi diem gui")


class ChatResult(BaseModel):
    """Ket qua phan tich chat cua mot Session."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "session_id": "session_abc123",
                "messages": [
                    {"role": "user", "content": "Em met qua", "created_at": "2024-01-20T10:05:00Z"},
                    {"role": "assistant", "content": "Ban oi, ban co muon chia se them khong?", "created_at": "2024-01-20T10:05:05Z"}
                ],
                "summary": "Nguoi dung dang bay to su met moi...",
                "keywords": ["met", "cong viec nhieu", "ngu khong du", "ap luc"],
                "stress_level": "medium",
                "burnout_signal": "medium",
                "analyzed_at": "2024-01-20T10:15:00Z"
            }
        }
    )

    session_id: str = Field(..., description="ID cua session")
    messages: List[ChatMessage] = Field(default_factory=list, description="Danh sach tin nhan")
    summary: str = Field(..., description="Tom tat hoi thoai")
    keywords: List[str] = Field(default_factory=list, description="Tu khoa quan trong")
    stress_level: Literal["low", "medium", "high"] = Field(..., description="Muc do stress")
    burnout_signal: Literal["none", "low", "medium", "high"] = Field(..., description="Tin hieu burnout")
    analyzed_at: datetime = Field(default_factory=datetime.utcnow, description="Thoi diem phan tich")
