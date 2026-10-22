"""
==============================================================
File: dashboard.py

Dashboard Routes - API endpoints cho Dashboard.

GET /api/v1/dashboard/overview      - Tổng quan
GET /api/v1/dashboard/burnout-history - Lịch sử burnout
GET /api/v1/dashboard/emotion-history - Lịch sử emotion

Lưu ý: Dashboard CHỈ đọc dữ liệu, KHÔNG tính toán lại.
==============================================================
"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from google.cloud import firestore

from app.core.deps import get_current_user
from app.core.firebase import get_firebase
from app.modules.burnout.repositories.burnout_repository import (
    get_burnout_repository,
)
from app.modules.emotion.repositories.emotion_repository import (
    get_emotion_repository,
)
from app.modules.assessment.repositories.assessment_session_repository import (
    get_assessment_session_repository,
)
from app.modules.survey.repositories.survey_history_repository import (
    get_survey_history_repository,
)
from app.modules.chat.repositories.chat_history_repository import (
    get_chat_history_repository,
)
from app.modules.burnout.helpers import ChatAnalysisAggregate

logger = logging.getLogger("burnout.dashboard.routes")

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


class OlbiHistoryPoint(BaseModel):
    id: str
    assessment_id: Optional[str] = None
    sequence: int
    completed_at: str
    timestamp: int
    exhaustion: float
    disengagement: float
    change_from_previous: Dict[str, Optional[float]]


class OlbiComparison(BaseModel):
    baseline: Optional[float] = None
    latest: Optional[float] = None
    change_from_baseline: Optional[float] = None
    change_from_previous: Optional[float] = None


class OlbiProgressResponse(BaseModel):
    period_days: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    scale_max: int = 4
    total_records: int
    visible_records: int
    excluded_records: int
    points: list[OlbiHistoryPoint]
    baseline_at: Optional[str] = None
    latest_at: Optional[str] = None
    next_due_at: Optional[str] = None
    comparisons: Dict[str, OlbiComparison]
    direction: str
    summary: str


@router.get("/olbi-history", response_model=OlbiProgressResponse)
async def get_olbi_history(
    days: Optional[int] = Query(default=None, ge=1, le=3650),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    user: dict = Depends(get_current_user),
):
    """Authenticated user's version-compatible OLBI history in the shared dashboard window."""
    from app.modules.dashboard.services.olbi_progress import build_olbi_progress
    from app.modules.dashboard.services.date_window import date_window
    try:
        date_window(start_date, end_date, days)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    records = await asyncio.to_thread(
        get_survey_history_repository().get_completed_questionnaires, user["uid"])
    return build_olbi_progress(records, days=days, start_date=start_date, end_date=end_date)


# ==========================================
# Helper Functions
# ==========================================

def _normalize_datetime(dt):
    """Normalize datetime to offset-naive for comparison."""
    if dt is None:
        return None
    if hasattr(dt, 'to_datetime'):
        dt = dt.to_datetime()
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except:
            return None
    if isinstance(dt, datetime):
        # Strip timezone info for consistent comparison
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    return None


# ==========================================
# Response Models
# ==========================================

class LatestBurnoutResponse(BaseModel):
    """Latest burnout result."""

    assessment_id: str
    burnout_score: float
    risk_level: str
    trend: str
    data_completeness: float
    analyzed_at: Optional[str] = None


class FactorSummary(BaseModel):
    """Factor summary."""

    factor: str
    label: str
    percentage: float
    sub_score: float


class RecommendationSummary(BaseModel):
    """Recommendation summary."""

    title: str
    priority: str
    target_factor: Optional[str] = None


class DashboardOverviewResponse(BaseModel):
    """Response cho /overview endpoint."""

    user_id: str

    # Latest burnout
    latest_burnout: Optional[LatestBurnoutResponse] = None

    # Trend info
    total_assessments: int = 0
    assessments_this_month: int = 0
    trend: str = "insufficient_data"

    # Factor summary (top 3)
    top_factors: list = Field(default_factory=list)

    # Latest recommendations (top 3)
    latest_recommendations: list = Field(default_factory=list)

    # Stats
    avg_burnout_score: Optional[float] = None
    burnout_history_count: int = 0
    emotion_history_count: int = 0

    # Last updated
    last_updated: Optional[str] = None


class BurnoutHistoryItem(BaseModel):
    """Một item trong burnout history."""

    assessment_id: str
    burnout_score: float
    risk_level: str
    trend: str
    data_completeness: float
    analyzed_at: Optional[str] = None


class BurnoutHistoryResponse(BaseModel):
    """Response cho /burnout-history endpoint."""

    user_id: str
    history: list
    count: int
    total: int


class EmotionHistoryItem(BaseModel):
    """Một item trong emotion history."""

    id: str
    dominant_emotion: str
    confidence: float
    assessment_id: Optional[str] = None
    analyzed_at: Optional[str] = None


class EmotionHistoryResponse(BaseModel):
    """Response cho /emotion-history endpoint."""

    user_id: str
    emotions: list
    count: int
    total: int

    # Aggregated stats
    dominant_emotions: dict = Field(default_factory=dict)
    avg_confidence: Optional[float] = None


# ==========================================
# Dependencies
# ==========================================

def get_burnout_repo():
    return get_burnout_repository()


def get_emotion_repo():
    return get_emotion_repository()


def get_assessment_repo():
    return get_assessment_session_repository()


