"""
==============================================================
File: admin_dashboard.py

Admin Dashboard Routes - API endpoints cho Admin Dashboard.

Endpoints:
GET  /api/v1/admin/dashboard/stats          - Tổng quan thống kê
GET  /api/v1/admin/dashboard/users         - Danh sách users gần đây
GET  /api/v1/admin/dashboard/activity      - Hoạt động gần đây
GET  /api/v1/admin/dashboard/ai-usage      - AI quota & usage
GET  /api/v1/admin/dashboard/data-overview - Tổng quan data

NOTE: Tất cả data là THẬT từ Firestore.
==============================================================
"""

import logging
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.deps import get_current_user
from app.core.firebase import get_firebase

logger = logging.getLogger("burnout.admin.dashboard")

router = APIRouter(prefix="/api/v1/admin/dashboard", tags=["Admin Dashboard"])


# ==========================================
# Helper Functions
# ==========================================

def _format_datetime(dt) -> Optional[str]:
    """Format datetime từ Firestore.

    Handles:
    - Python datetime objects (with or without timezone)
    - Firestore Timestamp objects
    - ISO format strings
    - None values

    Returns None if unable to format (for invalid dates).
    """
    if dt is None:
        return None

    logger.info("=" * 80)
    logger.info(f"_format_datetime INPUT:")
    logger.info(f"  type: {type(dt).__name__}")
    logger.info(f"  repr: {repr(dt)}")
    logger.info(f"  value: {dt}")

    try:
        # Handle Firestore Timestamp - check class name exactly
        type_name = type(dt).__name__
        logger.info(f"  type_name: {type_name}")
        logger.info(f"  hasattr to_datetime: {hasattr(dt, 'to_datetime')}")

        if type_name == 'Timestamp' or 'Timestamp' in str(type(dt)):
            logger.info("  -> Detected as Firestore Timestamp")
            try:
                dt = dt.to_datetime()
                logger.info(f"  -> After to_datetime(): type={type(dt).__name__}, value={dt}")
            except Exception as e:
                logger.error(f"  -> to_datetime() failed: {e}")
                return None

        # Handle string input
        if isinstance(dt, str):
            logger.info(f"  -> Detected as string: '{dt}'")
            if not dt.strip():
                logger.info("  -> Empty string, returning None")
                return None
            # Try to parse ISO format
            try:
                dt_clean = dt.strip()
                dt_clean = dt_clean.replace(' ', 'T')
                if not dt_clean.endswith('Z') and '+' not in dt_clean and '-' not in dt_clean[10:]:
                    dt_clean = dt_clean + 'Z'
                dt = datetime.fromisoformat(dt_clean.replace('Z', '+00:00'))
                logger.info(f"  -> Parsed ISO: {dt}")
            except Exception as e:
                logger.info(f"  -> ISO parse failed: {e}")
                try:
                    dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
                    logger.info(f"  -> Parsed '%Y-%m-%d %H:%M:%S': {dt}")
                except:
                    try:
                        dt = datetime.strptime(dt, '%Y-%m-%d')
                        logger.info(f"  -> Parsed '%Y-%m-%d': {dt}")
                    except Exception as e2:
                        logger.info(f"  -> All parse failed, returning None")
                        return None

        # Now dt should be a datetime object
        if hasattr(dt, 'isoformat') and callable(dt.isoformat):
            iso_str = dt.isoformat()
            logger.info(f"  -> ISO string: '{iso_str}'")
            # Ensure it ends with Z for consistency
            if iso_str.endswith('+00:00'):
                iso_str = iso_str[:-6] + 'Z'
            elif not iso_str.endswith('Z'):
                iso_str = iso_str + 'Z'
            logger.info(f"  -> FINAL OUTPUT: '{iso_str}'")
            logger.info("=" * 80)
            return iso_str
        else:
            logger.info(f"  -> No isoformat method. dt type: {type(dt).__name__}")

    except Exception as e:
        logger.error(f"  -> EXCEPTION: {e}")
        logger.error(f"  -> traceback: {traceback.format_exc()}")
        logger.info("=" * 80)

    return None


def _to_utc_datetime(val) -> Optional[datetime]:
    """Chuyển đổi an toàn bất kỳ dạng datetime nào sang datetime UTC có timezone."""
    if val is None:
        return None
    if isinstance(val, str):
        if not val.strip():
            return None
        try:
            val = datetime.fromisoformat(val.strip().replace("Z", "+00:00"))
        except Exception:
            return None
    elif hasattr(val, "to_datetime"):
        try:
            val = val.to_datetime()
        except Exception:
            pass
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    return None


def _parse_datetime(dt_str: str) -> datetime:
    """Parse datetime string."""
    if not dt_str:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except:
        return datetime.now(timezone.utc)


# ==========================================
# Response Models
# ==========================================

class UserStats(BaseModel):
    """User statistics."""
    total: int = 0
    active_today: int = 0
    active_this_week: int = 0
    active_this_month: int = 0
    new_users_today: int = 0
    new_users_this_week: int = 0
    new_users_this_month: int = 0
    admin_count: int = 0


class AssessmentStats(BaseModel):
    """Assessment statistics."""
    total: int = 0
    today: int = 0
    this_week: int = 0
    this_month: int = 0


class EmotionStats(BaseModel):
    """Emotion statistics."""
    total: int = 0
    today: int = 0
    this_week: int = 0
    this_month: int = 0


class BurnoutStats(BaseModel):
    """Burnout result statistics."""
    total: int = 0
    today: int = 0
    this_week: int = 0
    this_month: int = 0
    avg_score: Optional[float] = None
    risk_distribution: Dict[str, int] = Field(default_factory=dict)


class AIUsageStats(BaseModel):
    """AI usage statistics."""
    total_api_calls: int = 0
    today_api_calls: int = 0
    this_week_api_calls: int = 0
    this_month_api_calls: int = 0
    failed_calls: int = 0
    avg_response_time_ms: Optional[float] = None
    model_usage: Dict[str, int] = Field(default_factory=dict)


class DashboardStatsResponse(BaseModel):
    """Response cho /stats endpoint."""
    users: UserStats
    assessments: AssessmentStats
    emotions: EmotionStats
    burnout: BurnoutStats
    ai_usage: AIUsageStats
    timestamp: str


class RecentUser(BaseModel):
    """Recent user info."""
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None

    class Config:
        # Force string serialization
        json_encoders = {
            datetime: lambda v: v.isoformat() + 'Z' if v else None
        }


class RecentActivityItem(BaseModel):
    """Một activity item."""
    id: str
    type: str  # login, register, assessment, emotion_capture, burnout_analysis
    user_id: str
    username: str
    description: str
    timestamp: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + 'Z' if v else None
        }


class ActivityResponse(BaseModel):
    """Response cho /activity endpoint."""
    activities: List[RecentActivityItem]
    count: int


class AIUsageItem(BaseModel):
    """Một AI usage item."""
    id: str
    timestamp: str
    model: str
    operation: str
    user_id: Optional[str] = None
    success: bool
    response_time_ms: Optional[float] = None
    tokens_used: Optional[int] = None


