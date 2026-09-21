"""
==============================================================
File: report.py

Report Routes - GET /api/report?month=YYYY-MM.

Aggregate emotion + assessment cua user trong thang -> Report.
==============================================================
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import get_current_user

logger = logging.getLogger("burnout.report.routes")

router = APIRouter(prefix="/api/report", tags=["Report"])


def get_report_svc():
    from app.modules.report.services import get_report_service
    return get_report_service()


def _fetch_emotions(user_id: str) -> List[Dict[str, Any]]:
    try:
        from app.core.firebase import FirestoreCollections, get_firebase
        from google.cloud import firestore
        db = get_firebase().db
        coll = db.collection(FirestoreCollections.EMOTIONS)
        query = (
            coll.where("user_id", "==", user_id)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
        )
        return [{**d.to_dict(), "id": d.id} for d in query.stream()]
    except Exception as exc:
        logger.warning("Fetch emotions failed: %s", exc)
        return []


def _fetch_assessments(user_id: str) -> Dict[str, Dict[str, Any]]:
    try:
        from app.core.firebase import FirestoreCollections, get_firebase
        db = get_firebase().db
        coll = db.collection(FirestoreCollections.ASSESSMENTS)
        query = coll.where("user_id", "==", user_id)
        result: Dict[str, Dict[str, Any]] = {}
        for d in query.stream():
            data = d.to_dict()
            eid = data.get("emotion_id")
            if eid:
                result[eid] = data
        return result
    except Exception as exc:
        logger.warning("Fetch assessments failed: %s", exc)
        return {}


@router.get("")
async def get_monthly_report(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$", description="YYYY-MM"),
    current_user: dict = Depends(get_current_user),
    svc=Depends(get_report_svc),
):
    """GET /api/report?month=YYYY-MM - Report thang cua user."""
    user_id = current_user.get("uid") or current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Khong xac dinh user_id.")

    emotions = _fetch_emotions(user_id=user_id)
    assess_by_eid = _fetch_assessments(user_id=user_id)
    assessments = list(assess_by_eid.values())

    report = svc.build_monthly_report(
        user_id=user_id,
        emotions=emotions,
        assessments=assessments,
        month=month,
    )
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"Khong co data trong thang {month}.",
        )
    return report.model_dump(mode="json")