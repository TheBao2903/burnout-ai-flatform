"""
==============================================================
File: burnout.py

Burnout Routes - API endpoints cho Burnout Engine.

Endpoints:
- GET  /api/burnout/latest           -> Lay burnout result moi nhat cua user
- GET  /api/burnout/history         -> Lay lich su (default 20 item)
- POST /api/burnout/recommendations -> Sinh recommendations tu latest burnout

NOTE: Main burnout analysis flow la POST /api/v1/assessments/{id}/analyze
      su dung BurnoutInputBuilder va BurnoutEngine.

==============================================================
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user

logger = logging.getLogger("burnout.routes")

router = APIRouter(prefix="/api/burnout", tags=["Burnout"])


# ==========================================
# Dependency
# ==========================================

def get_burnout_svc():
    from app.modules.burnout.services.burnout_service import get_burnout_service
    return get_burnout_service()


# ==========================================
# Routes
# ==========================================

@router.get("/latest")
async def get_latest_burnout(
    current_user: dict = Depends(get_current_user),
    svc=Depends(get_burnout_svc),
):
    """GET /api/burnout/latest - Tra burnout result moi nhat cua user."""
    user_id = current_user.get("uid") or current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Khong xac dinh user_id.")

    latest = svc.get_latest(user_id=user_id)
    if latest is None:
        raise HTTPException(status_code=404, detail="Chua co burnout result.")
    return latest


@router.get("/history")
async def get_burnout_history(
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
    svc=Depends(get_burnout_svc),
):
    """GET /api/burnout/history?limit=N - Tra lich su burnout cua user."""
    user_id = current_user.get("uid") or current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Khong xac dinh user_id.")
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit phai trong [1, 100].")

    history: List[Dict[str, Any]] = svc.get_history(
        user_id=user_id, limit=limit,
    )
    return {"user_id": user_id, "count": len(history), "items": history}


@router.post("/recommendations")
async def get_recommendations(
    current_user: dict = Depends(get_current_user),
    svc=Depends(get_burnout_svc),
):
    """POST /api/burnout/recommendations - Lay recommendations tu latest burnout.

    Neu user chua co burnout result -> 404.

    NOTE: Burnout analysis chinh thuc di qua POST /api/v1/assessments/{id}/analyze
    """
    from app.modules.burnout.models.burnout import BurnoutEngineOutput

    user_id = current_user.get("uid") or current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Khong xac dinh user_id.")

    latest = svc.get_latest(user_id=user_id)
    if latest is None:
        raise HTTPException(
            status_code=404,
            detail="Chua co burnout result. Hay goi POST /api/v1/assessments/{id}/analyze truoc.",
        )

    # Reconstruct BurnoutEngineOutput tu doc
    try:
        from app.modules.burnout.models.burnout import (
            BurnoutResult,
            BurnoutFactor,
        )
        factors_data = latest.get("factors", [])
        factors = [
            BurnoutFactor(**f) for f in factors_data
        ]
        burnout_result = BurnoutResult(
            burnout_score=latest["burnout_score"],
            data_completeness=latest.get("data_completeness", 0.5),
            risk_level=latest["risk_level"],
            factors=factors,
            recommendations=latest.get("recommendations", []),
            analyzed_at=latest.get("analyzed_at") or "1970-01-01T00:00:00",
        )
        output = BurnoutEngineOutput(
            burnout=burnout_result,
            insight=latest.get("insight", {}),
        )
    except Exception as exc:
        logger.exception("Reconstruct burnout failed")
        raise HTTPException(
            status_code=500,
            detail=f"Loi reconstruct burnout: {exc}",
        )

    recs = svc.get_recommendations(burnout=output)
    return {
        "user_id": user_id,
        "burnout_score": output.burnout.burnout_score,
        "risk_level": output.burnout.risk_level,
        "count": len(recs),
        "items": [r.model_dump() for r in recs],
    }
