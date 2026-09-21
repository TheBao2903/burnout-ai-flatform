"""
==============================================================
File: survey_history.py

Survey History Routes - API endpoints cho survey.

GET  /api/v1/assessments/{id}/survey/questions  - Lấy câu hỏi survey
GET  /api/v1/assessments/{id}/survey           - Lấy survey của assessment
POST /api/v1/assessments/{id}/survey           - Submit survey
POST /api/survey/analyze                       - Phân tích survey (tách biệt)
POST /api/survey/recommendations               - Tìm địa điểm gợi ý
==============================================================
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.deps import get_current_user
from app.modules.survey.repositories.survey_history_repository import (
    SurveyHistoryRepository,
    get_survey_history_repository,
)
from app.modules.survey.models.survey_history import SurveyQuestions
from app.modules.survey.services.survey_analysis_service import (
    SurveyAnalysisService,
    get_survey_analysis_service,
)
from app.modules.recommendation.services.place_recommendation_service import (
    get_place_recommendation_service,
)

logger = logging.getLogger("burnout.survey.routes")

router = APIRouter(prefix="/api/v1/assessments", tags=["Survey"])


# ==========================================
# Request/Response Models
# ==========================================

# DEPRECATED: Analysis result và recommendations KHÔNG còn lưu trong Survey
# Chúng thuộc về BurnoutResult
class SurveyAnalysisResultRequest(BaseModel):
    """[DEPRECATED] Kết quả phân tích survey."""
    risk_level: str
    risk_score: int = 0
    summary: str = ""
    suggestions: list[str] = Field(default_factory=list)


class SurveyRecommendationRequest(BaseModel):
    """[DEPRECATED] Một recommendation."""
    place_id: Optional[str] = None
    name: str
    address: Optional[str] = None
    distance_meters: Optional[int] = None
    category: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None


class SurveySubmitRequest(BaseModel):
    """Request body cho POST /survey.

    CLEAN ARCHITECTURE:
    - Survey CHỉ nhận raw answers
    - KHÔNG nhận analysis_result (thuộc BurnoutResult)
    - KHÔNG nhận recommendations (thuộc Recommendation Engine)
    """

    sleep_hours: float = Field(..., ge=0.0, le=24.0, description="Số giờ ngủ")
    working_hours: float = Field(..., ge=0.0, le=24.0, description="Số giờ làm việc/ngày")
    overtime_hours: int = Field(default=0, ge=0, le=24, description="Số giờ tăng ca")
    has_deadline: str = Field(..., description="Mức độ deadline: low/medium/high/extreme")
    work_days_per_week: int = Field(..., ge=1, le=7, description="Số ngày làm việc/tuần")
    stress_level: int = Field(..., ge=1, le=10, description="Mức độ stress (1-10)")
    motivation_level: int = Field(default=5, ge=1, le=10, description="Mức độ động lực (1-10)")

    # Optional fields
    consecutive_work_days: Optional[int] = Field(default=None, ge=0, le=30)
    rest_days: Optional[int] = Field(default=None, ge=0, le=7)
    work_satisfaction: Optional[int] = Field(default=None, ge=1, le=10)
    heart_rate: Optional[int] = Field(default=None, ge=30, le=220)

    class Config:
        json_schema_extra = {
            "example": {
                "sleep_hours": 5.5,
                "working_hours": 10.0,
                "overtime_hours": 3,
                "has_deadline": "high",
                "work_days_per_week": 6,
                "stress_level": 8,
                "motivation_level": 3
            }
        }


class SurveyResponse(BaseModel):
    """Response cho survey data."""

    id: str
    assessment_id: str
    survey: dict
    status: str
    completed_at: Optional[str] = None
    created_at: str


class SurveyQuestionsResponse(BaseModel):
    """Response cho /questions endpoint."""

    questions: list


# ==========================================
# New: Analyze Request/Response Models
# ==========================================

class AnalyzeRequest(BaseModel):
    """Request body cho POST /api/survey/analyze."""

    sleep_hours: float = Field(..., ge=0.0, le=24.0, description="Số giờ ngủ")
    working_hours: float = Field(..., ge=0.0, le=24.0, description="Số giờ làm việc/ngày")
    overtime_hours: int = Field(default=0, ge=0, le=24, description="Số giờ tăng ca")
    has_deadline: str = Field(..., description="Mức độ deadline: low/medium/high/extreme")
    work_days_per_week: int = Field(..., ge=1, le=7, description="Số ngày làm việc/tuần")
    stress_level: int = Field(..., ge=1, le=10, description="Mức độ stress (1-10)")
    motivation_level: int = Field(default=5, ge=1, le=10, description="Mức độ động lực (1-10)")

    # Optional fields
    consecutive_work_days: Optional[int] = Field(default=None, ge=0, le=30)
    rest_days: Optional[int] = Field(default=None, ge=0, le=7)
    work_satisfaction: Optional[int] = Field(default=None, ge=1, le=10)
    heart_rate: Optional[int] = Field(default=None, ge=30, le=220)

    class Config:
        json_schema_extra = {
            "example": {
                "sleep_hours": 5.5,
                "working_hours": 10.0,
                "overtime_hours": 3,
                "has_deadline": "high",
                "work_days_per_week": 6,
                "stress_level": 8,
                "motivation_level": 3,
                "consecutive_work_days": 5,
                "rest_days": 1,
            }
        }


class AnalysisFactorResponse(BaseModel):
    """Một factor trong kết quả phân tích."""

    code: str
    score: float
    severity: str  # low, medium, high
    title: str
    description: str


class RecommendationResponse(BaseModel):
    """Một khuyến nghị trong kết quả phân tích."""

    code: str
    title: str
    description: str
    priority: str  # low, medium, high
    severity: str


class AnalyzeResponse(BaseModel):
    """Response cho POST /api/survey/analyze."""

    risk_score: float
    risk_level: str  # low, medium, high, critical
    summary: str
    factors: List[AnalysisFactorResponse]
    recommendations: List[RecommendationResponse]
    analysis_version: str


# ==========================================
# New: Recommendations Request/Response
# ==========================================

class RecommendationsRequest(BaseModel):
    """Request body cho POST /api/survey/recommendations."""

    analysis_result: AnalyzeResponse
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_meters: int = Field(default=3000, ge=100, le=10000)
    limit: int = Field(default=10, ge=1, le=20)
    address: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "analysis_result": {
                    "risk_score": 65.0,
                    "risk_level": "high",
                    "factors": [],
                    "recommendations": [],
                },
                "latitude": 10.7769,
                "longitude": 106.7009,
                "radius_meters": 3000,
            }
        }


class PlaceRecommendationResponse(BaseModel):
    """Một địa điểm gợi ý."""

    place_id: str
    name: str
    category: str
    reason: str
    address: Optional[str] = None
    distance: Optional[int] = None
    distance_meters: Optional[int] = None
    categories: List[str] = Field(default_factory=list)
    opening_hours: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class RecommendationsResponse(BaseModel):
    """Response cho POST /api/survey/recommendations."""

    places: List[PlaceRecommendationResponse]
    count: int
    searched_location: Dict[str, float]
    address: Optional[str] = None
    message: str


# ==========================================
# Dependency
# ==========================================

def get_survey_repo() -> SurveyHistoryRepository:
    return get_survey_history_repository()


# ==========================================
# Endpoints
# ==========================================

@router.get("/{assessment_id}/survey/questions", response_model=SurveyQuestionsResponse)
async def get_survey_questions(
    assessment_id: str,
    user: dict = Depends(get_current_user),
):
    """Lấy danh sách câu hỏi survey.

    Câu hỏi là static, không cần query DB.
    """
    questions = SurveyQuestions()
    return SurveyQuestionsResponse(questions=questions.questions)


@router.get("/{assessment_id}/survey", response_model=Optional[SurveyResponse])
async def get_survey(
    assessment_id: str,
    user: dict = Depends(get_current_user),
    survey_repo: SurveyHistoryRepository = Depends(get_survey_repo),
):
    """Lấy survey của một assessment."""
    user_id = user["uid"]

    survey = survey_repo.get_by_assessment(assessment_id)

    if not survey:
        return None

    # Check authorization
    if survey.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this survey")

    return SurveyResponse(
        id=survey.get("id", ""),
        assessment_id=survey.get("assessment_id", ""),
        survey=survey.get("survey", {}),
        status=survey.get("status", ""),
        completed_at=str(survey.get("completed_at")) if survey.get("completed_at") else None,
        created_at=str(survey.get("created_at")) if survey.get("created_at") else "",
    )


@router.post("/{assessment_id}/survey", response_model=SurveyResponse)
async def submit_survey(
    assessment_id: str,
    request: SurveySubmitRequest,
    user: dict = Depends(get_current_user),
    survey_repo: SurveyHistoryRepository = Depends(get_survey_repo),
):
    """Submit survey cho một assessment.

    Lưu survey data và chạy analysis ngay để có results khi xem lịch sử.
    """
    user_id = user["uid"]

    logger.info(
        "submit_survey received: stress_level=%d, sleep=%s, work=%s, overtime=%s, deadline=%s",
        request.stress_level, request.sleep_hours, request.working_hours,
        request.overtime_hours, request.has_deadline
    )

    # Build survey data
    survey_data = {
        "sleep_hours": request.sleep_hours,
        "working_hours": request.working_hours,
        "overtime_hours": request.overtime_hours,
        "has_deadline": request.has_deadline,
        "work_days_per_week": request.work_days_per_week,
        "stress_level": request.stress_level,
        "motivation_level": request.motivation_level,
    }

    # Add optional fields if provided
    if request.consecutive_work_days is not None:
        survey_data["consecutive_work_days"] = request.consecutive_work_days
    if request.rest_days is not None:
        survey_data["rest_days"] = request.rest_days
    if request.work_satisfaction is not None:
        survey_data["work_satisfaction"] = request.work_satisfaction
    if request.heart_rate is not None:
        survey_data["heart_rate"] = request.heart_rate

    # Analyze immediately to save with survey
    analysis_service = get_survey_analysis_service()
    result = analysis_service.analyze(survey_data)

    # Build analysis result
    analysis_result = {
        "risk_score": result.risk_score,
        "risk_level": result.risk_level,
        "summary": result.summary,
        "factors": [f.to_dict() for f in result.factors],
        "recommendations": result.recommendations,
        "analysis_version": result.analysis_version,
    }

    # Save survey with analysis result
    doc_id = survey_repo.save(
        assessment_id=assessment_id,
        user_id=user_id,
        survey=survey_data,
        status="completed",
        analysis_result=analysis_result,
    )

    # Get saved survey to return
    saved_survey = survey_repo.get_by_id(doc_id)

    if not saved_survey:
        raise HTTPException(status_code=500, detail="Failed to save survey")

    logger.info(
        "Survey submitted with analysis for assessment %s by user %s, risk=%s",
        assessment_id, user_id, result.risk_level,
    )

    # Trigger BurnoutEngine analysis (async, non-blocking)
    # This ensures burnout_results table gets populated for dashboard analytics
    try:
        from app.modules.burnout.services.burnout_input_builder import BurnoutInputBuilder
        from app.modules.burnout.services.burnout_engine import get_burnout_engine
        from app.modules.burnout.repositories.burnout_repository import get_burnout_repository
        from app.modules.emotion.repositories.emotion_repository import get_emotion_repository
        from app.modules.chat.repositories.chat_history_repository import get_chat_history_repository

        # Load related data
        emotion_repo = get_emotion_repository()
        chat_repo = get_chat_history_repository()
        burnout_repo = get_burnout_repository()

        emotions = emotion_repo.list_by_assessment(assessment_id, limit=100)
        chats = chat_repo.get_messages_by_assessment(assessment_id, limit=100)
        historical_results = burnout_repo.list_by_user(user_id, limit=20)

        # Build BurnoutInput
        builder = BurnoutInputBuilder(
            assessment_id=assessment_id,
            user_id=user_id,
            assessment={"id": assessment_id, "user_id": user_id},
            survey=saved_survey,
            emotions=emotions,
            chats=chats,
            historical_results=historical_results,
        )
        burnout_input = builder.build()

        # Run BurnoutEngine
        engine = get_burnout_engine()
        engine_output = engine.analyze(burnout_input)
        burnout_result = engine_output.burnout

        # Save burnout result
        burnout_doc = {
            "assessment_id": assessment_id,
            "user_id": user_id,
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
            "recommendations": [
                {
                    "title": r.title,
                    "description": r.description,
                    "priority": r.priority,
                    "type": r.type,
                    "target_factor": r.target_factor,
                }
                for r in burnout_result.recommendations
            ],
            "insight": burnout_result.insight,
            "analyzed_at": burnout_result.analyzed_at,
        }
        burnout_repo.save(user_id=user_id, result=burnout_doc, assessment_id=assessment_id)

        logger.info(
            "BurnoutEngine completed for assessment %s: score=%.1f, risk=%s",
            assessment_id, burnout_result.burnout_score, burnout_result.risk_level,
        )
    except Exception as e:
        # Non-blocking: don't fail survey submission if burnout analysis fails
        logger.warning("BurnoutEngine analysis failed for %s: %s", assessment_id, e)

    return SurveyResponse(
        id=saved_survey.get("id", doc_id),
        assessment_id=assessment_id,
        survey=survey_data,
        status="completed",
        completed_at=str(saved_survey.get("completed_at")) if saved_survey.get("completed_at") else None,
        created_at=str(saved_survey.get("created_at")) if saved_survey.get("created_at") else "",
    )


@router.get("/{assessment_id}/survey/status", response_model=dict)
async def get_survey_status(
    assessment_id: str,
    user: dict = Depends(get_current_user),
    survey_repo: SurveyHistoryRepository = Depends(get_survey_repo),
):
    """Lấy trạng thái survey của một assessment."""
    user_id = user["uid"]

    survey = survey_repo.get_by_assessment(assessment_id)

    if not survey:
        return {"assessment_id": assessment_id, "status": "not_started"}

    if survey.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return {
        "assessment_id": assessment_id,
        "status": survey.get("status", "unknown"),
        "has_submitted": survey.get("status") == "completed",
    }


# ==========================================
# Standalone Survey History (no assessment_id)
# ==========================================

survey_standalone_router = APIRouter(prefix="/api/survey", tags=["Survey"])


@survey_standalone_router.get("/history", response_model=list)
async def get_survey_history(
    limit: int = 30,
    user: dict = Depends(get_current_user),
    survey_repo: SurveyHistoryRepository = Depends(get_survey_repo),
):
    """Lấy lịch sử khảo sát của user (standalone, không cần assessment_id)."""
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit phai trong [1, 100]")

    surveys = survey_repo.list_by_user(
        user_id=user["uid"],
        limit=limit,
        completed_only=True,
    )

    return surveys


@survey_standalone_router.get("/{survey_id}", response_model=dict)
async def get_survey_detail(
    survey_id: str,
    user: dict = Depends(get_current_user),
    survey_repo: SurveyHistoryRepository = Depends(get_survey_repo),
):
    """Lấy chi tiết một survey."""
    survey = survey_repo.get_by_id(survey_id)

    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    if survey.get("user_id") != user["uid"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    return survey


# ==========================================
# New: Analyze & Recommendations Endpoints
# ==========================================


@survey_standalone_router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_survey(
    request: AnalyzeRequest,
    user: dict = Depends(get_current_user),
):
    """Phân tích survey data và trả về kết quả.

    Backend chịu trách nhiệm tính toán risk_score, risk_level, factors, summary.

    Flow:
    1. Frontend submit survey data
    2. Backend phân tích và trả về kết quả
    3. Frontend chỉ render kết quả
    """
    # Convert request to dict
    survey_data = {
        "sleep_hours": request.sleep_hours,
        "working_hours": request.working_hours,
        "overtime_hours": request.overtime_hours,
        "has_deadline": request.has_deadline,
        "work_days_per_week": request.work_days_per_week,
        "stress_level": request.stress_level,
        "motivation_level": request.motivation_level,
    }

    # Add optional fields
    if request.consecutive_work_days is not None:
        survey_data["consecutive_work_days"] = request.consecutive_work_days
    if request.rest_days is not None:
        survey_data["rest_days"] = request.rest_days
    if request.work_satisfaction is not None:
        survey_data["work_satisfaction"] = request.work_satisfaction
    if request.heart_rate is not None:
        survey_data["heart_rate"] = request.heart_rate

    # Analyze
    analysis_service = get_survey_analysis_service()
    result = analysis_service.analyze(survey_data)

    logger.info(
        "Survey analyzed for user %s: risk_score=%.1f, risk_level=%s",
        user["uid"],
        result.risk_score,
        result.risk_level,
    )

    return AnalyzeResponse(
        risk_score=result.risk_score,
        risk_level=result.risk_level,
        summary=result.summary,
        factors=[AnalysisFactorResponse(**f.to_dict()) for f in result.factors],
        recommendations=[RecommendationResponse(**r) for r in result.recommendations],
        analysis_version=result.analysis_version,
    )


@survey_standalone_router.post("/recommendations", response_model=RecommendationsResponse)
async def get_recommendations(
    request: RecommendationsRequest,
    user: dict = Depends(get_current_user),
):
    """Tìm địa điểm gợi ý dựa trên analysis result.

    Flow:
    1. Frontend đã có analysis result từ /analyze endpoint
    2. Frontend gửi analysis + location để tìm địa điểm phù hợp
    3. Backend load recommendation rules -> tìm categories -> search places -> rank
    4. Backend trả về danh sách địa điểm với reason

    Lưu ý: Backend không tự quyết định risk_score/risk_level.
    Đó là việc của /analyze endpoint.
    """
    analysis = request.analysis_result

    # Check if location is valid
    if not -90 <= request.latitude <= 90 or not -180 <= request.longitude <= 180:
        raise HTTPException(status_code=400, detail="Invalid coordinates")

    # Get place service
    place_service = get_place_recommendation_service()

    # Check stress level to decide if we need places
    stress_level = 5
    for factor in analysis.factors:
        if factor.code == "HIGH_STRESS":
            stress_level = int(factor.score / 10)
            break

    # If risk is low, return empty
    if analysis.risk_level == "low":
        return RecommendationsResponse(
            places=[],
            count=0,
            searched_location={"latitude": request.latitude, "longitude": request.longitude},
            address=request.address,
            message="Tình trạng ổn định! Hãy duy trì lối sống lành mạnh.",
        )

    try:
        # Search places for survey
        result = place_service.search_places_for_survey(
            user_id=user["uid"],
            latitude=request.latitude,
            longitude=request.longitude,
            stress_level=stress_level,
            radius_meters=request.radius_meters,
            limit=request.limit,
            address=request.address,
        )

        # Transform to response format
        places = []
        for place in result.get("places", []):
            places.append(PlaceRecommendationResponse(
                place_id=place.get("place_id", ""),
                name=place.get("name", ""),
                category=place.get("category", "place"),
                reason=place.get("reason", ""),
                address=place.get("address"),
                distance=place.get("distance"),
                distance_meters=place.get("distance"),
                categories=place.get("categories", []),
                opening_hours=place.get("opening_hours"),
                phone=place.get("phone"),
                website=place.get("website"),
                rating=place.get("rating"),
            ))

        return RecommendationsResponse(
            places=places,
            count=len(places),
            searched_location={
                "latitude": request.latitude,
                "longitude": request.longitude,
            },
            address=request.address or f"{request.latitude}, {request.longitude}",
            message=result.get("message", f"Tìm thấy {len(places)} địa điểm"),
        )

    except Exception as e:
        logger.error("Failed to search places: %s", e)
        raise HTTPException(status_code=500, detail="Failed to search places")
