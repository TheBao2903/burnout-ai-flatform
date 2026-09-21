"""
==============================================================
File: user_profile_repository.py

Repository cho User Profile operations voi Firestore.
Document key = Firebase UID.
==============================================================
"""

from datetime import datetime
from typing import Optional

from app.core.firebase import get_firebase, FirestoreCollections


class UserProfileRepository:
    """Repository cho User Profile operations."""

    def __init__(self):
        self.db = get_firebase().db
        self.collection = self.db.collection(FirestoreCollections.USERS)

    def get_profile(self, uid: str) -> Optional[dict]:
        """Lay profile user theo Firebase UID."""
        doc = self.collection.document(uid).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def create_profile(self, uid: str, profile_data: dict) -> bool:
        """Tao moi profile doc."""
        self.collection.document(uid).set(profile_data)
        return True

    def update_profile(self, uid: str, update_data: dict) -> bool:
        """Cap nhat profile (merge)."""
        update_data["updated_at"] = datetime.utcnow()
        self.collection.document(uid).set(update_data, merge=True)
        return True

    def update_avatar(self, uid: str, avatar_url: str) -> bool:
        """Cap nhat avatar."""
        self.collection.document(uid).set(
            {
                "avatar": avatar_url,
                "updated_at": datetime.utcnow(),
            },
            merge=True,
        )
        return True


# Singleton instance
_profile_repo: Optional[UserProfileRepository] = None


def get_profile_repository() -> UserProfileRepository:
    """Lay UserProfileRepository singleton."""
    global _profile_repo
    if _profile_repo is None:
        _profile_repo = UserProfileRepository()
    return _profile_repo
