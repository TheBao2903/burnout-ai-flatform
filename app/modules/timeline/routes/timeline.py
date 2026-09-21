"""
==============================================================
File: timeline.py

Timeline Routes - GET /api/timeline?days=N.

Lay emotion + assessment docs tu Firestore, tra timeline aggregate.
==============================================================
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import get_current_user

logger = logging.getLogger("burnout.timeline.routes")

router = APIRouter(prefix="/api/timeline", tags=["Timeline"])


def get_timeline_svc():
    from app.modules.timeline.services import get_timeline_service
    return get_timeline_service()


def _fetch_emotions(user_id: str, since: datetime) -> List[Dict[str, Any]]:
    """Fetch emotion docs tu Firestore (best-effort)."""
    try:
        from app.core.firebase import FirestoreCollections, get_firebase
        from google.cloud import firestore
        db = get_firebase().db
        coll = db.collection(FirestoreCollections.EMOTIONS)
        # Query theo user + created_at (neu co field). Fallback: query chi user.
        try:
            query = (
                coll.where("user_id", "==", user_id)
                .where("created_at", ">=", since)
                .order_by("created_at", direction=firestore.Query.DESCENDING)
            )
        except Exception:
            query = (
                coll.where("user_id", "==", user_id)
                .order_by("created_at", direction=firestore.Query.DESCENDING)
            )
        docs = query.stream()
        return [{**d.to_dict(), "id": d.id} for d in docs]
    except Exception as exc:
        logger.warning("Fetch emotions failed: %s", exc)
        return []


def _fetch_assessments(user_id: str) -> Dict[str, Dict[str, Any]]:
    """Fetch assessments indexed by emotion_id."""
    try:
        from app.core.firebase import FirestoreCollections, get_firebase
        from google.cloud import firestore
        db = get_firebase().db
        coll = db.collection(FirestoreCollections.ASSESSMENTS)
        query = coll.where("user_id", "==", user_id)
        docs = query.stream()
        result: Dict[str, Dict[str, Any]] = {}
        for d in docs:
            data = d.to_dict()
            eid = data.get("emotion_id")
            if eid:
                result[eid] = data
        return result
    except Exception as exc:
        logger.warning("Fetch assessments failed: %s", exc)
        return {}


@router.get("")
async def get_timeline(
    days: int = Query(7, ge=1, le=90, description="So ngay (1-90)"),
    current_user: dict = Depends(get_current_user),
    svc=Depends(get_timeline_svc),
):
    """GET /api/timeline?days=N - Tra timeline aggregate cua user."""
    user_id = current_user.get("uid") or current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Khong xac dinh user_id.")

    since = datetime.utcnow() - timedelta(days=days)
    emotions = _fetch_emotions(user_id=user_id, since=since)
    assess_by_eid = _fetch_assessments(user_id=user_id)
    assessments = list(assess_by_eid.values())

    timeline = svc.aggregate(
        emotions=emotions, assessments=assessments, days=days,
    )
    return {
        "user_id": user_id,
        "days": days,
        "count": len(timeline),
        "items": [t.model_dump(mode="json") for t in timeline],
    }