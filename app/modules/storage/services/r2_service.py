"""
==============================================================
File: r2_service.py

R2Service - Upload/lenh/xoa file tren Cloudflare R2 (S3-compatible).

Quy uoc:
- DB/Firestore chi luu RELATIVE KEY (vd "emotion/{user_id}/{YYYY-MM-DD}/{YYYYmmddTHHMMSSffffff}.jpg").
- Khi can URL (tra response cho client), R2Service.generate_presigned_url()
  se tra ve presigned URL tam thoi (mac dinh 1 gio).
- KHONG can enable public access tren bucket.

Lazy init: boto3 client chi duoc tao khi goi upload/generate URL lan dau.
Neu R2 credentials trong env bi rong, raise StorageError.
==============================================================
"""

import logging
from datetime import datetime
from typing import Optional

from app.core.settings import get_settings
from app.modules.storage.models.storage import StorageError, UploadResult

logger = logging.getLogger("burnout.storage")

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Mac dinh presigned URL song 1 gio
DEFAULT_PRESIGNED_EXPIRES = 3600


def build_emotion_key(user_id: str, when: Optional[datetime] = None) -> str:
    """
    Tao object key cho emotion theo user, dang:
        emotion/{user_id}/{YYYY-MM-DD}/{YYYYmmddTHHMMSSffffff}.jpg
    """
    when = when or datetime.utcnow()
    date_part = when.strftime("%Y-%m-%d")
    stamp_part = when.strftime("%Y%m%dT%H%M%S%f")
    return f"emotion/{user_id}/{date_part}/{stamp_part}.jpg"


class R2Service:
    """Service lam viec voi Cloudflare R2."""

    def __init__(self, client_factory=None):
        self._client = None
        self._bucket: Optional[str] = None
        self._client_factory = client_factory

    # -------------------------
    # Lazy init
    # -------------------------

    def _get_client(self):
        if self._client is not None:
            return self._client

        settings = get_settings().r2
        if not (settings.access_key_id and settings.secret_access_key and settings.account_id):
            raise StorageError("R2 credentials not configured")

        if self._client_factory is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError as exc:
                raise StorageError("boto3 not installed. Run: pip install boto3") from exc

            def _factory():
                return boto3.client(
                    "s3",
                    endpoint_url=f"https://{settings.account_id}.r2.cloudflarestorage.com",
                    region_name=settings.region,
                    aws_access_key_id=settings.access_key_id,
                    aws_secret_access_key=settings.secret_access_key,
                    config=Config(signature_version="s3v4"),
                )

            self._client_factory = _factory

        self._client = self._client_factory()
        self._bucket = settings.bucket_name
        logger.info("R2 client initialized (bucket=%s)", self._bucket)
        return self._client

    # -------------------------
    # Public API
    # -------------------------

    def upload_image(
        self,
        user_id: str,
        image_bytes: bytes,
        content_type: str = "image/jpeg",
        when: Optional[datetime] = None,
    ) -> UploadResult:
        """Upload anh len R2, tra UploadResult voi key tuong doi (KHONG co URL).

        Goi them generate_presigned_url(key) neu can URL tam thoi de client truy cap.
        """
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise StorageError(f"Unsupported content_type: {content_type}")

        client = self._get_client()
        key = build_emotion_key(user_id, when=when)
        logger.info("R2 upload: key=%s, size=%d, content_type=%s", key, len(image_bytes), content_type)

        try:
            client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=image_bytes,
                ContentType=content_type,
            )
        except Exception as exc:
            logger.exception("R2 put_object failed: %s", exc)
            raise StorageError(f"Upload failed: {exc}") from exc

        logger.info("Uploaded %s bytes to %s", len(image_bytes), key)
        # Tra UploadResult chi voi key, KHONG co url (url phai generate sau)
        return UploadResult(
            key=key,
            url="",  # de trong; client goi generate_presigned_url de lay URL tam thoi
            bucket=self._bucket or "",
            size_bytes=len(image_bytes),
            content_type=content_type,
        )

    def generate_presigned_url(
        self,
        key: str,
        expires_in: int = DEFAULT_PRESIGNED_EXPIRES,
        method: str = "get_object",
    ) -> str:
        """Sinh presigned URL tam thoi cho key.

        Args:
            key: Object key tuong doi (vd "emotion/{user_id}/{YYYY-MM-DD}/{YYYYmmddTHHMMSSffffff}.jpg").
            expires_in: So giay URL song (mac dinh 3600 = 1 gio).
            method: 'get_object' (download) hoac 'put_object' (upload truc tiep).

        Returns:
            URL tam thoi dang ky. Neu client can GET anh, truyen method='get_object'.

        Raises:
            StorageError: Neu co loi generate URL.
        """
        client = self._get_client()

        try:
            url = client.generate_presigned_url(
                ClientMethod=method,
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )
            logger.info("Generated presigned URL for key: %s", key)
            return url
        except Exception as exc:
            logger.error("generate_presigned_url failed for key %s: %s", key, exc)
            raise StorageError(f"Presign failed: {exc}") from exc

    def delete_object(self, key: str) -> bool:
        """Xoa object theo key."""
        client = self._get_client()
        try:
            client.delete_object(Bucket=self._bucket, Key=key)
            logger.info("Deleted %s", key)
            return True
        except Exception as exc:
            logger.exception("R2 delete_object failed: %s", exc)
            return False


# ==========================================
# Singleton
# ==========================================

_r2_service: Optional[R2Service] = None


def get_r2_service() -> R2Service:
    """Lay R2Service singleton."""
    global _r2_service
    if _r2_service is None:
        _r2_service = R2Service()
    return _r2_service