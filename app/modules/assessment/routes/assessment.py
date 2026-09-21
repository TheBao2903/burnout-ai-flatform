"""
==============================================================
File: assessment.py

Assessment Routes - API goi AI assessment tu emotion_id.
==============================================================
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.core.deps import get_current_user
from app.modules.assessment.services.ai_service import (
    AIAssessmentResult,
    AssessmentService,
)
from app.modules.emotion.repositories.emotion_repository import (
    EmotionRepository,
    get_emotion_repository,
)

logger = logging.getLogger("burnout.assessment.routes")

router = APIRouter(prefix="/api/assessment", tags=["Assessment"])


class GenerateFromEmotionIdRequest(BaseModel):
    """Body cho POST /api/assessment/generate."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"emotion_id": "emotion_doc_id_abc"}}
    )
    emotion_id: str = Field(..., min_length=1)


def get_assessment_svc() -> AssessmentService:
    from app.modules.assessment.services.ai_service import get_assessment_service
    return get_assessment_service()


def get_emotion_repo() -> EmotionRepository:
    return get_emotion_repository()


@router.post("/generate", response_model=AIAssessmentResult)
async def generate_assessment(
    req: GenerateFromEmotionIdRequest,
    user: dict = Depends(get_current_user),
    assessment_service: AssessmentService = Depends(get_assessment_svc),
    repo: EmotionRepository = Depends(get_emotion_repo),
):
    """
    Lay emotion theo id, goi AI de sinh assessment (moi).

    Dung khi client da co emotion_id luu tu truoc va muon
    generate AI assessment moi (khong can upload anh lai).
    """
    record = repo.get(req.emotion_id)
    if not record:
        raise HTTPException(status_code=404, detail="Emotion khong ton tai")
    if record.get("user_id") != user["uid"]:
        raise HTTPException(status_code=403, detail="Khong co quyen")

    # Reconstruct EmotionResult
    from app.modules.emotion.models.emotion import EmotionResult, EmotionScores
    from datetime import datetime

    emotion_data = record.get("emotions", {}) or {}
    scores = EmotionScores(
        happy=emotion_data.get("happy", 0.0),
        sad=emotion_data.get("sad", 0.0),
        neutral=emotion_data.get("neutral", 0.0),
        fear=emotion_data.get("fear", 0.0),
        angry=emotion_data.get("angry", 0.0),
        surprise=emotion_data.get("surprise", 0.0),
        disgust=emotion_data.get("disgust", 0.0),
    )
    analyzed_at_str = record.get("analyzed_at")
    analyzed_at_dt = None
    if analyzed_at_str:
        try:
            # "2026-08-03T09:30:00Z" -> datetime
            analyzed_at_dt = datetime.fromisoformat(analyzed_at_str.rstrip("Z"))
        except Exception:
            analyzed_at_dt = None

    emotion_result = EmotionResult(
        emotions=scores,
        dominant_emotion=record.get("dominant_emotion", "Unknown"),
        confidence=float(record.get("confidence", 0.0)),
        image_url=record.get("image_url"),
        analyzed_at=analyzed_at_dt,
    )

    return await assessment_service.generate(emotion_result)