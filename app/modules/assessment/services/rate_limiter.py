"""
==============================================================
File: rate_limiter.py

RateLimiter - Firestore-based rate limiting cho AI API calls.

Cơ chế:
- Per-user quota: limit AI calls per user per day
- Global quota: limit total AI calls per hour
- Atomic increments với Firestore
- Fail-soft: nếu Firestore lỗi → cho đi qua ( không block user)

Usage:
    rate_limiter = RateLimiter()

    # Check before API call
    result = rate_limiter.check("user_123")
    if not result["allowed"]:
        raise QuotaExceededError(result["reason"])

    # After successful API call
    rate_limiter.record("user_123")

==============================================================
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from google.cloud import firestore

from app.core.firebase import get_firebase
from app.core.settings import get_settings

logger = logging.getLogger("burnout.rate_limiter")


class QuotaExceededError(Exception):
    """Exception khi quota bị exceeded."""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class RateLimiter:
    """Rate limiter cho AI API calls."""

    COLLECTION_NAME = "rate_limits"

    def __init__(self):
        """Init rate limiter với config từ settings (env)."""
        settings = get_settings().rate_limit
        self.db = get_firebase().db
        self.collection = self.db.collection(self.COLLECTION_NAME)
        self.user_daily_limit = settings.user_daily_limit
        self.global_hourly_limit = settings.global_hourly_limit

    # ==========================================
    # Key Generation
    # ==========================================

    @staticmethod
    def _user_key(user_id: str, date: datetime) -> str:
        """Generate rate limit key cho user."""
        return f"user:{user_id}:{date.strftime('%Y-%m-%d')}"

    @staticmethod
    def _global_key(date: datetime) -> str:
        """Generate rate limit key cho global."""
        return f"global:{date.strftime('%Y-%m-%dT%H:00')}"

    # ==========================================
    # Check Quota
    # ==========================================

    def check(self, user_id: str) -> Dict[str, Any]:
        """Kiểm tra xem user có được phép call AI không.

        Args:
            user_id: Firebase uid

        Returns:
            Dict với:
            - allowed: bool
            - reason: str (nếu not allowed)
            - user_count: int (số calls của user hôm nay)
            - global_count: int (số calls global giờ này)
            - user_remaining: int
            - global_remaining: int
            - retry_after: int (seconds, nếu not allowed)
        """
        now = datetime.utcnow()
        user_key = self._user_key(user_id, now)
        global_key = self._global_key(now)

        try:
            # Get both counters atomically
            user_doc = self.collection.document(user_key).get()
            global_doc = self.collection.document(global_key).get()

            user_data = user_doc.to_dict() or {}
            global_data = global_doc.to_dict() or {}

            user_count = user_data.get("count", 0)
            global_count = global_data.get("count", 0)

            # Check user quota
            user_allowed = user_count < self.user_daily_limit
            user_remaining = max(0, self.user_daily_limit - user_count)

            # Check global quota
            global_allowed = global_count < self.global_hourly_limit
            global_remaining = max(0, self.global_hourly_limit - global_count)

            # Calculate retry_after
            retry_after = None
            if not user_allowed:
                # Reset at midnight
                tomorrow = (now + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                retry_after = int((tomorrow - now).total_seconds())
            elif not global_allowed:
                # Reset at next hour
                next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                retry_after = int((next_hour - now).total_seconds())

            allowed = user_allowed and global_allowed
            reason = None
            if not allowed:
                if not user_allowed:
                    reason = f"User daily quota exceeded ({user_count}/{self.user_daily_limit})"
                else:
                    reason = f"Global hourly quota exceeded ({global_count}/{self.global_hourly_limit})"

            return {
                "allowed": allowed,
                "reason": reason,
                "user_count": user_count,
                "global_count": global_count,
                "user_remaining": user_remaining,
                "global_remaining": global_remaining,
                "retry_after": retry_after,
            }

        except Exception as exc:
            logger.warning("Rate limit check failed (allowing): %s", exc)
            # Fail-soft: cho đi qua nếu Firestore lỗi
            return {
                "allowed": True,
                "reason": None,
                "user_count": 0,
                "global_count": 0,
                "user_remaining": self.user_daily_limit,
                "global_remaining": self.global_hourly_limit,
                "retry_after": None,
                "error": str(exc),
            }

    # ==========================================
    # Record Call
    # ==========================================

    def record(self, user_id: str) -> Dict[str, Any]:
        """Ghi nhận một AI call thành công.

        Atomic increment cả user counter và global counter.

        Args:
            user_id: Firebase uid

        Returns:
            Updated quota info
        """
        now = datetime.utcnow()
        user_key = self._user_key(user_id, now)
        global_key = self._global_key(now)

        try:
            # Atomic increment both counters
            batch = self.db.batch()

            # User counter (expires at end of day + 1 hour buffer)
            user_ref = self.collection.document(user_key)
            batch.set(
                user_ref,
                {
                    "type": "user",
                    "user_id": user_id,
                    "count": firestore.Increment(1),
                    "date": now.strftime("%Y-%m-%d"),
                    "created_at": firestore.SERVER_TIMESTAMP,
                    "expires_at": firestore.Timestamp(
                        datetime.utcnow() + timedelta(hours=25)
                    ),
                },
                merge=True,
            )

            # Global counter (expires at end of hour + 1 hour buffer)
            global_ref = self.collection.document(global_key)
            batch.set(
                global_ref,
                {
                    "type": "global",
                    "count": firestore.Increment(1),
                    "hour": now.strftime("%Y-%m-%dT%H:00"),
                    "created_at": firestore.SERVER_TIMESTAMP,
                    "expires_at": firestore.Timestamp(
                        datetime.utcnow() + timedelta(hours=2)
                    ),
                },
                merge=True,
            )

            batch.commit()

            logger.debug(
                "Recorded AI call for user %s (user_key=%s, global_key=%s)",
                user_id, user_key, global_key,
            )

            return self.check(user_id)

        except Exception as exc:
            logger.warning("Rate limit record failed (non-critical): %s", exc)
            return {
                "allowed": True,
                "error": str(exc),
            }

    # ==========================================
    # Cleanup
    # ==========================================

    def cleanup_expired(self, dry_run: bool = False) -> int:
        """Xóa các rate limit entries đã hết hạn.

        Args:
            dry_run: True = chỉ đếm, không xóa

        Returns:
            Số entries đã/xóa
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=48)  # Xóa entries cũ hơn 48h
        count = 0

        try:
            docs = (
                self.collection
                .where("expires_at", "<", cutoff)
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
                logger.info("%s %d expired rate limit entries", action, count)

        except Exception as exc:
            logger.warning("Rate limit cleanup failed: %s", exc)

        return count

    # ==========================================
    # Stats
    # ==========================================

    def get_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Lấy rate limit statistics.

        Args:
            user_id: Optional user ID (nếu muốn xem chi tiết user)

        Returns:
            Dict với quota info
        """
        try:
            if user_id:
                user_key = self._user_key(user_id, datetime.utcnow())
                doc = self.collection.document(user_key).get()
                user_data = doc.to_dict() or {}
                user_count = user_data.get("count", 0)
            else:
                user_count = 0

            global_key = self._global_key(datetime.utcnow())
            doc = self.collection.document(global_key).get()
            global_data = doc.to_dict() or {}
            global_count = global_data.get("count", 0)

            return {
                "user_daily_limit": self.user_daily_limit,
                "user_today_count": user_count,
                "user_remaining": max(0, self.user_daily_limit - user_count),
                "global_hourly_limit": self.global_hourly_limit,
                "global_this_hour_count": global_count,
                "global_remaining": max(0, self.global_hourly_limit - global_count),
            }

        except Exception as exc:
            logger.warning("Rate limit stats failed: %s", exc)
            return {
                "error": str(exc),
            }


# ==========================================
# Singleton
# ==========================================

_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Lay RateLimiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