def get_survey_repo():
    return get_survey_history_repository()


def get_chat_repo():
    return get_chat_history_repository()


# ==========================================
# GET /api/v1/dashboard/overview
# ==========================================

@router.get("/overview", response_model=DashboardOverviewResponse)
async def get_dashboard_overview(
    user: dict = Depends(get_current_user),
):
    """Lấy tổng quan dashboard.

    Dashboard CHỈ đọc dữ liệu, KHÔNG tính toán lại.
    """
    user_id = user["uid"]

    burnout_repo = get_burnout_repo()
    emotion_repo = get_emotion_repo()
    assessment_repo = get_assessment_repo()

    # 1. Load burnout history
    burnout_history = burnout_repo.list_by_user(user_id, limit=50)

    # 2. Load emotion count
    emotion_count = emotion_repo.count_by_user(user_id)

    # 3. Load assessment count
    assessments = assessment_repo.list_by_user(user_id, limit=100)
    total_assessments = len(assessments)

    # Count assessments this month
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    assessments_this_month = sum(
        1 for a in assessments
        if a.get("created_at") and
        (isinstance(a["created_at"], str) and
         datetime.fromisoformat(a["created_at"].replace("Z", "+00:00")) >= month_start or
         isinstance(a["created_at"], datetime) and a["created_at"] >= month_start)
    )

    # 4. Get latest burnout
    latest_burnout = None
    top_factors = []
    latest_recommendations = []
    trend = "insufficient_data"
    avg_burnout_score = None

    if burnout_history:
        latest = burnout_history[0]
        latest_burnout = LatestBurnoutResponse(
            assessment_id=latest.get("assessment_id", ""),
            burnout_score=latest.get("burnout_score", 0.0),
            risk_level=latest.get("risk_level", "unknown"),
            trend=latest.get("trend", "insufficient_data"),
            data_completeness=latest.get("data_completeness", 0.0),
            analyzed_at=str(latest.get("analyzed_at")) if latest.get("analyzed_at") else None,
        )

        # Get trend
        trend = latest.get("trend", "insufficient_data")

        # Get top factors
        factors = latest.get("factors", [])
        for f in factors[:3]:
            top_factors.append(FactorSummary(
                factor=f.get("factor", ""),
                label=f.get("details", {}).get("label", f.get("factor", "")),
                percentage=f.get("percentage", 0.0),
                sub_score=f.get("details", {}).get("sub_score", 0.0) if f.get("details") else 0.0,
            ).model_dump())

        # Get latest recommendations
        recommendations = latest.get("recommendations", [])
        for r in recommendations[:3]:
            latest_recommendations.append(RecommendationSummary(
                title=r.get("title", ""),
                priority=r.get("priority", "medium"),
                target_factor=r.get("target_factor"),
            ).model_dump())

        # Calculate average
        scores = [b.get("burnout_score", 0.0) for b in burnout_history if b.get("burnout_score")]
        if scores:
            avg_burnout_score = round(sum(scores) / len(scores), 1)

    return DashboardOverviewResponse(
        user_id=user_id,
        latest_burnout=latest_burnout,
        total_assessments=total_assessments,
        assessments_this_month=assessments_this_month,
        trend=trend,
        top_factors=top_factors,
        latest_recommendations=latest_recommendations,
        avg_burnout_score=avg_burnout_score,
        burnout_history_count=len(burnout_history),
        emotion_history_count=emotion_count,
        last_updated=str(datetime.utcnow()),
    )


# ==========================================
# GET /api/v1/dashboard/burnout-history
# ==========================================

@router.get("/burnout-history", response_model=BurnoutHistoryResponse)
async def get_burnout_history(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
):
    """Lấy lịch sử burnout.

    Dashboard CHỈ đọc dữ liệu.
    """
    user_id = user["uid"]

    burnout_repo = get_burnout_repo()

    # Load all (for total count)
    all_history = burnout_repo.list_by_user(user_id, limit=1000)
    total = len(all_history)

    # Apply pagination
    history = all_history[offset:offset + limit]

    # Build response
    items = []
    for b in history:
        items.append(BurnoutHistoryItem(
            assessment_id=b.get("assessment_id", ""),
            burnout_score=b.get("burnout_score", 0.0),
            risk_level=b.get("risk_level", "unknown"),
            trend=b.get("trend", "insufficient_data"),
            data_completeness=b.get("data_completeness", 0.0),
            analyzed_at=str(b.get("analyzed_at")) if b.get("analyzed_at") else None,
        ).model_dump())

    return BurnoutHistoryResponse(
        user_id=user_id,
        history=items,
        count=len(items),
        total=total,
    )


# ==========================================
# GET /api/v1/dashboard/emotion-history
# ==========================================

