"""
==============================================================
File: storage.py

Models cho Storage (Cloudflare R2).
==============================================================
"""

from pydantic import BaseModel, Field, ConfigDict


class UploadResult(BaseModel):
    """Ket qua upload file len R2."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key": "emotion/user_abc123/2026-08-03/20260803T093000123456.jpg",
                "url": "https://bucket.r2.dev/emotion/user_abc123/2026-08-03/20260803T093000123456.jpg",
                "bucket": "burnout-ai-images",
                "size_bytes": 123456,
                "content_type": "image/jpeg",
            }
        }
    )

    key: str = Field(..., description="Object key trong bucket")
    url: str = Field(..., description="Public URL de truy cap")
    bucket: str = Field(..., description="Ten bucket")
    size_bytes: int = Field(..., description="Kich thuoc file (bytes)")
    content_type: str = Field(..., description="MIME type")


class StorageError(Exception):
    """Exception cho cac loi Storage."""
    pass
