"""
==============================================================
File: chat_cache_repository.py

ChatCacheRepository - Firestore-based exact cache cho Chat Analysis.

Dùng SHA256 hash của normalized text làm cache key.
- Cùng text → cùng hash → cache hit
- Text được normalize trước khi hash (lowercase, strip whitespace)

Logic:
1. Input: raw text
2. Normalize: lowercase, strip, collapse whitespace
3. Hash: SHA256(normalized_text)
4. Check: Firestore exact match
   - Hit → return cached result ✅
   - Miss → call AI → save to cache
==============================================================
"""

import hashlib
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from google.cloud import firestore

from app.core.firebase import FirestoreCollections, get_firebase
from app.core.settings import get_settings

logger = logging.getLogger("burnout.chat_cache")


class ChatCacheRepository:
    """Repository cho chat analysis cache (Firestore-based)."""

    COLLECTION_NAME = "chat_cache"

    def __init__(self):
        """Init repository với config từ settings (env)."""
        settings = get_settings().cache
        self.db = get_firebase().db
        self.collection = self.db.collection(self.COLLECTION_NAME)
        self.ttl_hours = settings.chat_ttl_hours

    # ==========================================
    # Normalization & Hashing
    # ==========================================

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text để tăng cache hit rate.

        Rules:
        - Lowercase
        - Strip leading/trailing whitespace
        - Collapse multiple spaces to single space
        - Remove newlines (replace with space)
        - Remove special unicode chars (keep Vietnamese)

        Args:
            text: Raw input text

        Returns:
            Normalized text
        """
        if not text:
            return ""

        # Lowercase
        text = text.lower()

        # Replace newlines with space
        text = text.replace("\n", " ").replace("\r", " ")

        # Collapse multiple spaces to single space
        text = re.sub(r"\s+", " ", text)

        # Strip leading/trailing
        text = text.strip()

        return text

    @staticmethod
    def generate_cache_key(text: str) -> str:
        """Generate deterministic cache key từ text.

        Args:
            text: Raw input text

        Returns:
            SHA256 hash string (32 chars prefix)
        """
        normalized = ChatCacheRepository.normalize_text(text)
        if not normalized:
            # Return empty string hash for empty input
            return hashlib.sha256(b"").hexdigest()[:32]

        hash_obj = hashlib.sha256(normalized.encode("utf-8"))
        return hash_obj.hexdigest()[:32]

    # ==========================================
    # Cache Operations
    # ==========================================

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Lấy cached chat analysis result.

        Args:
            cache_key: Hash key generated from normalized text

        Returns:
            Cached result dict hoặc None nếu miss/expired
        """
        try:
            doc = self.collection.document(cache_key).get()

            if not doc.exists:
                return None

            data = doc.to_dict()
            if not data:
                return None

            # Check TTL
            cached_at = data.get("cached_at")
            if cached_at:
                if isinstance(cached_at, datetime):
                    expiry = cached_at + timedelta(hours=self.ttl_hours)
                    if datetime.utcnow() > expiry:
                        # Expired - delete and return None
                        self.collection.document(cache_key).delete()
                        logger.debug("Chat cache expired for key %s", cache_key[:8])
                        return None

            # Cache hit
            logger.debug("Chat cache HIT for key %s", cache_key[:8])

            # Increment hit counter (async-safe)
            try:
                self.collection.document(cache_key).update({
                    "hit_count": firestore.Increment(1),
                    "last_accessed": firestore.SERVER_TIMESTAMP,
                })
            except Exception:
                pass  # Non-critical

            return data.get("result")

        except Exception as exc:
            logger.warning("Chat cache get failed: %s", exc)
            return None

    def get_by_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Convenience method - get cached result by raw text.

        Args:
            text: Raw input text

        Returns:
            Cached result dict hoặc None
        """
        cache_key = self.generate_cache_key(text)
        return self.get(cache_key)

    def save(
        self,
        cache_key: str,
        result: Dict[str, Any],
        original_text: str,
        normalized_text: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """Lưu chat analysis result vào cache.

        Args:
            cache_key: Hash key
            result: Analysis result dict
            original_text: Original raw text (for debugging)
            normalized_text: Normalized text (optional, will compute if not provided)
            user_id: Optional user ID (for analytics)

        Returns:
            Cache key
        """
        try:
            now = datetime.utcnow()
            norm_text = normalized_text or self.normalize_text(original_text)

            data = {
                "cache_key": cache_key,
                "result": result,
                # Store text for debugging
                "original_text_length": len(original_text),
                "normalized_text": norm_text,
                # Stats
                "hit_count": 0,
                "created_at": firestore.SERVER_TIMESTAMP,
                "cached_at": now,
                "last_accessed": now,
                "ttl_hours": self.ttl_hours,
            }

            if user_id:
                data["user_id"] = user_id

            self.collection.document(cache_key).set(data)
            logger.info(
                "Cached chat analysis (key=%s, text_len=%d)",
                cache_key[:8], len(original_text),
            )
            return cache_key

        except Exception as exc:
            logger.warning("Chat cache save failed: %s", exc)
            return cache_key

    def save_by_text(
        self,
        text: str,
        result: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> str:
        """Convenience method - save result with auto-generated key.

        Args:
            text: Raw input text
            result: Analysis result dict
            user_id: Optional user ID

        Returns:
            Cache key
        """
        cache_key = self.generate_cache_key(text)
        return self.save(cache_key, result, text, user_id=user_id)

    def delete(self, cache_key: str) -> bool:
        """Xóa một cache entry.

        Args:
            cache_key: Cache key

        Returns:
            True nếu xóa thành công
        """
        try:
            self.collection.document(cache_key).delete()
            logger.debug("Deleted chat cache entry %s", cache_key[:8])
            return True
        except Exception as exc:
            logger.warning("Chat cache delete failed: %s", exc)
            return False

    def delete_expired(self, dry_run: bool = False) -> int:
        """Xóa các cache entries đã hết hạn.

        Args:
            dry_run: True = chỉ đếm, không xóa

        Returns:
            Số entries đã/xóa
        """
        cutoff = datetime.utcnow() - timedelta(hours=self.ttl_hours)
        count = 0

        try:
            docs = (
                self.collection
                .where("cached_at", "<", cutoff)
                .limit(500)
                .stream()
            )

            for doc in docs:
                if dry_run:
                    count += 1
                else:
                    doc.reference.delete()
                    count += 1

            if count:
                action = "Would delete" if dry_run else "Deleted"
                logger.info("%s %d expired chat cache entries", action, count)

        except Exception as exc:
            logger.warning("Chat cache cleanup failed: %s", exc)

        return count

    # ==========================================
    # Analytics
    # ==========================================

    def get_stats(self) -> Dict[str, Any]:
        """Lấy cache statistics.

        Returns:
            Dict với hit rate, size, etc.
        """
        try:
            total_docs = sum(1 for _ in self.collection.limit(10000).stream())

            total_hits = 0
            recent_count = 0
            for doc in self.collection.limit(100).stream():
                data = doc.to_dict()
                if data:
                    total_hits += data.get("hit_count", 0)
                    recent_count += 1

            avg_hits = total_hits / recent_count if recent_count > 0 else 0

            return {
                "total_entries": total_docs,
                "recent_avg_hits": round(avg_hits, 2),
                "ttl_hours": self.ttl_hours,
                "collection": self.COLLECTION_NAME,
            }

        except Exception as exc:
            logger.warning("Chat cache stats failed: %s", exc)
            return {
                "total_entries": 0,
                "recent_avg_hits": 0,
                "ttl_hours": self.ttl_hours,
                "error": str(exc),
            }

    def clear_all(self) -> int:
        """Xóa toàn bộ cache (dùng cho testing/admin).

        WARNING: destructive operation!

        Returns:
            Số entries đã xóa
        """
        count = 0
        try:
            docs = self.collection.limit(1000).stream()
            for doc in docs:
                doc.reference.delete()
                count += 1

            logger.warning("Cleared %d chat cache entries", count)

        except Exception as exc:
            logger.warning("Chat cache clear failed: %s", exc)

        return count


# ==========================================
# Singleton
# ==========================================

_chat_cache_repo: Optional[ChatCacheRepository] = None


def get_chat_cache_repository() -> ChatCacheRepository:
    """Lay ChatCacheRepository singleton."""
    global _chat_cache_repo
    if _chat_cache_repo is None:
        _chat_cache_repo = ChatCacheRepository()
    return _chat_cache_repo