@router.get("/emotion-history", response_model=EmotionHistoryResponse)
async def get_emotion_history(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
):
    """Lấy lịch sử emotion.

    Dashboard CHỈ đọc dữ liệu.
    """
    user_id = user["uid"]

    emotion_repo = get_emotion_repo()

    # Load emotions
    emotions = emotion_repo.list_by_user(user_id, limit=1000)
    total = len(emotions)

    # Apply pagination
    emotions_page = emotions[offset:offset + limit]

    # Build response
    items = []
    dominant_counts: dict = {}
    total_confidence = 0.0
    confidence_count = 0

    for e in emotions_page:
        items.append(EmotionHistoryItem(
            id=e.get("id", ""),
            dominant_emotion=e.get("dominant_emotion", "neutral"),
            confidence=float(e.get("confidence", 0.0)),
            assessment_id=e.get("assessment_id"),
            analyzed_at=str(e.get("analyzed_at")) if e.get("analyzed_at") else None,
        ).model_dump())

        # Aggregate
        dom = e.get("dominant_emotion", "neutral")
        dominant_counts[dom] = dominant_counts.get(dom, 0) + 1

        conf = e.get("confidence")
        if conf is not None:
            total_confidence += float(conf)
            confidence_count += 1

    avg_confidence = round(total_confidence / confidence_count, 2) if confidence_count > 0 else None

    return EmotionHistoryResponse(
        user_id=user_id,
        emotions=items,
        count=len(items),
        total=total,
        dominant_emotions=dominant_counts,
        avg_confidence=avg_confidence,
    )


# ==========================================
# GET /api/v1/dashboard/analytics
# ==========================================

class UserAnalyticsResponse(BaseModel):
    """Response cho /analytics endpoint - User Dashboard Analytics."""

    user_id: str

    # Overview stats
    total_assessments: int = 0
    completed_assessments: int = 0
    assessment_completion_rate: float = 0.0
    assessments_this_month: int = 0

    # Burnout stats
    total_burnout_analyses: int = 0
    avg_burnout_score: Optional[float] = None
    current_risk_level: Optional[str] = None
    current_trend: str = "insufficient_data"
    burnout_trend: list = Field(default_factory=list)

    # Emotion stats
    total_emotion_analyses: int = 0
    avg_confidence: Optional[float] = None
    emotion_distribution: dict = Field(default_factory=dict)
    emotions_this_month: int = 0
    emotions_trend: list = Field(default_factory=list)

    # Activity stats
    login_count: int = 0
    last_login: Optional[str] = None
    login_trend: list = Field(default_factory=list)

    # Assessment trends
    assessments_trend: list = Field(default_factory=list)

    # AI Quality metrics
    unknown_emotion_count: int = 0
    unknown_rate: float = 0.0
    success_rate: float = 0.0

    # Recent history (last 10)
    recent_assessments: list = Field(default_factory=list)
    recent_emotions: list = Field(default_factory=list)


