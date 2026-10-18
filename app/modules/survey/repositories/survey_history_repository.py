"""
==============================================================
File: survey_history_repository.py

SurveyHistoryRepository - Lưu và truy vấn lịch sử survey trong Firestore.

Collection: FirestoreCollections.SURVEY_HISTORY ("survey_history").
Mỗi assessment chỉ có một survey record (upsert behavior).

Features:
- Lưu survey theo assessment
- Upsert (update nếu đã tồn tại)
- Query lịch sử survey theo user
- Aggregation helpers cho dashboard
==============================================================
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from google.cloud import firestore

from app.core.firebase import FirestoreCollections, get_firebase
from app.modules.survey.models.survey_history import (
    SurveyData,
    SurveyHistoryRecord,
)

logger = logging.getLogger("burnout.survey.repo")


class SurveyHistoryRepository:
    """Repository cho survey history."""

    def __init__(self):
        self.db = get_firebase().db
        self.collection = self.db.collection(FirestoreCollections.SURVEY_HISTORY)
        self.periodic_collection = self.db.collection(FirestoreCollections.PERIODIC_SURVEYS)

    def save(
        self,
        assessment_id: str,
        user_id: str,
        survey: Dict[str, Any],
        status: str = "completed",
        analysis_result: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Lưu survey vào Firestore (upsert theo assessment_id).

        Args:
            assessment_id: Assessment ID.
            user_id: Firebase uid.
            survey: Survey data dict (raw answers).
            status: "in_progress" hoặc "completed".
            analysis_result: Kết quả phân tích (tùy chọn).

        Returns:
            Document id.
        """
        now = datetime.utcnow()

        # Check if survey exists for this assessment
        existing = self.get_by_assessment(assessment_id)
        doc_id = existing.get("id") if existing else None

        data = {
            "assessment_id": assessment_id,
            "user_id": user_id,
            "survey": survey,
            "status": status,
            "completed_at": now if status == "completed" else None,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        # Save analysis result if provided
        if analysis_result:
            data["analysis_result"] = analysis_result

        if doc_id:
            # Update existing
            doc_ref = self.collection.document(doc_id)
            doc_ref.update(data)
            logger.info("Updated survey %s for assessment %s", doc_id, assessment_id)
            return doc_id
        else:
            # Create new
            data["created_at"] = firestore.SERVER_TIMESTAMP
            doc_ref = self.collection.document()
            doc_ref.set(data)
            logger.info("Created survey %s for assessment %s", doc_ref.id, assessment_id)
            return doc_ref.id

    def get_by_assessment(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        """Lấy survey của một assessment.

        Args:
            assessment_id: Assessment ID.

        Returns:
            Survey dict hoặc None.
        """
        query = self.collection.where("assessment_id", "==", assessment_id).limit(1)
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            return data
        return None

    def get_by_id(self, survey_id: str) -> Optional[Dict[str, Any]]:
        """Lấy survey theo document id.

        Args:
            survey_id: Document id.

        Returns:
            Survey dict hoặc None.
        """
        doc = self.collection.document(survey_id).get()
        if doc.exists:
            data = doc.to_dict() or {}
            data["id"] = doc.id
            return data
        return None

    def list_by_user(
        self,
        user_id: str,
        limit: int = 30,
        completed_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Lấy lịch sử survey của user.

        Args:
            user_id: Firebase uid.
            limit: Max docs.
            completed_only: True -> chỉ lấy survey đã completed.

        Returns:
            List of survey dicts (mới nhất trước).
        """
        # Query đơn giản nhất có thể - chỉ filter user_id, không filter status
        # Vì query `.where(status, ...)` với completed_only=True cần composite index
        # nên ta lấy tất cả rồi filter bằng Python
        query = self.collection.where("user_id", "==", user_id).limit(limit * 3)

        results = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id

            # Filter completed_only bằng Python (tránh composite index)
            if completed_only:
                status = data.get("status")
                if status != "completed":
                    continue

            results.append(data)

        # Sort bằng Python theo completed_at DESC
        def get_sort_key(item):
            ts = item.get("completed_at")
            if ts is None:
                ts = item.get("created_at")
            if isinstance(ts, datetime):
                return ts
            return datetime.min

        results.sort(key=get_sort_key, reverse=True)
        return results[:limit]

    def get_recent_completed_surveys(self, user_id: str, limit: int = 14) -> List[Dict[str, Any]]:
        """Lấy các survey completed gần đây nhất của user."""
        query = self.collection.where("user_id", "==", user_id).limit(limit * 3)
        results = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            if data.get("status") == "completed":
                results.append(data)
                
        def get_sort_key(item):
            ts = item.get("completed_at")
            if ts is None:
                ts = item.get("created_at")
            if isinstance(ts, datetime):
                return ts
            return datetime.min

        results.sort(key=get_sort_key, reverse=True)
        return results[:limit]

    def list_by_user_in_range(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Lấy surveys trong khoảng thời gian.

        Args:
            user_id: Firebase uid.
            start_date: Start datetime.
            end_date: End datetime.
            limit: Max docs.

        Returns:
            List of survey dicts.
        """
        query = (
            self.collection
            .where("user_id", "==", user_id)
            .where("status", "==", "completed")
            .where("completed_at", ">=", start_date.isoformat() + "Z")
            .where("completed_at", "<", end_date.isoformat() + "Z")
            .order_by("completed_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        results = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            results.append(data)
        return results

    def count_by_user(self, user_id: str, completed_only: bool = True) -> int:
        """Đếm surveys của user.

        Args:
            user_id: Firebase uid.
            completed_only: True -> chỉ đếm survey đã completed.

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

    def update_status(
        self,
        assessment_id: str,
        status: str,
    ) -> bool:
        """Cập nhật trạng thái survey.

        Args:
            assessment_id: Assessment ID.
            status: "in_progress" hoặc "completed".

        Returns:
            True nếu cập nhật thành công.
        """
        survey = self.get_by_assessment(assessment_id)
        if not survey:
            return False

        now = datetime.utcnow()
        update_data = {
            "status": status,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        if status == "completed":
            update_data["completed_at"] = now

        self.collection.document(survey["id"]).update(update_data)
        logger.info("Updated survey status to %s for assessment %s", status, assessment_id)
        return True

    def delete_by_assessment(self, assessment_id: str) -> bool:
        """Xóa survey của một assessment.

        Args:
            assessment_id: Assessment ID.

        Returns:
            True nếu xóa thành công.
        """
        survey = self.get_by_assessment(assessment_id)
        if not survey:
            return False
        self.collection.document(survey["id"]).delete()
        logger.info("Deleted survey for assessment %s", assessment_id)
        return True

    # ==========================================
    # Aggregation helpers cho Dashboard
    # ==========================================

    def get_avg_sleep_hours(
        self,
        user_id: str,
        days: int = 30,
    ) -> Optional[float]:
        """Lấy số giờ ngủ trung bình của user.

        Args:
            user_id: Firebase uid.
            days: Số ngày gần đây.

        Returns:
            Avg sleep hours hoặc None.
        """
        from datetime import timedelta

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        surveys = self.list_by_user_in_range(user_id, start_date, end_date, limit=1000)
        if not surveys:
            return None

        sleep_hours = []
        for s in surveys:
            survey_data = s.get("survey", {})
            if isinstance(survey_data, dict):
                hours = survey_data.get("sleep_hours") or survey_data.get("sleep_hour")
                if hours is not None:
                    sleep_hours.append(float(hours))

        if not sleep_hours:
            return None

        return round(sum(sleep_hours) / len(sleep_hours), 1)

    def get_avg_workload(
        self,
        user_id: str,
        days: int = 30,
    ) -> Optional[float]:
        """Lấy số giờ làm việc trung bình của user.

        Args:
            user_id: Firebase uid.
            days: Số ngày gần đây.

        Returns:
            Avg working hours hoặc None.
        """
        from datetime import timedelta

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        surveys = self.list_by_user_in_range(user_id, start_date, end_date, limit=1000)
        if not surveys:
            return None

        work_hours = []
        for s in surveys:
            survey_data = s.get("survey", {})
            if isinstance(survey_data, dict):
                hours = survey_data.get("working_hours") or survey_data.get("working_hour")
                if hours is not None:
                    work_hours.append(float(hours))

        if not work_hours:
            return None

        return round(sum(work_hours) / len(work_hours), 1)

    def get_avg_stress_level(
        self,
        user_id: str,
        days: int = 30,
    ) -> Optional[float]:
        """Lấy mức stress trung bình của user.

        Args:
            user_id: Firebase uid.
            days: Số ngày gần đây.

        Returns:
            Avg stress level (1-10) hoặc None.
        """
        from datetime import timedelta

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        surveys = self.list_by_user_in_range(user_id, start_date, end_date, limit=1000)
        if not surveys:
            return None

        stress_levels = []
        for s in surveys:
            survey_data = s.get("survey", {})
            if isinstance(survey_data, dict):
                stress = survey_data.get("stress_level")
                if stress is not None:
                    stress_levels.append(float(stress))

        if not stress_levels:
            return None

        return round(sum(stress_levels) / len(stress_levels), 1)

    def save_periodic_survey(
        self,
        user_id: str,
        job_resources: Dict[str, Any],
        six_areas: Dict[str, Any],
    ) -> str:
        """Lưu kết quả khảo sát định kỳ (Job Resources & Six Areas of Worklife)."""
        data = {
            "user_id": user_id,
            "job_resources": job_resources,
            "six_areas": six_areas,
            "submitted_at": firestore.SERVER_TIMESTAMP,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        doc_ref = self.periodic_collection.document()
        doc_ref.set(data)
        logger.info("Saved periodic survey %s for user %s", doc_ref.id, user_id)
        return doc_ref.id

    def get_latest_periodic_survey(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Lấy kết quả khảo sát định kỳ mới nhất của user."""
        try:
            docs = (
                self.periodic_collection
                .where("user_id", "==", user_id)
                .order_by("submitted_at", direction=firestore.Query.DESCENDING)
                .limit(1)
                .stream()
            )
            for doc in docs:
                d = doc.to_dict()
                d["id"] = doc.id
                return d
        except Exception as e:
            logger.warning("Failed to query latest periodic survey for %s: %s", user_id, e)
        return None


# ==========================================
# Singleton
# ==========================================

_survey_history_repo: Optional[SurveyHistoryRepository] = None


def get_survey_history_repository() -> SurveyHistoryRepository:
    """Lay SurveyHistoryRepository singleton."""
    global _survey_history_repo
    if _survey_history_repo is None:
        _survey_history_repo = SurveyHistoryRepository()
    return _survey_history_repo
