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
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
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
            dt = dt.replace(tzinfo=None)
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
):
    """Lấy analytics tổng hợp cho user dashboard.

    Endpoint này cung cấp data cho Analysis tab trong ProfilePage.
    """
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
                date_key = analyzed_dt.strftime("%Y-%m-%d")
                burnout_daily[date_key] = burnout_daily.get(date_key, 0) + 1

    burnout_trend = []
    for i in range(89, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
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
                    date_key = ts.strftime("%Y-%m-%d")
                    login_daily[date_key] = login_daily.get(date_key, 0) + 1
    except Exception as e:
        logger.warning(f"Error building login trend: {e}")

    login_trend = []
    for i in range(89, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
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
                date_key = created.strftime("%Y-%m-%d")
                emotions_daily[date_key] = emotions_daily.get(date_key, 0) + 1

    emotions_trend = []
    for i in range(89, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
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
                date_key = created.strftime("%Y-%m-%d")
                assessments_daily[date_key] = assessments_daily.get(date_key, 0) + 1

    assessments_trend = []
    for i in range(89, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
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


async def _compute_sta_analytics(range_surveys: list, days: int, user_id: Optional[str] = None, profile: Optional[dict] = None) -> dict:
    """Tổng hợp phân tích theo chuẩn khoa học STA (Core - Context - Trend - Synthesized Insight)."""
    if not range_surveys:
        return {
            "sta_core": None,
            "sta_context": None,
            "sta_trend": [],
            "synthesized_insight": None,
        }

    ex_list = []
    dis_list = []
    jd_list = []
    sleep_list = []
    rec_list = []
    ov_list = []
    reason_counter: Dict[str, int] = {}
    other_reasons = []
    ot_hours_total = 0.0
    ot_days_count = 0
    sta_trend_items = []

    for s in range_surveys:
        raw = s.get("survey") or {}
        c_at = _normalize_datetime(s.get("completed_at") or s.get("created_at"))
        date_str = c_at.strftime("%Y-%m-%d") if c_at else "N/A"
        iso_str = c_at.isoformat() if c_at else None

        # 1. Exhaustion (E1-E3, Likert 1-5)
        ex_dict = raw.get("exhaustion") or {}
        if ex_dict and any(k in ex_dict for k in ("e1", "e2", "e3")):
            e_vals = [float(v) for v in ex_dict.values() if v is not None]
            ex = round(sum(e_vals) / len(e_vals), 2) if e_vals else 2.5
        else:
            st = float(raw.get("stress_level") or 5)
            ex = round(max(1.0, min(5.0, st / 2.0)), 2)
        ex_list.append(ex)

        # 2. Disengagement (D1-D3, Likert 1-5)
        dis_dict = raw.get("disengagement") or {}
        if dis_dict and any(k in dis_dict for k in ("d1", "d2", "d3")):
            d_vals = [float(v) for v in dis_dict.values() if v is not None]
            dis = round(sum(d_vals) / len(d_vals), 2) if d_vals else 2.0
        else:
            mot = float(raw.get("motivation_level") or 5)
            dis = round(max(1.0, min(5.0, (11.0 - mot) / 2.0)), 2)
        dis_list.append(dis)

        # 3. Job Demands (JD1-JD3, Likert 1-5)
        jd_dict = raw.get("job_demands") or {}
        if jd_dict and any(k in jd_dict for k in ("jd1", "jd2", "jd3")):
            jd_vals = [float(v) for v in jd_dict.values() if v is not None]
            jd = round(sum(jd_vals) / len(jd_vals), 2) if jd_vals else 2.5
        else:
            jd = 3.0
        jd_list.append(jd)

        # 4. Sleep & Recovery
        sleep_h = float(raw.get("sleep_hours") or (raw.get("recovery") or {}).get("sleep_hours") or 7.0)
        rec_s = int(raw.get("recovery_score") or (raw.get("recovery") or {}).get("recovery_score") or 3)
        sleep_list.append(sleep_h)
        rec_list.append(rec_s)

        # 5. Overload & Reasons
        ov = int(raw.get("quick_overload") or (raw.get("quick_overload_data") or {}).get("rating") or 2)
        ov_list.append(ov)
        reasons = raw.get("overload_reasons") or (raw.get("quick_overload_data") or {}).get("reasons") or []
        for r in reasons:
            clean_r = r.split("(")[0].strip() if "(" in r else r.strip()
            if clean_r:
                reason_counter[clean_r] = reason_counter.get(clean_r, 0) + 1

        other_text = raw.get("other_overload_reason") or (raw.get("quick_overload_data") or {}).get("other_reason")
        if other_text and isinstance(other_text, str) and other_text.strip() and other_text.strip() not in other_reasons:
            other_reasons.append(other_text.strip())

        # 6. Overtime
        had_ot = bool(raw.get("has_overtime_today") or (raw.get("work_changes") or {}).get("had_overtime"))
        ot_h = float(raw.get("overtime_hours_today") or (raw.get("work_changes") or {}).get("overtime_hours") or 0.0)
        if had_ot or ot_h > 0:
            ot_hours_total += ot_h
            ot_days_count += 1

        sta_trend_items.append({
            "date": date_str,
            "analyzed_at": iso_str,
            "exhaustion": ex,
            "disengagement": dis,
            "job_demands": jd,
            "recovery_score": rec_s,
            "sleep_hours": sleep_h,
            "quick_overload": ov,
        })

    # Aggregates
    n = len(range_surveys)
    avg_ex = round(sum(ex_list) / n, 2)
    avg_dis = round(sum(dis_list) / n, 2)
    avg_jd = round(sum(jd_list) / n, 2)
    avg_sleep = round(sum(sleep_list) / n, 1)
    avg_rec = round(sum(rec_list) / n, 1)
    overload_count = sum(1 for o in ov_list if o >= 4)

    def calc_trend(series):
        if len(series) < 2:
            return "stable"
        mid = len(series) // 2
        first_half = sum(series[:mid]) / max(1, mid)
        second_half = sum(series[mid:]) / max(1, len(series) - mid)
        diff = second_half - first_half
        if diff >= 0.25:
            return "increasing"
        elif diff <= -0.25:
            return "decreasing"
        return "stable"

    ex_trend = calc_trend(ex_list)
    dis_trend = calc_trend(dis_list)

    def get_score_level(score):
        if score >= 3.8:
            return "critical"
        elif score >= 3.2:
            return "high"
        elif score >= 2.5:
            return "medium"
        return "low"

    total_reasons_selected = sum(reason_counter.values())
    top_reasons = []
    for r, count in sorted(reason_counter.items(), key=lambda x: x[1], reverse=True):
        pct = round((count / max(1, total_reasons_selected)) * 100, 1)
        top_reasons.append({
            "reason": r,
            "count": count,
            "percentage": pct,
        })

    sta_core = {
        "exhaustion": {
            "score": avg_ex,
            "level": get_score_level(avg_ex),
            "trend": ex_trend,
            "label": "Cạn kiệt năng lượng (Exhaustion)",
        },
        "disengagement": {
            "score": avg_dis,
            "level": get_score_level(avg_dis),
            "trend": dis_trend,
            "label": "Mất gắn kết (Disengagement)",
        },
    }

    rec_status = "poor" if avg_rec < 2.5 or avg_sleep < 6.0 else ("good" if avg_rec >= 3.5 and avg_sleep >= 7.0 else "moderate")

    sta_context = {
        "job_demands": {
            "score": avg_jd,
            "level": get_score_level(avg_jd),
            "label": "Yêu cầu & Áp lực công việc",
        },
        "recovery": {
            "avg_sleep_hours": avg_sleep,
            "avg_recovery_score": avg_rec,
            "status": rec_status,
        },
        "overload_stats": {
            "overload_count": overload_count,
            "total_checkins": n,
            "top_reasons": top_reasons[:5],
            "other_reasons": other_reasons[:5],
        },
        "work_changes": {
            "total_overtime_hours": round(ot_hours_total, 1),
            "overtime_days": ot_days_count,
        },
    }

    # 7. Resolve Industry Context & Cross-Metric Burnout Archetype
    job_title = None
    industry_code = None
    if profile:
        job_title = profile.get("job_title")
        industry_code = profile.get("industry_code")
    elif user_id:
        try:
            from app.modules.user.services.user_profile_service import get_profile_service
            p = get_profile_service().get_profile(user_id) or {}
            job_title = p.get("job_title")
            industry_code = p.get("industry_code")
        except Exception:
            pass

    from app.modules.burnout.helpers.industry_archetypes import resolve_industry_context
    from app.modules.burnout.helpers.matrix_resolver import resolve_burnout_archetype

    ind_ctx = resolve_industry_context(industry_code=industry_code, job_title=job_title)
    daily_stats = {
        "job_demands": avg_jd,
        "sleep_hours": avg_sleep,
        "recovery_score": avg_rec,
        "ot_hours_total": ot_hours_total,
        "overload_count": overload_count,
    }
    archetype = resolve_burnout_archetype(avg_ex, avg_dis, daily_stats)

    # 8. Generate Synthesized Insight narrative using Gemini AI Interpreter (Tầng 3)
    evidence = {
        "days": days,
        "total_checkins": n,
        "exhaustion_level": get_score_level(avg_ex),
        "exhaustion_trend": ex_trend,
        "disengagement_level": get_score_level(avg_dis),
        "disengagement_trend": dis_trend,
        "recovery_status": rec_status,
        "overload_count": overload_count,
        "top_reasons": [r["reason"] for r in top_reasons[:5]],
        "other_reasons": other_reasons[:5],
        "ot_hours_total": round(ot_hours_total, 1),
        "ot_days_count": ot_days_count,
        # Industry & Archetype context
        "job_title": job_title or ind_ctx.typical_roles[0],
        "industry_name": ind_ctx.name,
        "industry_icon": ind_ctx.icon,
        "vocabulary_hints": ind_ctx.vocabulary_hints,
        "stressors_context": ind_ctx.stressors_context,
        "archetype_name": f"{archetype.icon} {archetype.name}",
        "empathy_direction": archetype.empathy_direction,
        "ai_prompt_instruction": archetype.ai_prompt_instruction,
    }

    try:
        from app.modules.dashboard.services.dashboard_ai_interpreter import get_dashboard_ai_interpreter
        interpreter = get_dashboard_ai_interpreter()
        synthesized_insight = await asyncio.to_thread(interpreter.generate_synthesized_insight, evidence)
    except Exception as e:
        logger.warning("Failed to invoke Dashboard AI Interpreter: %s", e)
        synthesized_insight = {
            "summary": f"Trong {days} ngày vừa qua, nhịp làm việc và năng lượng của bạn duy trì ở mức cân bằng tốt.",
            "key_observations": ["Các chỉ số bối cảnh công việc và năng lượng duy trì ở mức ổn định."],
        }

    return {
        "sta_core": sta_core,
        "sta_context": sta_context,
        "sta_trend": sta_trend_items,
        "synthesized_insight": synthesized_insight,
    }


@router.get("/burnout-analytics", response_model=BurnoutAnalyticsResponse)
async def get_burnout_analytics(
    days: int = Query(default=30, ge=1, le=365, description="Số ngày để phân tích"),
    user_id: Optional[str] = Query(default=None, description="User ID (dành cho admin xem chi tiết user)"),
    user: dict = Depends(get_current_user),
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
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    burnout_repo = get_burnout_repo()
    emotion_repo = get_emotion_repo()
    survey_repo = get_survey_repo()
    chat_repo = get_chat_repo()

    from app.modules.user.services.user_profile_service import get_profile_service
    profile_service = get_profile_service()

    # Load burnout history, survey history, and profile concurrently in parallel threads
    all_burnout_history, all_user_surveys, user_profile = await asyncio.gather(
        asyncio.to_thread(burnout_repo.list_by_user, user_id, 100),
        asyncio.to_thread(survey_repo.list_by_user, user_id, 100),
        asyncio.to_thread(profile_service.get_profile, user_id),
    )

    # Filter by date range for trend
    filtered_history = []
    for b in all_burnout_history:
        analyzed = b.get("analyzed_at")
        if analyzed:
            analyzed_dt = _normalize_datetime(analyzed)
            if analyzed_dt and analyzed_dt >= start_date:
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
            surveys = all_user_surveys[:20]
            emotions, chats = await asyncio.gather(
                asyncio.to_thread(emotion_repo.list_by_user, user_id, 100),
                asyncio.to_thread(chat_repo.list_by_user, user_id, 50),
            )

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
        if c_at and c_at >= start_date:
            range_surveys.append(s)
    range_surveys.sort(key=lambda x: _normalize_datetime(x.get("completed_at") or x.get("created_at")) or datetime.min)

    sta_data = await _compute_sta_analytics(range_surveys, days, user_id=user_id, profile=user_profile)

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