class AIUsageResponse(BaseModel):
    """Response cho /ai-usage endpoint."""
    usage: List[AIUsageItem]
    count: int
    total_calls: int


class DataOverviewResponse(BaseModel):
    """Response cho /data-overview endpoint."""
    collections: Dict[str, Dict[str, Any]]
    timestamp: str


# ==========================================
# Auth Check
# ==========================================

async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Yêu cầu quyền admin."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


# ==========================================
# GET /api/v1/admin/dashboard/stats
# ==========================================

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    admin: dict = Depends(require_admin),
):
    """Lấy tổng quan thống kê.

    Tất cả data là THẬT từ Firestore.
    """
    db = get_firebase().db
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    # Initialize stats
    users_stats = UserStats()
    assessment_stats = AssessmentStats()
    emotion_stats = EmotionStats()
    burnout_stats = BurnoutStats()
    ai_stats = AIUsageStats()

    try:
        # === USERS ===
        users_ref = db.collection("users")
        users = [doc.to_dict() | {"id": doc.id} for doc in users_ref.stream()]

        users_stats.total = len(users)
        users_stats.admin_count = sum(1 for u in users if u.get("role") == "admin")

        for user in users:
            last_login = _to_utc_datetime(user.get("last_login_at"))
            created = _to_utc_datetime(user.get("created_at"))

            # Count active
            if last_login:
                if last_login >= today_start:
                    users_stats.active_today += 1
                if last_login >= week_start:
                    users_stats.active_this_week += 1
                if last_login >= month_start:
                    users_stats.active_this_month += 1

            # Count new users
            if created:
                if created >= today_start:
                    users_stats.new_users_today += 1
                if created >= week_start:
                    users_stats.new_users_this_week += 1
                if created >= month_start:
                    users_stats.new_users_this_month += 1

    except Exception as e:
        logger.error("Error getting user stats: %s", e)

    try:
        # === ASSESSMENTS / SURVEYS ===
        seen_assessment_ids = set()
        all_assessments = []

        # 1. From assessments collection
        for doc in db.collection("assessments").stream():
            d = doc.to_dict() | {"id": doc.id}
            aid = d.get("id") or doc.id
            seen_assessment_ids.add(aid)
            all_assessments.append(d)

        # 2. From survey_history collection (STA surveys)
        for doc in db.collection("survey_history").stream():
            d = doc.to_dict() | {"id": doc.id}
            aid = d.get("assessment_id") or doc.id
            if aid not in seen_assessment_ids:
                seen_assessment_ids.add(aid)
                all_assessments.append({
                    "id": aid,
                    "created_at": d.get("created_at") or d.get("completed_at"),
                })

        assessment_stats.total = len(all_assessments)

        for a in all_assessments:
            created = _to_utc_datetime(a.get("created_at"))
            if not created:
                continue

            if created >= today_start:
                assessment_stats.today += 1
            if created >= week_start:
                assessment_stats.this_week += 1
            if created >= month_start:
                assessment_stats.this_month += 1

    except Exception as e:
        logger.error("Error getting assessment stats: %s", e)

    try:
        # === EMOTIONS ===
        emotions_ref = db.collection("emotions")
        emotions = [doc.to_dict() | {"id": doc.id} for doc in emotions_ref.stream()]

        emotion_stats.total = len(emotions)

        for e in emotions:
            created = _to_utc_datetime(e.get("created_at"))
            if not created:
                continue

            if created >= today_start:
                emotion_stats.today += 1
            if created >= week_start:
                emotion_stats.this_week += 1
            if created >= month_start:
                emotion_stats.this_month += 1

    except Exception as e:
        logger.error("Error getting emotion stats: %s", e)

    try:
        # === BURNOUT RESULTS ===
        burnout_ref = db.collection("burnout_results")
        burnout_results = [doc.to_dict() | {"id": doc.id} for doc in burnout_ref.stream()]

        burnout_stats.total = len(burnout_results)
        scores = []

        for b in burnout_results:
            created = _to_utc_datetime(b.get("created_at"))
            if not created:
                continue

            if created >= today_start:
                burnout_stats.today += 1
            if created >= week_start:
                burnout_stats.this_week += 1
            if created >= month_start:
                burnout_stats.this_month += 1

            # Collect scores and risk levels
            score = b.get("burnout_score")
            if score is not None:
                scores.append(float(score))

            risk = b.get("risk_level", "unknown")
            burnout_stats.risk_distribution[risk] = burnout_stats.risk_distribution.get(risk, 0) + 1

        if scores:
            burnout_stats.avg_score = round(sum(scores) / len(scores), 1)

    except Exception as e:
        logger.error("Error getting burnout stats: %s", e)

    return DashboardStatsResponse(
        users=users_stats,
        assessments=assessment_stats,
        emotions=emotion_stats,
        burnout=burnout_stats,
        ai_usage=ai_stats,  # TODO: Implement when tracking AI usage
        timestamp=str(now),
    )


# ==========================================
# GET /api/v1/admin/dashboard/users
# ==========================================

@router.get("/users", response_model=Dict)
async def get_recent_users(
    limit: int = Query(default=10, ge=1, le=100),
    admin: dict = Depends(require_admin),
):
    """Lấy danh sách users hoạt động gần đây nhất."""
    db = get_firebase().db

    users_ref = db.collection("users")
    all_users = []

    # Đọc tất cả users
    for doc in users_ref.stream():
        data = doc.to_dict()
        data["id"] = doc.id
        all_users.append(data)

    # Sort theo last_login_at DESCENDING - users đăng nhập gần nhất lên đầu
    # Những user có last_login_at sẽ lên đầu, null sẽ xuống cuối
    def get_last_login(user):
        last_login = user.get("last_login_at")
        if last_login is None:
            return ""  # Null sẽ ở cuối
        # Parse datetime để sort
        try:
            if isinstance(last_login, str):
                from datetime import datetime
                return datetime.fromisoformat(last_login.replace("Z", "+00:00"))
            return last_login
        except:
            return ""

    all_users.sort(key=get_last_login, reverse=True)

    # Giới hạn kết quả
    all_users = all_users[:limit]

    # Format response
    users = []
    for user in all_users:
        users.append({
            "id": user.get("id"),
            "username": user.get("username"),
            "email": user.get("email"),
            "full_name": user.get("full_name"),
            "role": user.get("role", "user"),
            "is_active": user.get("is_active", True),
            "email_verified": user.get("email_verified", False),
            "created_at": _format_datetime(user.get("created_at")),
            "last_login_at": _format_datetime(user.get("last_login_at")),
        })

    return {
        "users": users,
        "count": len(users),
    }


# ==========================================
# GET /api/v1/admin/dashboard/activity
# ==========================================

