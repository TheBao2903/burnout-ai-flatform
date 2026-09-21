"""
==============================================================
File: user_repository.py

UserRepository - CRUD users trong Firestore.

Collection: "users"
Document id: tu dong (Firestore doc id)
Fields: username (lowercase, unique), email, full_name, phone,
        avatar_url, role, is_active, email_verified,
        password_hash, created_at, last_login_at
==============================================================
"""

import logging
from datetime import datetime
from typing import Optional

from app.core.firebase import get_firebase
from app.modules.auth.models.user import User

logger = logging.getLogger("burnout.auth.repo")


class UserRepository:
    """CRUD users."""

    COLLECTION = "users"

    def __init__(self):
        self.collection = get_firebase().db.collection(self.COLLECTION)

    # -------------------------
    # Helpers
    # -------------------------

    @staticmethod
    def _doc_to_user(doc) -> User:
        data = doc.to_dict()
        created_at = data["created_at"]
        # Backward compat: neu doc cu chua updated_at, fallback = created_at
        updated_at = data.get("updated_at", created_at)
        return User(
            id=doc.id,
            username=data["username"],
            email=data.get("email"),
            password_hash=data["password_hash"],
            full_name=data.get("full_name"),
            phone=data.get("phone"),
            avatar_url=data.get("avatar_url"),
            role=data.get("role", "user"),
            is_active=data.get("is_active", True),
            email_verified=data.get("email_verified", False),
            created_at=created_at,
            updated_at=updated_at,
            last_login_at=data.get("last_login_at"),
        )

    # -------------------------
    # Queries
    # -------------------------

    def get_by_username(self, username: str) -> Optional[User]:
        """Lay user theo username (lowercase match)."""
        username = username.strip().lower()
        docs = self.collection.where("username", "==", username).limit(1).stream()
        for doc in docs:
            return self._doc_to_user(doc)
        return None

    def get_by_email(self, email: str) -> Optional[User]:
        """Lay user theo email (lowercase match)."""
        email = email.strip().lower()
        docs = self.collection.where("email", "==", email).limit(1).stream()
        for doc in docs:
            return self._doc_to_user(doc)
        return None

    def get_by_id(self, user_id: str) -> Optional[User]:
        """Lay user theo doc id."""
        doc = self.collection.document(user_id).get()
        if not doc.exists:
            return None
        return self._doc_to_user(doc)

    # -------------------------
    # Mutations
    # -------------------------

    def create(
        self,
        username: str,
        password_hash: str,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        phone: Optional[str] = None,
        role: str = "user",
        is_active: bool = True,
        email_verified: bool = False,
    ) -> User:
        """Tao user moi. Raise ValueError neu username/email trung."""
        username = username.strip().lower()
        if email:
            email = email.strip().lower()

        if self.get_by_username(username) is not None:
            raise ValueError(f"Username '{username}' da ton tai")
        if email and self.get_by_email(email) is not None:
            raise ValueError(f"Email '{email}' da ton tai")

        doc_ref = self.collection.document()
        now = datetime.utcnow()
        data = {
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "full_name": full_name,
            "phone": phone,
            "avatar_url": None,
            "role": role,
            "is_active": is_active,
            "email_verified": email_verified,
            "created_at": now,
            "updated_at": now,  # bang created_at luc tao
            "last_login_at": None,
        }
        doc_ref.set(data)
        logger.info("User created: %s (id=%s, role=%s)", username, doc_ref.id, role)
        return User(
            id=doc_ref.id,
            username=username,
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            phone=phone,
            avatar_url=None,
            role=role,
            is_active=is_active,
            email_verified=email_verified,
            created_at=now,
            updated_at=now,
            last_login_at=None,
        )

    def update_last_login(self, user_id: str) -> None:
        """Update last_login_at + auto-update updated_at."""
        now = datetime.utcnow()
        self.collection.document(user_id).update(
            {"last_login_at": now, "updated_at": now}
        )

    def update_user(
        self,
        user_id: str,
        full_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        avatar_url: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[User]:
        """Update mot so field cua user (KHONG update username/password_hash/role/email_verified).

        Chi update field khac None. Auto set updated_at = now.
        Tra User moi hoac None neu user khong ton tai.
        """
        update_data: dict = {"updated_at": datetime.utcnow()}
        if full_name is not None:
            update_data["full_name"] = full_name.strip()
        if email is not None:
            update_data["email"] = email.strip().lower()
        if phone is not None:
            update_data["phone"] = phone.strip()
        if avatar_url is not None:
            update_data["avatar_url"] = avatar_url
        if is_active is not None:
            update_data["is_active"] = is_active

        self.collection.document(user_id).update(update_data)
        logger.info("User updated: %s (fields=%s)", user_id, list(update_data.keys()))
        return self.get_by_id(user_id)

    def touch(self, user_id: str) -> None:
        """Chi update updated_at (khong doi field nao khac)."""
        self.collection.document(user_id).update(
            {"updated_at": datetime.utcnow()}
        )


# ==========================================
# Singleton
# ==========================================

_user_repo: Optional[UserRepository] = None


def get_user_repository() -> UserRepository:
    global _user_repo
    if _user_repo is None:
        _user_repo = UserRepository()
    return _user_repo