@router.get("/analytics", response_model=UserAnalyticsResponse)
async def get_user_dashboard_analytics(
    user: dict = Depends(get_current_user),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    """Lấy analytics tổng hợp cho user dashboard.

    Endpoint này cung cấp data cho Analysis tab trong ProfilePage.
    """
    from app.modules.dashboard.services.date_window import date_window, in_window, calendar_day
    try:
        window = date_window(start_date, end_date, days=90)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    first_day = calendar_day(window[0])
    trend_days = [(first_day + timedelta(days=i)).isoformat() for i in range(window[2])]
    user_id = user["uid"]

    burnout_repo = get_burnout_repo()
    emotion_repo = get_emotion_repo()
    assessment_repo = get_assessment_repo()

    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)

    # === LOAD REPOSITORIES CONCURRENTLY ===
    burnout_history, emotions, assessments = await asyncio.gather(
        asyncio.to_thread(burnout_repo.list_by_user, user_id, 100),
        asyncio.to_thread(emotion_repo.list_by_user, user_id, 500),
        asyncio.to_thread(assessment_repo.list_by_user, user_id, 100),
    )

    if start_date is not None:
        burnout_history = [item for item in burnout_history if in_window(item.get("analyzed_at"), window)]
        emotions = [item for item in emotions if in_window(item.get("created_at"), window)]
        assessments = [item for item in assessments if in_window(item.get("created_at"), window)]

    # === BURNOUT DATA ===
    total_burnout = len(burnout_history)

    # Calculate avg burnout score
    scores = [b.get("burnout_score", 0) for b in burnout_history if b.get("burnout_score")]
    avg_burnout = round(sum(scores) / len(scores), 1) if scores else None

    # Current risk level (latest burnout)
    current_risk = None
    current_trend = "insufficient_data"
    if burnout_history:
        current_risk = burnout_history[0].get("risk_level", "unknown")
        current_trend = burnout_history[0].get("trend", "insufficient_data")

    # Build burnout trend (daily for last 90 days)
    burnout_daily: Dict[str, int] = {}
    for b in burnout_history:
        analyzed = b.get("analyzed_at")
        if analyzed:
            analyzed_dt = _normalize_datetime(analyzed)
            if analyzed_dt:
                date_key = calendar_day(analyzed).isoformat()
                burnout_daily[date_key] = burnout_daily.get(date_key, 0) + 1

    burnout_trend = []
    for day in trend_days:
        burnout_trend.append({"date": day, "count": burnout_daily.get(day, 0)})

    # === EMOTION DATA ===
    total_emotions = len(emotions)

    # Calculate avg confidence
    confidences = [e.get("confidence", 0) for e in emotions if e.get("confidence")]
    avg_confidence = round(sum(confidences) / len(confidences), 3) if confidences else None

    # Emotion distribution
    emotion_dist: Dict[str, int] = {}
    unknown_count = 0
    for e in emotions:
        dom = e.get("dominant_emotion", "neutral")
        emotion_dist[dom] = emotion_dist.get(dom, 0) + 1
        if dom in ["unknown", "Other"]:
            unknown_count += 1

    # Emotions this month
    emotions_this_month = 0
    for e in emotions:
        created = _normalize_datetime(e.get("created_at"))
        if created and created >= month_start:
            emotions_this_month += 1

    # === ASSESSMENT DATA ===
    total_assessments = len(assessments)
    completed = sum(1 for a in assessments if a.get("status") == "completed")
    completion_rate = round((completed / total_assessments * 100), 1) if total_assessments > 0 else 0.0

    # Assessments this month
    assessments_this_month = 0
    for a in assessments:
        created = _normalize_datetime(a.get("created_at"))
        if created and created >= month_start:
            assessments_this_month += 1

    # Recent assessments (chỉ lấy completed)
    recent_assessments = []
    completed_assessments = [a for a in assessments if a.get("status") == "completed"]
    for a in sorted(completed_assessments, key=lambda x: x.get("completed_at", x.get("created_at", "")), reverse=True)[:10]:
        recent_assessments.append({
            "id": a.get("id", ""),
            "status": a.get("status", "unknown"),
            "created_at": str(a.get("created_at")) if a.get("created_at") else None,
            "completed_at": str(a.get("completed_at")) if a.get("completed_at") else None,
        })

    # Recent emotions (last 10)
    recent_emotions = []
    for e in sorted(emotions, key=lambda x: x.get("created_at", ""), reverse=True)[:10]:
        recent_emotions.append({
            "id": e.get("id", ""),
            "dominant_emotion": e.get("dominant_emotion", "unknown"),
            "confidence": e.get("confidence", 0),
            "created_at": str(e.get("created_at")) if e.get("created_at") else None,
        })

    # === LOGIN DATA ===
    # Try to get login count from login_activities
    login_count = 0
    last_login = None
    login_docs = []  # Initialize to avoid NameError if query fails
    try:
        db = get_firebase().db
        login_query = (
            db.collection("login_activities")
            .where("user_id", "==", user_id)
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(100)
        )
        login_docs = list(login_query.stream())
        if start_date is not None:
            login_docs = [doc for doc in login_docs if in_window(doc.to_dict().get("timestamp"), window)]
        login_count = len(login_docs)
        if login_docs:
            last_doc = login_docs[0].to_dict()
            last_login = str(last_doc.get("timestamp")) if last_doc.get("timestamp") else None
    except Exception as e:
        logger.warning(f"Could not fetch login activities: {e}")
        login_docs = []  # Reset to empty list on error

    # === AI QUALITY METRICS ===
    unknown_rate = round((unknown_count / total_emotions * 100), 1) if total_emotions > 0 else 0.0
    success_rate = round(((total_emotions - unknown_count) / total_emotions * 100), 1) if total_emotions > 0 else 0.0

    # === BUILD TRENDS (90 days) ===
    # Login trend
    login_daily: Dict[str, int] = {}
    try:
        for doc in login_docs:
            data = doc.to_dict()
            ts = data.get("timestamp")
            if ts:
                if hasattr(ts, 'to_datetime'):
                    ts = ts.to_datetime()
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except:
                        continue
                if isinstance(ts, datetime):
                    date_key = calendar_day(ts).isoformat()
                    login_daily[date_key] = login_daily.get(date_key, 0) + 1
    except Exception as e:
        logger.warning(f"Error building login trend: {e}")

    login_trend = []
    for day in trend_days:
        login_trend.append({"date": day, "count": login_daily.get(day, 0)})

    # Emotions trend
    emotions_daily: Dict[str, int] = {}
    for e in emotions:
        created = e.get("created_at")
        if created:
            if hasattr(created, 'to_datetime'):
                created = created.to_datetime()
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except:
                    continue
            if isinstance(created, datetime):
                date_key = calendar_day(created).isoformat()
                emotions_daily[date_key] = emotions_daily.get(date_key, 0) + 1

    emotions_trend = []
    for day in trend_days:
        emotions_trend.append({"date": day, "count": emotions_daily.get(day, 0)})

    # Assessments trend
    assessments_daily: Dict[str, int] = {}
    for a in assessments:
        created = a.get("created_at")
        if created:
            if hasattr(created, 'to_datetime'):
                created = created.to_datetime()
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except:
                    continue
            if isinstance(created, datetime):
                date_key = calendar_day(created).isoformat()
                assessments_daily[date_key] = assessments_daily.get(date_key, 0) + 1

    assessments_trend = []
    for day in trend_days:
        assessments_trend.append({"date": day, "count": assessments_daily.get(day, 0)})

    return UserAnalyticsResponse(
        user_id=user_id,
        total_assessments=total_assessments,
        completed_assessments=completed,
        assessment_completion_rate=completion_rate,
        assessments_this_month=assessments_this_month,
        assessments_trend=assessments_trend,
        total_burnout_analyses=total_burnout,
        avg_burnout_score=avg_burnout,
        current_risk_level=current_risk,
        current_trend=current_trend,
        burnout_trend=burnout_trend,
        total_emotion_analyses=total_emotions,
        avg_confidence=avg_confidence,
        emotion_distribution=emotion_dist,
        emotions_this_month=emotions_this_month,
        emotions_trend=emotions_trend,
        login_count=login_count,
        last_login=last_login,
        login_trend=login_trend,
        unknown_emotion_count=unknown_count,
        unknown_rate=unknown_rate,
        success_rate=success_rate,
        recent_assessments=recent_assessments,
        recent_emotions=recent_emotions,
    )


