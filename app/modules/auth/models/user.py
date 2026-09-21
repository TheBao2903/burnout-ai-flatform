"""
==============================================================
File: user.py

Models cho auth: User.

User có 2 cach tao:
- Self signup (POST /api/auth/signup): bat buoc username, password, email.
- Admin create (POST /api/auth/admin/create-user): chi bat buoc
  username, password, full_name. Email/phone optional.
==============================================================
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ==========================================
# User (internal)
# ==========================================

class User(BaseModel):
    """User record luu trong Firestore."""

    id: str
    username: str
    email: Optional[str] = None
    password_hash: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: Literal["user", "admin"] = "user"
    is_active: bool = True
    email_verified: bool = False
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None


# ==========================================
# UserPublic (response)
# ==========================================

class UserPublic(BaseModel):
    """User info tra ve client (KHONG bao gom password_hash)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "abc123",
                "username": "admin",
                "email": None,
                "full_name": "Administrator",
                "phone": None,
                "avatar_url": None,
                "role": "admin",
                "is_active": True,
                "email_verified": False,
                "created_at": "2026-08-03T10:00:00Z",
                "updated_at": "2026-08-03T10:15:00Z",
                "last_login_at": "2026-08-03T10:15:00Z",
            }
        }
    )

    id: str
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    is_active: bool
    email_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None


# ==========================================
# Self signup (email REQUIRED)
# ==========================================

class SignupRequest(BaseModel):
    """POST /api/auth/signup body (user tu dang ky).

    Email la bat buoc (de verify + reset password).
    """

    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)
    email: EmailStr = Field(..., description="Email bat buoc de verify")
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=100)


# ==========================================
# Bootstrap first admin (one-time)
# ==========================================

class BootstrapAdminRequest(BaseModel):
    """POST /api/auth/bootstrap-admin body.

    Chi dung duoc mot lan (khi DB chua co admin). Sau do admin moi
    phai tao qua /admin/create-user voi admin token.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "admin",
                "password": "ChangeMe123!",
                "full_name": "System Administrator",
                "email": "admin@burnout.local",
            }
        }
    )

    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr = Field(...)


# ==========================================
# Admin create-user (full_name REQUIRED, email/phone optional)
# ==========================================

class AdminCreateUserRequest(BaseModel):
    """POST /api/auth/admin/create-user body (admin tao nhanh).

    Email/phone KHONG bat buoc - admin co the tao account noi bo
    cho nhan vien chi can username, password, full_name.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "nhan_vien_01",
                "password": "TempPass123!",
                "full_name": "Nguyen Van A",
                "email": "nva@company.com",
                "phone": "+84987654321",
                "role": "user",
            }
        }
    )

    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=100, description="Ho ten day du (bat buoc)")
    email: Optional[EmailStr] = Field(default=None, description="Email (optional)")
    phone: Optional[str] = Field(default=None, min_length=8, max_length=20, description="Phone (optional)")
    role: Literal["user", "admin"] = Field(default="user", description="Mac dinh 'user'")


# ==========================================
# Update profile
# ==========================================

class UpdateProfileRequest(BaseModel):
    """PATCH /api/auth/me body — user update profile cua minh.

    Chi gui field muon doi; field None bo qua (giu nguyen gia tri cu).
    """

    full_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, min_length=8, max_length=20)
    avatar_url: Optional[str] = None


# ==========================================
# Login (van giu username/password)
# ==========================================

class LoginRequest(BaseModel):
    """POST /api/auth/login body."""

    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """POST /api/auth/login response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in_hours": 24,
                "refresh_token": "rt_abc123xyz...",
                "refresh_expires_in_days": 7,
                "user": {
                    "id": "abc123",
                    "username": "admin",
                    "email": None,
                    "full_name": "Administrator",
                    "role": "admin",
                    "is_active": True,
                },
            }
        }
    )

    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int
    refresh_token: str
    refresh_expires_in_days: int
    user: UserPublic


# ==========================================
# Refresh Token
# ==========================================

class RefreshTokenRequest(BaseModel):
    """POST /api/auth/refresh body."""

    refresh_token: str = Field(..., description="Refresh token nhận được từ login")


class RefreshTokenResponse(BaseModel):
    """POST /api/auth/refresh response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in_hours": 24,
                "refresh_token": "rt_def456uvw...",  # Token mới, token cũ bị revoke
                "refresh_expires_in_days": 7,
            }
        }
    )

    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int
    refresh_token: str
    refresh_expires_in_days: int