"""
==============================================================
File: chat_history_repository.py

ChatHistoryRepository - Lưu và truy vấn lịch sử chat trong Firestore.

Collection: FirestoreCollections.CHAT_HISTORY ("chat_history").
Document id = auto_id.

Features:
- Lưu từng tin nhắn chat theo assessment
- Lưu GPT analysis cho mỗi user message
- Query lịch sử chat theo user/assessment
- Aggregation helpers cho dashboard
==============================================================
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from google.cloud import firestore
from google.api_core.exceptions import FailedPrecondition

from app.core.firebase import FirestoreCollections, get_firebase
from app.modules.chat.models.chat_history import (
    ChatAnalysis,
    ChatHistoryRecord,
    ChatSessionSummary,
)

logger = logging.getLogger("burnout.chat.repo")


class ChatHistoryRepository:
    """Repository cho chat history."""

    def __init__(self):
        self.db = get_firebase().db
        self.collection = self.db.collection(FirestoreCollections.CHAT_HISTORY)

    def save_message(
        self,
        assessment_id: str,
        user_id: str,
        role: str,
        content: str,
        analysis: Optional[Dict[str, Any]] = None,
        ai_model: Optional[str] = None,
        session_id: Optional[str] = None,
        client_message_id: Optional[str] = None,
        is_fallback: bool = False,
        finish_reason: Optional[str] = None,
        response_to: Optional[str] = None,
    ) -> str:
        """Lưu một tin nhắn chat vào Firestore.

        Args:
            assessment_id: Assessment ID.
            user_id: Firebase uid.
            role: "user" hoặc "assistant".
            content: Nội dung tin nhắn.
            analysis: Optional GPT analysis dict (sẽ convert sang ChatAnalysis).
            ai_model: Tên model AI đã sử dụng.
            session_id: Optional session ID (nullable cho backward compatibility).
            client_message_id: Idempotency key từ client (Q5). Dùng để detect
                duplicate request. Nếu None, không enforce idempotency.

        Returns:
            Document id.
        """
        doc_ref = self.collection.document()
        now = datetime.utcnow()

        # Build analysis object if provided
        analysis_data = None
        if analysis:
            analysis_data = {
                "stress_level": analysis.get("stress_level", {}),
                "fatigue_signal": analysis.get("fatigue_signal", {}),
                "motivation_level": analysis.get("motivation_level", {}),
                "work_avoidance_signal": analysis.get("work_avoidance_signal", {}),
                "sleep_problem_signal": analysis.get("sleep_problem_signal", {}),
                "emotional_negative_signal": analysis.get("emotional_negative_signal", {}),
                "workload_signal": analysis.get("workload_signal", {}),
                "burnout_related_signal": analysis.get("burnout_related_signal", {}),
                "detected_signals": analysis.get("detected_signals", []),
                "important_phrases": analysis.get("important_phrases", []),
                "uncertainty": analysis.get("uncertainty", 0.0),
                "ai_model": ai_model,
                "analyzed_at": now.isoformat() + "Z",
            }

        data = {
            "assessment_id": assessment_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "analysis": analysis_data,
            "created_at": firestore.SERVER_TIMESTAMP,
            "is_fallback": is_fallback,
            "finish_reason": finish_reason,
            "response_to": response_to,
        }
        # session_id is nullable - only add if provided (backward compatible)
        if session_id:
            data["session_id"] = session_id
        # Q5: Idempotency key
        if client_message_id:
            data["client_message_id"] = client_message_id
        doc_ref.set(data)

        logger.info(
            "Saved chat message %s for assessment %s (role=%s, has_analysis=%s, client_msg_id=%s)",
            doc_ref.id, assessment_id, role, bool(analysis), bool(client_message_id),
        )
        return doc_ref.id

    def get_by_client_message_id(
        self,
        assessment_id: str,
        client_message_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Tìm message trong assessment theo client_message_id.

        Dùng cho Q5 idempotency: nếu client retry request cùng ID,
        trả về message cũ thay vì xử lý lại.
        """
        if not client_message_id:
            return None
        query = (
            self.collection
            .where("assessment_id", "==", assessment_id)
            .where("client_message_id", "==", client_message_id)
            .limit(1)
        )
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            return data
        return None

    def get_messages_by_assessment(
        self,
        assessment_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Lấy tất cả tin nhắn của một assessment.

        Args:
            assessment_id: Assessment ID.
            limit: Max documents.

        Returns:
            List of message dicts (id included).
        """
        return self._get_recent_messages("assessment_id", assessment_id, limit)

    def _get_recent_messages(self, field: str, value: str, limit: int) -> List[Dict[str, Any]]:
        filtered = self.collection.where(field, "==", value)
        try:
            documents = list(filtered.order_by(
                "created_at", direction=firestore.Query.DESCENDING,
            ).limit(limit).stream())
        except FailedPrecondition as exc:
            if "requires an index" not in str(exc).lower():
                raise
            # Session history is small (STA 3/4 turns plus optional extension).
            # A single-field query works while the composite index is absent
            # or building. Do not limit before sorting: that loses newer rows.
            logger.warning("Chat history composite index unavailable; using single-field query (%s)", field)
            documents = list(filtered.stream())

        results = []
        for doc in documents:
            data = doc.to_dict() or {}
            if data.get("created_at") is None:
                continue  # Match order_by semantics for missing fields.
            data["id"] = doc.id
            results.append(data)

        def chronological(message):
            created = message["created_at"]
            if isinstance(created, str):
                created = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            return created, message["id"]

        results.sort(key=chronological)
        return results[-limit:] if limit > 0 else []

    def list_by_user(
        self,
        user_id: str,
        limit: int = 30,
        cursor: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Lấy tin nhắn gần nhất của user (mọi assessment).

        Args:
            user_id: Firebase uid.
            limit: Max docs per page.
            cursor: Optional dict co 'id' + 'created_at' de tiep tuc page.

        Returns:
            List of message dicts.
        """
        query = (
            self.collection
            .where("user_id", "==", user_id)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )

        if cursor and "doc_ref" in cursor:
            query = query.start_after(cursor["doc_ref"])

        results = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            results.append(data)
        return results

    def list_by_assessment(
        self,
        assessment_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Lấy tin nhắn của một assessment.

        Args:
            assessment_id: Assessment ID.
            limit: Max docs.

        Returns:
            List of message dicts.
        """
        query = (
            self.collection
            .where("assessment_id", "==", assessment_id)
            .order_by("created_at", direction=firestore.Query.ASCENDING)
            .limit(limit)
        )
        results = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            results.append(data)
        return results

    def get_user_messages_in_range(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Lấy tin nhắn trong khoảng thời gian.

        Args:
            user_id: Firebase uid.
            start_date: Start datetime (inclusive).
            end_date: End datetime (exclusive).
            limit: Max docs.

        Returns:
            List of message dicts.
        """
        query = (
            self.collection
            .where("user_id", "==", user_id)
            .where("created_at", ">=", start_date.isoformat() + "Z")
            .where("created_at", "<", end_date.isoformat() + "Z")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        results = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            results.append(data)
        return results

    def count_by_assessment(self, assessment_id: str) -> int:
        """Đếm số tin nhắn của một assessment.

        Returns:
            int count.
        """
        try:
            query = self.collection.where("assessment_id", "==", assessment_id)
            agg = query.count()
            results = agg.get()
            return int(results[0][0].value)
        except Exception as exc:
            logger.warning("count_by_assessment failed: %s", exc)
            return 0

    def count_by_user(self, user_id: str) -> int:
        """Đếm tổng số tin nhắn của user.

        Returns:
            int count.
        """
        try:
            query = self.collection.where("user_id", "==", user_id)
            agg = query.count()
            results = agg.get()
            return int(results[0][0].value)
        except Exception as exc:
            logger.warning("count_by_user failed: %s", exc)
            return 0

    def get_latest_message(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        """Lấy tin nhắn cuối cùng của assessment.

        Returns:
            Message dict hoặc None.
        """
        query = (
            self.collection
            .where("assessment_id", "==", assessment_id)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(1)
        )
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            return data
        return None

    def get_session_summary(self, assessment_id: str) -> Optional[ChatSessionSummary]:
        """Tạo tóm tắt session chat.

        Args:
            assessment_id: Assessment ID.

        Returns:
            ChatSessionSummary hoặc None nếu không có tin nhắn.
        """
        messages = self.get_messages_by_assessment(assessment_id, limit=1000)
        if not messages:
            return None

        # Count messages
        message_count = len(messages)

        # Get last message time
        last_message_at = None
        for msg in reversed(messages):
            if msg.get("created_at"):
                try:
                    last_message_at = msg["created_at"]
                    if isinstance(last_message_at, str):
                        last_message_at = datetime.fromisoformat(last_message_at.replace("Z", "+00:00"))
                    break
                except Exception:
                    continue

        # Check if has analysis
        has_analysis = any(msg.get("analysis") is not None for msg in messages)

        # Aggregate signals from all user messages with analysis
        all_signals: Dict[str, set] = {}
        all_stress_scores: List[float] = []
        all_burnout_scores: List[float] = []
        all_keywords: List[str] = []

        for msg in messages:
            if msg.get("role") == "user" and msg.get("analysis"):
                analysis = msg["analysis"]

                # Stress level
                stress = analysis.get("stress_level", {})
                if isinstance(stress, dict) and "score" in stress:
                    all_stress_scores.append(float(stress["score"]))

                # Burnout signal
                burnout = analysis.get("burnout_related_signal", {})
                if isinstance(burnout, dict) and "score" in burnout:
                    all_burnout_scores.append(float(burnout["score"]))

                # Detected signals
                detected = analysis.get("detected_signals", [])
                for sig in detected:
                    if sig not in all_signals:
                        all_signals[sig] = set()
                    all_signals[sig].add(sig)

                # Keywords
                keywords = analysis.get("important_phrases", [])
                all_keywords.extend(keywords)

        # Calculate aggregates
        avg_stress = sum(all_stress_scores) / len(all_stress_scores) if all_stress_scores else None
        avg_burnout = sum(all_burnout_scores) / len(all_burnout_scores) if all_burnout_scores else None

        return ChatSessionSummary(
            assessment_id=assessment_id,
            user_id=messages[0].get("user_id", ""),
            message_count=message_count,
            last_message_at=last_message_at,
            has_analysis=has_analysis,
            aggregated_stress_level=round(avg_stress, 2) if avg_stress else None,
            aggregated_burnout_signal=round(avg_burnout, 2) if avg_burnout else None,
            detected_signals=list(all_signals.keys()),
            keywords=list(set(all_keywords))[:20],  # Dedupe and limit
        )

    def delete_by_assessment(self, assessment_id: str) -> int:
        """Xóa tất cả tin nhắn của một assessment.

        Returns:
            Số docs đã xóa.
        """
        docs = self.collection.where("assessment_id", "==", assessment_id).stream()
        count = 0
        for doc in docs:
            doc.reference.delete()
            count += 1
        if count:
            logger.info("Deleted %d chat messages for assessment %s", count, assessment_id)
        return count

    def delete(self, message_id: str) -> bool:
        """Xóa một tin nhắn.

        Returns:
            True nếu xóa thành công.
        """
        doc_ref = self.collection.document(message_id)
        doc = doc_ref.get()
        if not doc.exists:
            return False
        doc_ref.delete()
        logger.info("Deleted chat message %s", message_id)
        return True

    def get_messages_by_session(
        self,
        session_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Lấy tin nhắn của một session (theo thứ tự thời gian).

        Args:
            session_id: Session ID.
            limit: Max documents.

        Returns:
            List of message dicts (id included).
        """
        return self._get_recent_messages("session_id", session_id, limit)


# ==========================================
# Singleton
# ==========================================

_chat_history_repo: Optional[ChatHistoryRepository] = None


def get_chat_history_repository() -> ChatHistoryRepository:
    """Lay ChatHistoryRepository singleton."""
    global _chat_history_repo
    if _chat_history_repo is None:
        _chat_history_repo = ChatHistoryRepository()
    return _chat_history_repo
