"""
==============================================================
File: user_profile.py

Models cho User Profile operations.
==============================================================
"""

from enum import Enum
from typing import Optional, Literal

from pydantic import BaseModel, Field, ConfigDict


class Gender(str, Enum):
    """Gender options."""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class UpdateProfileRequest(BaseModel):
    """Request model cho cap nhat profile."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Nguyen Van A Updated",
                "avatar": "https://storage.example.com/avatars/new.jpg",
                "gender": "male",
                "birthday": "1995-03-15",
                "phone": "0912345678"
            }
        }
    )

    full_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Ho ten moi"
    )

    avatar: Optional[str] = Field(
        default=None,
        description="URL avatar moi"
    )

    gender: Optional[Literal["male", "female", "other"]] = Field(
        default=None,
        description="Gioi tinh"
    )

    birthday: Optional[str] = Field(
        default=None,
        description="Ngay sinh YYYY-MM-DD"
    )

    phone: Optional[str] = Field(
        default=None,
        description="So dien thoai (10 so)"
    )

    # Work baseline info (Thong tin cong viec nen - khong can nhap lai moi ngay)
    standard_working_hours_per_day: Optional[float] = Field(
        default=None, ge=1.0, le=24.0,
        description="So gio lam viec tieu chuan/ngay (mac dinh 8.0)"
    )
    work_days_per_week: Optional[int] = Field(
        default=None, ge=1, le=7,
        description="So ngay lam viec/tuan (mac dinh 5)"
    )
    average_overtime_hours_per_week: Optional[float] = Field(
        default=None, ge=0.0,
        description="So gio tang ca trung binh/tuan"
    )
    job_title: Optional[str] = Field(
        default=None, max_length=100,
        description="Chuc danh / Vi tri cong viec"
    )
    industry_code: Optional[str] = Field(
        default=None, max_length=50,
        description="Ma nhom nganh nghe (tech, sales, finance, ...)"
    )


class UserProfileResponse(BaseModel):
    """Response model cho profile."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "uid": "firebase_uid_abc123",
                "email": "johndoe@example.com",
                "full_name": "John Doe",
                "avatar": "https://storage.example.com/avatars/user_abc123.jpg",
                "gender": "male",
                "birthday": "1995-03-15",
                "phone": "0912345678",
                "email_verified": True,
                "standard_working_hours_per_day": 8.0,
                "work_days_per_week": 5,
                "average_overtime_hours_per_week": 2.5,
                "job_title": "Software Engineer",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
    )

    uid: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    avatar: Optional[str] = None
    gender: Optional[str] = None
    birthday: Optional[str] = None
    phone: Optional[str] = None
    email_verified: bool = False
    standard_working_hours_per_day: Optional[float] = 8.0
    work_days_per_week: Optional[int] = 5
    average_overtime_hours_per_week: Optional[float] = 0.0
    job_title: Optional[str] = None
    industry_code: Optional[str] = None
    created_at: Optional[str] = None