# ==========================================
# BURNOUT ANALYTICS ENDPOINTS
# ==========================================

# Factor labels mapping
FACTOR_LABELS = {
    "sleep": "Giấc ngủ",
    "workload": "Công việc",
    "stress": "Stress",
    "emotion": "Cảm xúc",
    "behavior": "Hành vi",
}


class BurnoutFactorResponse(BaseModel):
    """Response cho một factor."""
    key: str = Field(..., description="Factor key: sleep, workload, stress, emotion, behavior")
    label: str = Field(..., description="Vietnamese label")
    score: float = Field(..., description="Factor score (0-100)")
    weight: float = Field(..., description="Factor weight (0-1)")
    contribution: float = Field(..., description="Contribution to burnout (0-100)")


class BurnoutWarningItem(BaseModel):
    """Response cho một warning."""
    type: str = Field(..., description="Warning type code")
    severity: str = Field(..., description="Severity: high, medium, low")
    title: str = Field(..., description="Warning title")
    description: str = Field(..., description="Warning description")
    factor: Optional[str] = Field(default=None, description="Related factor")
    current_value: Optional[float] = Field(default=None, description="Current value")
    previous_value: Optional[float] = Field(default=None, description="Previous value")
    change: Optional[float] = Field(default=None, description="Change amount")


class BurnoutTrendItem(BaseModel):
    """Response cho một điểm trong burnout trend."""
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    analyzed_at: Optional[str] = Field(default=None, description="Full timestamp ISO format")
    score: Optional[float] = Field(default=None, description="Burnout score for this date")
    risk_level: Optional[str] = Field(default=None, description="Risk level for this date")


class BurnoutAnalyticsResponse(BaseModel):
    """Response cho /api/v1/dashboard/burnout-analytics endpoint."""

    user_id: str

    # Current burnout status
    current: Optional[dict] = Field(default=None, description="Current burnout status")

    # 5 factors breakdown
    factors: list = Field(default_factory=list, description="5 burnout factors")

    # Total contribution (should be = burnout_score)
    total_contribution: Optional[float] = Field(default=None, description="Sum of contributions")

    # Burnout score trend (SCORES not counts!)
    burnout_trend: list = Field(default_factory=list, description="Burnout score trend over time")

    # Warnings generated from data
    warnings: list = Field(default_factory=list, description="Burnout warnings")

    # AI summary and recommendations
    summary: Optional[dict] = Field(default=None, description="AI summary and recommendations")

    # Statistics
    stats: dict = Field(default_factory=dict, description="Statistics")

    # Data quality
    data_completeness: float = Field(default=0.0, description="Data completeness (0-1)")
    available_factors: list = Field(default_factory=list, description="Available factors")
    missing_factors: list = Field(default_factory=list, description="Missing factors")

    # STA Scientific Dimensions
    sta_core: Optional[dict] = Field(default=None, description="OLBI Burnout Core: Exhaustion & Disengagement")
    sta_context: Optional[dict] = Field(default=None, description="Context: Demands, Recovery, Overload, Work Changes")
    sta_trend: list = Field(default_factory=list, description="Daily trend of STA dimensions")
    synthesized_insight: Optional[dict] = Field(default=None, description="Synthesized contextual narrative")


