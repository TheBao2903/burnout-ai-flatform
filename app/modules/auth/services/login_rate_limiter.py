"""
==============================================================
File: login_rate_limiter.py

LoginRateLimiter - In-memory rate limiter cho login attempts.

Logic:
- Track số lần login thất bại theo username/IP
- Lock 60s khi sai >= 3 lần liên tiếp
- Reset count khi login thành công
- Auto-cleanup expired entries

Usage:
    limiter = LoginRateLimiter()
    if limiter.is_locked(username):
        return {"error": "locked", "wait_seconds": limiter.get_wait_seconds(username)}

    # Xử lý login...
    if failed:
        limiter.record_failure(username)
    else:
        limiter.record_success(username)
==============================================================
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger("burnout.auth.ratelimit")


@dataclass
class LoginAttempt:
    """Track login attempts cho một username/IP."""
    count: int = 0
    first_failure: float = field(default_factory=time.time)
    locked_until: Optional[float] = None

    def is_locked(self, lock_seconds: int = 60) -> bool:
        if self.locked_until is None:
            return False
        return time.time() < self.locked_until

    def get_wait_seconds(self) -> int:
        if self.locked_until is None:
            return 0
        remaining = self.locked_until - time.time()
        return max(0, int(remaining))


class LoginRateLimiter:
    """
    In-memory rate limiter cho login.

    Config:
        - max_attempts: Số lần thất bại trước khi lock (default: 3)
        - lock_seconds: Thời gian lock (default: 60)
        - cleanup_interval: Dọn dẹp entries cũ sau (default: 300s)
    """

    LOCK_THRESHOLD = 3  # Số lần sai trước khi lock
    LOCK_DURATION = 60  # Giây bị lock
    CLEANUP_INTERVAL = 300  # Dọn dẹp sau 5 phút

    def __init__(self):
        self._attempts: Dict[str, LoginAttempt] = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.time()

    def _cleanup_expired(self) -> None:
        """Dọn dẹp entries đã hết hạn."""
        now = time.time()
        if now - self._last_cleanup < self.CLEANUP_INTERVAL:
            return

        with self._lock:
            expired_keys = [
                key for key, attempt in self._attempts.items()
                if attempt.count == 0 or (attempt.locked_until and now > attempt.locked_until)
            ]
            for key in expired_keys:
                del self._attempts[key]

        self._last_cleanup = now

    def is_locked(self, identifier: str) -> bool:
        """Kiểm tra identifier có bị lock không."""
        self._cleanup_expired()

        with self._lock:
            attempt = self._attempts.get(identifier)
            if attempt is None:
                return False
            return attempt.is_locked(self.LOCK_DURATION)

    def get_wait_seconds(self, identifier: str) -> int:
        """Lấy số giây còn phải đợi."""
        with self._lock:
            attempt = self._attempts.get(identifier)
            if attempt is None:
                return 0
            return attempt.get_wait_seconds()

    def get_remaining_attempts(self, identifier: str) -> int:
        """Lấy số lần thử còn lại trước khi lock."""
        with self._lock:
            attempt = self._attempts.get(identifier)
            if attempt is None:
                return self.LOCK_THRESHOLD
            if attempt.is_locked(self.LOCK_DURATION):
                return 0
            return max(0, self.LOCK_THRESHOLD - attempt.count)

    def record_failure(self, identifier: str) -> Dict[str, any]:
        """Ghi nhận login thất bại.

        Returns:
            dict với thông tin:
            - locked: bool - có bị lock không
            - attempts: int - số lần đã thử
            - remaining: int - số lần còn lại
            - wait_seconds: int - số giây phải đợi (nếu locked)
        """
        self._cleanup_expired()

        with self._lock:
            if identifier not in self._attempts:
                self._attempts[identifier] = LoginAttempt()

            attempt = self._attempts[identifier]

            # Nếu đang lock, không tăng count
            if attempt.is_locked(self.LOCK_DURATION):
                return {
                    "locked": True,
                    "attempts": attempt.count,
                    "remaining": 0,
                    "wait_seconds": attempt.get_wait_seconds(),
                }

            # Tăng số lần thất bại
            attempt.count += 1

            # Kiểm tra nếu đạt ngưỡng lock
            if attempt.count >= self.LOCK_THRESHOLD:
                attempt.locked_until = time.time() + self.LOCK_DURATION
                logger.warning(
                    "Login locked for %s after %d attempts, locked until %s",
                    identifier,
                    attempt.count,
                    attempt.locked_until,
                )
                return {
                    "locked": True,
                    "attempts": attempt.count,
                    "remaining": 0,
                    "wait_seconds": self.LOCK_DURATION,
                }

            remaining = self.LOCK_THRESHOLD - attempt.count
            logger.info(
                "Login failed for %s, attempts=%d, remaining=%d",
                identifier,
                attempt.count,
                remaining,
            )
            return {
                "locked": False,
                "attempts": attempt.count,
                "remaining": remaining,
                "wait_seconds": 0,
            }

    def record_success(self, identifier: str) -> None:
        """Ghi nhận login thành công, reset counter."""
        with self._lock:
            if identifier in self._attempts:
                # Reset hoặc xóa entry
                logger.info("Login success for %s, resetting attempts", identifier)
                del self._attempts[identifier]

    def get_status(self, identifier: str) -> Dict[str, any]:
        """Lấy trạng thái hiện tại của identifier."""
        with self._lock:
            attempt = self._attempts.get(identifier)
            if attempt is None:
                return {
                    "locked": False,
                    "attempts": 0,
                    "remaining": self.LOCK_THRESHOLD,
                    "wait_seconds": 0,
                }

            return {
                "locked": attempt.is_locked(self.LOCK_DURATION),
                "attempts": attempt.count,
                "remaining": max(0, self.LOCK_THRESHOLD - attempt.count) if not attempt.is_locked(self.LOCK_DURATION) else 0,
                "wait_seconds": attempt.get_wait_seconds(),
            }


# ==========================================
# Singleton
# ==========================================

_login_rate_limiter: Optional[LoginRateLimiter] = None


def get_login_rate_limiter() -> LoginRateLimiter:
    """Lấy LoginRateLimiter singleton."""
    global _login_rate_limiter
    if _login_rate_limiter is None:
        _login_rate_limiter = LoginRateLimiter()
    return _login_rate_limiter
