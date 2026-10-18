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
from app.modules.survey.services.survey_ai_interpreter import (
    get_survey_ai_interpreter,
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
    - Survey CHỈ nhận raw answers
    - Hỗ trợ cả cấu trúc STA (Exhaustion, Disengagement, Job Demands, Recovery, Quick Overload)
      lẫn flattened/legacy fields.
    """
    # STA Structured Groups
    exhaustion: Optional[Dict[str, Any]] = None
    disengagement: Optional[Dict[str, Any]] = None
    job_demands: Optional[Dict[str, Any]] = None
    recovery: Optional[Dict[str, Any]] = None
    quick_overload_data: Optional[Dict[str, Any]] = None
    work_changes: Optional[Dict[str, Any]] = None

    # STA Flattened Daily Check-in fields
    sleep_hours: Optional[float] = Field(default=None, ge=0.0, le=24.0, description="Số giờ ngủ đêm qua")
    recovery_score: Optional[int] = Field(default=None, ge=1, le=5, description="Cảm nhận hồi phục (1-5)")
    quick_overload: Optional[int] = Field(default=None, ge=1, le=5, description="Mức độ quá tải (1-5)")
    overload_reasons: List[str] = Field(default_factory=list, description="Lý do quá tải")
    has_overtime_today: Optional[bool] = Field(default=None, description="Có làm thêm hôm nay không")
    overtime_hours_today: Optional[float] = Field(default=None, ge=0.0, le=24.0, description="Số giờ tăng ca hôm nay")
    current_deadline_pressure: Optional[str] = Field(default=None, description="Áp lực deadline (low, medium, high, extreme)")

    # Legacy fields (optional with defaults for backward compatibility)
    working_hours: Optional[float] = Field(default=8.0, ge=0.0, le=24.0, description="Số giờ làm việc/ngày")
    overtime_hours: Optional[int] = Field(default=0, ge=0, le=24, description="Số giờ tăng ca")
    has_deadline: Optional[str] = Field(default="medium", description="Mức độ deadline")
    work_days_per_week: Optional[int] = Field(default=5, ge=1, le=7, description="Số ngày làm việc/tuần")
    stress_level: Optional[int] = Field(default=5, ge=1, le=10, description="Mức độ stress (1-10)")
    motivation_level: Optional[int] = Field(default=5, ge=1, le=10, description="Mức độ động lực (1-10)")
    consecutive_work_days: Optional[int] = Field(default=None, ge=0, le=30)
    rest_days: Optional[int] = Field(default=None, ge=0, le=7)
    work_satisfaction: Optional[int] = Field(default=None, ge=1, le=10)
    heart_rate: Optional[int] = Field(default=None, ge=30, le=220)


class PeriodicSurveySubmitRequest(BaseModel):
    """Request body cho POST /api/survey/periodic."""
    job_resources: Dict[str, Optional[float]] = Field(..., description="JR1-JR4 scores (1-5)")
    six_areas: Dict[str, Optional[float]] = Field(..., description="Six Areas scores (1-5)")


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
    daily_questions: Optional[list] = None
    periodic_questions: Optional[list] = None


# ==========================================
# New: Analyze Request/Response Models
# ==========================================

class AnalyzeRequest(BaseModel):
    """Request body cho POST /api/survey/analyze."""

    # Optional legacy fields with defaults
    sleep_hours: Optional[float] = Field(default=7.0, ge=0.0, le=24.0, description="Số giờ ngủ")
    working_hours: Optional[float] = Field(default=8.0, ge=0.0, le=24.0, description="Số giờ làm việc/ngày")
    overtime_hours: Optional[int] = Field(default=0, ge=0, le=24, description="Số giờ tăng ca")
    has_deadline: Optional[str] = Field(default="medium", description="Mức độ deadline: low/medium/high/extreme")
    work_days_per_week: Optional[int] = Field(default=5, ge=1, le=7, description="Số ngày làm việc/tuần")
    stress_level: Optional[int] = Field(default=5, ge=1, le=10, description="Mức độ stress (1-10)")
    motivation_level: Optional[int] = Field(default=5, ge=1, le=10, description="Mức độ động lực (1-10)")

    # Optional fields
    consecutive_work_days: Optional[int] = Field(default=None, ge=0, le=30)
    rest_days: Optional[int] = Field(default=None, ge=0, le=7)
    work_satisfaction: Optional[int] = Field(default=None, ge=1, le=10)
    heart_rate: Optional[int] = Field(default=None, ge=30, le=220)

    # STA Scientific Dimension Groups (OLBI & JD-R)
    exhaustion: Optional[Dict[str, Any]] = None
    disengagement: Optional[Dict[str, Any]] = None
    job_demands: Optional[Dict[str, Any]] = None
    recovery: Optional[Dict[str, Any]] = None
    quick_overload_data: Optional[Dict[str, Any]] = None
    work_changes: Optional[Dict[str, Any]] = None


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


class AIInsightResponse(BaseModel):
    """Kết quả phân tích định tính từ Gemini AI."""

    current_state_text: str
    change_text: str
    contributing_factors_text: str
    reflection_question: str
    suggested_chat_prompt: str


class AnalyzeResponse(BaseModel):
    """Response cho POST /api/survey/analyze."""

    risk_score: float
    risk_level: str  # low, medium, high, critical
    summary: str
    factors: List[AnalysisFactorResponse]
    recommendations: List[RecommendationResponse]
    analysis_version: str
    ai_insight: Optional[AIInsightResponse] = None


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

class DimensionStats(BaseModel):
    current: Optional[float] = None
    average: Optional[float] = None
    trend: str = 'stable'
    values: List[float] = Field(default_factory=list)

class RollingStatsResponse(BaseModel):
    user_id: str
    period_days: int = 7
    total_surveys: int = 0
    dimensions: Dict[str, DimensionStats] = Field(default_factory=dict)
    overall_trend: str = 'stable'
    computed_at: str = ''

class AlertItem(BaseModel):
    type: str
    severity: str
    title: str
    message: str
    consecutive_days: int = 0
    details: Dict[str, Any] = Field(default_factory=dict)

class AlertsResponse(BaseModel):
    alerts: List[AlertItem] = Field(default_factory=list)
    has_critical: bool = False

# ==========================================
# Dependency
# ==========================================

def get_survey_repo() -> SurveyHistoryRepository:
    return get_survey_history_repository()


# ==========================================
# Endpoints
# ==========================================

@router.get("/questions", response_model=SurveyQuestionsResponse)
@router.get("/{assessment_id}/survey/questions", response_model=SurveyQuestionsResponse)
async def get_survey_questions(
    assessment_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Lấy danh sách câu hỏi survey (cả daily và periodic)."""
    return SurveyQuestionsResponse(
        questions=SurveyQuestions.DAILY_QUESTIONS,
        daily_questions=SurveyQuestions.DAILY_QUESTIONS,
        periodic_questions=SurveyQuestions.PERIODIC_QUESTIONS,
    )


@router.post("/periodic")
async def submit_periodic_survey(
    request: PeriodicSurveySubmitRequest,
    user: dict = Depends(get_current_user),
    survey_repo: SurveyHistoryRepository = Depends(get_survey_repo),
):
    """Submit khảo sát định kỳ (Job Resources + Six Areas)."""
    user_id = user["uid"]
    doc_id = survey_repo.save_periodic_survey(
        user_id=user_id,
        job_resources=request.job_resources,
        six_areas=request.six_areas,
    )
    return {"id": doc_id, "status": "success", "message": "Periodic survey saved successfully"}


@router.get("/periodic/latest")
async def get_latest_periodic_survey(
    user: dict = Depends(get_current_user),
    survey_repo: SurveyHistoryRepository = Depends(get_survey_repo),
):
    """Lấy kết quả khảo sát định kỳ gần nhất."""
    user_id = user["uid"]
    result = survey_repo.get_latest_periodic_survey(user_id)
    return result or {}


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
    survey_data = request.model_dump(exclude_none=True)

    # Legacy field sync if provided
    if "sleep_hours" in survey_data and "sleep_hour" not in survey_data:
        survey_data["sleep_hour"] = survey_data["sleep_hours"]
    if "working_hours" in survey_data and "working_hour" not in survey_data:
        survey_data["working_hour"] = survey_data["working_hours"]

    # Best-effort analysis for backward compatibility
    analysis_result = None
    try:
        analysis_service = get_survey_analysis_service()
        result = analysis_service.analyze(survey_data)
        if result:
            analysis_result = {
                "risk_score": getattr(result, "risk_score", 0),
                "risk_level": getattr(result, "risk_level", "low"),
                "summary": getattr(result, "summary", ""),
                "factors": [f.to_dict() for f in getattr(result, "factors", [])],
                "recommendations": getattr(result, "recommendations", []),
                "analysis_version": getattr(result, "analysis_version", "v2.0"),
            }
    except Exception as e:
        logger.warning("Survey analysis fallback ignored: %s", e)

    # Save survey
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


@survey_standalone_router.get('/rolling-stats', response_model=RollingStatsResponse)
async def get_rolling_stats(days: int = 7, user: dict = Depends(get_current_user)):
    """Lấy thống kê trung bình trượt (rolling average) và trend của user."""
    survey_repo = get_survey_history_repository()
    surveys = survey_repo.get_recent_completed_surveys(user['uid'], limit=days * 2)
    stats = SurveyAnalysisService.compute_rolling_stats(surveys, days=days)
    stats['user_id'] = user['uid']
    return stats


@survey_standalone_router.get('/alerts', response_model=AlertsResponse)
async def get_alerts(user: dict = Depends(get_current_user)):
    """Lấy danh sách cảnh báo Allostatic Overload của user."""
    survey_repo = get_survey_history_repository()
    surveys = survey_repo.get_recent_completed_surveys(user['uid'], limit=7)
    alerts = []
    overload = SurveyAnalysisService.check_allostatic_overload(surveys)
    if overload:
        alerts.append(overload)
    return {'alerts': alerts, 'has_critical': any(a.get('severity') == 'critical' for a in alerts)}


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
    survey_repo: SurveyHistoryRepository = Depends(get_survey_repo),
):
    """Phân tích survey data và trả về kết quả cá nhân hóa đa ngữ cảnh.

    Backend chịu trách nhiệm tính toán risk_score, risk_level, factors, summary và AI Qualitative Insight.
    """
    rec_data = request.recovery or {}
    quick_data = request.quick_overload_data or {}

    # Convert request to dict
    survey_data = {
        "sleep_hours": request.sleep_hours,
        "working_hours": request.working_hours,
        "overtime_hours": request.overtime_hours,
        "has_deadline": request.has_deadline,
        "work_days_per_week": request.work_days_per_week,
        "stress_level": request.stress_level,
        "motivation_level": request.motivation_level,
        "exhaustion": request.exhaustion,
        "disengagement": request.disengagement,
        "job_demands": request.job_demands,
        "recovery": request.recovery,
        "quick_overload_data": request.quick_overload_data,
        "work_changes": request.work_changes,
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

    # Load past survey history for temporal trend comparison
    prev_comparison = "Đây là lần đầu tiên người dùng làm khảo sát."
    trend_summary = "Chưa có đủ lịch sử khảo sát để so sánh xu hướng."
    try:
        recent_surveys = survey_repo.get_recent_completed_surveys(user["uid"], limit=5)
        if recent_surveys:
            prev_doc = recent_surveys[0]
            prev_s = prev_doc.get("survey") or {}
            prev_sleep = prev_s.get("sleep_hours")
            prev_rec = (prev_s.get("recovery") or {}).get("recovery_score") if isinstance(prev_s.get("recovery"), dict) else prev_s.get("recovery_score")
            prev_overload = (prev_s.get("quick_overload_data") or {}).get("rating") if isinstance(prev_s.get("quick_overload_data"), dict) else prev_s.get("quick_overload")

            comparison_parts = []
            if prev_sleep is not None:
                comparison_parts.append(f"Giấc ngủ lần trước: {prev_sleep}h (lần này: {request.sleep_hours}h)")
            if prev_rec is not None:
                comparison_parts.append(f"Điểm phục hồi lần trước: {prev_rec}/5 (lần này: {rec_data.get('recovery_score', 3)}/5)")
            if prev_overload is not None:
                comparison_parts.append(f"Mức quá tải lần trước: {prev_overload}/5 (lần này: {quick_data.get('rating', 2)}/5)")

            if comparison_parts:
                prev_comparison = "So sánh với lần khảo sát trước: " + ", ".join(comparison_parts)

            count = len(recent_surveys) + 1
            trend_summary = f"Người dùng đã thực hiện tổng cộng {count} lần khảo sát. Dữ liệu xu hướng ghi nhận sự thay đổi thực tế qua từng lần check-in."
    except Exception as e:
        logger.warning("Failed to fetch historical survey trend: %s", e)

    # Resolve Industry Context & Cross-Metric Archetype
    job_title = None
    industry_code = None
    try:
        from app.modules.user.services.user_profile_service import get_profile_service
        p = get_profile_service().get_profile(user["uid"]) or {}
        job_title = p.get("job_title")
        industry_code = p.get("industry_code")
    except Exception:
        pass

    from app.modules.burnout.helpers.industry_archetypes import resolve_industry_context
    from app.modules.burnout.helpers.matrix_resolver import resolve_burnout_archetype

    ind_ctx = resolve_industry_context(industry_code=industry_code, job_title=job_title)

    ex_score = 3.0
    if request.exhaustion:
        vals = [float(v) for v in request.exhaustion.values() if v is not None]
        if vals:
            ex_score = sum(vals) / len(vals)
    else:
        ex_score = max(1.0, min(5.0, (request.stress_level or 5) / 2.0))

    dis_score = 2.5
    if request.disengagement:
        vals = [float(v) for v in request.disengagement.values() if v is not None]
        if vals:
            dis_score = sum(vals) / len(vals)
    else:
        mot = float(request.motivation_level or 5)
        dis_score = max(1.0, min(5.0, (11.0 - mot) / 2.0))

    daily_stats = {
        "job_demands": 3.0,
        "sleep_hours": request.sleep_hours,
        "recovery_score": rec_data.get("recovery_score", 3),
        "quick_overload": quick_data.get("rating", 2),
        "overload_reasons": quick_data.get("reasons", []),
        "overtime_hours": request.overtime_hours or 0.0,
    }
    archetype = resolve_burnout_archetype(ex_score, dis_score, daily_stats)

    evidence = {
        "exhaustion_level": result.risk_level,
        "disengagement_level": result.risk_level,
        "sleep_hours": request.sleep_hours,
        "recovery_score": rec_data.get("recovery_score", 3),
        "quick_overload": quick_data.get("rating", 2),
        "overload_reasons": quick_data.get("reasons", []),
        "other_reason": quick_data.get("other_reason", ""),
        "previous_comparison": prev_comparison,
        "trend_summary": trend_summary,
        # Industry & Archetype context
        "job_title": job_title or ind_ctx.typical_roles[0],
        "industry_name": ind_ctx.name,
        "industry_icon": ind_ctx.icon,
        "vocabulary_hints": ind_ctx.vocabulary_hints,
        "stressors_context": ind_ctx.stressors_context,
        "reflection_theme": ind_ctx.reflection_theme,
        "archetype_name": f"{archetype.icon} {archetype.name}",
        "empathy_direction": archetype.empathy_direction,
        "ai_prompt_instruction": archetype.ai_prompt_instruction,
    }
    ai_insight_result = get_survey_ai_interpreter().generate_insight(evidence)

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
        ai_insight=AIInsightResponse(**ai_insight_result.to_dict()),
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

