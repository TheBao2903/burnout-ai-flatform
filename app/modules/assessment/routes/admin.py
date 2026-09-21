"""
==============================================================
File: admin.py

Admin Routes - API cho testing Cache & Rate Limit.
==============================================================
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.modules.assessment.services.ai_service import get_assessment_service
from app.modules.assessment.services.rate_limiter import get_rate_limiter

logger = logging.getLogger("burnout.assessment.admin")

router = APIRouter(prefix="/api/assessment", tags=["Assessment Admin"])


# ==========================================
# Request/Response Models
# ==========================================

class ChatAnalyzeRequest(BaseModel):
    text: str


class CacheEntryResponse(BaseModel):
    cache_key: str
    dominant_emotion: Optional[str] = None
    confidence: Optional[float] = None
    hit_count: int = 0
    created_at: Optional[str] = None


class RateLimitStatusResponse(BaseModel):
    user_daily_limit: int
    user_today_count: int
    user_remaining: int
    global_hourly_limit: int
    global_this_hour_count: int
    global_remaining: int


class CacheStatsResponse(BaseModel):
    total_entries: int
    recent_avg_hits: float
    ttl_days: int


# ==========================================
# Chat Analysis Endpoint
# ==========================================

@router.post("/chat/analyze")
async def chat_analyze(
    req: ChatAnalyzeRequest,
    user: dict = Depends(get_current_user),
    skip_cache: bool = Query(False, description="Bỏ qua cache, luôn gọi AI"),
):
    """
    Phân tích chat text và trả về structured analysis.

    - Nếu text đã được phân tích trước đó → trả cached result
    - Nếu chưa → gọi AI và lưu vào cache

    Test cache:
    1. Gọi lần 1 → AI được gọi
    2. Gọi lần 2 cùng text → cache hit (nhanh hơn)
    """
    service = get_assessment_service()
    result = await service.analyze_chat_text(req.text, skip_cache=skip_cache)

    if result is None:
        raise HTTPException(status_code=400, detail="Text rỗng hoặc không hợp lệ")

    return {
        "text": req.text,
        "text_length": len(req.text),
        "result": result,
    }


# ==========================================
# Rate Limit Status
# ==========================================

@router.get("/rate-limit/status", response_model=RateLimitStatusResponse)
async def get_rate_limit_status(
    user: dict = Depends(get_current_user),
):
    """
    Lấy thông tin rate limit hiện tại của user.

    Trả về:
    - user_daily_limit: Giới hạn AI calls/ngày
    - user_today_count: Số calls hôm nay
    - user_remaining: Số calls còn lại
    - global_hourly_limit: Giới hạn global/giờ
    - global_this_hour_count: Số calls giờ này
    - global_remaining: Số calls global còn lại
    """
    rate_limiter = get_rate_limiter()
    user_id = user["uid"]
    stats = rate_limiter.get_stats(user_id)

    return RateLimitStatusResponse(**stats)


# ==========================================
# Cache Admin Endpoints
# ==========================================

@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    user: dict = Depends(get_current_user),
):
    """
    Lấy thống kê assessment cache.

    Trả về:
    - total_entries: Tổng số entries trong cache
    - recent_avg_hits: Số lần hit trung bình của các entry gần đây
    - ttl_days: TTL của cache (ngày)
    """
    from app.modules.assessment.repositories.assessment_cache_repository import (
        get_assessment_cache_repository,
    )

    repo = get_assessment_cache_repository()
    stats = repo.get_stats()

    return CacheStatsResponse(**stats)


@router.get("/cache/entries")
async def get_cache_entries(
    user: dict = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Lấy danh sách cache entries (để debug).

    Chỉ trả metadata, không trả full result (có thể lớn).
    """
    from app.core.firebase import get_firebase

    db = get_firebase().db
    collection = db.collection("assessment_cache")

    docs = (
        collection
        .order_by("cached_at", direction="DESCENDING")
        .offset(offset)
        .limit(limit)
        .stream()
    )

    entries = []
    for doc in docs:
        data = doc.to_dict() or {}
        entries.append({
            "cache_key": data.get("cache_key", doc.id),
            "dominant_emotion": data.get("dominant_emotion"),
            "confidence": data.get("confidence"),
            "hit_count": data.get("hit_count", 0),
            "cached_at": str(data.get("cached_at")) if data.get("cached_at") else None,
        })

    return {"entries": entries, "offset": offset, "limit": limit}


@router.post("/cache/cleanup")
async def cleanup_cache(
    user: dict = Depends(get_current_user),
    dry_run: bool = Query(True, description="True = chỉ đếm, False = xóa thật"),
):
    """
    Xóa các cache entries đã hết hạn.

    - dry_run=True: Chỉ đếm số entries sẽ xóa
    - dry_run=False: Thực sự xóa
    """
    from app.modules.assessment.repositories.assessment_cache_repository import (
        get_assessment_cache_repository,
    )

    repo = get_assessment_cache_repository()
    count = repo.delete_expired(dry_run=dry_run)

    return {
        "action": "would_delete" if dry_run else "deleted",
        "count": count,
    }


@router.delete("/cache/all")
async def clear_all_cache(
    user: dict = Depends(get_current_user),
):
    """
    Xóa toàn bộ assessment cache.

    ⚠️ WARNING: Đây là destructive operation!
    Chỉ dùng để testing.
    """
    from app.modules.assessment.repositories.assessment_cache_repository import (
        get_assessment_cache_repository,
    )

    repo = get_assessment_cache_repository()
    count = repo.clear_all()

    return {"deleted": count}


# ==========================================
# Chat Cache Admin Endpoints
# ==========================================

@router.get("/chat-cache/stats")
async def get_chat_cache_stats(
    user: dict = Depends(get_current_user),
):
    """
    Lấy thống kê chat cache.
    """
    from app.modules.chat.repositories.chat_cache_repository import (
        get_chat_cache_repository,
    )

    repo = get_chat_cache_repository()
    stats = repo.get_stats()

    return stats


@router.post("/chat-cache/cleanup")
async def cleanup_chat_cache(
    user: dict = Depends(get_current_user),
    dry_run: bool = Query(True),
):
    """
    Xóa các chat cache entries đã hết hạn.
    """
    from app.modules.chat.repositories.chat_cache_repository import (
        get_chat_cache_repository,
    )

    repo = get_chat_cache_repository()
    count = repo.delete_expired(dry_run=dry_run)

    return {
        "action": "would_delete" if dry_run else "deleted",
        "count": count,
    }


# ==========================================
# Rate Limit Admin Endpoints
# ==========================================

@router.post("/rate-limit/cleanup")
async def cleanup_rate_limits(
    user: dict = Depends(get_current_user),
    dry_run: bool = Query(True),
):
    """
    Xóa các rate limit entries đã hết hạn.
    """
    rate_limiter = get_rate_limiter()
    count = rate_limiter.cleanup_expired(dry_run=dry_run)

    return {
        "action": "would_delete" if dry_run else "deleted",
        "count": count,
    }
