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
            "current_stage": "greeting_and_probe",
            "user_turn_count": 0,
            "is_extended": False,
            "is_crisis_active": False,
            "started_at": now,
            "last_activity_at": now,
            "closed_at": None,
            "summary": None,
            "message_count": 0,
            "closed_reason": None,
            "used_topics": [],
            "primary_cause": None,
            "micro_action_offered": None,
            # PR 2: Context analysis fields (init rỗng để tránh None khi serialize)
            "detected_stressors": [],
            "detected_emotions": [],
            "behavioral_signals": [],
            "context_facts": [],
            "evidence_spans": [],
            "support_need": None,
            "last_analysis_confidence": 0.0,
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
        """Tăng message count tổng."""
        self.collection.document(session_id).update({
            "message_count": firestore.Increment(1)
        })

    def _process_message_transaction(
        self,
        transaction,
        session_id: str,
        new_stage: str,
        is_extended: Optional[bool],
        is_crisis_active: Optional[bool],
        increment_turn: bool,
        was_fatigued_turn1: Optional[bool] = None,
    ) -> int:
        """Atomic transaction: đọc state, kiểm tra version, cập nhật stage + turn.

        Q5/GAP-8: Gộp 2 writes (increment + update_stage) vào 1 transaction
        để tránh race khi nhiều worker xử lý cùng session.

        Returns:
            user_turn_count SAU KHI increment (để route tính stage).

        Raises:
            ValueError: nếu session không tồn tại.
        """
        doc_ref = self.collection.document(session_id)
        snapshot = doc_ref.get(transaction=transaction)
        if not snapshot.exists:
            raise ValueError(f"Session {session_id} disappeared mid-transaction")

        data = snapshot.to_dict() or {}
        current_turn = int(data.get("user_turn_count", 0))

        if increment_turn:
            new_turn = current_turn + 1
        else:
            new_turn = current_turn

        updates = {
            "current_stage": new_stage,
            "user_turn_count": new_turn,
            "last_activity_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        if is_extended is not None:
            updates["is_extended"] = is_extended
        if is_crisis_active is not None:
            updates["is_crisis_active"] = is_crisis_active
        if was_fatigued_turn1 is not None:
            updates["was_fatigued_turn1"] = was_fatigued_turn1
        transaction.update(doc_ref, updates)
        return new_turn

    def process_message_atomically(
        self,
        session_id: str,
        new_stage: str,
        is_extended: Optional[bool] = None,
        is_crisis_active: Optional[bool] = None,
        increment_turn: bool = True,
        was_fatigued_turn1: Optional[bool] = None,
    ) -> int:
        """Public API cho transaction trên. Trả về user_turn_count mới.

        Raises:
            ValueError: nếu session không tồn tại.
        """
        @firestore.transactional
        def _txn_fn(transaction):
            return self._process_message_transaction(
                transaction, session_id, new_stage,
                is_extended, is_crisis_active, increment_turn,
                was_fatigued_turn1,
            )

        transaction = self.db.transaction()
        return _txn_fn(transaction)

    def get_user_turn_count(self, session_id: str) -> int:
        """Đọc nhanh user_turn_count từ session."""
        doc = self.collection.document(session_id).get()
        if not doc.exists:
            return 0
        data = doc.to_dict() or {}
        return int(data.get("user_turn_count", 0))

    def get_session_flags(self, session_id: str) -> dict:
        """Đọc các flag cần cho state machine: is_extended, is_crisis_active, was_fatigued_turn1, user_extended."""
        doc = self.collection.document(session_id).get()
        if not doc.exists:
            return {
                "is_extended": False,
                "is_crisis_active": False,
                "was_fatigued_turn1": False,
                "user_extended": False,
                "current_stage": None,
                "is_closed": False,
            }
        data = doc.to_dict() or {}
        return {
            "is_extended": bool(data.get("is_extended", False)),
            "is_crisis_active": bool(data.get("is_crisis_active", False)),
            "was_fatigued_turn1": bool(data.get("was_fatigued_turn1", False)),
            "user_extended": bool(data.get("user_extended", False)),
            "current_stage": data.get("current_stage"),
            "is_closed": data.get("status") == "closed",
        }

    def extend_session(self, session_id: str) -> bool:
        """Kích hoạt gia hạn phiên trò chuyện (User-driven extension +3 lượt)."""
        doc_ref = self.collection.document(session_id)
        doc = doc_ref.get()
        if not doc.exists:
            return False
        doc_ref.update({
            "status": "active",
            "user_extended": True,
            "closed_at": None,
            "closed_reason": None,
            "updated_at": datetime.utcnow(),
        })
        logger.info("Extended chat session %s (user_extended=True)", session_id)
        return True

    def increment_user_turns(self, session_id: str) -> None:
        """Tăng số lượt hợp lệ của user (STA 4+2 discipline)."""
        self.collection.document(session_id).update({
            "user_turn_count": firestore.Increment(1),
            "message_count": firestore.Increment(1),
            "last_activity_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })

    def update_stage(
        self,
        session_id: str,
        stage: str,
        is_extended: Optional[bool] = None,
        is_crisis_active: Optional[bool] = None,
    ) -> None:
        """Cập nhật trạng thái hội thoại và các cờ điều phối."""
        updates = {
            "current_stage": stage,
            "updated_at": datetime.utcnow(),
        }
        if is_extended is not None:
            updates["is_extended"] = is_extended
        if is_crisis_active is not None:
            updates["is_crisis_active"] = is_crisis_active
        self.collection.document(session_id).update(updates)

    def close_session(
        self,
        session_id: str,
        reason: str,
        summary: Optional[str] = None,
        primary_cause: Optional[str] = None,
        micro_action_offered: Optional[str] = None,
    ) -> Optional[ChatSession]:
        """
        Đóng session.

        Args:
            session_id: Session ID
            reason: idle_timeout | max_duration | manual | completed_wrap_up | max_turns_completed
            summary: Optional session summary
            primary_cause: Nguyên nhân chính (STA Compact Context Tagging)
            micro_action_offered: Micro-action 5 phút đã khuyến nghị (STA Compact)
        """
        now = datetime.utcnow()
        doc_ref = self.collection.document(session_id)

        reason = "manual" if reason == "manual_user_decision" else reason
        if reason not in {"idle_timeout", "max_duration", "manual", "completed_wrap_up", "max_turns_completed"}:
            raise ValueError("Invalid chat session close reason")
        updates = {
            "status": "closed",
            "closed_at": now,
            "closed_reason": reason,
            "summary": summary,
            "updated_at": now,
        }
        if primary_cause is not None:
            updates["primary_cause"] = primary_cause
        if micro_action_offered is not None:
            updates["micro_action_offered"] = micro_action_offered

        doc_ref.update(updates)

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
                    current_stage=new_session.current_stage,
                    user_turn_count=new_session.user_turn_count,
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
                    current_stage=getattr(active_session, "current_stage", "greeting_and_probe"),
                    user_turn_count=getattr(active_session, "user_turn_count", 0),
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
                current_stage=new_session.current_stage,
                user_turn_count=new_session.user_turn_count,
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

    def add_used_topic(self, session_id: str, topic: str) -> None:
        """Thêm 1 topic vào used_topics của session (idempotent).

        Dùng bởi ProbingQuestionsService để tránh hỏi lặp topic giữa
        các request trong cùng session. State nằm trên Firestore nên
        chia sẻ đúng giữa nhiều gunicorn worker.
        """
        if not topic:
            return
        doc_ref = self.collection.document(session_id)
        doc_ref.update({
            "used_topics": firestore.ArrayUnion([topic]),
            "updated_at": datetime.utcnow(),
        })

    def update_session_tagging(
        self,
        session_id: str,
        primary_cause: Optional[str] = None,
        micro_action_offered: Optional[str] = None,
    ) -> None:
        """Cập nhật Context Tagging (STA Compact) cho session.

        Chỉ ghi đè khi giá trị mới khác None, tránh overwrite kết quả
        đã ghi từ lượt trước (vd Turn 2.5 → Turn 3 phản ánh lại cùng topic).
        """
        updates = {"updated_at": datetime.utcnow()}
        if primary_cause:
            updates["primary_cause"] = primary_cause
        if micro_action_offered:
            updates["micro_action_offered"] = micro_action_offered
        if len(updates) > 1:
            self.collection.document(session_id).update(updates)

    def update_context_analysis(
        self,
        session_id: str,
        detected_stressors: Optional[list] = None,
        detected_emotions: Optional[list] = None,
        behavioral_signals: Optional[list] = None,
        context_facts: Optional[list] = None,
        evidence_spans: Optional[list] = None,
        support_need: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> None:
        """PR 2: Cập nhật context analysis lên session document.

        - Dùng ArrayUnion cho list fields (không ghi đè, chỉ thêm).
        - Dùng set cho scalar fields (chỉ update khi khác None).
        - Best-effort: lỗi Firestore KHÔNG block chat flow.
        """
        try:
            doc_ref = self.collection.document(session_id)
            updates: dict = {"updated_at": datetime.utcnow()}

            if detected_stressors:
                updates["detected_stressors"] = firestore.ArrayUnion(detected_stressors)
            if detected_emotions:
                updates["detected_emotions"] = firestore.ArrayUnion(detected_emotions)
            if behavioral_signals:
                updates["behavioral_signals"] = firestore.ArrayUnion(behavioral_signals)
            if context_facts:
                updates["context_facts"] = firestore.ArrayUnion(context_facts)
            if evidence_spans:
                updates["evidence_spans"] = firestore.ArrayUnion(evidence_spans)
            if support_need is not None:
                updates["support_need"] = support_need
            if confidence is not None:
                updates["last_analysis_confidence"] = confidence

            if len(updates) > 1:
                doc_ref.update(updates)
        except Exception as exc:
            logger.debug("update_context_analysis skipped for session %s: %s", session_id, exc)

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

    def get_sessions_by_assessment(self, assessment_id: str, limit: int = 10) -> list[ChatSession]:
        """Lấy sessions gần nhất theo assessment_id (moi trang thai)."""
        query = (
            self.collection
            .where("assessment_id", "==", assessment_id)
            .order_by("last_activity_at", direction=firestore.Query.DESCENDING)
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
