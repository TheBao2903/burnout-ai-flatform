"""
==============================================================
File: auth.py

Routes cho auth:
- POST /api/auth/signup               (user tu dang ky, email REQUIRED)
- POST /api/auth/login                (login username/password)
- POST /api/auth/admin/create-user    (admin tao nhanh user)
- GET  /api/auth/me                   (verify token)
==============================================================
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.modules.auth.models.user import (
    AdminCreateUserRequest,
    BootstrapAdminRequest,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    SignupRequest,
    UpdateProfileRequest,
    UserPublic,
)
from app.modules.auth.services.auth_service import AuthError, AuthService, get_auth_service

logger = logging.getLogger("burnout.auth.routes")

router = APIRouter(prefix="/api/auth", tags=["Auth"])

_security = HTTPBearer(auto_error=False)


# ==========================================
# Dependencies
# ==========================================

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_security),
) -> dict:
    """Verify JWT, tra dict user info dang chuan hoa."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    svc = get_auth_service()
    try:
        user = svc.get_current_user(credentials.credentials)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    return {
        "uid": user.id,
        "username": user.username,
        "role": user.role,
        "email": user.email,
        "name": user.full_name or user.username,
        "picture": user.avatar_url,
        "email_verified": user.email_verified,
    }


async def require_admin(
    user: dict = Depends(get_current_user),
) -> dict:
    """Chi cho phep admin."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


# ==========================================
# Routes
# ==========================================

@router.post("/signup", response_model=LoginResponse)
async def signup(
    payload: SignupRequest,
    svc: AuthService = Depends(get_auth_service),
):
    """User tu dang ky. Email la BAT BUOC (de verify + reset password)."""
    try:
        return svc.signup(
            username=payload.username,
            password=payload.password,
            email=payload.email,
            full_name=payload.full_name,
        )
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/bootstrap-admin", response_model=LoginResponse)
async def bootstrap_admin(
    payload: BootstrapAdminRequest,
    svc: AuthService = Depends(get_auth_service),
):
    """Tao admin DAU TIEN trong he thong (khi DB rong).

    Chi thanh cong neu chua co admin nao. Sau do admin moi phai tao user
    qua /admin/create-user (can admin token).

    Day la pattern 'first user becomes admin' - khong can setup thu cong.
    """
    try:
        return svc.bootstrap_first_admin(
            username=payload.username,
            password=payload.password,
            full_name=payload.full_name,
            email=payload.email,
        )
    except AuthError as exc:
        # 409 neu admin da ton tai (khong 400)
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    svc: AuthService = Depends(get_auth_service),
):
    """Login bang username/password.

    Rate limit: 3 lần sai liên tiếp → khóa 60s.
    """
    try:
        return svc.login(payload.username, payload.password)
    except AuthError as exc:
        if exc.code == "account_locked":
            raise HTTPException(
                status_code=429,
                detail={
                    "message": exc.message,
                    "code": exc.code,
                    "wait_seconds": exc.wait_seconds,
                }
            )
        raise HTTPException(status_code=401, detail=str(exc))


@router.post("/admin/create-user", response_model=UserPublic)
async def admin_create_user(
    payload: AdminCreateUserRequest,
    admin: dict = Depends(require_admin),
    svc: AuthService = Depends(get_auth_service),
):
    """Admin tao user moi (chi admin moi goi duoc).

    - full_name BAT BUOC
    - email/phone optional
    - Admin co the tao tai khoan noi bo cho nhan vien khong co email.
    """
    logger.info("Admin %s creating user: %s", admin["username"], payload.username)
    try:
        return svc.admin_create_user(
            username=payload.username,
            password=payload.password,
            full_name=payload.full_name,
            email=payload.email,
            phone=payload.phone,
            role=payload.role,
        )
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class MeResponse(BaseModel):
    """Response cho GET /api/auth/me."""

    id: str
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    is_active: bool
    email_verified: bool
    created_at: str
    updated_at: str
    last_login_at: Optional[str] = None


@router.get("/me", response_model=MeResponse)
async def me(
    user: dict = Depends(get_current_user),
    svc: AuthService = Depends(get_auth_service),
):
    """Tra thong tin user hien tai (verify token, doc tu DB)."""
    try:
        db_user = svc.get_current_user_by_id(user["uid"])
    except AuthError:
        raise HTTPException(status_code=401, detail="User not found")

    return MeResponse(
        id=db_user.id,
        username=db_user.username,
        email=db_user.email,
        full_name=db_user.full_name,
        phone=db_user.phone,
        avatar_url=db_user.avatar_url,
        role=db_user.role,
        is_active=db_user.is_active,
        email_verified=db_user.email_verified,
        created_at=db_user.created_at.isoformat() + "Z" if db_user.created_at else "",
        updated_at=db_user.updated_at.isoformat() + "Z" if db_user.updated_at else "",
        last_login_at=db_user.last_login_at.isoformat() + "Z" if db_user.last_login_at else None,
    )


@router.patch("/me", response_model=UserPublic)
async def update_me(
    payload: UpdateProfileRequest,
    user: dict = Depends(get_current_user),
    svc: AuthService = Depends(get_auth_service),
):
    """User tu update profile cua minh.

    Body chi can gui field muon doi (cac field khac giu nguyen).
    Auto set updated_at = now.
    """
    try:
        return svc.update_profile(
            user_id=user["uid"],
            full_name=payload.full_name,
            email=str(payload.email) if payload.email else None,
            phone=payload.phone,
            avatar_url=payload.avatar_url,
        )
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    svc: AuthService = Depends(get_auth_service),
):
    """Refresh access token bằng refresh token.

    Token cũ bị revoke, tạo token mới (rotation).
    Client nên lưu refresh token mới vào storage.
    """
    try:
        access_token, new_refresh_token, expires_in_hours, refresh_expires_days = \
            svc.refresh_access_token(payload.refresh_token)

        return RefreshTokenResponse(
            access_token=access_token,
            expires_in_hours=expires_in_hours,
            refresh_token=new_refresh_token,
            refresh_expires_in_days=refresh_expires_days,
        )
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.post("/logout")
async def logout(
    payload: RefreshTokenRequest,
    svc: AuthService = Depends(get_auth_service),
):
    """Logout - revoke refresh token."""
    try:
        svc.revoke_refresh_token(payload.refresh_token)
        return {"message": "Logged out successfully"}
    except Exception as exc:
        logger.warning("Logout failed: %s", exc)
        return {"message": "Logged out"}  # Vẫn return success để client clear local state