@router.get("/activity", response_model=ActivityResponse)
async def get_recent_activity(
    limit: int = Query(default=50, ge=1, le=200),
    admin: dict = Depends(require_admin),
):
    """Lấy hoạt động gần đây (login, assessments, etc).

    Tổng hợp từ nhiều collections:
    - login_activities (auth)
    - assessments (captures)
    - emotions (captures)
    - burnout_results (analyses)
    """
    db = get_firebase().db
    now = datetime.utcnow()
    activities: List[RecentActivityItem] = []

    # 1. Login activities
    try:
        login_ref = db.collection("login_activities")
        for doc in login_ref.order_by("timestamp", direction="DESCENDING").limit(limit).stream():
            data = doc.to_dict()
            user_data = _get_user_info(db, data.get("user_id", ""))
            activities.append(RecentActivityItem(
                id=doc.id,
                type="login",
                user_id=data.get("user_id", ""),
                username=user_data.get("username", "Unknown"),
                description="User logged in",
                timestamp=str(_format_datetime(data.get("timestamp"))) if _format_datetime(data.get("timestamp")) else "",
                metadata={
                    "ip_address": data.get("ip_address"),
                    "user_agent": data.get("user_agent"),
                    "success": data.get("success", True),
                },
            ))
    except Exception as e:
        logger.warning("Error reading login_activities: %s", e)

    # 2. Recent assessments
    try:
        assessments_ref = db.collection("assessments")
        for doc in assessments_ref.order_by("created_at", direction="DESCENDING").limit(limit).stream():
            data = doc.to_dict()
            user_data = _get_user_info(db, data.get("user_id", ""))
            activities.append(RecentActivityItem(
                id=doc.id,
                type="assessment",
                user_id=data.get("user_id", ""),
                username=user_data.get("username", "Unknown"),
                description=f"New assessment created: {data.get('status', 'unknown')}",
                timestamp=str(_format_datetime(data.get("created_at"))) if _format_datetime(data.get("created_at")) else "",
                metadata={
                    "status": data.get("status"),
                    "status_detail": data.get("status_detail"),
                },
            ))
    except Exception as e:
        logger.warning("Error reading assessments: %s", e)

    # 3. Recent emotions
    try:
        emotions_ref = db.collection("emotions")
        for doc in emotions_ref.order_by("created_at", direction="DESCENDING").limit(limit).stream():
            data = doc.to_dict()
            user_data = _get_user_info(db, data.get("user_id", ""))
            activities.append(RecentActivityItem(
                id=doc.id,
                type="emotion_capture",
                user_id=data.get("user_id", ""),
                username=user_data.get("username", "Unknown"),
                description=f"Emotion captured: {data.get('dominant_emotion', 'unknown')}",
                timestamp=str(_format_datetime(data.get("created_at"))) if _format_datetime(data.get("created_at")) else "",
                metadata={
                    "dominant_emotion": data.get("dominant_emotion"),
                    "confidence": data.get("confidence"),
                    "risk_level": data.get("assessment", {}).get("risk_level") if data.get("assessment") else None,
                },
            ))
    except Exception as e:
        logger.warning("Error reading emotions: %s", e)

    # 4. Recent burnout results
    try:
        burnout_ref = db.collection("burnout_results")
        for doc in burnout_ref.order_by("created_at", direction="DESCENDING").limit(limit).stream():
            data = doc.to_dict()
            user_data = _get_user_info(db, data.get("user_id", ""))
            activities.append(RecentActivityItem(
                id=doc.id,
                type="burnout_analysis",
                user_id=data.get("user_id", ""),
                username=user_data.get("username", "Unknown"),
                description=f"Burnout analyzed: score={data.get('burnout_score', 0)}, risk={data.get('risk_level', 'unknown')}",
                timestamp=str(_format_datetime(data.get("created_at"))) if _format_datetime(data.get("created_at")) else "",
                metadata={
                    "burnout_score": data.get("burnout_score"),
                    "risk_level": data.get("risk_level"),
                    "data_completeness": data.get("data_completeness"),
                },
            ))
    except Exception as e:
        logger.warning("Error reading burnout_results: %s", e)

    # Sort by timestamp (most recent first)
    activities.sort(key=lambda x: x.timestamp or "", reverse=True)

    return ActivityResponse(
        activities=activities[:limit],
        count=len(activities[:limit]),
    )


def _get_user_info(db, user_id: str) -> Dict:
    """Lấy thông tin user từ Firestore."""
    if not user_id:
        return {}
    try:
        doc = db.collection("users").document(user_id).get()
        if doc.exists:
            return doc.to_dict()
    except:
        pass
    return {}


# ==========================================
# GET /api/v1/admin/dashboard/ai-usage
# ==========================================

@router.get("/ai-usage", response_model=AIUsageResponse)
async def get_ai_usage(
    limit: int = Query(default=50, ge=1, le=200),
    admin: dict = Depends(require_admin),
):
    """Lấy AI usage gần đây.

    Đọc từ security_events collection nơi AI-related events được log.
    """
    db = get_firebase().db
    usage: List[AIUsageItem] = []
    total_calls = 0

    try:
        # Read from security_events (AI events)
        events_ref = db.collection("security_events")
        for doc in events_ref.order_by("timestamp", direction="DESCENDING").limit(limit * 2).stream():
            data = doc.to_dict()
            event_type = data.get("event_type", "")

            # Filter only AI-related events
            if event_type not in ["ai_api_call", "gemini_call", "embedding_call", "analysis_completed"]:
                continue

            total_calls += 1
            usage.append(AIUsageItem(
                id=doc.id,
                timestamp=str(_format_datetime(data.get("timestamp"))) if _format_datetime(data.get("timestamp")) else "",
                model=data.get("model", "gemini-1.5-flash"),
                operation=data.get("operation", event_type),
                user_id=data.get("user_id"),
                success=data.get("success", True),
                response_time_ms=data.get("response_time_ms"),
                tokens_used=data.get("tokens_used"),
            ))

            if len(usage) >= limit:
                break

    except Exception as e:
        logger.warning("Error reading AI usage: %s", e)

    return AIUsageResponse(
        usage=usage,
        count=len(usage),
        total_calls=total_calls,
    )


# ==========================================
# GET /api/v1/admin/dashboard/data-overview
# ==========================================

@router.get("/data-overview", response_model=DataOverviewResponse)
async def get_data_overview(
    admin: dict = Depends(require_admin),
):
    """Lấy tổng quan data trong Firestore.

    Đếm documents trong các collections chính.
    """
    db = get_firebase().db
    now = datetime.utcnow()

    collections = {
        "users": {"count": 0, "last_doc": None},
        "assessments": {"count": 0, "last_doc": None},
        "emotions": {"count": 0, "last_doc": None},
        "burnout_results": {"count": 0, "last_doc": None},
        "survey_history": {"count": 0, "last_doc": None},
        "chat_history": {"count": 0, "last_doc": None},
        "login_activities": {"count": 0, "last_doc": None},
        "security_events": {"count": 0, "last_doc": None},
    }

    for col_name in collections.keys():
        try:
            col_ref = db.collection(col_name)
            docs = list(col_ref.limit(1).stream())

            if docs:
                collections[col_name]["count"] = col_ref.count().get().value if hasattr(col_ref.count(), 'get') else "N/A"
                collections[col_name]["last_doc"] = _format_datetime(docs[0].to_dict().get("created_at") or docs[0].to_dict().get("timestamp"))

        except Exception as e:
            logger.warning("Error counting %s: %s", col_name, e)
            collections[col_name]["count"] = "Error"
            collections[col_name]["error"] = str(e)

    return DataOverviewResponse(
        collections=collections,
        timestamp=str(now),
    )


