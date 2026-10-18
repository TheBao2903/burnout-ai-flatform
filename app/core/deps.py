"""
==============================================================
File: deps.py

Dependencies - FastAPI dependencies dùng chung.

get_current_user() ưu tiên verify Firebase ID Token (Firebase Auth).
Fallback hỗ trợ legacy JWT cho kiểm thử nội bộ.
==============================================================
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as fb_auth

from app.modules.auth.repositories.user_repository import get_user_repository
from app.modules.auth.services.auth_service import AuthError, get_auth_service

logger = logging.getLogger("burnout.deps")

_security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_security),
) -> dict:
    """
    Verify Token (Firebase ID Token hoặc fallback JWT).
    Trả dict user info chuẩn hóa.

    Returns:
        Dict:
            {
                "uid": str,
                "username": str,
                "role": str,
                "email": Optional[str],
                "name": str,
                "picture": Optional[str],
                "email_verified": bool,
            }
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = credentials.credentials
    user_repo = get_user_repository()

    # 1. Thử xác thực qua Firebase Admin Auth (Firebase ID Token)
    try:
        # Cho phep sai lech dong ho toi da 60s (gioi han cua Firebase Admin SDK).
        # Neu lech nhieu hon (vi du may ao/docker khong sync NTP) thi can sync dong ho.
        decoded_token = fb_auth.verify_id_token(token, clock_skew_seconds=60)
        uid = decoded_token.get("uid")
        if uid:
            email = decoded_token.get("email")
            name = decoded_token.get("name") or (email.split("@")[0] if email else uid)
            picture = decoded_token.get("picture")
            email_verified = decoded_token.get("email_verified", False)
            claim_role = decoded_token.get("role")

            # Đồng bộ hoặc lấy thông tin người dùng từ Firestore
            user = user_repo.sync_firebase_user(
                uid=uid,
                email=email,
                full_name=name,
                picture=picture,
                email_verified=email_verified,
                role=claim_role,
            )

            if not user.is_active:
                raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa")

            return {
                "uid": user.id,
                "username": user.username,
                "role": user.role,
                "email": user.email,
                "name": user.full_name or user.username,
                "picture": user.avatar_url,
                "email_verified": user.email_verified,
            }
    except HTTPException:
        raise
    except Exception as fb_exc:
        # Log WARNING (không phải debug) để thấy lỗi Firebase thật sự
        logger.warning("Firebase token verification failed: %s", fb_exc)
        raise HTTPException(status_code=401, detail=f"Firebase token invalid: {fb_exc}")


async def require_admin(
    user: dict = Depends(get_current_user),
) -> dict:
    """Chỉ cho phép tài khoản có role admin."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user
