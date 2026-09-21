"""
==============================================================
File: chat_session_repository.py

ChatSessionRepository - Quản lý Emotion Chat Sessions trong Firestore.

Collection: "emotion_chat_sessions"

Features:
- Tạo session mới
- Tìm active session
- Close session (idle timeout / max duration)
- Update last activity
- Generate summary
==============================================================
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from google.cloud import firestore

from app.core.firebase import FirestoreCollections, get_firebase
from app.core.settings import get_settings
from app.modules.chat.models.chat_session import (
    ChatSession,
    ChatSessionCreate,
    ChatSessionResponse,
)

logger = logging.getLogger("burnout.chat.session")


class ChatSessionRepository:
    """Repository cho Emotion Chat Sessions."""

    def __init__(self):
        self.db = get_firebase().db
        self.collection = self.db.collection("emotion_chat_sessions")
        self.settings = get_settings().emotion_chat

    def _is_session_valid(self, session: ChatSession) -> tuple[bool, Optional[str]]:
        """
        Kiểm tra session còn hợp lệ không.

        Returns:
            (is_valid, reason_if_invalid)
        """
        now = datetime.utcnow()
        settings = self.settings

        # Make both datetimes naive for comparison if needed
        session_started = session.started_at
        if hasattr(session_started, 'replace') and session_started.tzinfo is not None:
            # Convert aware datetime to naive UTC
            session_started = session_started.replace(tzinfo=None) - session_started.utcoffset()

        # Check max duration
        max_duration = timedelta(hours=settings.max_session_hours)
        if now - session_started > max_duration:
            return False, "max_duration"

        # Check idle timeout
        last_activity = session.last_activity_at
        if hasattr(last_activity, 'replace') and last_activity.tzinfo is not None:
            last_activity = last_activity.replace(tzinfo=None) - last_activity.utcoffset()

        idle_timeout = timedelta(minutes=settings.idle_timeout_minutes)
        if now - last_activity > idle_timeout:
            return False, "idle_timeout"

        return True, None

    def get_active_session(self, assessment_id: str) -> Optional[ChatSession]:
        """Tìm active session của một assessment."""
        query = (
            self.collection
            .where("assessment_id", "==", assessment_id)
            .where("status", "==", "active")
            .order_by("last_activity_at", direction=firestore.Query.DESCENDING)
            .limit(1)
        )

        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            return ChatSession(**data)
        return None

    def create_session(self, data: ChatSessionCreate) -> ChatSession:
        """Tạo session mới."""
        now = datetime.utcnow()
        doc_ref = self.collection.document()

        session_data = {
            "assessment_id": data.assessment_id,
            "user_id": data.user_id,
            "status": "active",
            "started_at": now,
            "last_activity_at": now,
            "closed_at": None,
            "summary": None,
            "message_count": 0,
            "closed_reason": None,
            "created_at": now,
            "updated_at": now,
        }

        doc_ref.set(session_data)
        logger.info(
            "Created new chat session %s for assessment %s",
            doc_ref.id, data.assessment_id
        )

        session_data["id"] = doc_ref.id
        return ChatSession(**session_data)

    def update_last_activity(self, session_id: str) -> None:
        """Cập nhật last_activity_at."""
        now = datetime.utcnow()
        self.collection.document(session_id).update({
            "last_activity_at": now,
            "updated_at": now,
        })

    def increment_message_count(self, session_id: str) -> None:
        """Tăng message count."""
        self.collection.document(session_id).update({
            "message_count": firestore.Increment(1)
        })

    def close_session(
        self,
        session_id: str,
        reason: str,
        summary: Optional[str] = None
    ) -> Optional[ChatSession]:
        """
        Đóng session.

        Args:
            session_id: Session ID
            reason: idle_timeout | max_duration | manual
            summary: Optional session summary
        """
        now = datetime.utcnow()
        doc_ref = self.collection.document(session_id)

        doc_ref.update({
            "status": "closed",
            "closed_at": now,
            "closed_reason": reason,
            "summary": summary,
            "updated_at": now,
        })

        logger.info("Closed chat session %s (reason=%s)", session_id, reason)

        # Return updated session
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict() or {}
            data["id"] = doc.id
            return ChatSession(**data)
        return None

    def delete_session(self, session_id: str) -> bool:
        """Xóa hoàn toàn session document.

        Args:
            session_id: Session ID (cũng là assessment_id)

        Returns:
            True nếu xóa thành công
        """
        doc_ref = self.collection.document(session_id)
        doc = doc_ref.get()

        if doc.exists:
            doc_ref.delete()
            logger.info("Deleted chat session %s", session_id)
            return True
        else:
            logger.warning("Session %s not found for deletion", session_id)
            return False

    def find_or_create_session(self, assessment_id: str, user_id: str) -> ChatSessionResponse:
        """
        Tim active session hoac tao moi.

        Returns:
            ChatSessionResponse voi thong tin session
        """
        # Tim active session
        active_session = self.get_active_session(assessment_id)

        if active_session:
            # Kiem tra session con hop le khong
            is_valid, invalid_reason = self._is_session_valid(active_session)

            logger.info(
                "Session %s validity check: is_valid=%s, reason=%s, started_at=%s, last_activity=%s, max_hours=%d, idle_timeout=%d",
                active_session.id,
                is_valid,
                invalid_reason,
                active_session.started_at,
                active_session.last_activity_at,
                self.settings.max_session_hours,
                self.settings.idle_timeout_minutes,
            )

            if not is_valid:
                # Close old session
                logger.info(
                    "Session %s expired (reason=%s), creating new session",
                    active_session.id, invalid_reason
                )
                self.close_session(
                    session_id=active_session.id,
                    reason=invalid_reason,
                    summary=None  # TODO: generate summary
                )

                # Tạo session mới
                new_session = self.create_session(
                    ChatSessionCreate(assessment_id=assessment_id, user_id=user_id)
                )
                return ChatSessionResponse(
                    session_id=new_session.id,
                    assessment_id=new_session.assessment_id,
                    status=new_session.status,
                    is_new=True,
                    message=f"Session trước đã đóng ({invalid_reason}). Session mới đã được tạo."
                )
            else:
                # Reuse session
                logger.info("Reusing active session %s", active_session.id)
                return ChatSessionResponse(
                    session_id=active_session.id,
                    assessment_id=active_session.assessment_id,
                    status=active_session.status,
                    is_new=False,
                    message=None
                )
        else:
            # Tạo session mới
            new_session = self.create_session(
                ChatSessionCreate(assessment_id=assessment_id, user_id=user_id)
            )
            logger.info("Created new session for assessment %s", assessment_id)
            return ChatSessionResponse(
                session_id=new_session.id,
                assessment_id=new_session.assessment_id,
                status=new_session.status,
                is_new=True,
                message=None
            )

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Lấy session theo ID."""
        doc = self.collection.document(session_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        data["id"] = doc.id
        return ChatSession(**data)

    def get_sessions_by_user(self, user_id: str, limit: int = 10) -> list[ChatSession]:
        """Lấy sessions của user."""
        query = (
            self.collection
            .where("user_id", "==", user_id)
            .order_by("started_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )

        sessions = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["id"] = doc.id
            sessions.append(ChatSession(**data))
        return sessions


# ==========================================
# Singleton
# ==========================================

_chat_session_repo: Optional[ChatSessionRepository] = None


def get_chat_session_repository() -> ChatSessionRepository:
    """Lay ChatSessionRepository singleton."""
    global _chat_session_repo
    if _chat_session_repo is None:
        _chat_session_repo = ChatSessionRepository()
    return _chat_session_repo
