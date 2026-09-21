"""
==============================================================
File: emotion_repository.py

EmotionRepository - Luu va truy van emotion records trong Firestore.

Document id = tu sinh (auto_id).
Collection = FirestoreCollections.EMOTIONS.

Sprint 26 optimizations:
- Pagination cursor (start_after) de load page-by-page.
- Aggregation helpers (count_by_user).
- Batch insert (batch_save).
- Cached collection reference.
- Composite index definitions: see firestore.indexes.json.
==============================================================
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from google.cloud import firestore

from app.core.firebase import FirestoreCollections, get_firebase
from app.modules.emotion.models.emotion import EmotionResult

logger = logging.getLogger("burnout.emotion.repo")


class EmotionRepository:
    """Repository cho emotion records."""

    def __init__(self):
        db = get_firebase().db
        # Cache collection reference (tranh re-lookup nhieu lan)
        self._db = db
        self._collection_name = FirestoreCollections.EMOTIONS
        self._collection = db.collection(FirestoreCollections.EMOTIONS)

    @property
    def collection(self):
        return self._collection

    def save(
        self,
        user_id: str,
        emotion: EmotionResult,
        image_key: Optional[str] = None,
        assessment_id: Optional[str] = None,
    ) -> str:
        """Luu emotion vao Firestore, tra document id.

        Args:
            user_id: Firebase uid.
            emotion: EmotionResult.
            image_key: relative path trong R2 bucket.
            assessment_id: Optional assessment ID để link với Assessment Session.

        Returns:
            Document id.
        """
        doc_ref = self._collection.document()
        data = self._build_emotion_data(user_id, emotion, image_key, assessment_id)
        doc_ref.set(data)
        logger.info("Saved emotion doc %s for user %s (assessment=%s)", doc_ref.id, user_id, assessment_id)
        return doc_ref.id

    def batch_save(
        self,
        user_id: str,
        emotions: List[EmotionResult],
        image_keys: Optional[List[Optional[str]]] = None,
    ) -> List[str]:
        """Luu nhieu emotion trong 1 batch (atomicity: all-or-nothing).

        Args:
            user_id: Firebase uid.
            emotions: list EmotionResult.
            image_keys: optional list image_key (parallel voi emotions).
                Neu None -> image_key=None cho tat ca.

        Returns:
            list[doc_id] theo thu tu.

        Raises:
            Exception: neu batch fail (rollback).
        """
        if not emotions:
            return []
        if image_keys is None:
            image_keys = [None] * len(emotions)
        if len(image_keys) != len(emotions):
            raise ValueError(
                f"image_keys length ({len(image_keys)}) != emotions length ({len(emotions)})"
            )

        batch = self._db.batch()
        doc_ids: List[str] = []
        for emotion, img_key in zip(emotions, image_keys):
            doc_ref = self._collection.document()
            doc_ids.append(doc_ref.id)
            data = self._build_emotion_data(user_id, emotion, img_key)
            batch.set(doc_ref, data)

        batch.commit()
        logger.info(
            "Batch saved %d emotion docs for user %s", len(emotions), user_id,
        )
        return doc_ids

    def _build_emotion_data(
        self,
        user_id: str,
        emotion: EmotionResult,
        image_key: Optional[str],
        assessment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Helper: build dict payload tu EmotionResult."""
        data = {
            "user_id": user_id,
            "emotions": emotion.emotions.model_dump(),
            "dominant_emotion": emotion.dominant_emotion,
            "confidence": emotion.confidence,
            "age": emotion.age,
            "gender": emotion.gender,
            "image_url": image_key,  # Store image_key in image_url field (compatible with frontend)
            "image_key": image_key,  # Keep for backward compat
            "analyzed_at": (
                emotion.analyzed_at.isoformat() + "Z"
                if emotion.analyzed_at
                else datetime.utcnow().isoformat() + "Z"
            ),
            "created_at": firestore.SERVER_TIMESTAMP,
        }
        if assessment_id:
            data["assessment_id"] = assessment_id
        return data

    def list_by_user(
        self,
        user_id: str,
        limit: int = 30,
        cursor: Optional[Dict[str, Any]] = None,
    ) -> List[dict]:
        """Lay emotion gan nhat cua user, sort theo analyzed_at desc.

        Args:
            user_id: Firebase uid.
            limit: max docs per page.
            cursor: optional dict co 'id' + 'analyzed_at' de tiep tuc tu
                diem truoc (sau khi stream het 1 page).

        Returns:
            list[dict] emotion docs (id included).
        """
        query = (
            self._collection.where("user_id", "==", user_id)
            .order_by("analyzed_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        if cursor and "id" in cursor and "analyzed_at" in cursor:
            query = query.start_after(
                {  # type: ignore
                    firestore.firestore.FieldFilter.reference_field(): cursor["id"]
                }
            ) if False else query  # Placeholder; use snapshot doc
            # Dung snapshot reference de start_after (an toan hon dict)
            cursor_doc = self._collection.document(cursor["id"]).get()
            if cursor_doc.exists:
                query = query.start_after(cursor_doc)

        results = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            results.append(data)
        return results

    def list_by_user_in_range(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 100,
    ) -> List[dict]:
        """Lay emotion trong khoang thoi gian [start, end).

        Args:
            user_id: Firebase uid.
            start_date: datetime (inclusive).
            end_date: datetime (exclusive).
            limit: max docs.

        Returns:
            list[dict] emotion docs.
        """
        query = (
            self._collection.where("user_id", "==", user_id)
            .where("analyzed_at", ">=", start_date.isoformat() + "Z")
            .where("analyzed_at", "<", end_date.isoformat() + "Z")
            .order_by("analyzed_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        results = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            results.append(data)
        return results

    def list_by_dominant_emotion(
        self,
        user_id: str,
        dominant_emotion: str,
        limit: int = 50,
    ) -> List[dict]:
        """Lay emotion co dominant_emotion cu the (sau khi fix issue #1 tach dual-write).

        Args:
            user_id: Firebase uid.
            dominant_emotion: 'sad', 'happy', ...
            limit: max docs.

        Returns:
            list[dict] emotion docs.
        """
        query = (
            self._collection.where("user_id", "==", user_id)
            .where("dominant_emotion", "==", dominant_emotion)
            .order_by("analyzed_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        results = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            results.append(data)
        return results

    def list_by_assessment(
        self,
        assessment_id: str,
        limit: int = 100,
    ) -> List[dict]:
        """Lay emotion records theo assessment ID.

        Args:
            assessment_id: Assessment Session ID.
            limit: max docs.

        Returns:
            list[dict] emotion docs.
        """
        query = (
            self._collection.where("assessment_id", "==", assessment_id)
            .order_by("analyzed_at", direction=firestore.Query.ASCENDING)
            .limit(limit)
        )
        results = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            results.append(data)
        return results

    def count_by_assessment(self, assessment_id: str) -> int:
        """Đếm số emotion records của một assessment.

        Returns:
            int count.
        """
        try:
            query = self._collection.where("assessment_id", "==", assessment_id)
            agg = query.count()
            results = agg.get()
            return int(results[0][0].value)
        except Exception as exc:
            logger.warning("count_by_assessment failed: %s", exc)
            return 0

    def count_by_user(self, user_id: str) -> int:
        """Dem tong so emotion cua user (aggregation query, nhanh hon stream+count).

        Returns:
            int so docs. Tra 0 neu loi.
        """
        try:
            query = self._collection.where("user_id", "==", user_id)
            agg = query.count()
            results = agg.get()
            # results[0][0].value la int count
            return int(results[0][0].value)
        except Exception as exc:
            logger.warning("count_by_user failed: %s", exc)
            return 0

    def count_by_user_in_range(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> int:
        """Dem emotion trong khoang thoi gian."""
        try:
            query = (
                self._collection.where("user_id", "==", user_id)
                .where("analyzed_at", ">=", start_date.isoformat() + "Z")
                .where("analyzed_at", "<", end_date.isoformat() + "Z")
            )
            agg = query.count()
            results = agg.get()
            return int(results[0][0].value)
        except Exception as exc:
            logger.warning("count_by_user_in_range failed: %s", exc)
            return 0

    def get(self, emotion_id: str) -> Optional[dict]:
        """Lay 1 emotion theo id."""
        doc = self._collection.document(emotion_id).get()
        if doc.exists:
            data = doc.to_dict() or {}
            data["id"] = doc.id
            return data
        return None

    def clear_image(self, emotion_id: str) -> bool:
        """Xoa image_key trong doc (sau khi xoa khoi R2)."""
        self._collection.document(emotion_id).update(
            {"image_key": None, "image_cleared_at": firestore.SERVER_TIMESTAMP}
        )
        return True

    def update_assessment(
        self,
        emotion_id: str,
        risk_level: str,
        summary: str,
        recommendations: List[str],
        key_signals: List[str],
        disclaimer: str,
        ai_model: Optional[str] = None,
        ai_prompt_version: Optional[str] = None,
        input_emotion_snapshot: Optional[dict] = None,
    ) -> bool:
        """Luu / update AI assessment vao emotion document.

        Vi sao co method rieng: assessment duoc generate SAU emotion (Gemini
        call bat dong bo), nen can update doc da save.

        UNIFIED: AI assessment được lưu vào emotion doc (embedded assessment field),
        KHÔNG còn lưu vào collection riêng.
        """
        assessment_data = {
            "risk_level": risk_level,
            "summary": summary,
            "recommendations": recommendations,
            "key_signals": key_signals,
            "disclaimer": disclaimer,
            "generated_at": firestore.SERVER_TIMESTAMP,
        }
        if ai_model:
            assessment_data["ai_model"] = ai_model
        if ai_prompt_version:
            assessment_data["ai_prompt_version"] = ai_prompt_version
        if input_emotion_snapshot:
            assessment_data["input_snapshot"] = input_emotion_snapshot

        self._collection.document(emotion_id).update(
            {
                "assessment": assessment_data,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        )
        logger.info("Updated assessment for emotion doc %s", emotion_id)
        return True

    def delete(self, emotion_id: str) -> bool:
        """Xoa emotion document.

        Returns:
            True neu ton tai va xoa, False neu khong.
        """
        doc_ref = self._collection.document(emotion_id)
        doc = doc_ref.get()
        if not doc.exists:
            return False
        doc_ref.delete()
        logger.info("Deleted emotion doc %s", emotion_id)
        return True

    def delete_by_user(self, user_id: str) -> int:
        """Xoa tất cả emotion docs của một user.

        Warning: Đây là hành động destructive. Chỉ gọi khi xóa user hoặc assessment.

        Returns:
            Số docs đã xóa.
        """
        docs = self._collection.where("user_id", "==", user_id).stream()
        count = 0
        for doc in docs:
            doc.reference.delete()
            count += 1
        if count:
            logger.info("Deleted %d emotion docs for user %s", count, user_id)
        return count

    def delete_by_assessment(self, assessment_id: str) -> int:
        """Xoa tất cả emotion docs của một assessment.

        Args:
            assessment_id: Assessment Session ID.

        Returns:
            Số docs đã xóa.
        """
        docs = self._collection.where("assessment_id", "==", assessment_id).stream()
        count = 0
        for doc in docs:
            doc.reference.delete()
            count += 1
        if count:
            logger.info("Deleted %d emotion docs for assessment %s", count, assessment_id)
        return count

    def get_pagination_cursor(
        self,
        emotions: List[Dict[str, Any]],
    ) -> Optional[Dict[str, str]]:
        """Tao cursor tu list emotion (last item) de tiep tuc page sau.

        Args:
            emotions: list emotion docs (co 'id' + 'analyzed_at').

        Returns:
            cursor dict hoac None neu list rong.
        """
        if not emotions:
            return None
        last = emotions[-1]
        return {
            "id": last.get("id", ""),
            "analyzed_at": last.get("analyzed_at", ""),
        }


# Singleton
_emotion_repo: Optional[EmotionRepository] = None


def get_emotion_repository() -> EmotionRepository:
    """Lay EmotionRepository singleton."""
    global _emotion_repo
    if _emotion_repo is None:
        _emotion_repo = EmotionRepository()
    return _emotion_repo