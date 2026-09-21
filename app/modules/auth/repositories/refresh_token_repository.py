"""
==============================================================
File: refresh_token_repository.py

RefreshTokenRepository - CRUD refresh tokens trong Firestore.

Collection: "refresh_tokens"
Document id: token hash (để lookup nhanh)
Fields: user_id, token_hash, created_at, expires_at, revoked_at, replaced_by

Logic:
- Refresh token có expire = 7 ngày (configurable)
- Khi refresh: token cũ bị revoke, tạo token mới
- Token bị revoke khi: logout, refresh bằng token khác, hết hạn
==============================================================
"""

import logging
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from app.core.firebase import get_firebase

logger = logging.getLogger("burnout.refresh_token.repo")


class RefreshTokenRepository:
    """CRUD refresh tokens."""

    COLLECTION = "refresh_tokens"
    DEFAULT_EXPIRE_DAYS = 7

    def __init__(self, expire_days: int = DEFAULT_EXPIRE_DAYS):
        self.collection = get_firebase().db.collection(self.COLLECTION)
        self.expire_days = expire_days

    @staticmethod
    def _hash_token(token: str) -> str:
        """Hash token bằng SHA256 để lưu trữ an toàn."""
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def generate_token() -> str:
        """Generate random refresh token."""
        return secrets.token_urlsafe(64)

    def create(self, user_id: str) -> tuple[str, datetime]:
        """Tạo refresh token mới cho user.

        Revoke tất cả token cũ của user (single session - optional).

        Args:
            user_id: User ID.

        Returns:
            (token, expires_at).
        """
        token = self.generate_token()
        token_hash = self._hash_token(token)
        now = datetime.utcnow()
        expires_at = now + timedelta(days=self.expire_days)

        doc_ref = self.collection.document(token_hash)
        doc_ref.set({
            "user_id": user_id,
            "token_hash": token_hash,
            "created_at": now,
            "expires_at": expires_at,
            "revoked_at": None,
            "replaced_by": None,
        })

        logger.info("Refresh token created for user %s, expires %s", user_id, expires_at)
        return token, expires_at

    def verify(self, token: str) -> Optional[str]:
        """Verify refresh token và trả về user_id.

        Args:
            token: Refresh token.

        Returns:
            user_id nếu token hợp lệ, None nếu không.
        """
        token_hash = self._hash_token(token)
        doc = self.collection.document(token_hash).get()

        if not doc.exists:
            logger.warning("Refresh token not found")
            return None

        data = doc.to_dict()

        # Check revoked
        if data.get("revoked_at"):
            logger.warning("Refresh token was revoked")
            return None

        # Check expired
        expires_at = data.get("expires_at")
        if isinstance(expires_at, datetime) and expires_at < datetime.utcnow():
            logger.warning("Refresh token expired")
            return None

        return data.get("user_id")

    def revoke(self, token: str) -> bool:
        """Revoke một refresh token.

        Args:
            token: Refresh token.

        Returns:
            True nếu revoke thành công.
        """
        token_hash = self._hash_token(token)
        doc = self.collection.document(token_hash)

        if not doc.get().exists:
            return False

        doc.update({
            "revoked_at": datetime.utcnow(),
        })
        logger.info("Refresh token revoked: %s...", token_hash[:16])
        return True

    def revoke_all_for_user(self, user_id: str) -> int:
        """Revoke tất cả refresh tokens của user.

        Args:
            user_id: User ID.

        Returns:
            Số tokens đã revoke.
        """
        docs = self.collection.where("user_id", "==", user_id).stream()
        count = 0
        for doc in docs:
            if not doc.to_dict().get("revoked_at"):
                doc.reference.update({"revoked_at": datetime.utcnow()})
                count += 1

        if count:
            logger.info("Revoked %d refresh tokens for user %s", count, user_id)
        return count

    def rotate(self, old_token: str) -> Optional[tuple[str, datetime]]:
        """Rotate token: revoke cũ, tạo mới.

        Args:
            old_token: Token cũ.

        Returns:
            (new_token, expires_at) nếu thành công, None nếu fail.
        """
        user_id = self.verify(old_token)
        if not user_id:
            return None

        # Revoke old token
        self.revoke(old_token)

        # Create new token
        new_token, expires_at = self.create(user_id)
        return new_token, expires_at

    def cleanup_expired(self) -> int:
        """Xóa tokens đã hết hạn (housekeeping).

        Returns:
            Số tokens đã xóa.
        """
        now = datetime.utcnow()
        docs = self.collection.where("expires_at", "<", now).stream()
        count = 0
        for doc in docs:
            doc.reference.delete()
            count += 1

        if count:
            logger.info("Cleaned up %d expired refresh tokens", count)
        return count


# ==========================================
# Singleton
# ==========================================

_refresh_token_repo: Optional[RefreshTokenRepository] = None


def get_refresh_token_repository() -> RefreshTokenRepository:
    global _refresh_token_repo
    if _refresh_token_repo is None:
        _refresh_token_repo = RefreshTokenRepository()
    return _refresh_token_repo
