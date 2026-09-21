"""
==============================================================
Module: Storage

Chuc nang:
- Upload / xoa file tren Cloudflare R2 (S3-compatible).
- Dung noi bo cho EmotionService (luu anh khi user dong y).
- KHONG mount router, chi la internal service.
==============================================================
"""

from app.modules.storage.models.storage import StorageError, UploadResult
from app.modules.storage.services.r2_service import (
    R2Service,
    build_emotion_key,
    get_r2_service,
)

__all__ = [
    "R2Service",
    "StorageError",
    "UploadResult",
    "build_emotion_key",
    "get_r2_service",
]