# ==========================================
# GET /api/v1/admin/dashboard/recent-logins
# ==========================================

@router.get("/recent-logins")
async def get_recent_logins(
    limit: int = Query(default=20, ge=1, le=100),
    admin: dict = Depends(require_admin),
):
    """Lấy các lần đăng nhập gần đây."""
    db = get_firebase().db
    logins = []

    try:
        login_ref = db.collection("login_activities")
        for doc in login_ref.order_by("timestamp", direction="DESCENDING").limit(limit).stream():
            data = doc.to_dict()
            user_data = _get_user_info(db, data.get("user_id", ""))
            logins.append({
                "id": doc.id,
                "user_id": data.get("user_id"),
                "username": user_data.get("username", "Unknown"),
                "email": user_data.get("email"),
                "ip_address": data.get("ip_address"),
                "user_agent": data.get("user_agent"),
                "success": data.get("success", True),
                "timestamp": _format_datetime(data.get("timestamp")),
            })
    except Exception as e:
        logger.error("Error getting recent logins: %s", e)

    return {
        "logins": logins,
        "count": len(logins),
    }


# ==========================================
# ANALYTICS ENDPOINTS
# ==========================================

# Response Models for Analytics
class DailyTrendResponse(BaseModel):
    date: str
    count: int


class RoleDistributionResponse(BaseModel):
    admin: int
    user: int


class UserAnalyticsResponse(BaseModel):
    role_distribution: RoleDistributionResponse
    user_activity_trend: List[DailyTrendResponse]
    new_users_trend: List[DailyTrendResponse]
    top_active_users: List[Dict[str, Any]]
    inactive_users: int
    retention_rate: float


class AssessmentAnalyticsResponse(BaseModel):
    status_distribution: Dict[str, int]
    completion_rate: float
    avg_completion_time_minutes: Optional[float]
    assessments_trend: List[DailyTrendResponse]
    top_users_by_assessments: List[Dict[str, Any]]


class EmotionDistributionResponse(BaseModel):
    high: int
    medium: int
    low: int


class EmotionAnalyticsResponse(BaseModel):
    # Basic stats
    emotion_distribution: Dict[str, int]
    avg_confidence: Optional[float]
    confidence_distribution: EmotionDistributionResponse
    emotions_trend: List[DailyTrendResponse]
    dominant_emotions_trend: List[DailyTrendResponse]

    # AI Quality Metrics (NEW)
    total: int = 0
    unknown_count: int = 0
    unknown_rate: float = 0.0  # percentage
    success_count: int = 0
    success_rate: float = 0.0  # percentage


class UserDetailAnalyticsResponse(BaseModel):
    """Response model cho chi tiết analytics của 1 user."""
    user_id: str
    username: str
    # Login stats
    total_logins: int
    logins_this_week: int
    logins_this_month: int
    login_trend: List[DailyTrendResponse]
    # Assessment stats
    total_assessments: int
    assessments_this_week: int
    assessments_this_month: int
    assessments_trend: List[DailyTrendResponse]
    assessment_status_distribution: Dict[str, int]
    # Emotion stats
    total_emotions: int
    emotions_this_week: int
    emotions_this_month: int
    emotions_trend: List[DailyTrendResponse]
    emotion_distribution: Dict[str, int]
    avg_confidence: Optional[float]
    # Burnout stats
    total_burnout: int
    burnout_this_week: int
    burnout_this_month: int
    burnout_trend: List[DailyTrendResponse]
    avg_burnout_score: Optional[float]
    risk_level: Optional[str]


class BurnoutAnalyticsResponse(BaseModel):
    score_distribution: List[Dict[str, Any]]
    risk_distribution: Dict[str, int]
    avg_burnout_score: Optional[float]
    avg_emotional_exhaustion: Optional[float]
    avg_depersonalization: Optional[float]
    avg_reduced_accomplishment: Optional[float]
    burnout_trend: List[DailyTrendResponse]
    high_risk_users: List[Dict[str, Any]]
    top_stressors: Optional[List[Dict[str, Any]]] = None


class LoginAnalyticsResponse(BaseModel):
    total_logins: int
    successful_logins: int
    failed_logins: int
    success_rate: float
    login_trend: List[DailyTrendResponse]
    failed_login_patterns: List[Dict[str, Any]]
    peak_hours: List[Dict[str, Any]]


