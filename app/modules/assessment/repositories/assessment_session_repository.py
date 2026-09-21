"""
==============================================================
File: assessment_session_repository.py

AssessmentSessionRepository - Quản lý lifecycle của Assessment Sessions.

Collection: FirestoreCollections.ASSESSMENTS ("assessments").

Features:
- Tạo assessment mới
- Cập nhật trạng thái
- Query lịch sử assessment theo user
- Tính data_completeness
==============================================================
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from google.cloud import firestore

from app.core.firebase import FirestoreCollections, get_firebase
from app.modules.assessment.models.assessment_session import (
    AssessmentSession,
    AssessmentStatus,
)

logger = logging.getLogger("burnout.assessment.session.repo")


class AssessmentSessionRepository:
    """Repository cho Assessment Sessions."""

    def __init__(self):
        self.db = get_firebase().db
        self.collection = self.db.collection(FirestoreCollections.ASSESSMENTS)

    def create(
        self,
        user_id: str,
        status: str = "collecting",
    ) -> str:
        """Tạo assessment mới.

        Args:
            user_id: Firebase uid.
            status: Trạng thái ban đầu.

        Returns:
            Document id (assessment_id).
        """
        doc_ref = self.collection.document()
        now = datetime.utcnow()

        data = {
            "user_id": user_id,
            "status": status,
            "status_detail": {
                "has_emotion": False,
                "emotion_count": 0,
                "has_survey": False,
                "has_chat": False,
                "has_result": False,
                "is_completed": False,
            },
            "data_completeness": 0.0,
            "burnout_result_id": None,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "completed_at": None,
        }

        doc_ref.set(data)
        logger.info("Created assessment %s for user %s", doc_ref.id, user_id)
        return doc_ref.id

    def get(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        """Lấy assessment theo id.

        Args:
            assessment_id: Assessment ID.

        Returns:
            Assessment dict hoặc None.
        """
        doc = self.collection.document(assessment_id).get()
        if doc.exists:
            data = doc.to_dict() or {}
            data["id"] = doc.id
            return data
        return None

    def update_status(
        self,
        assessment_id: str,
        status: str,
        status_detail: Optional[Dict[str, Any]] = None,
        data_completeness: Optional[float] = None,
        burnout_result_id: Optional[str] = None,
    ) -> bool:
        """Cập nhật trạng thái assessment.

        Args:
            assessment_id: Assessment ID.
            status: Trạng thái mới.
            status_detail: Trạng thái chi tiết.
            data_completeness: Độ hoàn thiện dữ liệu.
            burnout_result_id: FK -> burnout result.

        Returns:
            True nếu cập nhật thành công.
        """
        doc_ref = self.collection.document(assessment_id)
        doc = doc_ref.get()

        if not doc.exists:
            return False

        update_data: Dict[str, Any] = {
            "status": status,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        if status_detail is not None:
            update_data["status_detail"] = status_detail

        if data_completeness is not None:
            update_data["data_completeness"] = data_completeness

        if burnout_result_id is not None:
            update_data["burnout_result_id"] = burnout_result_id

        if status == "completed":
            update_data["completed_at"] = firestore.SERVER_TIMESTAMP

        doc_ref.update(update_data)
        logger.info("Updated assessment %s to status %s", assessment_id, status)
        return True

    def update_status_detail(
        self,
        assessment_id: str,
        status_detail: Dict[str, Any],
    ) -> bool:
        """Cập nhật status_detail của assessment.

        Args:
            assessment_id: Assessment ID.
            status_detail: Trạng thái chi tiết mới.

        Returns:
            True nếu cập nhật thành công.
        """
        doc_ref = self.collection.document(assessment_id)
        doc = doc_ref.get()

        if not doc.exists:
            return False

        doc_ref.update({
            "status_detail": status_detail,
            "updated_at": firestore.SERVER_TIMESTAMP,
        })
        return True

    def mark_emotion_collected(
        self,
        assessment_id: str,
        emotion_count: int,
    ) -> bool:
        """Đánh dấu đã thu thập emotion.

        Args:
            assessment_id: Assessment ID.
            emotion_count: Số frame emotion đã thu thập.

        Returns:
            True nếu cập nhật thành công.
        """
        assessment = self.get(assessment_id)
        if not assessment:
            return False

        status_detail = assessment.get("status_detail", {})
        status_detail["has_emotion"] = True
        status_detail["emotion_count"] = emotion_count

        # Tính data_completeness mới
        completeness = self._calculate_completeness(status_detail)

        return self.update_status(
            assessment_id,
            assessment.get("status", "collecting"),
            status_detail=status_detail,
            data_completeness=completeness,
        )

    def mark_survey_submitted(self, assessment_id: str) -> bool:
        """Đánh dấu đã submit survey.

        Args:
            assessment_id: Assessment ID.

        Returns:
            True nếu cập nhật thành công.
        """
        assessment = self.get(assessment_id)
        if not assessment:
            return False

        status_detail = assessment.get("status_detail", {})
        status_detail["has_survey"] = True

        completeness = self._calculate_completeness(status_detail)

        return self.update_status(
            assessment_id,
            assessment.get("status", "collecting"),
            status_detail=status_detail,
            data_completeness=completeness,
        )

    def mark_chat_started(self, assessment_id: str) -> bool:
        """Đánh dấu đã bắt đầu chat.

        Args:
            assessment_id: Assessment ID.

        Returns:
            True nếu cập nhật thành công.
        """
        assessment = self.get(assessment_id)
        if not assessment:
            return False

        status_detail = assessment.get("status_detail", {})
        status_detail["has_chat"] = True

        completeness = self._calculate_completeness(status_detail)

        return self.update_status(
            assessment_id,
            assessment.get("status", "collecting"),
            status_detail=status_detail,
            data_completeness=completeness,
        )

    def mark_result_ready(
        self,
        assessment_id: str,
        burnout_result_id: str,
    ) -> bool:
        """Đánh dấu đã có kết quả burnout.

        Args:
            assessment_id: Assessment ID.
            burnout_result_id: FK -> burnout result.

        Returns:
            True nếu cập nhật thành công.
        """
        assessment = self.get(assessment_id)
        if not assessment:
            return False

        status_detail = assessment.get("status_detail", {})
        status_detail["has_result"] = True
        status_detail["is_completed"] = True

        completeness = self._calculate_completeness(status_detail)

        return self.update_status(
            assessment_id,
            "completed",
            status_detail=status_detail,
            data_completeness=completeness,
            burnout_result_id=burnout_result_id,
        )

    @staticmethod
    def _calculate_completeness(status_detail: Dict[str, Any]) -> float:
        """Tính data_completeness dựa trên status_detail.

        UNIFIED WEIGHTS (aligned with BurnoutEngine):
        - Emotion: 30% (cần ít nhất 1 frame)
        - Survey: 30% (sleep, workload, stress data)
        - Chat: 20% (optional - cần có analysis)
        - Trend: 20% (bonus - có historical data)

        Returns:
            Float 0.0 - 1.0
        """
        total = 0.0

        # Emotion: 30% (cần ít nhất 1 frame)
        if status_detail.get("has_emotion"):
            total += 0.30

        # Survey: 30%
        if status_detail.get("has_survey"):
            total += 0.30

        # Chat: 20% (optional - cần có analysis mới tính)
        if status_detail.get("has_chat"):
            total += 0.20

        # Trend: 20% bonus (có historical data)
        if status_detail.get("has_result"):  # has_result = có burnout result = có trend context
            total += 0.20

        return round(min(1.0, total), 2)

    def list_by_user(
        self,
        user_id: str,
        limit: int = 30,
        status_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lấy danh sách assessments của user.

        Args:
            user_id: Firebase uid.
            limit: Max docs.
            status_filter: Lọc theo status (collecting, analyzing, completed, cancelled).

        Returns:
            List of assessment dicts.
        """
        query = self.collection.where("user_id", "==", user_id)

        if status_filter:
            query = query.where("status", "==", status_filter)

        query = query.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)

        results = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            results.append(data)
        return results

    def list_recent(
        self,
        user_id: str,
        days: int = 30,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Lấy các assessments gần đây của user.

        Args:
            user_id: Firebase uid.
            days: Số ngày gần đây.
            limit: Max docs.

        Returns:
            List of assessment dicts.
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)

        query = (
            self.collection
            .where("user_id", "==", user_id)
            .where("created_at", ">=", cutoff.isoformat() + "Z")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )

        results = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            results.append(data)
        return results

    def count_by_user(self, user_id: str, completed_only: bool = True) -> int:
        """Đếm số assessments của user.

        Args:
            user_id: Firebase uid.
            completed_only: True -> chỉ đếm completed.

        Returns:
            int count.
        """
        try:
            query = self.collection.where("user_id", "==", user_id)
            if completed_only:
                query = query.where("status", "==", "completed")
            agg = query.count()
            results = agg.get()
            return int(results[0][0].value)
        except Exception as exc:
            logger.warning("count_by_user failed: %s", exc)
            return 0

    def delete(self, assessment_id: str) -> bool:
        """Xóa assessment.

        Args:
            assessment_id: Assessment ID.

        Returns:
            True nếu xóa thành công.
        """
        doc_ref = self.collection.document(assessment_id)
        doc = doc_ref.get()

        if not doc.exists:
            return False

        doc_ref.delete()
        logger.info("Deleted assessment %s", assessment_id)
        return True


# ==========================================
# Singleton
# ==========================================

_assessment_session_repo: Optional[AssessmentSessionRepository] = None


def get_assessment_session_repository() -> AssessmentSessionRepository:
    """Lay AssessmentSessionRepository singleton."""
    global _assessment_session_repo
    if _assessment_session_repo is None:
        _assessment_session_repo = AssessmentSessionRepository()
    return _assessment_session_repo
