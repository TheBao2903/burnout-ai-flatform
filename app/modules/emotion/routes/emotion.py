"""
==============================================================
File: emotion.py

Emotion Routes - API endpoints cho emotion analysis.

1. POST /api/emotion/analyze
   - Upload anh -> DeepFace -> R2 -> AI
   - Optional: assessment_id để cập nhật Assessment Session

2. GET  /api/emotion/history
   - Lich su emotion cua user

3. DELETE /api/emotion/{id}/image
   - Xoa anh da luu tren R2
==============================================================
"""

import logging
from datetime import datetime
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.deps import get_current_user
from app.core.settings import get_settings
from app.modules.emotion.repositories.emotion_repository import (
    EmotionRepository,
    get_emotion_repository,
)
from app.modules.emotion.services.deepface_service import EmotionService

logger = logging.getLogger("burnout.emotion.routes")

router = APIRouter(prefix="/api/emotion", tags=["Emotion"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _check_image_resolution(image_bytes: bytes, max_w: int, max_h: int) -> tuple[int, int]:
    """
    Doc width/height cua anh ma KHONG can Opencv (chi dung Pillow).

    Args:
        image_bytes: Anh dau vao.
        max_w, max_h: Gioi han chieu ngang/doc.

    Returns:
        (width, height).

    Raises:
        HTTPException 400 neu anh qua lon.
    """
    try:
        from PIL import Image
        img = Image.open(BytesIO(image_bytes))
        w, h = img.size
        img.close()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Khong doc duoc anh (corrupted hoac khong phai image): {exc}",
        )

    if w > max_w or h > max_h:
        raise HTTPException(
            status_code=413,
            detail=f"Resolution qua lon ({w}x{h}). Gioi han: {max_w}x{max_h} pixels.",
        )
    return w, h


class AnalyzeResponse(BaseModel):
    """Response cho /analyze."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "request_id": "emotion_doc_id_abc",
                "emotion": {
                    "emotions": {
                        "happy": 10.0,
                        "sad": 60.0,
                        "neutral": 20.0,
                        "fear": 5.0,
                        "angry": 5.0,
                    },
                    "dominant_emotion": "sad",
                    "confidence": 0.6,
                    "analyzed_at": "2026-08-03T09:30:00Z",
                },
                "assessment": {
                    "risk_level": "medium",
                    "summary": "Cảm xúc tiêu cực nhẹ.",
                    "recommendations": ["Nghỉ ngơi", "Nói chuyện với bạn bè"],
                    "key_signals": ["sad dominant"],
                    "disclaimer": "AI chỉ đánh giá nguy cơ, không chẩn đoán bệnh.",
                },
                "image_key": "emotion/user_abc123/2026-08-03/abc.jpg",
                "image_url": "https://bucket.r2.cloudflarestorage.com/burnout-ai-flatform/emotion/user_abc123/2026-08-03/abc.jpg?X-Amz-...",
                "saved_to_r2": True,
                "generated_at": "2026-08-03T09:30:01Z",
            }
        }
    )

    request_id: str
    emotion: dict
    assessment: Optional[dict] = None
    assessment_status: Optional[dict] = None  # Cap nhat khi co assessment_id
    image_key: Optional[str] = None  # relative path trong bucket (luu DB)
    image_url: Optional[str] = None  # presigned URL tam thoi (tra client)
    saved_to_r2: bool
    generated_at: str


# ==========================================
# Dependencies
# ==========================================

def get_emotion_svc() -> EmotionService:
    """Lay EmotionService singleton (lazy)."""
    from app.modules.emotion.services.deepface_service import get_emotion_service
    return get_emotion_service()


def get_emotion_repo() -> EmotionRepository:
    return get_emotion_repository()


# ==========================================
# Endpoints
# ==========================================

@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
)
async def analyze_emotion(
    file: UploadFile = File(..., description="Anh khuon mat (jpg/png/webp)"),
    save_image: bool = Form(default=False, description="User dong y luu anh len R2?"),
    generate_ai: bool = Form(default=True, description="Co goi AI assessment khong?"),
    assessment_id: Optional[str] = Query(default=None, description="Assessment ID (optional)"),
    user: dict = Depends(get_current_user),
    emotion_service: EmotionService = Depends(get_emotion_svc),
):
    """
    Phan tich emotion tu anh, tuy chon luu anh len R2 va goi AI de sinh danh gia.

    Neu assessment_id duoc cung cap, se dong thoi cap nhat Assessment Session status.
    """
    # Validate content type
    content_type = file.content_type or "image/jpeg"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content_type: {content_type}. Cho phep: {sorted(ALLOWED_CONTENT_TYPES)}",
        )

    # Read bytes
    image_bytes = await file.read()
    max_size = get_settings().server.max_upload_size
    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="File rong")
    if len(image_bytes) > max_size:
        mb = len(image_bytes) / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File qua lon ({mb:.1f} MB > {max_size / (1024*1024):.0f} MB)",
        )

    # Check resolution (PIL only, khong load Opencv)
    settings = get_settings().server
    _check_image_resolution(image_bytes, settings.max_image_width, settings.max_image_height)

    # Verify assessment ownership if assessment_id provided
    assessment_status = None
    assessment = None
    if assessment_id:
        from app.modules.assessment.repositories.assessment_session_repository import (
            get_assessment_session_repository,
        )
        assessment_repo = get_assessment_session_repository()
        assessment = assessment_repo.get(assessment_id)
        if not assessment:
            raise HTTPException(
                status_code=404,
                detail="Assessment not found",
            )
        if assessment.get("user_id") != user["uid"]:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to use this assessment",
            )

    result = await emotion_service.analyze(
        user_id=user["uid"],
        image_bytes=image_bytes,
        content_type=content_type,
        save_image=save_image,
        generate_ai=generate_ai,
        assessment_id=assessment_id,
    )

    # Update Assessment Session status if assessment_id provided
    if assessment_id:
        from app.modules.assessment.repositories.assessment_session_repository import (
            get_assessment_session_repository,
        )
        from app.modules.emotion.repositories.emotion_repository import (
            get_emotion_repository,
        )
        assessment_repo = get_assessment_session_repository()
        emotion_repo = get_emotion_repository()

        # Get emotion count for this assessment
        emotion_count = emotion_repo.count_by_assessment(assessment_id)
        assessment_repo.mark_emotion_collected(assessment_id, emotion_count=emotion_count)

        # Get updated assessment status
        updated_assessment = assessment_repo.get(assessment_id)
        if updated_assessment:
            assessment_status = {
                "has_emotion": True,
                "emotion_count": emotion_count,
                "data_completeness": updated_assessment.get("data_completeness", 0.0),
            }

    return AnalyzeResponse(
        request_id=result.get("request_id", ""),
        emotion=result.get("emotion", {}),
        assessment=result.get("assessment"),
        assessment_status=assessment_status,
        image_key=result.get("image_key"),
        image_url=result.get("image_url"),
        saved_to_r2=result.get("saved_to_r2", False),
        generated_at=result.get("generated_at", ""),
    )


@router.get("/history", response_model=list)
async def get_emotion_history(
    limit: int = 30,
    user: dict = Depends(get_current_user),
    repo: EmotionRepository = Depends(get_emotion_repo),
):
    """Lay lich su emotion cua user (moi nhat truoc), kem assessment neu co."""
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit phai trong [1, 100]")

    # Lay emotion history
    emotions = repo.list_by_user(user_id=user["uid"], limit=limit)

    # NOTE: Presigned URL generation moved to client-side to reduce backend load
    # Client calls /api/emotion/image-url?key=... to get presigned URL for each image

    return emotions


@router.delete("/{emotion_id}/image", response_model=dict)
async def delete_emotion_image(
    emotion_id: str,
    user: dict = Depends(get_current_user),
    repo: EmotionRepository = Depends(get_emotion_repo),
):
    """Xoa anh da luu (R2 + clear image_url trong Firestore)."""
    record = repo.get(emotion_id)
    if not record:
        raise HTTPException(status_code=404, detail="Emotion khong ton tai")
    if record.get("user_id") != user["uid"]:
        raise HTTPException(status_code=403, detail="Khong co quyen")

    # record.image_url dang luu relative key (khong phai full URL)
    image_key = record.get("image_url")
    if not image_key:
        return {"message": "Khong co anh de xoa", "emotion_id": emotion_id}

    from app.modules.storage import get_r2_service
    from app.modules.storage.models.storage import StorageError

    r2 = get_r2_service()
    try:
        r2.delete_object(image_key)
    except StorageError as exc:
        logger.warning("R2 delete failed (tiep tuc clear DB): %s", exc)

    repo.clear_image(emotion_id)
    return {"message": "Da xoa anh", "emotion_id": emotion_id, "image_key": image_key}