def _get_daily_trend(docs: List, date_field: str = "created_at") -> List[DailyTrendResponse]:
    """Generate daily trend from documents."""
    daily_counts: Dict[str, int] = {}
    now = datetime.utcnow()

    for doc in docs:
        data = doc.to_dict() if hasattr(doc, 'to_dict') else doc
        dt = data.get(date_field)
        if dt:
            if hasattr(dt, 'to_datetime'):
                dt = dt.to_datetime()
            if isinstance(dt, str):
                try:
                    dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
                except:
                    continue
            if isinstance(dt, datetime):
                date_key = dt.strftime("%Y-%m-%d")
                daily_counts[date_key] = daily_counts.get(date_key, 0) + 1

    # Generate last 90 days
    result = []
    for i in range(89, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        result.append(DailyTrendResponse(date=day, count=daily_counts.get(day, 0)))

    return result


def _get_user_info_simple(db, user_id: str) -> Dict:
    """Lấy thông tin user cơ bản."""
    if not user_id:
        return {}
    try:
        doc = db.collection("users").document(user_id).get()
        if doc.exists:
            return doc.to_dict()
    except:
        pass
    return {}


# ==========================================
# GET /api/v1/admin/dashboard/analytics/users
# ==========================================

@router.get("/analytics/users", response_model=UserAnalyticsResponse)
async def get_user_analytics(
    admin: dict = Depends(require_admin),
):
    """Lấy user analytics chi tiết."""
    db = get_firebase().db
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)

    # Get all users
    users = [doc.to_dict() | {"id": doc.id} for doc in db.collection("users").stream()]

    # Role distribution
    admin_count = sum(1 for u in users if u.get("role") == "admin")
    role_distribution = RoleDistributionResponse(
        admin=admin_count,
        user=len(users) - admin_count
    )

    # Calculate activity
    active_users = []
    inactive_count = 0

    for user in users:
        last_login = user.get("last_login_at")
        if last_login:
            if hasattr(last_login, 'to_datetime'):
                last_login = last_login.to_datetime()
            if isinstance(last_login, str):
                try:
                    last_login = datetime.fromisoformat(last_login.replace("Z", "+00:00"))
                except:
                    last_login = None

            if last_login and isinstance(last_login, datetime):
                # Make timezone-aware datetime naive for comparison
                if last_login.tzinfo is not None:
                    last_login = last_login.replace(tzinfo=None)
                if last_login >= thirty_days_ago:
                    active_users.append(user)
                if last_login < thirty_days_ago and user.get("is_active"):
                    inactive_count += 1
        elif user.get("is_active"):
            inactive_count += 1

    # Retention rate
    retention_rate = round(len(active_users) / len(users) * 100, 1) if users else 0

    # New users trend (from created_at)
    new_users = [doc.to_dict() | {"id": doc.id} for doc in db.collection("users").stream()]
    new_users_trend = _get_daily_trend(new_users, "created_at")

    # User activity trend (from login_activities)
    logins = list(db.collection("login_activities").stream())
    user_activity_trend = _get_daily_trend(logins, "timestamp")

    # Top active users
    login_counts: Dict[str, int] = {}
    login_times: Dict[str, str] = {}
    for login_doc in db.collection("login_activities").stream():
        data = login_doc.to_dict()
        uid = data.get("user_id", "")
        if uid:
            login_counts[uid] = login_counts.get(uid, 0) + 1
            login_times[uid] = _format_datetime(data.get("timestamp")) or ""

    top_active = []
    for uid, count in sorted(login_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        user_info = _get_user_info_simple(db, uid)
        top_active.append({
            "user_id": uid,
            "username": user_info.get("username", "Unknown"),
            "login_count": count,
            "last_login": login_times.get(uid, "")
        })

    return UserAnalyticsResponse(
        role_distribution=role_distribution,
        user_activity_trend=user_activity_trend,
        new_users_trend=new_users_trend,
        top_active_users=top_active,
        inactive_users=inactive_count,
        retention_rate=retention_rate
    )


# ==========================================
# GET /api/v1/admin/dashboard/analytics/assessments
# ==========================================

@router.get("/analytics/assessments", response_model=AssessmentAnalyticsResponse)
async def get_assessment_analytics(
    admin: dict = Depends(require_admin),
):
    """Lấy assessment analytics chi tiết."""
    db = get_firebase().db

    # Get all assessments from assessments and survey_history
    seen_ids = set()
    assessments = []

    for doc in db.collection("assessments").stream():
        d = doc.to_dict() | {"id": doc.id}
        aid = d.get("id") or doc.id
        seen_ids.add(aid)
        assessments.append(d)

    for doc in db.collection("survey_history").stream():
        d = doc.to_dict() | {"id": doc.id}
        aid = d.get("assessment_id") or doc.id
        if aid not in seen_ids:
            seen_ids.add(aid)
            assessments.append({
                "id": aid,
                "user_id": d.get("user_id"),
                "status": d.get("status", "completed"),
                "created_at": d.get("created_at") or d.get("completed_at"),
            })

    # Status distribution
    status_dist: Dict[str, int] = {}
    for a in assessments:
        status = a.get("status", "completed")
        status_dist[status] = status_dist.get(status, 0) + 1

    # Completion rate
    completed = sum(1 for a in assessments if a.get("status") in ["completed", "done"])
    completion_rate = round(completed / len(assessments) * 100, 1) if assessments else 100.0

    # Trend
    assessments_trend = _get_daily_trend(assessments, "created_at")

    # Top users
    user_assessment_counts: Dict[str, int] = {}
    for a in assessments:
        uid = a.get("user_id", "")
        if uid:
            user_assessment_counts[uid] = user_assessment_counts.get(uid, 0) + 1

    top_users = []
    for uid, count in sorted(user_assessment_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        user_info = _get_user_info_simple(db, uid)
        top_users.append({
            "user_id": uid,
            "username": user_info.get("username", "Unknown"),
            "assessment_count": count
        })

    return AssessmentAnalyticsResponse(
        status_distribution=status_dist,
        completion_rate=completion_rate,
        avg_completion_time_minutes=None,  # Need tracking of start/end time
        assessments_trend=assessments_trend,
        top_users_by_assessments=top_users
    )


# ==========================================
# GET /api/v1/admin/dashboard/analytics/emotions
# ==========================================

@router.get("/analytics/emotions", response_model=EmotionAnalyticsResponse)
async def get_emotion_analytics(
    admin: dict = Depends(require_admin),
):
    """Lấy emotion analytics chi tiết."""
    db = get_firebase().db

    # Get all emotions
    emotions = [doc.to_dict() | {"id": doc.id} for doc in db.collection("emotions").stream()]

    # Emotion distribution
    emotion_dist: Dict[str, int] = {}
    total_confidence = 0.0
    confidence_count = 0
    high_conf = 0
    med_conf = 0
    low_conf = 0

    for e in emotions:
        dom = e.get("dominant_emotion", "neutral")
        emotion_dist[dom] = emotion_dist.get(dom, 0) + 1

        conf = e.get("confidence")
        if conf is not None:
            total_confidence += float(conf)
            confidence_count += 1
            if float(conf) >= 0.8:
                high_conf += 1
            elif float(conf) >= 0.5:
                med_conf += 1
            else:
                low_conf += 1

    avg_confidence = round(total_confidence / confidence_count, 2) if confidence_count > 0 else None

    # Trend
    emotions_trend = _get_daily_trend(emotions, "created_at")

    # Dominant emotions trend
    dominant_trend: Dict[str, Dict[str, int]] = {}
    for e in emotions:
        dt = e.get("created_at")
        date_key = ""
        if dt:
            if hasattr(dt, 'to_datetime'):
                dt = dt.to_datetime()
            if isinstance(dt, str):
                try:
                    dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
                except:
                    pass
            if isinstance(dt, datetime):
                date_key = dt.strftime("%Y-%m-%d")

        if date_key:
            dom = e.get("dominant_emotion", "neutral")
            if date_key not in dominant_trend:
                dominant_trend[date_key] = {}
            dominant_trend[date_key][dom] = dominant_trend[date_key].get(dom, 0) + 1

    # Generate last 90 days
    now = datetime.utcnow()
    dominant_trend_result = []
    for i in range(89, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        count = sum(dominant_trend.get(day, {}).values())
        dominant_trend_result.append(DailyTrendResponse(date=day, count=count))

    # Calculate AI quality metrics
    total_emotions = len(emotions)
    unknown_count = emotion_dist.get("unknown", 0) + emotion_dist.get("Other", 0)
    success_count = total_emotions - unknown_count - low_conf
    success_rate = round((success_count / total_emotions * 100), 1) if total_emotions > 0 else 0.0
    unknown_rate = round((unknown_count / total_emotions * 100), 1) if total_emotions > 0 else 0.0

    return EmotionAnalyticsResponse(
        emotion_distribution=emotion_dist,
        avg_confidence=avg_confidence,
        confidence_distribution=EmotionDistributionResponse(
            high=high_conf,
            medium=med_conf,
            low=low_conf
        ),
        emotions_trend=emotions_trend,
        dominant_emotions_trend=dominant_trend_result,
        # AI Quality Metrics
        total=total_emotions,
        unknown_count=unknown_count,
        unknown_rate=unknown_rate,
        success_count=success_count,
        success_rate=success_rate,
    )


# ==========================================
# GET /api/v1/admin/dashboard/analytics/burnout
# ==========================================

@router.get("/analytics/burnout", response_model=BurnoutAnalyticsResponse)
async def get_burnout_analytics(
    admin: dict = Depends(require_admin),
):
    """Lấy burnout analytics chi tiết."""
    db = get_firebase().db

    # Get all burnout results
    results = [doc.to_dict() | {"id": doc.id} for doc in db.collection("burnout_results").stream()]

    # Also include survey_history records if not already represented
    existing_user_dates = {(r.get("user_id"), str(r.get("created_at"))[:10]) for r in results}
    for doc in db.collection("survey_history").stream():
        d = doc.to_dict() | {"id": doc.id}
        uid = d.get("user_id")
        created = d.get("created_at") or d.get("completed_at")
        date_key = str(created)[:10] if created else ""
        if (uid, date_key) not in existing_user_dates:
            ar = d.get("analysis_result") or {}
            score = ar.get("risk_score")
            risk = ar.get("risk_level")
            # If STA survey exists without explicit risk_score, compute from exhaustion
            if score is None and "survey" in d:
                raw_s = d["survey"]
                ex_dict = raw_s.get("exhaustion") or {}
                if ex_dict:
                    vals = [float(v) for v in ex_dict.values() if v is not None]
                    if vals:
                        avg_ex = sum(vals) / len(vals)
                        score = round((avg_ex / 5.0) * 100, 1)
                        risk = "critical" if avg_ex >= 3.8 else ("high" if avg_ex >= 3.2 else ("medium" if avg_ex >= 2.5 else "low"))
            if score is not None:
                results.append({
                    "id": d["id"],
                    "user_id": uid,
                    "burnout_score": score,
                    "risk_level": risk or "low",
                    "created_at": created,
                    "survey": d.get("survey"),
                    "analysis_result": ar,
                })
                existing_user_dates.add((uid, date_key))

    # Score distribution (histogram)
    score_ranges = [
        ("0-20", 0, 20),
        ("20-40", 20, 40),
        ("40-60", 40, 60),
        ("60-80", 60, 80),
        ("80-100", 80, 100),
    ]
    score_dist = []
    for label, low, high in score_ranges:
        count = sum(1 for r in results
                   if (score := r.get("burnout_score")) is not None
                   and low <= float(score) < high)
        score_dist.append({"range": label, "count": count})

    # Risk distribution
    risk_dist: Dict[str, int] = {}
    total_score = 0.0
    score_count = 0

    for r in results:
        risk = r.get("risk_level", "unknown")
        risk_dist[risk] = risk_dist.get(risk, 0) + 1

        score = r.get("burnout_score")
        if score is not None:
            total_score += float(score)
            score_count += 1

    avg_score = round(total_score / score_count, 1) if score_count > 0 else None

    # Trend
    burnout_trend = _get_daily_trend(results, "created_at")

    # Group by user_id -> ONLY the LATEST assessment for each user
    user_latest: Dict[str, Dict] = {}
    for r in results:
        uid = r.get("user_id")
        if not uid:
            continue
        c_at = str(r.get("created_at") or "")
        if uid not in user_latest or c_at > str(user_latest[uid].get("created_at") or ""):
            user_latest[uid] = r

    # High risk users (from latest assessment per user)
    high_risk = []
    for uid, r in user_latest.items():
        risk = r.get("risk_level", "")
        if risk in ["high", "critical"]:
            user_info = _get_user_info_simple(db, uid)
            high_risk.append({
                "user_id": uid,
                "username": user_info.get("username", "Unknown"),
                "full_name": user_info.get("full_name") or user_info.get("username", "Unknown"),
                "avatar_url": user_info.get("avatar_url"),
                "burnout_score": r.get("burnout_score", 0),
                "risk_level": risk,
                "last_assessment": _format_datetime(r.get("created_at")) or ""
            })

    high_risk.sort(key=lambda x: x["burnout_score"], reverse=True)
    high_risk = high_risk[:10]

    # Top Stressors Ranking (from latest assessment per user)
    stressors_def = [
        {
            "id": "workload",
            "title": "Khối lượng công việc quá tải",
            "category": "Yêu cầu công việc (Job Demands)",
            "users": [],
            "scores": [],
        },
        {
            "id": "recovery_sleep",
            "title": "Thiếu ngủ & Hồi phục kém",
            "category": "Khả năng hồi phục (Recovery)",
            "users": [],
            "scores": [],
        },
        {
            "id": "time_pressure",
            "title": "Áp lực thời hạn / Deadline",
            "category": "Áp lực tiến độ (Pace & Deadlines)",
            "users": [],
            "scores": [],
        },
        {
            "id": "emotional_demands",
            "title": "Căng thẳng & Áp lực cảm xúc",
            "category": "Sức khỏe tâm lý (Emotional Strain)",
            "users": [],
            "scores": [],
        },
        {
            "id": "disengagement",
            "title": "Mất gắn kết & Giảm động lực",
            "category": "Động lực làm việc (Disengagement)",
            "users": [],
            "scores": [],
        },
        {
            "id": "custom_overload",
            "title": "Nguyên nhân khác (User trải lòng)",
            "category": "Phản hồi trực tiếp từ nhân sự",
            "users": [],
            "scores": [],
        },
    ]

    total_assessed_users = max(1, len(user_latest))

    for uid, r in user_latest.items():
        user_info = _get_user_info_simple(db, uid)
        u_name = user_info.get("username", "Unknown")
        f_name = user_info.get("full_name") or u_name
        avatar = user_info.get("avatar_url")
        c_at_str = _format_datetime(r.get("created_at")) or ""

        survey = r.get("survey") or {}
        context = r.get("context") or {}
        sta = r.get("sta_core") or {}
        primary = str(r.get("primary_factor") or "")

        reasons = list(survey.get("overload_reasons") or [])
        if isinstance(survey.get("quick_overload_data"), dict):
            reasons = reasons or list(survey["quick_overload_data"].get("overload_reasons") or [])

        other_note = survey.get("other_overload_reason") or ""
        for reason_item in reasons:
            if "Khác" in str(reason_item) and "(" in str(reason_item):
                extracted = str(reason_item).split("(", 1)[1].rstrip(")")
                if extracted:
                    other_note = extracted

        # Workload check
        jd_dict = survey.get("job_demands") or {}
        jd1 = float(jd_dict.get("jd1") or 0)
        jd_mean = float(jd_dict.get("score") or 0)
        workload_score = jd1 or jd_mean or (4.5 if any("nhiều việc" in str(x).lower() for x in reasons) else 0)
        if workload_score >= 3.5 or any("nhiều việc" in str(x).lower() for x in reasons) or primary == "workload":
            score_val = round(workload_score if workload_score > 0 else 4.0, 1)
            stressors_def[0]["users"].append({
                "user_id": uid,
                "username": u_name,
                "full_name": f_name,
                "avatar_url": avatar,
                "score": score_val,
                "level": "critical" if score_val >= 4.0 else "high",
                "last_assessment": c_at_str,
                "notes": "Báo cáo khối lượng công việc vượt mức khả năng xử lý"
            })
            stressors_def[0]["scores"].append(score_val)

        # Recovery & Sleep check
        sleep_h = float(survey.get("sleep_hours") or (context.get("recovery") or {}).get("sleep_hours") or 8.0)
        rec_score = float(survey.get("recovery_score") or (context.get("recovery") or {}).get("recovery_perception") or 3.0)
        if sleep_h < 6.0 or rec_score <= 2.0 or any("ngủ" in str(x).lower() or "mệt" in str(x).lower() for x in reasons) or primary in ["sleep", "recovery"]:
            score_val = round(5.0 - min(4.0, rec_score), 1)
            stressors_def[1]["users"].append({
                "user_id": uid,
                "username": u_name,
                "full_name": f_name,
                "avatar_url": avatar,
                "score": score_val,
                "level": "critical" if sleep_h < 5.0 or rec_score <= 1.0 else "high",
                "last_assessment": c_at_str,
                "notes": f"Ngủ {sleep_h:.1f}h đêm qua, điểm hồi phục: {rec_score:.0f}/5"
            })
            stressors_def[1]["scores"].append(score_val)

        # Time Pressure / Deadline check
        jd2 = float(jd_dict.get("jd2") or 0)
        deadline_p = str(survey.get("current_deadline_pressure") or "").lower()
        if jd2 >= 3.5 or deadline_p in ["high", "extreme"] or any("deadline" in str(x).lower() for x in reasons):
            score_val = round(jd2 if jd2 > 0 else (5.0 if deadline_p == "extreme" else 4.0), 1)
            stressors_def[2]["users"].append({
                "user_id": uid,
                "username": u_name,
                "full_name": f_name,
                "avatar_url": avatar,
                "score": score_val,
                "level": "critical" if score_val >= 4.5 else "high",
                "last_assessment": c_at_str,
                "notes": f"Áp lực tiến độ & thời gian ở mức {deadline_p or 'cao'}"
            })
            stressors_def[2]["scores"].append(score_val)

        # Emotional demands
        ex_dict = survey.get("exhaustion") or {}
        ex_vals = [float(v) for v in ex_dict.values() if v is not None]
        avg_ex = (sum(ex_vals) / len(ex_vals)) if ex_vals else float((sta.get("exhaustion") or {}).get("score") or 0)
        if avg_ex >= 3.5 or any("cảm xúc" in str(x).lower() for x in reasons) or primary == "stress":
            score_val = round(avg_ex if avg_ex > 0 else 4.0, 1)
            stressors_def[3]["users"].append({
                "user_id": uid,
                "username": u_name,
                "full_name": f_name,
                "avatar_url": avatar,
                "score": score_val,
                "level": "critical" if score_val >= 4.0 else "high",
                "last_assessment": c_at_str,
                "notes": "Mức độ kiệt sức cảm xúc đáng chú ý"
            })
            stressors_def[3]["scores"].append(score_val)

        # Disengagement
        dis_dict = survey.get("disengagement") or {}
        dis_vals = [float(v) for v in dis_dict.values() if v is not None]
        avg_dis = (sum(dis_vals) / len(dis_vals)) if dis_vals else float((sta.get("disengagement") or {}).get("score") or 0)
        if avg_dis >= 3.0 or any("động lực" in str(x).lower() for x in reasons) or primary == "behavior":
            score_val = round(avg_dis if avg_dis > 0 else 3.5, 1)
            stressors_def[4]["users"].append({
                "user_id": uid,
                "username": u_name,
                "full_name": f_name,
                "avatar_url": avatar,
                "score": score_val,
                "level": "critical" if score_val >= 4.0 else "high",
                "last_assessment": c_at_str,
                "notes": "Có dấu hiệu xa cách hoặc giảm gắn kết công việc"
            })
            stressors_def[4]["scores"].append(score_val)

        # Custom overload notes
        if other_note or any("khác" in str(x).lower() for x in reasons):
            stressors_def[5]["users"].append({
                "user_id": uid,
                "username": u_name,
                "full_name": f_name,
                "avatar_url": avatar,
                "score": 4.5,
                "level": "high",
                "last_assessment": c_at_str,
                "notes": other_note or "Nguyên nhân cá nhân / bối cảnh riêng"
            })
            stressors_def[5]["scores"].append(4.5)

    # Format stressors list
    top_stressors = []
    for s in stressors_def:
        cnt = len(s["users"])
        pct = round((cnt / total_assessed_users) * 100, 1) if user_latest else 0.0
        avg_sc = round(sum(s["scores"]) / cnt, 1) if cnt > 0 else 0.0
        s["users"].sort(key=lambda u: u["score"], reverse=True)
        top_stressors.append({
            "id": s["id"],
            "title": s["title"],
            "category": s["category"],
            "affected_users_count": cnt,
            "affected_percentage": pct,
            "avg_score": avg_sc,
            "users": s["users"],
        })

    # Sort stressors by affected_users_count descending
    top_stressors.sort(key=lambda x: (x["affected_users_count"], x["avg_score"]), reverse=True)

    return BurnoutAnalyticsResponse(
        score_distribution=score_dist,
        risk_distribution=risk_dist,
        avg_burnout_score=avg_score,
        avg_emotional_exhaustion=None,
        avg_depersonalization=None,
        avg_reduced_accomplishment=None,
        burnout_trend=burnout_trend,
        high_risk_users=high_risk,
        top_stressors=top_stressors,
    )


# ==========================================
# GET /api/v1/admin/dashboard/analytics/logins
# ==========================================

@router.get("/analytics/logins", response_model=LoginAnalyticsResponse)
async def get_login_analytics(
    admin: dict = Depends(require_admin),
):
    """Lấy login analytics chi tiết."""
    db = get_firebase().db

    # Get all logins
    logins = [doc.to_dict() | {"id": doc.id} for doc in db.collection("login_activities").stream()]

    # Summary
    total = len(logins)
    successful = sum(1 for l in logins if l.get("success", True))
    failed = total - successful
    success_rate = round(successful / total * 100, 1) if total > 0 else 0

    # Trend
    login_trend = _get_daily_trend(logins, "timestamp")

    # Failed login patterns (by IP)
    failed_by_ip: Dict[str, int] = {}
    failed_times: Dict[str, str] = {}
    for l in logins:
        if not l.get("success", True):
            ip = l.get("ip_address", "unknown")
            failed_by_ip[ip] = failed_by_ip.get(ip, 0) + 1
            ts = _format_datetime(l.get("timestamp"))
            if ts:
                failed_times[ip] = ts

    failed_patterns = [
        {
            "ip_address": ip,
            "attempts": count,
            "last_attempt": failed_times.get(ip, "")
        }
        for ip, count in sorted(failed_by_ip.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    # Peak hours
    hour_counts: Dict[int, int] = {}
    for l in logins:
        ts = l.get("timestamp")
        if ts:
            if hasattr(ts, 'to_datetime'):
                ts = ts.to_datetime()
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except:
                    continue
            if isinstance(ts, datetime):
                hour = ts.hour
                hour_counts[hour] = hour_counts.get(hour, 0) + 1

    peak_hours = [
        {"hour": h, "count": c}
        for h, c in sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    return LoginAnalyticsResponse(
        total_logins=total,
        successful_logins=successful,
        failed_logins=failed,
        success_rate=success_rate,
        login_trend=login_trend,
        failed_login_patterns=failed_patterns,
        peak_hours=peak_hours
    )


# ==========================================
# GET /api/v1/admin/dashboard/user/{user_id}/analytics
# ==========================================

@router.get("/user/{user_id}/analytics", response_model=UserDetailAnalyticsResponse)
async def get_user_detail_analytics(
    user_id: str,
    admin: dict = Depends(require_admin),
):
    """Lấy chi tiết analytics của 1 user.

    Tối ưu: Dùng indexed queries và batch reads thay vì đọc tất cả docs.
    """
    db = get_firebase().db
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # Get user info
    user_info = _get_user_info_simple(db, user_id)
    username = user_info.get("username", "Unknown")

    # === LOGIN STATS (sử dụng indexed query) ===
    login_ref = db.collection("login_activities")
    # Query chỉ lấy logins của user này trong tháng
    login_query = login_ref.where("user_id", "==", user_id).order_by("timestamp", direction="DESCENDING")

    login_docs = list(login_query.limit(500).stream())
    total_logins = len(login_docs)

    # Login trend (daily)
    login_daily: Dict[str, int] = {}
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

    # Generate last 90 days
    login_trend = []
    for i in range(89, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        login_trend.append(DailyTrendResponse(date=day, count=login_daily.get(day, 0)))

    logins_this_week = sum(1 for d in login_docs if _is_in_range(d.to_dict().get("timestamp"), week_ago, now))
    logins_this_month = sum(1 for d in login_docs if _is_in_range(d.to_dict().get("timestamp"), month_ago, now))

    # === ASSESSMENT STATS (indexed query) ===
    assessment_ref = db.collection("assessments")
    assessment_query = assessment_ref.where("user_id", "==", user_id).order_by("created_at", direction="DESCENDING")

    assessment_docs = list(assessment_query.limit(500).stream())
    total_assessments = len(assessment_docs)

    # Assessment trend
    assessment_daily: Dict[str, int] = {}
    assessment_status: Dict[str, int] = {}
    for doc in assessment_docs:
        data = doc.to_dict()
        status = data.get("status", "unknown")
        assessment_status[status] = assessment_status.get(status, 0) + 1

        ts = data.get("created_at")
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
                assessment_daily[date_key] = assessment_daily.get(date_key, 0) + 1

    assessments_trend = []
    for i in range(89, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        assessments_trend.append(DailyTrendResponse(date=day, count=assessment_daily.get(day, 0)))

    assessments_this_week = sum(1 for d in assessment_docs if _is_in_range(d.to_dict().get("created_at"), week_ago, now))
    assessments_this_month = sum(1 for d in assessment_docs if _is_in_range(d.to_dict().get("created_at"), month_ago, now))

    # === EMOTION STATS (indexed query) ===
    emotion_ref = db.collection("emotions")
    emotion_query = emotion_ref.where("user_id", "==", user_id).order_by("created_at", direction="DESCENDING")

    emotion_docs = list(emotion_query.limit(500).stream())
    total_emotions = len(emotion_docs)

    # Emotion distribution
    emotion_dist: Dict[str, int] = {}
    total_confidence = 0.0
    conf_count = 0

    # Emotion trend
    emotion_daily: Dict[str, int] = {}
    for doc in emotion_docs:
        data = doc.to_dict()
        dom = data.get("dominant_emotion", "neutral")
        emotion_dist[dom] = emotion_dist.get(dom, 0) + 1

        conf = data.get("confidence")
        if conf is not None:
            total_confidence += float(conf)
            conf_count += 1

        ts = data.get("created_at")
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
                emotion_daily[date_key] = emotion_daily.get(date_key, 0) + 1

    emotions_trend = []
    for i in range(89, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        emotions_trend.append(DailyTrendResponse(date=day, count=emotion_daily.get(day, 0)))

    emotions_this_week = sum(1 for d in emotion_docs if _is_in_range(d.to_dict().get("created_at"), week_ago, now))
    emotions_this_month = sum(1 for d in emotion_docs if _is_in_range(d.to_dict().get("created_at"), month_ago, now))

    avg_confidence = round(total_confidence / conf_count, 2) if conf_count > 0 else None

    # === BURNOUT STATS (indexed query) ===
    burnout_ref = db.collection("burnout_results")
    burnout_query = burnout_ref.where("user_id", "==", user_id).order_by("created_at", direction="DESCENDING")

    burnout_docs = list(burnout_query.limit(500).stream())
    total_burnout = len(burnout_docs)

    # Burnout trend
    burnout_daily: Dict[str, int] = {}
    total_score = 0.0
    score_count = 0
    latest_risk = None

    for doc in burnout_docs:
        data = doc.to_dict()
        score = data.get("burnout_score")
        if score is not None:
            total_score += float(score)
            score_count += 1
            # Get latest risk level
            if latest_risk is None:
                latest_risk = data.get("risk_level")

        ts = data.get("created_at")
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
                burnout_daily[date_key] = burnout_daily.get(date_key, 0) + 1

    burnout_trend = []
    for i in range(89, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        burnout_trend.append(DailyTrendResponse(date=day, count=burnout_daily.get(day, 0)))

    burnout_this_week = sum(1 for d in burnout_docs if _is_in_range(d.to_dict().get("created_at"), week_ago, now))
    burnout_this_month = sum(1 for d in burnout_docs if _is_in_range(d.to_dict().get("created_at"), month_ago, now))

    avg_burnout_score = round(total_score / score_count, 1) if score_count > 0 else None

    return UserDetailAnalyticsResponse(
        user_id=user_id,
        username=username,
        total_logins=total_logins,
        logins_this_week=logins_this_week,
        logins_this_month=logins_this_month,
        login_trend=login_trend,
        total_assessments=total_assessments,
        assessments_this_week=assessments_this_week,
        assessments_this_month=assessments_this_month,
        assessments_trend=assessments_trend,
        assessment_status_distribution=assessment_status,
        total_emotions=total_emotions,
        emotions_this_week=emotions_this_week,
        emotions_this_month=emotions_this_month,
        emotions_trend=emotions_trend,
        emotion_distribution=emotion_dist,
        avg_confidence=avg_confidence,
        total_burnout=total_burnout,
        burnout_this_week=burnout_this_week,
        burnout_this_month=burnout_this_month,
        burnout_trend=burnout_trend,
        avg_burnout_score=avg_burnout_score,
        risk_level=latest_risk
    )


def _is_in_range(ts, start: datetime, end: datetime) -> bool:
    """Check if timestamp is in range.

    Normalizes timezone-aware and timezone-naive datetimes for comparison.
    """
    if ts is None:
        return False

    # Convert Firestore Timestamp if needed
    if hasattr(ts, 'to_datetime'):
        ts = ts.to_datetime()

    # Parse string to datetime
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except:
            try:
                ts = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
            except:
                return False

    if isinstance(ts, datetime):
        # Normalize: strip timezone info to make both offset-naive
        # This is safe because we only care about the date portion
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)

        # Also normalize start/end if they somehow have tzinfo
        norm_start = start.replace(tzinfo=None) if start.tzinfo else start
        norm_end = end.replace(tzinfo=None) if end.tzinfo else end

        return norm_start <= ts <= norm_end
    return False

