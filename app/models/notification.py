"""
==============================================================
File: notification.py

Chức năng:
- Định nghĩa model Notification - thông báo gửi đến user.
- Phục vụ hệ thống reminder và alert.

Được sử dụng tại:
- Notification Service (tạo notification)
- API Layer (trả notification list)
- Push Notification (FCM, Email)
- In-App Notification

Luồng dữ liệu:
Trigger Event → Notification Service → Notification → Push/In-App → User
                        ↓
                Firebase FCM
==============================================================
"""

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field, ConfigDict


class Notification(BaseModel):
    """
    Domain Model cho một thông báo gửi đến user.

    Đại diện cho notification trong hệ thống.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "notif_xyz789",
                "user_id": "user_123",
                "title": "Nhắc nhở đánh giá Burnout",
                "message": "Bạn đã 3 ngày chưa đánh giá. Hãy dành 5 phút để kiểm tra mức độ burnout nhé!",
                "is_read": False,
                "type": "reminder",
                "created_at": "2024-01-20T09:00:00Z"
            }
        }
    )

    id: str = Field(
        ...,
        description="Unique identifier của notification"
    )

    user_id: str = Field(
        ...,
        description="ID của user nhận notification"
    )

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Tiêu đề notification"
    )

    message: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Nội dung notification"
    )

    is_read: bool = Field(
        default=False,
        description="Đã đọc hay chưa"
    )

    type: Literal["reminder", "alert", "recommendation", "system"] = Field(
        default="system",
        description="Loại notification"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm tạo notification"
    )