def _generate_warnings(
    latest: Optional[dict],
    previous: Optional[dict],
    factors: list,
) -> list:
    """Generate warnings based on burnout data."""
    warnings = []

    if not latest:
        return warnings

    current_score = latest.get("burnout_score", 0)
    current_risk = latest.get("risk_level", "unknown")
    current_trend = latest.get("trend", "insufficient_data")

    # Warning: Critical risk level
    if current_risk == "critical":
        warnings.append({
            "type": "CRITICAL_RISK",
            "severity": "high",
            "title": "Nguy cơ Burnout nghiêm trọng",
            "description": f"Điểm burnout của bạn đang ở mức {current_score:.1f}/100. Cần hành động ngay để cải thiện tình trạng.",
            "factor": None,
            "current_value": current_score,
            "previous_value": previous.get("burnout_score") if previous else None,
            "change": current_score - previous.get("burnout_score", 0) if previous else None,
        })

    # Warning: High risk level
    elif current_risk == "high":
        warnings.append({
            "type": "HIGH_RISK",
            "severity": "high",
            "title": "Nguy cơ Burnout cao",
            "description": f"Điểm burnout của bạn đang ở mức {current_score:.1f}/100. Cần chú ý cải thiện sớm.",
            "factor": None,
            "current_value": current_score,
            "previous_value": previous.get("burnout_score") if previous else None,
            "change": current_score - previous.get("burnout_score", 0) if previous else None,
        })

    # Warning: Burnout increasing
    if current_trend == "increasing":
        warnings.append({
            "type": "TREND_INCREASING",
            "severity": "medium",
            "title": "Burnout đang tăng",
            "description": "Xu hướng burnout của bạn đang tăng dần. Hãy chú ý nghỉ ngơi và cân bằng cuộc sống.",
            "factor": None,
            "current_value": current_score,
            "previous_value": previous.get("burnout_score") if previous else None,
            "change": current_score - previous.get("burnout_score", 0) if previous else None,
        })

    # Check each factor for high scores
    for f in factors:
        factor_key = f.get("key", "")
        factor_score = f.get("score", 0)

        # High sleep factor (means bad sleep)
        if factor_key == "sleep" and factor_score >= 70:
            warnings.append({
                "type": "HIGH_SLEEP_FACTOR",
                "severity": "high" if factor_score >= 85 else "medium",
                "title": "Vấn đề giấc ngủ",
                "description": f"Điểm giấc ngủ của bạn ở mức {factor_score:.0f}/100. Thiếu ngủ nghiêm trọng ảnh hưởng trực tiếp đến sức khỏe và công việc.",
                "factor": "sleep",
                "current_value": factor_score,
                "previous_value": None,
                "change": None,
            })

        # High workload factor
        elif factor_key == "workload" and factor_score >= 70:
            warnings.append({
                "type": "HIGH_WORKLOAD",
                "severity": "high" if factor_score >= 85 else "medium",
                "title": "Quá tải công việc",
                "description": f"Mức độ làm việc của bạn ở {factor_score:.0f}/100. Làm việc quá nhiều có thể dẫn đến kiệt sức.",
                "factor": "workload",
                "current_value": factor_score,
                "previous_value": None,
                "change": None,
            })

        # High stress factor
        elif factor_key == "stress" and factor_score >= 70:
            warnings.append({
                "type": "HIGH_STRESS",
                "severity": "high" if factor_score >= 85 else "medium",
                "title": "Mức stress cao",
                "description": f"Stress của bạn đang ở mức {factor_score:.0f}/100. Cần tìm cách thư giãn và giảm bớt áp lực.",
                "factor": "stress",
                "current_value": factor_score,
                "previous_value": None,
                "change": None,
            })

        # High emotion factor (means negative emotions)
        elif factor_key == "emotion" and factor_score >= 70:
            warnings.append({
                "type": "NEGATIVE_EMOTIONS",
                "severity": "high" if factor_score >= 85 else "medium",
                "title": "Cảm xúc tiêu cực",
                "description": f"Cảm xúc tiêu cực chiếm {factor_score:.0f}%. Hãy chú ý đến sức khỏe tinh thần của bạn.",
                "factor": "emotion",
                "current_value": factor_score,
                "previous_value": None,
                "change": None,
            })

        # High behavior factor (means worsening behavior)
        elif factor_key == "behavior" and factor_score >= 70:
            warnings.append({
                "type": "BEHAVIOR_DECLINE",
                "severity": "high" if factor_score >= 85 else "medium",
                "title": "Xu hướng hành vi xấu đi",
                "description": f"Xu hướng hành vi của bạn đang ở mức {factor_score:.0f}%. Có dấu hiệu thay đổi tiêu cực.",
                "factor": "behavior",
                "current_value": factor_score,
                "previous_value": None,
                "change": None,
            })

    return warnings


async def _compute_sta_analytics(range_surveys: list, days: int, user_id: Optional[str] = None, profile: Optional[dict] = None, window_end: Optional[datetime] = None) -> dict:
    from app.modules.dashboard.services.dashboard_evidence import build_dashboard_evidence, daily_dashboard_view
    from app.modules.dashboard.services.date_window import calendar_day
    end = calendar_day(window_end or datetime.now(timezone.utc))
    evidence = build_dashboard_evidence(range_surveys, end - timedelta(days=days - 1), end, profile=profile)
    return daily_dashboard_view(evidence)


@router.get("/context-insight", response_model=dict)
async def get_context_insight(
    user: dict = Depends(get_current_user),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    days: int = Query(default=30, ge=1, le=365),
):
    from app.modules.dashboard.services.date_window import date_window, calendar_day
    from app.modules.dashboard.services.dashboard_evidence import build_dashboard_evidence
    from app.modules.dashboard.services.dashboard_ai_interpreter import get_dashboard_ai_interpreter
    from app.modules.user.services.user_profile_service import get_profile_service
    try:
        window = date_window(start_date, end_date, days)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    uid = user["uid"]
    # Factories run inside workers too: unavailable optional sources remain distinguishable from empty sources.
    calls = {
        "surveys": lambda: get_survey_repo().get_completed_questionnaires(uid),
        "profile": lambda: get_profile_service().get_profile(uid),
        "work_environment": lambda: get_survey_repo().list_periodic_surveys(uid),
        "facial": lambda: get_emotion_repo().list_by_user(uid, 500),
        "chat": lambda: get_chat_repo().list_by_user(uid, 500),
    }
    results = await asyncio.gather(*(asyncio.to_thread(call) for call in calls.values()), return_exceptions=True)
    data, statuses = {}, {}
    for source, result in zip(calls, results):
        if isinstance(result, Exception):
            statuses[source] = "unavailable"
            data[source] = {} if source == "profile" else []
            logger.warning("Dashboard insight source unavailable: %s", source)
        else:
            statuses[source] = "available"
            data[source] = result or ({} if source == "profile" else [])
    # Recent supporting sources are bounded; disclose potential truncation instead of claiming full coverage.
    for source in ("facial", "chat"):
        if len(data[source]) >= 500:
            statuses[source] = "recent_500_records_only"
    evidence = build_dashboard_evidence(data["surveys"], calendar_day(window[0]), calendar_day(window[1] - timedelta(microseconds=1)),
        profile=data["profile"], resources=data["work_environment"], emotions=data["facial"], chats=data["chat"], source_status=statuses)
    return await asyncio.to_thread(get_dashboard_ai_interpreter().generate_synthesized_insight, evidence, uid)


