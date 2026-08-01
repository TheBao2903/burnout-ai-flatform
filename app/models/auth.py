"""
==============================================================
File: auth.py

Chức năng:
- Định nghĩa các models cho Authentication System.
- Hỗ trợ đăng nhập: Username/Password, Google OAuth.
- Quản lý Access Token và Blacklist.

Đơn giản, đủ dùng cho:
- Đăng nhập/đăng ký bằng username
- Đăng nhập bằng Google OAuth
- Xác thực Access Token
- Blacklist token vi phạm

Được sử dụng tại:
- Auth Service (xác thực)
- API Middleware (kiểm tra token)
- Login/Register endpoints
==============================================================
"""

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field, ConfigDict


# ==========================================
# AUTH PROVIDER
# ==========================================

class AuthProvider(BaseModel):
    """
    Model cho biết user đăng nhập bằng gì.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "provider": "google",
                "provider_user_id": "google_123456",
                "email": "user@gmail.com",
                "verified": True
            }
        }
    )

    provider: Literal["account", "google"] = Field(
        ...,
        description="Nguồn xác thực: account hoặc google"
    )

    provider_user_id: Optional[str] = Field(
        default=None,
        description="User ID từ provider (Google ID)"
    )

    email: Optional[str] = Field(
        default=None,
        description="Email từ provider"
    )

    verified: bool = Field(
        default=False,
        description="Email đã được xác thực chưa"
    )


# ==========================================
# AUTH CREDENTIALS (Register/Login)
# ==========================================

class RegisterRequest(BaseModel):
    """
    Request model cho đăng ký tài khoản.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "johndoe",
                "password": "securePassword123",
                "full_name": "Nguyễn Văn A",
                "email": "johndoe@example.com"
            }
        }
    )

    username: str = Field(
        ...,
        min_length=3,
        max_length=30,
        description="Username đăng nhập (unique)"
    )

    password: str = Field(
        ...,
        min_length=8,
        description="Password (đã hashed trong DB)"
    )

    full_name: str = Field(
        ...,
        description="Họ tên đầy đủ"
    )

    email: Optional[str] = Field(
        default=None,
        description="Email (optional, dùng để khôi phục tài khoản)"
    )


class LoginRequest(BaseModel):
    """
    Request model cho đăng nhập bằng username/password.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "johndoe",
                "password": "securePassword123"
            }
        }
    )

    username: str = Field(
        ...,
        description="Username đăng nhập"
    )

    password: str = Field(
        ...,
        description="Password"
    )


class GoogleLoginRequest(BaseModel):
    """
    Request model cho đăng nhập Google OAuth.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "google_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }
    )

    google_token: str = Field(
        ...,
        description="Token từ Google OAuth (ID Token)"
    )


# ==========================================
# AUTH RESPONSE
# ==========================================

class AuthResponse(BaseModel):
    """
    Response model sau khi đăng nhập/đăng ký thành công.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "user_123",
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 86400
            }
        }
    )

    user_id: str = Field(
        ...,
        description="ID của user vừa đăng nhập"
    )

    access_token: str = Field(
        ...,
        description="JWT Access Token"
    )

    token_type: str = Field(
        default="bearer",
        description="Loại token"
    )

    expires_in: int = Field(
        ...,
        description="Thời gian hết hạn token (seconds)"
    )


# ==========================================
# SESSION & TOKEN
# ==========================================

class AuthSession(BaseModel):
    """
    Model cho một phiên đăng nhập.
    Lưu thông tin session và access token.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "session_abc123",
                "user_id": "user_123",
                "access_token_hash": "hashed_token...",
                "token_type": "bearer",
                "expires_at": "2024-01-21T10:00:00Z",
                "created_at": "2024-01-20T10:00:00Z",
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0...",
                "is_active": True
            }
        }
    )

    id: str = Field(
        ...,
        description="Unique session ID"
    )

    user_id: str = Field(
        ...,
        description="User ID sở hữu session này"
    )

    access_token_hash: str = Field(
        ...,
        description="Hash của access token (không lưu token gốc)"
    )

    token_type: str = Field(
        default="bearer",
        description="Loại token"
    )

    expires_at: datetime = Field(
        ...,
        description="Thời điểm token hết hạn"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm tạo session"
    )

    ip_address: Optional[str] = Field(
        default=None,
        description="IP address khi đăng nhập"
    )

    user_agent: Optional[str] = Field(
        default=None,
        description="User Agent của browser/device"
    )

    is_active: bool = Field(
        default=True,
        description="Session còn active không"
    )


class TokenPayload(BaseModel):
    """
    Payload được encode trong JWT token.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sub": "user_123",
                "session_id": "session_abc123",
                "exp": 1705824000,
                "iat": 1705737600
            }
        }
    )

    sub: str = Field(
        ...,
        description="Subject - user_id"
    )

    session_id: str = Field(
        ...,
        description="Session ID tương ứng"
    )

    exp: int = Field(
        ...,
        description="Expiration time (timestamp)"
    )

    iat: int = Field(
        ...,
        description="Issued at time (timestamp)"
    )


# ==========================================
# BLACKLIST
# ==========================================

class TokenBlacklist(BaseModel):
    """
    Model cho token đã bị revoke/blacklist.
    Dùng để khóa user vi phạm hoặc logout.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "blacklist_001",
                "token_hash": "hashed_token...",
                "user_id": "user_123",
                "session_id": "session_abc123",
                "reason": "user_logout",
                "blacklisted_at": "2024-01-20T12:00:00Z",
                "expires_at": "2024-01-21T10:00:00Z"
            }
        }
    )

    id: str = Field(
        ...,
        description="Unique blacklist entry ID"
    )

    token_hash: str = Field(
        ...,
        description="Hash của token đã bị revoke"
    )

    user_id: str = Field(
        ...,
        description="User ID sở hữu token này"
    )

    session_id: str = Field(
        ...,
        description="Session ID tương ứng"
    )

    reason: Literal["user_logout", "user_banned", "admin_revoke", "token_expired", "policy_violation"] = Field(
        ...,
        description="Lý do token bị blacklist"
    )

    blacklisted_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm blacklist"
    )

    expires_at: datetime = Field(
        ...,
        description="Thời điểm blacklist hết hiệu lực (thường = token expiry)"
    )


class UserBanInfo(BaseModel):
    """
    Thông tin ban của user (vi phạm chính sách).
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "user_id": "user_123",
                "reason": "policy_violation",
                "description": "Vi phạm điều khoản sử dụng",
                "banned_at": "2024-01-20T12:00:00Z",
                "banned_until": None,
                "permanent": True,
                "banned_by": "admin_001"
            }
        }
    )

    user_id: str = Field(
        ...,
        description="User ID bị ban"
    )

    reason: Literal["spam", "abuse", "policy_violation", "fraud", "other"] = Field(
        ...,
        description="Lý do ban"
    )

    description: Optional[str] = Field(
        default=None,
        description="Mô tả chi tiết vi phạm"
    )

    banned_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm ban"
    )

    banned_until: Optional[datetime] = Field(
        default=None,
        description="Ban tạm thời đến thời điểm này"
    )

    permanent: bool = Field(
        default=False,
        description="Ban vĩnh viễn hay tạm thời"
    )

    banned_by: str = Field(
        ...,
        description="Admin ban user này"
    )
