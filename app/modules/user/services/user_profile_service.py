"""
==============================================================
File: user_profile_service.py

User Profile Service - Business logic cho Profile operations.

Luu y: Password va email duoc Firebase Auth quan ly phia client.
Server chi luu profile metadata (full_name, avatar, gender, ...).
==============================================================
"""

import re
from datetime import datetime
from typing import Optional

from app.modules.user.repositories.user_profile_repository import (
    UserProfileRepository,
    get_profile_repository,
)


class UserProfileServiceError(Exception):
    """Custom exception for UserProfileService errors."""
    pass


class UserProfileService:
    """Service cho User Profile operations."""

    def __init__(self, profile_repo: Optional[UserProfileRepository] = None):
        self.profile_repo = profile_repo or get_profile_repository()

    def get_profile(self, uid: str) -> Optional[dict]:
        """Lay profile hien tai theo Firebase UID. Tao moi neu chua co."""
        profile = self.profile_repo.get_profile(uid)
        if profile is None:
            # Lazy create khi user lan dau goi /me
            now = datetime.utcnow().isoformat() + "Z"
            new_profile = {
                "uid": uid,
                "created_at": now,
                "updated_at": now,
            }
            self.profile_repo.create_profile(uid, new_profile)
            return new_profile
        return profile

    def update_profile(self, uid: str, req: "UpdateProfileRequest") -> dict:
        """Cap nhat profile."""
        update_data = {}

        if req.full_name is not None:
            update_data["full_name"] = req.full_name

        if req.avatar is not None:
            update_data["avatar"] = req.avatar

        if req.gender is not None:
            update_data["gender"] = req.gender

        if req.birthday is not None:
            update_data["birthday"] = req.birthday

        if req.phone is not None:
            phone_clean = req.phone.replace(" ", "").replace("-", "")
            if not re.match(r"^\d{10}$", phone_clean):
                raise UserProfileServiceError("So dien thoai phai co 10 so")
            update_data["phone"] = phone_clean

        if update_data:
            self.profile_repo.update_profile(uid, update_data)

        return self.profile_repo.get_profile(uid) or {"uid": uid}

    def update_avatar(self, uid: str, avatar_url: str) -> dict:
        """Cap nhat avatar."""
        self.profile_repo.update_avatar(uid, avatar_url)
        return self.profile_repo.get_profile(uid) or {"uid": uid}


# Singleton instance
_profile_service: Optional[UserProfileService] = None


def get_profile_service() -> UserProfileService:
    """Lay UserProfileService singleton."""
    global _profile_service
    if _profile_service is None:
        _profile_service = UserProfileService()
    return _profile_service
