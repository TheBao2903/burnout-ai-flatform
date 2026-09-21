"""
==============================================================
File: profile.py

User Profile Routes - API endpoints cho profile operations.
Xac thuc bang Firebase ID token (xem app.core.deps).
==============================================================
"""

from fastapi import APIRouter, HTTPException, Depends

from app.core.deps import get_current_user
from app.modules.user.services.user_profile_service import (
    UserProfileService,
    UserProfileServiceError,
    get_profile_service,
)
from app.modules.user.models.user_profile import UpdateProfileRequest

router = APIRouter(prefix="/api/users", tags=["User Profile"])


def get_profile_svc() -> UserProfileService:
    """Dependency de lay UserProfileService."""
    return get_profile_service()


@router.get("/me", response_model=dict)
async def get_my_profile(
    user: dict = Depends(get_current_user),
    profile_service: UserProfileService = Depends(get_profile_svc),
):
    """Lay profile cua user hien tai (theo Firebase UID)."""
    uid = user["uid"]
    profile = profile_service.get_profile(uid)
    if not profile:
        raise HTTPException(status_code=404, detail="User khong tim thay")
    return profile


@router.put("/me", response_model=dict)
async def update_my_profile(
    req: UpdateProfileRequest,
    user: dict = Depends(get_current_user),
    profile_service: UserProfileService = Depends(get_profile_svc),
):
    """Cap nhat profile cua user hien tai."""
    try:
        profile = profile_service.update_profile(user["uid"], req)
        return profile
    except UserProfileServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/me/avatar", response_model=dict)
async def update_my_avatar(
    avatar_url: str,
    user: dict = Depends(get_current_user),
    profile_service: UserProfileService = Depends(get_profile_svc),
):
    """Cap nhat avatar cua user hien tai."""
    try:
        profile = profile_service.update_avatar(user["uid"], avatar_url)
        return profile
    except UserProfileServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))