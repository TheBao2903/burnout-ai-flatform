"""
==============================================================
File: assessment_cache_repository.py

AssessmentCacheRepository - Firestore-based semantic cache cho AI Assessment.

Thay vì dùng Qdrant (tốn thêm infra), dùng Firestore với:
- Deterministic hash key từ emotion snapshot
- TTL để tự động cleanup
- Batch operations

Cache hit rate tối ưu bằng cách round emotion values
trước khi hash (0.876543 → 0.88 → 0.9).

Logic:
1. Input: emotion_snapshot
2. Hash: deterministic key = hash(emotion_rounded)
3. Check: Firestore exact match
   - Hit → return cached result ✅
   - Miss → call AI → save to cache
==============================================================
"""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from google.cloud import firestore

from app.core.firebase import FirestoreCollections, get_firebase
from app.core.settings import get_settings

logger = logging.getLogger("burnout.assessment_cache")


class AssessmentCacheRepository:
    """Repository cho assessment cache (Firestore-based)."""

    COLLECTION_NAME = "assessment_cache"

    def __init__(self):
        """Init repository với config từ settings (env)."""
        settings = get_settings().cache
        self.db = get_firebase().db
        self.collection = self.db.collection(self.COLLECTION_NAME)
        self.ttl_days = settings.assessment_ttl_days

    # ==========================================
    # Hash Key Generation
    # ==========================================

    @staticmethod
    def generate_cache_key(
        emotions: Dict[str, float],
        dominant_emotion: str,
        confidence: float,
        round_precision: int = 1,
    ) -> str:
        """Generate deterministic cache key từ emotion data.

        Dùng rounded values để tăng cache hit rate:
        - happy=0.876543 → happy=0.9
        - sad=0.123456 → sad=0.1

        Args:
            emotions: Dict emotion scores
            dominant_emotion: Dominant emotion string
            confidence: Confidence score
            round_precision: Số chữ số thập phân (default 1 = 0.1)

        Returns:
            SHA256 hash string (32 chars prefix)
        """
        # Round all emotion values
        rounded = {
            k: round(v, round_precision)
            for k, v in emotions.items()
        }

        # Sort keys for deterministic ordering
        emotion_str = "|".join(f"{k}={rounded[k]}" for k in sorted(rounded.keys()))

        # Build deterministic input
        input_str = f"{dominant_emotion}|{confidence:.2f}|{emotion_str}"

        # SHA256 hash
        hash_obj = hashlib.sha256(input_str.encode("utf-8"))
        return hash_obj.hexdigest()[:32]  # 32 chars prefix

    # ==========================================
    # Cache Operations
    # ==========================================

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Lấy cached assessment result.

        Args:
            cache_key: Hash key generated from emotion data

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
                    expiry = cached_at + timedelta(days=self.ttl_days)
                    if datetime.utcnow() > expiry:
                        # Expired - delete and return None
                        self.collection.document(cache_key).delete()
                        logger.debug("Cache expired for key %s", cache_key)
                        return None

            # Cache hit
            logger.debug("Cache HIT for key %s", cache_key)

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
            logger.warning("Cache get failed: %s", exc)
            return None

    def save(
        self,
        cache_key: str,
        result: Dict[str, Any],
        emotions: Dict[str, float],
        dominant_emotion: str,
        confidence: float,
        user_id: Optional[str] = None,
    ) -> str:
        """Lưu assessment result vào cache.

        Args:
            cache_key: Hash key
            result: Assessment result dict
            emotions: Original emotion scores (for debugging)
            dominant_emotion: Dominant emotion
            confidence: Confidence score
            user_id: Optional user ID (for analytics)

        Returns:
            Cache key
        """
        try:
            now = datetime.utcnow()

            data = {
                "cache_key": cache_key,
                "result": result,
                # Store rounded values for debugging
                "emotions_snapshot": {
                    k: round(v, 1) for k, v in emotions.items()
                },
                "dominant_emotion": dominant_emotion,
                "confidence": round(confidence, 2),
                # Stats
                "hit_count": 0,
                "created_at": firestore.SERVER_TIMESTAMP,
                "cached_at": now,
                "last_accessed": now,
                "ttl_days": self.ttl_days,
            }

            if user_id:
                data["user_id"] = user_id

            self.collection.document(cache_key).set(data)
            logger.info(
                "Cached assessment result (key=%s, dominant=%s, confidence=%.2f)",
                cache_key[:8], dominant_emotion, confidence,
            )
            return cache_key

        except Exception as exc:
            logger.warning("Cache save failed: %s", exc)
            return cache_key

    def delete(self, cache_key: str) -> bool:
        """Xóa một cache entry.

        Args:
            cache_key: Cache key

        Returns:
            True nếu xóa thành công
        """
        try:
            self.collection.document(cache_key).delete()
            logger.debug("Deleted cache entry %s", cache_key[:8])
            return True
        except Exception as exc:
            logger.warning("Cache delete failed: %s", exc)
            return False

    def delete_expired(self, dry_run: bool = False) -> int:
        """Xóa các cache entries đã hết hạn.

        Args:
            dry_run: True = chỉ đếm, không xóa

        Returns:
            Số entries đã/xóa
        """
        cutoff = datetime.utcnow() - timedelta(days=self.ttl_days)
        count = 0

        try:
            # Query expired entries
            docs = (
                self.collection
                .where("cached_at", "<", cutoff)
                .limit(500)  # Batch size
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
                logger.info("%s %d expired cache entries", action, count)

        except Exception as exc:
            logger.warning("Cache cleanup failed: %s", exc)

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

            # Calculate hit rate from recent entries
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
                "ttl_days": self.ttl_days,
                "collection": self.COLLECTION_NAME,
            }

        except Exception as exc:
            logger.warning("Cache stats failed: %s", exc)
            return {
                "total_entries": 0,
                "recent_avg_hits": 0,
                "ttl_days": self.ttl_days,
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

            logger.warning("Cleared %d cache entries", count)

        except Exception as exc:
            logger.warning("Cache clear failed: %s", exc)

        return count


# ==========================================
# Singleton
# ==========================================

_cache_repo: Optional[AssessmentCacheRepository] = None


def get_assessment_cache_repository() -> AssessmentCacheRepository:
    """Lay AssessmentCacheRepository singleton."""
    global _cache_repo
    if _cache_repo is None:
        _cache_repo = AssessmentCacheRepository()
    return _cache_repo
