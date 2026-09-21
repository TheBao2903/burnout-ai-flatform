"""
==============================================================
File: deps.py

Dependencies - FastAPI dependencies dung chung.

get_current_user() verify JWT HS256 (custom auth).
==============================================================
"""

import logging
from typing import Optional

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.modules.auth.services.auth_service import AuthError, get_auth_service

logger = logging.getLogger("burnout.deps")

_security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_security),
) -> dict:
    """
    Verify JWT, tra dict user info dang chuan hoa.

    Returns:
        Dict:
            {
                "uid": str,
                "username": str,
                "email": None,
                "name": str,
                "picture": None,
                "email_verified": False,
            }
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    svc = get_auth_service()
    try:
        user = svc.get_current_user(credentials.credentials)
    except AuthError as exc:
        logger.warning("Auth failed: %s", exc)
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
