"""
==============================================================
File: burnout_result.py

Burnout Result Routes - API endpoints cho Burnout Result.

GET /api/v1/assessments/{id}/result  - Lấy kết quả burnout
GET /api/v1/assessments/{id}/emotions - Lấy emotion history của assessment

Lưu ý: KHÔNG tính lại Burnout. CHỈ đọc từ Firestore.

NOTE: Chat và Survey endpoints đã được chuyển sang:
- chat_history_router: /api/v1/assessments/{id}/chat
- survey_history_router: /api/v1/assessments/{id}/survey
==============================================================
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.modules.assessment.repositories.assessment_session_repository import (
    get_assessment_session_repository,
)
from app.modules.burnout.repositories.burnout_repository import (
    BurnoutRepository,
    get_burnout_repository,
)
from app.modules.emotion.repositories.emotion_repository import (
    get_emotion_repository,
)

logger = logging.getLogger("burnout.result.routes")

router = APIRouter(prefix="/api/v1/assessments", tags=["Burnout"])


# ==========================================
# Response Models
# ==========================================

class FactorResponse(BaseModel):
    """Factor response."""

    factor: str
    percentage: float
    details: Optional[dict] = None


class RecommendationResponse(BaseModel):
    """Recommendation response."""

    title: str
    description: str
    priority: str
    target_factor: Optional[str] = None


class BurnoutResultResponse(BaseModel):
    """Response cho /result endpoint."""

    assessment_id: str
    status: str
    user_id: str

    # STA Scientific Architecture (Item 17)
    burnout_core: Optional[dict] = None
    context: Optional[dict] = None
    supporting_signals: Optional[dict] = None
    data_quality: Optional[str] = "valid"
    data_sufficiency: Optional[str] = "sufficient"
    interpretation: Optional[str] = None
    confidence: Optional[float] = None
    disclaimer: Optional[str] = None

    # Legacy fields
    burnout_score: float = 0.0
    risk_level: str = "low"
    trend: str = "stable"
    data_completeness: float = 1.0

    factors: list = []
    recommendations: list = []

    created_at: str
    completed_at: Optional[str] = None
    analyzed_at: Optional[str] = None

    # Metadata
    assessment_data_completeness: float = 0.0


class EmotionHistoryResponse(BaseModel):
    """Response cho /emotions endpoint."""

    assessment_id: str
    emotions: list
    count: int
    aggregated: Optional[dict] = None


# ==========================================
# Dependencies
# ==========================================

def get_assessment_repo():
    return get_assessment_session_repository()


def get_burnout_repo() -> BurnoutRepository:
    return get_burnout_repository()


def get_emotion_repo():
    return get_emotion_repository()


# ==========================================
# GET /api/v1/assessments/{id}/result
# ==========================================

@router.get("/{assessment_id}/result", response_model=BurnoutResultResponse)
async def get_burnout_result(
    assessment_id: str,
    user: dict = Depends(get_current_user),
):
    """Lấy kết quả burnout của một assessment.

    API này KHÔNG tính lại Burnout.
    CHỈ đọc từ Firestore.

    Response:
    - assessment info
    - burnout score, risk level, trend
    - factors với contributions
    - recommendations
    """
    user_id = user["uid"]

    # 1. Verify assessment exists & ownership
    assessment_repo = get_assessment_repo()
    assessment = assessment_repo.get(assessment_id)

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if assessment.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this assessment",
        )

    # 2. Load burnout result
    burnout_repo = get_burnout_repo()
    burnout_result = burnout_repo.get_by_assessment(assessment_id)

    if not burnout_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Burnout result not found. Run POST /analyze first.",
        )

    # 3. Build response
    assessment_status = assessment.get("status", "")
    assessment_completeness = assessment.get("data_completeness", 0.0)

    # Parse burnout result
    burnout_score = burnout_result.get("burnout_score", 0.0)
    risk_level = burnout_result.get("risk_level", "unknown")
    trend = burnout_result.get("trend", "insufficient_data")
    result_completeness = burnout_result.get("data_completeness", 0.0)

    # Use the higher completeness
    data_completeness = max(assessment_completeness, result_completeness)

    # Factors
    factors = burnout_result.get("factors", [])
    if isinstance(factors, list):
        factors = [
            FactorResponse(
                factor=f.get("factor", ""),
                percentage=f.get("percentage", 0.0),
                details=f.get("details"),
            ).model_dump()
            for f in factors
        ]

    # Recommendations
    recommendations = burnout_result.get("recommendations", [])
    if isinstance(recommendations, list):
        recommendations = [
            RecommendationResponse(
                title=r.get("title", ""),
                description=r.get("description", ""),
                priority=r.get("priority", "medium"),
                target_factor=r.get("target_factor"),
            ).model_dump()
            for r in recommendations
        ]

    # Timestamps
    created_at = str(assessment.get("created_at", ""))
    completed_at = str(assessment.get("completed_at")) if assessment.get("completed_at") else None
    analyzed_at = str(burnout_result.get("analyzed_at", "")) if burnout_result.get("analyzed_at") else None

    return BurnoutResultResponse(
        assessment_id=assessment_id,
        status=assessment_status,
        user_id=user_id,
        burnout_core=burnout_result.get("burnout_core"),
        context=burnout_result.get("context"),
        supporting_signals=burnout_result.get("supporting_signals"),
        data_quality=burnout_result.get("data_quality", "valid"),
        data_sufficiency=burnout_result.get("data_sufficiency", "sufficient"),
        interpretation=burnout_result.get("interpretation"),
        confidence=burnout_result.get("confidence"),
        disclaimer=burnout_result.get("disclaimer"),
        burnout_score=burnout_score,
        risk_level=risk_level,
        trend=trend,
        data_completeness=data_completeness,
        factors=factors,
        recommendations=recommendations,
        created_at=created_at,
        completed_at=completed_at,
        analyzed_at=analyzed_at,
        assessment_data_completeness=assessment_completeness,
    )


# ==========================================
# GET /api/v1/assessments/{id}/emotions
# ==========================================

@router.get("/{assessment_id}/emotions", response_model=EmotionHistoryResponse)
async def get_assessment_emotions(
    assessment_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    """Lấy emotion history của một assessment.

    Trả về:
    - List các emotion records
    - Aggregated emotion data
    """
    user_id = user["uid"]

    # Verify ownership
    assessment_repo = get_assessment_repo()
    assessment = assessment_repo.get(assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if assessment.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    # Load emotions
    emotion_repo = get_emotion_repo()
    emotions = emotion_repo.list_by_assessment(assessment_id, limit=limit)

    # Build aggregated emotion
    aggregated = None
    if emotions:
        from app.modules.burnout.services.burnout_input_builder import EmotionAggregator
        aggregated = EmotionAggregator.aggregate(emotions)
        if aggregated:
            aggregated = aggregated.to_dict()

    return EmotionHistoryResponse(
        assessment_id=assessment_id,
        emotions=emotions,
        count=len(emotions),
        aggregated=aggregated,
    )


# NOTE: Chat và Survey endpoints đã được chuyển sang:
# - chat_history_router: GET /api/v1/assessments/{id}/chat
# - survey_history_router: GET /api/v1/assessments/{id}/survey
