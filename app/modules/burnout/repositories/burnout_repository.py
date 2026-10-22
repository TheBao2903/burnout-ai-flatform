"""
==============================================================
File: burnout_repository.py

BurnoutRepository - Luu va truy van burnout results trong Firestore.

Collection = FirestoreCollections.BURNOUT_RESULTS ("burnout_results").
Document id = auto_id.
==============================================================
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from google.cloud import firestore

from app.core.firebase import FirestoreCollections, get_firebase

logger = logging.getLogger("burnout.repo")


class BurnoutRepository:
    """Repository cho burnout results."""

    def __init__(self):
        self.db = get_firebase().db
        self.collection = self.db.collection(FirestoreCollections.BURNOUT_RESULTS)

    def save(
        self,
        user_id: str,
        result: Dict[str, Any],
        assessment_id: Optional[str] = None,
        emotion_id: Optional[str] = None,
    ) -> str:
        """Luu burnout result, tra document id.

        Args:
            user_id: Firebase uid.
            result: Burnout result dict (from BurnoutEngine output).
            assessment_id: Assessment ID (central identifier).
            emotion_id: Optional FK emotion doc.
        """
        existing = self.get_by_assessment(assessment_id) if assessment_id else None
        if existing and existing.get("user_id") != user_id:
            raise ValueError("Burnout result ownership mismatch")
        if existing:
            doc_ref = self.collection.document(existing["id"])
        elif assessment_id:
            from hashlib import sha256
            doc_ref = self.collection.document(sha256(f"{user_id}:{assessment_id}".encode()).hexdigest())
        else:
            doc_ref = self.collection.document()
        data = {
            "user_id": user_id,
            "assessment_id": assessment_id,  # Central identifier
            "emotion_id": emotion_id,
            "burnout_score": result.get("burnout_score", 0.0),
            "data_completeness": result.get("data_completeness", 0.0),
            "risk_level": result.get("risk_level", "unknown"),
            "trend": result.get("trend", "insufficient_data"),
            "factors": result.get("factors", []),
            "recommendations": result.get("recommendations", []),
            "insight": result.get("insight", {}),
            "analyzed_at": result.get("analyzed_at", datetime.utcnow()),
        }
        for field in ("survey_type", "questionnaire_version", "questionnaire_scores", "engine_version",
                      "burnout_core", "context", "supporting_signals", "data_quality", "data_sufficiency",
                      "interpretation", "confidence", "disclaimer"):
            if field in result:
                data[field] = result[field]
        if hasattr(data["insight"], "model_dump"):
            data["insight"] = data["insight"].model_dump()
        if existing:
            doc_ref.update(data)
        else:
            data["created_at"] = firestore.SERVER_TIMESTAMP
            doc_ref.set(data)
        logger.info(
            "Saved burnout doc %s for assessment %s (score=%.1f, risk=%s)",
            doc_ref.id, assessment_id,
            result.get("burnout_score", 0.0),
            result.get("risk_level", "unknown"),
        )
        return doc_ref.id

    def get(self, burnout_id: str) -> Optional[Dict[str, Any]]:
        """Lấy burnout result theo document id."""
        doc = self.collection.document(burnout_id).get()
        if doc.exists:
            data = doc.to_dict() or {}
            data["id"] = doc.id
            return data
        return None

    def get_by_assessment(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        """Lấy burnout result theo assessment_id.

        Mỗi assessment chỉ có một burnout result.
        """
        query = self.collection.where("assessment_id", "==", assessment_id).limit(1)
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            return data
        return None

    def list_by_user(
        self,
        user_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Lay danh sach burnout results cua user (moi nhat truoc).

        Args:
            user_id: Firebase uid.
            limit: max docs tra ve.
        """
        query = (
            self.collection
            .where("user_id", "==", user_id)
            .order_by("analyzed_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        results = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            results.append(data)
        return results

    def list_by_assessment(self, assessment_id: str) -> List[Dict[str, Any]]:
        """Lấy tất cả burnout results của một assessment."""
        query = (
            self.collection
            .where("assessment_id", "==", assessment_id)
            .order_by("analyzed_at", direction=firestore.Query.DESCENDING)
        )
        results = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            results.append(data)
        return results

    def delete(self, burnout_id: str) -> bool:
        """Xóa burnout result."""
        doc_ref = self.collection.document(burnout_id)
        doc = doc_ref.get()
        if not doc.exists:
            return False
        doc_ref.delete()
        logger.info("Deleted burnout doc %s", burnout_id)
        return True

    def delete_by_assessment(self, assessment_id: str) -> int:
        """Xóa tất cả burnout results của một assessment."""
        docs = self.collection.where("assessment_id", "==", assessment_id).stream()
        count = 0
        for doc in docs:
            doc.reference.delete()
            count += 1
        if count:
            logger.info("Deleted %d burnout docs for assessment %s", count, assessment_id)
        return count


# ==========================================
# Singleton
# ==========================================

_burnout_repo: Optional[BurnoutRepository] = None


def get_burnout_repository() -> BurnoutRepository:
    """Lay BurnoutRepository singleton."""
    global _burnout_repo
    if _burnout_repo is None:
        _burnout_repo = BurnoutRepository()
    return _burnout_repo
