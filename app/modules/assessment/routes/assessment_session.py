"""
==============================================================
File: assessment_session.py

Assessment Session Routes - API endpoints cho Assessment Sessions.

POST /api/v1/assessments              - Tạo assessment mới
GET  /api/v1/assessments              - Danh sách assessments của user
GET  /api/v1/assessments/{id}        - Thông tin chi tiết assessment
POST /api/v1/assessments/{id}/analyze - Chạy phân tích burnout
DELETE /api/v1/assessments/{id}      - Xóa assessment
==============================================================
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.deps import get_current_user
from app.modules.assessment.repositories.assessment_session_repository import (
    AssessmentSessionRepository,
    get_assessment_session_repository,
)
from app.modules.emotion.repositories.emotion_repository import (
    EmotionRepository,
    get_emotion_repository,
)
from app.modules.survey.repositories.survey_history_repository import (
    SurveyHistoryRepository,
    get_survey_history_repository,
)
from app.modules.chat.repositories.chat_history_repository import (
    ChatHistoryRepository,
    get_chat_history_repository,
)
from app.modules.burnout.repositories.burnout_repository import (
    BurnoutRepository,
    get_burnout_repository,
)

logger = logging.getLogger("burnout.assessment.session.routes")

router = APIRouter(prefix="/api/v1/assessments", tags=["Assessment"])


# ==========================================
# Request/Response Models
# ==========================================

class AssessmentCreateResponse(BaseModel):
    """Response khi tạo assessment mới."""

    assessment_id: str
    status: str
    message: str


class AssessmentListResponse(BaseModel):
    """Response khi lấy danh sách assessments."""

    assessments: list
    total: int


class AssessmentDetailResponse(BaseModel):
    """Response khi lấy thông tin chi tiết."""

    id: str
    user_id: str
    status: str
    status_detail: dict
    data_completeness: float
    has_result: bool
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None


class AssessmentAnalyzeResponse(BaseModel):
    """Response khi chạy phân tích burnout."""

    assessment_id: str
    status: str
    burnout_result_id: Optional[str] = None
    message: str
    result: Optional[dict] = None


# ==========================================
# Dependencies
# ==========================================

def get_assessment_session_repo() -> AssessmentSessionRepository:
    return get_assessment_session_repository()


def get_emotion_repo() -> EmotionRepository:
    return get_emotion_repository()


def get_survey_repo() -> SurveyHistoryRepository:
    return get_survey_history_repository()


def get_chat_repo() -> ChatHistoryRepository:
    return get_chat_history_repository()


def get_burnout_repo() -> BurnoutRepository:
    return get_burnout_repository()


# ==========================================
# Endpoints
# ==========================================

@router.post("", response_model=AssessmentCreateResponse)
async def create_assessment(
    user: dict = Depends(get_current_user),
    repo: AssessmentSessionRepository = Depends(get_assessment_session_repo),
):
    """Tạo một assessment mới.

    Assessment mới có status='collecting' và data_completeness=0.
    """
    user_id = user["uid"]

    assessment_id = repo.create(user_id=user_id, status="collecting")

    return AssessmentCreateResponse(
        assessment_id=assessment_id,
        status="collecting",
        message="Assessment created successfully. Start collecting data.",
    )


@router.get("", response_model=AssessmentListResponse)
async def list_assessments(
    limit: int = 30,
    status_filter: Optional[str] = None,
    user: dict = Depends(get_current_user),
    repo: AssessmentSessionRepository = Depends(get_assessment_session_repo),
):
    """Lấy danh sách assessments của user."""
    user_id = user["uid"]

    assessments = repo.list_by_user(
        user_id=user_id,
        limit=limit,
        status_filter=status_filter,
    )

    return AssessmentListResponse(
        assessments=assessments,
        total=len(assessments),
    )


@router.get("/{assessment_id}", response_model=AssessmentDetailResponse)
async def get_assessment(
    assessment_id: str,
    user: dict = Depends(get_current_user),
    repo: AssessmentSessionRepository = Depends(get_assessment_session_repo),
):
    """Lấy thông tin chi tiết của một assessment."""
    user_id = user["uid"]

    assessment = repo.get(assessment_id)

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

    return AssessmentDetailResponse(
        id=assessment.get("id", ""),
        user_id=assessment.get("user_id", ""),
        status=assessment.get("status", ""),
        status_detail=assessment.get("status_detail", {}),
        data_completeness=assessment.get("data_completeness", 0.0),
        has_result=assessment.get("status_detail", {}).get("has_result", False),
        created_at=str(assessment.get("created_at", "")),
        updated_at=str(assessment.get("updated_at", "")),
        completed_at=str(assessment.get("completed_at")) if assessment.get("completed_at") else None,
    )


@router.post("/{assessment_id}/analyze", response_model=AssessmentAnalyzeResponse)
async def run_burnout_analysis(
    assessment_id: str,
    user: dict = Depends(get_current_user),
    session_repo: AssessmentSessionRepository = Depends(get_assessment_session_repo),
    emotion_repo: EmotionRepository = Depends(get_emotion_repo),
    survey_repo: SurveyHistoryRepository = Depends(get_survey_history_repository),
    chat_repo: ChatHistoryRepository = Depends(get_chat_history_repository),
    burnout_repo: BurnoutRepository = Depends(get_burnout_repo),
):
    """Chạy phân tích burnout cho một assessment.

    Flow:
    1. Validate authentication & authorization
    2. Verify assessment exists & belongs to user
    3. Verify assessment is in valid state (collecting)
    4. Load all data: assessment, emotions, survey, chats, historical results
    5. Build BurnoutInput via BurnoutInputBuilder
    6. Run BurnoutEngine
    7. Run RecommendationEngine
    8. Persist burnout result to Firestore
    9. Update assessment status to completed
    10. Return final result
    """
    user_id = user["uid"]

    # 1. Verify ownership
    assessment = session_repo.get(assessment_id)
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

    # 2. Verify assessment status
    current_status = assessment.get("status")
    if current_status == "completed":
        # Idempotency: Return existing result
        burnout_result_id = assessment.get("burnout_result_id")
        return AssessmentAnalyzeResponse(
            assessment_id=assessment_id,
            status="completed",
            burnout_result_id=burnout_result_id,
            message="Analysis already completed. Use GET /result to view.",
        )
    if current_status == "analyzing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis is already in progress. Please wait.",
        )
    if current_status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot analyze a cancelled assessment.",
        )

    # 3. Update status to analyzing
    session_repo.update_status(assessment_id, "analyzing")

    try:
        # 4. Load all data
        # Load emotions for this assessment
        emotions = emotion_repo.list_by_assessment(assessment_id, limit=100)
        logger.info("Loaded %d emotion records for assessment %s", len(emotions), assessment_id)

        # Load survey (Daily Check-in)
        survey = survey_repo.get_by_assessment(assessment_id)
        logger.info("Loaded survey for assessment %s: %s", assessment_id, bool(survey))

        # Load latest periodic survey for user (Job Resources & Six Areas)
        periodic_survey = survey_repo.get_latest_periodic_survey(user_id)
        logger.info("Loaded periodic survey for user %s: %s", user_id, bool(periodic_survey))

        # Load chat history
        chats = chat_repo.get_messages_by_assessment(assessment_id, limit=100)
        logger.info("Loaded %d chat messages for assessment %s", len(chats), assessment_id)

        # Load historical burnout results (exclude current)
        historical_results = burnout_repo.list_by_user(user_id, limit=20)
        historical_results = [
            r for r in historical_results
            if r.get("assessment_id") != assessment_id
        ]
        logger.info("Loaded %d historical burnout results for user %s", len(historical_results), user_id)

        # 5. Build BurnoutInput
        from app.modules.burnout.services.burnout_input_builder import BurnoutInputBuilder

        builder = BurnoutInputBuilder(
            assessment_id=assessment_id,
            user_id=user_id,
            assessment=assessment,
            survey=survey,
            emotions=emotions,
            chats=chats,
            historical_results=historical_results,
        )
        burnout_input = builder.build()
        if periodic_survey:
            burnout_input.periodic_survey = periodic_survey

        logger.info(
            "Built BurnoutInput for %s: completeness=%.2f",
            assessment_id,
            burnout_input.data_completeness,
        )

        # 6. Run BurnoutEngine
        from app.modules.burnout.services.burnout_engine import get_burnout_engine

        engine = get_burnout_engine()
        engine_output = engine.analyze(burnout_input)
        burnout_result = engine_output.burnout
        logger.info(
            "BurnoutEngine result for %s: score=%.1f, risk=%s",
            assessment_id,
            burnout_result.burnout_score,
            burnout_result.risk_level,
        )

        # 7. Run RecommendationEngine
        from app.modules.recommendation.services.recommendation_engine import (
            get_recommendation_engine,
        )

        rec_engine = get_recommendation_engine()
        recommendations = rec_engine.generate(burnout_result)

        # Convert recommendations to dict
        recommendation_dicts = [
            {
                "title": getattr(r, "title", str(r)),
                "description": getattr(r, "description", ""),
                "priority": getattr(r, "priority", "medium"),
                "target_factor": getattr(r, "target_factor", None),
            }
            if not isinstance(r, dict) else r
            for r in recommendations
        ]
        logger.info(
            "Generated %d recommendations for %s",
            len(recommendation_dicts),
            assessment_id,
        )

        # 8. Persist burnout result with STA schema + backward compatibility
        burnout_doc = {
            "assessment_id": assessment_id,
            "user_id": user_id,
            "engine_version": burnout_result.engine_version,
            "burnout_core": burnout_result.burnout_core.model_dump() if hasattr(burnout_result.burnout_core, "model_dump") else burnout_result.burnout_core,
            "context": burnout_result.context.model_dump() if hasattr(burnout_result.context, "model_dump") else burnout_result.context,
            "supporting_signals": burnout_result.supporting_signals.model_dump() if hasattr(burnout_result.supporting_signals, "model_dump") else burnout_result.supporting_signals,
            "data_quality": burnout_result.data_quality,
            "data_sufficiency": burnout_result.data_sufficiency,
            "interpretation": burnout_result.interpretation,
            "confidence": burnout_result.confidence,
            "disclaimer": burnout_result.disclaimer,
            # Legacy fields
            "burnout_score": burnout_result.burnout_score,
            "data_completeness": burnout_result.data_completeness,
            "risk_level": burnout_result.risk_level,
            "trend": burnout_result.trend,
            "factors": [
                {
                    "factor": f.factor,
                    "score": f.score,
                    "weight": f.weight,
                    "contribution": f.contribution,
                    "details": f.details,
                }
                for f in burnout_result.factors
            ],
            "recommendations": recommendation_dicts,
            "insight": engine_output.insight.model_dump() if hasattr(engine_output.insight, "model_dump") else engine_output.insight,
            "analyzed_at": burnout_result.analyzed_at,
        }

        burnout_result_id = burnout_repo.save(
            user_id=user_id,
            result=burnout_doc,
            assessment_id=assessment_id,
        )
        logger.info("Saved burnout result %s for assessment %s", burnout_result_id, assessment_id)

        # 9. Update assessment status to completed
        session_repo.mark_result_ready(assessment_id, burnout_result_id)

        return AssessmentAnalyzeResponse(
            assessment_id=assessment_id,
            status="completed",
            burnout_result_id=burnout_result_id,
            message="Burnout analysis completed successfully.",
            result=burnout_doc,
        )

    except Exception as exc:
        logger.error("Burnout analysis failed for %s: %s", assessment_id, exc)
        # Revert status to collecting on failure
        session_repo.update_status(assessment_id, "collecting")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(exc)}",
        )


@router.delete("/{assessment_id}", response_model=dict)
async def delete_assessment(
    assessment_id: str,
    user: dict = Depends(get_current_user),
    session_repo: AssessmentSessionRepository = Depends(get_assessment_session_repo),
    emotion_repo: EmotionRepository = Depends(get_emotion_repo),
    survey_repo: SurveyHistoryRepository = Depends(get_survey_history_repository),
    chat_repo: ChatHistoryRepository = Depends(get_chat_repo),
):
    """Xóa một assessment và tất cả dữ liệu liên quan."""
    user_id = user["uid"]

    # Verify ownership
    assessment = session_repo.get(assessment_id)
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

    # Delete related data
    emotion_repo.delete_by_assessment(assessment_id)
    survey_repo.delete_by_assessment(assessment_id)
    chat_repo.delete_by_assessment(assessment_id)

    # Delete burnout result if exists
    burnout_repo = get_burnout_repo()
    burnout_result = burnout_repo.get_by_assessment(assessment_id)
    if burnout_result and burnout_result.get("id"):
        burnout_repo.delete(burnout_result["id"])

    # Delete assessment
    session_repo.delete(assessment_id)

    return {
        "message": "Assessment deleted successfully",
        "assessment_id": assessment_id,
    }
