"""
==============================================================
File: notification.py

Notification Models.
==============================================================
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class Notification(BaseModel):
    """Mot thong bao gui den user."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "notif_xyz789",
                "user_id": "user_123",
                "title": "Nhac nho danh gia Burnout",
                "message": "Ban da 3 ngay chua danh gia...",
                "is_read": False,
                "type": "reminder",
                "created_at": "2024-01-20T09:00:00Z"
            }
        }
    )

    id: str = Field(..., description="Unique ID")
    user_id: str = Field(..., description="ID nguoi nhan")
    title: str = Field(..., description="Tieu de")
    message: str = Field(..., description="Noi dung")
    is_read: bool = Field(default=False, description="Da doc chua")
    type: Literal["reminder", "alert", "recommendation", "system"] = Field(default="system", description="Loai thong bao")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Thoi diem tao")
