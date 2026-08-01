"""
==============================================================
File: user.py

Chức năng:
- Định nghĩa model User - đại diện cho người dùng cuối.
- Hoàn toàn độc lập với Database (không dùng Firestore model).
- Phục vụ Business Logic và API Layer.
- Có thể thay đổi Database mà không ảnh hưởng đến model này.

Được sử dụng tại:
- API Layer (request/response)
- Service Layer (truyền dữ liệu)
- Repository Layer (convert giữa DB model và domain model)

Luồng dữ liệu:
User Input → API → User (Domain Model) → Service → Repository → Database
==============================================================
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class User(BaseModel):
    """
    Domain Model cho người dùng.

    Đại diện cho user trong toàn bộ hệ thống.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "user_123",
                "full_name": "Nguyễn Văn A",
                "email": "nguyenvana@example.com",
                "avatar": "https://storage.example.com/avatars/user_123.jpg",
                "gender": "male",
                "birthday": "1995-03-15",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-20T14:45:00Z",
            }
        }
    )

    id: str = Field(
        ...,
        description="Unique identifier của user"
    )

    full_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Họ và tên đầy đủ của người dùng"
    )

    email: str = Field(
        ...,
        description="Địa chỉ email của người dùng"
    )

    avatar: Optional[str] = Field(
        default=None,
        description="URL avatar của người dùng"
    )

    gender: Optional[str] = Field(
        default=None,
        description="Giới tính: male, female, other"
    )

    birthday: Optional[str] = Field(
        default=None,
        description="Ngày sinh theo định dạng YYYY-MM-DD"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm tạo user"
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        description="Thời điểm cập nhật gần nhất"
    )
