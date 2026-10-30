"""
Module quản lý xoay vòng API Keys và Models của Google Gemini (Dual Rotation Pool).
Hỗ trợ:
- Xoay vòng danh sách API Keys khi gặp 429 Rate Limit (RPM) hoặc Quota Exceeded (Daily RPD).
- Xoay vòng danh sách Models (3.8-flash -> 3.6-flash -> 3.5-flash-lite) khi model hiện tại quá tải.
- Thread-safe, có cơ chế cooldown thông minh.
"""

import logging
import threading
import time
from typing import Callable, Optional, Tuple, Any, List

from google import genai
from google.genai import types
from httpx import TimeoutException, TransportError
from app.core.settings import get_settings

logger = logging.getLogger("burnout.gemini.rotator")


class GeminiRotator:
    """Quản lý xoay vòng thông minh giữa các API Keys và Models."""

    def __init__(self):
        self._lock = threading.Lock()
        self._clients: dict[str, genai.Client] = {}
        # Cooldown: dict mapping (key, model) -> expired_timestamp
        self._cooldowns: dict[Tuple[str, str], float] = {}

    def _get_keys(self) -> List[str]:
        settings = get_settings().google_ai
        keys = settings.api_keys
        if not keys:
            # Fallback nếu api_keys rỗng
            raw = (settings.api_key or "").strip()
            return [raw] if raw else []
        return keys

    def _get_models(self) -> List[str]:
        settings = get_settings().google_ai
        return settings.model_pool

    def _get_client_for_key(self, api_key: str) -> genai.Client:
        if api_key not in self._clients:
            self._clients[api_key] = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    timeout=get_settings().google_ai.timeout_seconds * 1000,
                    # Let the pool handle retries instead of repeatedly waiting
                    # for the same unavailable model inside the SDK.
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
        return self._clients[api_key]

    def _is_cooling_down(self, key: str, model: str) -> bool:
        pair = (key, model)
        if pair not in self._cooldowns:
            return False
        if time.time() > self._cooldowns[pair]:
            # Đã hết thời gian cooldown, giải phóng
            del self._cooldowns[pair]
            return False
        return True

    def mark_exhausted(self, key: str, model: str, error_msg: str):
        """Đánh dấu một cặp (key, model) bị kiệt hạn mức và kích hoạt thời gian chờ."""
        err_str = str(error_msg).lower()
        now = time.time()

        if "perday" in err_str or "limit: 20" in err_str or "402" in err_str or "prepayment" in err_str:
            # Chạm trần ngày (Daily Quota) hoặc hết tiền Prepay (402) -> khóa 6 giờ
            duration = 6 * 3600
            reason = "Daily Quota / Prepayment Depleted (402/RPD)"
        elif any(token in err_str for token in ("500", "502", "503", "504", "unavailable", "high demand", "timeout", "deadline_exceeded")):
            # Quá tải tạm thời (503) -> khóa 30 giây
            duration = 30
            reason = "Transient model / transport failure"
        else:
            # Mặc định: Giới hạn phút (5 RPM) -> khóa 65 giây
            duration = 65
            reason = "Rate Limit (RPM)"

        with self._lock:
            self._cooldowns[(key, model)] = now + duration
            key_preview = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "key"
            logger.warning(
                "Gemini Rotator: Marked pair (%s, %s) as exhausted for %ds. Reason: %s",
                key_preview,
                model,
                duration,
                reason,
            )

    def execute_with_failover(
        self,
        call_fn: Callable[[genai.Client, str], Any],
    ) -> Tuple[Any, str, str]:
        """Thực thi hàm gọi Gemini qua pool Key và Model, tự động failover nếu lỗi.

        Returns:
            Tuple[result, model_used, key_used]
        """
        keys = self._get_keys()
        models = self._get_models()

        if not keys:
            raise RuntimeError("No Google API Key configured in settings/environment.")

        last_error = None

        # Duyệt theo thứ tự ưu tiên: Ưu tiên Model tốt nhất, thử hết các Keys của Model đó
        for model in models:
            for key in keys:
                if self._is_cooling_down(key, model):
                    continue

                client = self._get_client_for_key(key)
                try:
                    res = call_fn(client, model)
                    return res, model, key
                except Exception as exc:
                    last_error = exc
                    err_msg = str(exc)
                    key_preview = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "key"

                    # Kiểm tra xem có phải lỗi quota/rate-limit/503/402 cần rotate không
                    is_quota = (
                        "429" in err_msg
                        or "402" in err_msg
                        or "resource_exhausted" in err_msg.lower()
                        or "prepayment" in err_msg.lower()
                    )
                    status_code = getattr(exc, "code", None)
                    is_transient = (
                        status_code in (500, 502, 503, 504)
                        or isinstance(exc, (TimeoutError, TimeoutException, TransportError))
                        or any(token in err_msg.lower() for token in (
                            "500", "502", "503", "504", "unavailable",
                            "deadline_exceeded", "timed out", "timeout",
                        ))
                    )

                    if is_transient:
                        # Changing keys does not fix an overloaded model. Move
                        # straight to the next model and cool down this one.
                        logger.warning("Gemini model %s temporarily unavailable (%s); trying next model", model, type(exc).__name__)
                        for model_key in keys:
                            self.mark_exhausted(model_key, model, "503 transient model failure")
                        break

                    if is_quota:
                        logger.warning(
                            "Call failed with pair (%s, %s): %s. Rotating to next pair...",
                            key_preview,
                            model,
                            err_msg[:120],
                        )
                        self.mark_exhausted(key, model, err_msg)
                        continue
                    else:
                        # Lỗi nghiệp vụ khác (ví dụ prompt invalid, context window), không rotate mà raise
                        raise exc

        # Nếu đã thử qua tất cả các cặp khả dụng mà đều thất bại
        raise RuntimeError(
            f"All Gemini keys ({len(keys)}) and models ({len(models)}) in pool are currently exhausted or unavailable. Last error: {last_error}"
        )


# Singleton
_rotator_instance: Optional[GeminiRotator] = None


def get_gemini_rotator() -> GeminiRotator:
    """Lấy singleton GeminiRotator."""
    global _rotator_instance
    if _rotator_instance is None:
        _rotator_instance = GeminiRotator()
    return _rotator_instance