@router.get("/burnout-analytics", response_model=BurnoutAnalyticsResponse)
async def get_burnout_analytics(
    days: int = Query(default=30, ge=1, le=365, description="Số ngày để phân tích"),
    user_id: Optional[str] = Query(default=None, description="User ID (dành cho admin xem chi tiết user)"),
    user: dict = Depends(get_current_user),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    """Lấy burnout analytics tổng hợp cho user.

    Endpoint này:
    1. Ưu tiên dùng burnout_results đã có
    2. Nếu không có → tính từ survey/emotion/chat history

    Cung cấp:
    - Current burnout score và risk level
    - 5 factors với scores, weights, contributions
    - Burnout score trend (theo ngày)
    - Warnings dựa trên data
    - AI summary và recommendations
    """
    target_user_id = user["uid"]
    if user_id and user.get("role") == "admin":
        target_user_id = user_id
    user_id = target_user_id
    from app.modules.dashboard.services.date_window import date_window, in_window
    try:
        window = date_window(start_date, end_date, days)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    days = window[2]
    window_end = window[1] - timedelta(microseconds=1)

    burnout_repo = get_burnout_repo()
    emotion_repo = get_emotion_repo()
    survey_repo = get_survey_repo()
    chat_repo = get_chat_repo()

    from app.modules.user.services.user_profile_service import get_profile_service
    profile_service = get_profile_service()

    # Load burnout history, survey history, and profile concurrently in parallel threads
    all_burnout_history, all_user_surveys, user_profile = await asyncio.gather(
        asyncio.to_thread(burnout_repo.list_by_user, user_id, 100),
        asyncio.to_thread(survey_repo.get_completed_questionnaires, user_id),
        asyncio.to_thread(profile_service.get_profile, user_id),
    )

    # This endpoint backs daily analysis. Periodic OLBI has its own timeline,
    # including when there are no daily check-ins and fallback analysis runs.
    all_burnout_history = [item for item in all_burnout_history if item.get("survey_type") != "olbi_periodic"]
    all_user_surveys = [item for item in all_user_surveys
                        if (item.get("survey") or {}).get("survey_type") != "olbi_periodic"]

    # Filter by date range for trend
    filtered_history = []
    for b in all_burnout_history:
        analyzed = b.get("analyzed_at")
        if analyzed:
            analyzed_dt = _normalize_datetime(analyzed)
            if in_window(analyzed, window):
                filtered_history.append(b)

    # Sort by date ascending for trend
    filtered_history.sort(key=lambda x: _normalize_datetime(x.get("analyzed_at")) or datetime.min)

    # Get latest and previous
    latest = filtered_history[-1] if filtered_history else None
    previous = filtered_history[-2] if len(filtered_history) >= 2 else None

    # Helper to safely convert recommendation to dict without exposing string methods
    def _recommendation_to_dict(r):
        if isinstance(r, str):
            return {
                "title": r,
                "description": r,
                "priority": "medium",
                "type": "behavior",
                "target_factor": None,
            }
        if isinstance(r, dict):
            t = r.get("title", "")
            d = r.get("description", "")
            return {
                "title": str(t) if not callable(t) else "",
                "description": str(d) if not callable(d) else "",
                "priority": r.get("priority") or "medium",
                "type": r.get("type") or "behavior",
                "target_factor": r.get("target_factor"),
            }
        # Pydantic Recommendation object
        t = getattr(r, "title", "")
        d = getattr(r, "description", "")
        return {
            "title": str(t) if not callable(t) else str(r),
            "description": str(d) if not callable(d) else "",
            "priority": getattr(r, "priority", None) or "medium",
            "type": getattr(r, "type", None) or "behavior",
            "target_factor": getattr(r, "target_factor", None),
        }

    # If no burnout results, calculate from survey/emotion/chat history
    if not latest:
        try:
            from app.modules.burnout.services.burnout_input_builder import BurnoutInputBuilder
            from app.modules.burnout.services.burnout_engine import get_burnout_engine

            # Load emotions & chats concurrently (surveys already loaded in parallel above)
            surveys = [item for item in all_user_surveys
                       if in_window(item.get("completed_at") or item.get("created_at"), window)]
            surveys.sort(key=lambda item: _normalize_datetime(item.get("completed_at") or item.get("created_at")) or datetime.min, reverse=True)
            surveys = surveys[:20]
            emotions, chats = await asyncio.gather(
                asyncio.to_thread(emotion_repo.list_by_user, user_id, 100),
                asyncio.to_thread(chat_repo.list_by_user, user_id, 50),
            )

            emotions = [item for item in emotions if in_window(item.get("created_at"), window)]
            chats = [item for item in chats if in_window(item.get("created_at"), window)]

            if surveys:
                # Use latest survey for current analysis
                latest_survey = surveys[0]
                assessment_id = latest_survey.get("assessment_id", "")

                # Load historical results for trend
                historical_results = all_burnout_history

                # Build BurnoutInput - use all available emotions/chats (not filtered by assessment_id)
                # This ensures we can calculate emotion and behavior factors
                builder = BurnoutInputBuilder(
                    assessment_id=assessment_id,
                    user_id=user_id,
                    assessment={"id": assessment_id, "user_id": user_id},
                    survey=latest_survey,
                    emotions=emotions,  # Use all emotions
                    chats=chats,  # Use all chats
                    historical_results=historical_results,
                )
                burnout_input = builder.build()

                # Run BurnoutEngine
                engine = get_burnout_engine()
                engine_output = engine.analyze(burnout_input)
                burnout_result = engine_output.burnout

                latest = {
                    "burnout_score": burnout_result.burnout_score,
                    "risk_level": burnout_result.risk_level,
                    "trend": burnout_result.trend,
                    "data_completeness": burnout_result.data_completeness,
                    "analyzed_at": burnout_result.analyzed_at,
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
                        _recommendation_to_dict(r)
                        for r in burnout_result.recommendations
                    ],
                    "insight": burnout_result.insight,
                }

                # Add to filtered_history for trend
                filtered_history.append(latest)

        except Exception as e:
            logger.warning("Failed to calculate burnout from history for user %s: %s", user_id, e)

    # Build current status
    current_status = None
    factors = []
    total_contribution = None
    available_factors = []
    missing_factors = []
    data_completeness = 0.0

    if latest:
        current_status = {
            "burnout_score": latest.get("burnout_score", 0),
            "risk_level": latest.get("risk_level", "unknown"),
            "trend": latest.get("trend", "insufficient_data"),
            "analyzed_at": str(latest.get("analyzed_at")) if latest.get("analyzed_at") else None,
            "confidence": latest.get("confidence", 1.0),
            "data_completeness": latest.get("data_completeness", 0),
        }

        # Process factors
        factors_data = latest.get("factors", [])
        all_factor_keys = ["sleep", "workload", "stress", "emotion", "behavior"]

        for key in all_factor_keys:
            found = False
            for f in factors_data:
                if f.get("factor") == key:
                    factors.append(BurnoutFactorResponse(
                        key=key,
                        label=FACTOR_LABELS.get(key, key),
                        score=f.get("score", 0),
                        weight=f.get("weight", 0),
                        contribution=f.get("contribution", 0),
                    ).model_dump())
                    available_factors.append(key)
                    found = True
                    break
            if not found:
                missing_factors.append(key)

        # Calculate total contribution
        total_contribution = round(sum(f.get("contribution", 0) for f in factors), 2)
        data_completeness = latest.get("data_completeness", 0)

    # Build burnout trend (SCORES not counts!)
    burnout_trend = []
    for b in filtered_history:
        analyzed = b.get("analyzed_at")
        date_str = ""
        analyzed_str = None
        if analyzed:
            analyzed_dt = _normalize_datetime(analyzed)
            if analyzed_dt:
                date_str = analyzed_dt.strftime("%Y-%m-%d")
                analyzed_str = analyzed_dt.isoformat()

        burnout_trend.append(BurnoutTrendItem(
            date=date_str,
            analyzed_at=analyzed_str,
            score=b.get("burnout_score"),
            risk_level=b.get("risk_level"),
        ).model_dump())

    # Generate warnings
    warnings = _generate_warnings(latest, previous, factors)

    # Build summary
    summary = None
    if latest:
        insight_raw = latest.get("insight")

        # Convert Pydantic model to dict if needed
        if insight_raw is not None and hasattr(insight_raw, 'model_dump'):
            insight = insight_raw.model_dump()
        elif isinstance(insight_raw, dict):
            insight = insight_raw
        else:
            insight = {}

        recommendations = latest.get("recommendations", [])

        # Build primary/secondary factor labels
        primary = insight.get("primary_factor") if insight else None
        secondary = insight.get("secondary_factor") if insight else None

        summary = {
            "primary_factor": FACTOR_LABELS.get(primary, primary) if primary else None,
            "secondary_factor": FACTOR_LABELS.get(secondary, secondary) if secondary else None,
            "ai_summary": insight.get("summary") if insight else None,
            "key_observations": insight.get("key_observations", []) if insight else [],
            "recommendations": [
                _recommendation_to_dict(r)
                for r in recommendations[:5]  # Top 5 recommendations
            ],
        }

    # === COMPUTE STA SCIENTIFIC ANALYTICS ===
    range_surveys = []
    for s in all_user_surveys:
        c_at = _normalize_datetime(s.get("completed_at") or s.get("created_at"))
        if in_window(s.get("completed_at") or s.get("created_at"), window):
            range_surveys.append(s)
    range_surveys.sort(key=lambda x: _normalize_datetime(x.get("completed_at") or x.get("created_at")) or datetime.min)

    sta_data = await _compute_sta_analytics(range_surveys, days, user_id=user_id, profile=user_profile, window_end=window_end)

    # Statistics
    stats = {
        "total_analyses": len(all_burnout_history),
        "analyses_in_range": len(filtered_history),
        "avg_score": round(sum(b.get("burnout_score", 0) for b in filtered_history) / len(filtered_history), 1) if filtered_history else None,
        "score_change": round(latest.get("burnout_score", 0) - previous.get("burnout_score", 0), 1) if latest and previous else None,
        "days_analyzed": days,
    }

    return BurnoutAnalyticsResponse(
        user_id=user_id,
        current=current_status,
        factors=factors,
        total_contribution=total_contribution,
        burnout_trend=burnout_trend,
        warnings=warnings,
        summary=summary,
        stats=stats,
        data_completeness=data_completeness,
        available_factors=available_factors,
        missing_factors=missing_factors,
        sta_core=sta_data["sta_core"],
        sta_context=sta_data["sta_context"],
        sta_trend=sta_data["sta_trend"],
        synthesized_insight=sta_data["synthesized_insight"],
    )
