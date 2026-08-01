"""
==============================================================
File: session.py

Chức năng:
- Định nghĩa model Session - một lần đánh giá Burnout của user.
- Chỉ chứa thông tin phiên, KHÔNG nhúng Emotion/Survey/Chat.
- Phục vụ việc tracking tiến trình đánh giá.

Được sử dụng tại:
- API Layer (bắt đầu/kết thúc session)
- Service Layer (quản lý trạng thái)
- Repository Layer (lưu trạng thái session)

Luồng dữ liệu:
Start Session → Session Created → (Emotion + Survey + Chat) → End Session → Burnout Result
==============================================================
"""

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field, ConfigDict


class Session(BaseModel):
    """
    Domain Model cho một phiên đánh giá Burnout.

    Đại diện cho một lần user thực hiện đánh giá.
    Một user có thể có nhiều session (nhiều lần đánh giá).
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "session_abc123",
                "user_id": "user_123",
                "started_at": "2024-01-20T10:00:00Z",
                "ended_at": "2024-01-20T10:15:00Z",
                "status": "completed",
                "platform": "web",
                "device": "desktop"
            }
        }
    )

    id: str = Field(
        ...,
        description="Unique identifier của session"
    )

    user_id: str = Field(
        ...,
        description="ID của user thực hiện đánh giá"
    )

    started_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm bắt đầu phiên đánh giá"
    )

    ended_at: Optional[datetime] = Field(
        default=None,
        description="Thời điểm kết thúc phiên đánh giá"
    )

    status: Literal["pending", "in_progress", "completed", "cancelled"] = Field(
        default="pending",
        description="Trạng thái phiên: pending, in_progress, completed, cancelled"
    )

    platform: Optional[str] = Field(
        default=None,
        description="Nền tảng thực hiện: web, mobile, desktop"
    )

    device: Optional[str] = Field(
        default=None,
        description="Thiết bị: desktop, tablet, mobile"
    )
