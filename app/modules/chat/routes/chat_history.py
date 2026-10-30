"""
==============================================================
File: chat_history.py

Chat History Routes - API endpoints cho chat history.

POST /api/v1/assessments/{id}/chat     - Gui tin nhan chat
GET  /api/v1/assessments/{id}/chat     - Lay lich su chat
GET  /api/v1/assessments/{id}/chat/summary - Tom tat session chat
==============================================================
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from google.cloud import firestore
from app.modules.chat.repositories.chat_request_repository import ChatRequestRepository, ChatRequestConflict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.core.deps import get_current_user
from app.modules.chat.repositories.chat_history_repository import (
    ChatHistoryRepository,
    get_chat_history_repository,
)
from app.modules.chat.repositories.chat_session_repository import (
    ChatSessionRepository,
    get_chat_session_repository,
)
from app.modules.assessment.repositories.assessment_session_repository import (
    AssessmentSessionRepository,
    get_assessment_session_repository,
)
from app.modules.chat.services.chat_response_generator import (
    get_chat_response_generator,
    evaluate_crisis_safety,
)
from app.modules.chat.services.probing_questions import (
    get_probing_questions_service,
)

logger = logging.getLogger("burnout.chat.routes")

router = APIRouter(prefix="/api/v1/assessments", tags=["Chat"])


# ==========================================
# Request/Response Models
# ==========================================

class ChatMessageRequest(BaseModel):
    """Request body cho /chat endpoint.

    v2.1 breaking changes:
    - max_length giảm 2000 → 1000 (Q6 giới hạn input).
    - Bỏ field `analyze` (Q1) — backend KHÔNG gọi analyze_chat_text nữa.
    - Thêm `client_message_id` (Q5 idempotency).
    """

    message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Nội dung tin nhắn (tối đa 1000 ký tự)",
    )
    client_message_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Idempotency key (UUID) do client sinh. Nếu retry cùng ID, "
                    "backend trả về response cũ thay vì xử lý lại.",
    )


class ChatMessageResponse(BaseModel):
    """Response cho /chat endpoint.

    v2.1 breaking change: bỏ field `analysis` (Q1) — chat không gọi inline
    analysis nữa. Frontend Signal Panel sẽ hiển thị placeholder.
    """

    message_id: str
    role: str
    content: str
    created_at: str

    @field_validator("created_at", mode="before")
    @classmethod
    def normalize_timestamp(cls, value):
        if not value:
            return value
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()
    session_id: Optional[str] = Field(default=None, description="Session ID")
    session_message: Optional[str] = Field(
        default=None,
        description="Thông báo về session (VD: session mới đã được tạo)"
    )
    ui_action: Optional[dict] = Field(
        default=None,
        description="Hành động gợi ý giao diện (VD: decision_buttons tại Gatekeeper Lượt 4)"
    )
    is_fallback: bool = False
    finish_reason: Optional[str] = None
    can_reply: bool = Field(
        default=True,
        description="True nếu người dùng vẫn có thể tiếp tục trò chuyện; False nếu phiên đã đóng"
    )
    can_extend: bool = Field(
        default=False,
        description="True nếu phiên có thể được gia hạn thêm (+3 lượt) ở mốc tổng kết"
    )
    user_extended: bool = Field(
        default=False,
        description="True nếu phiên đang trong khối gia hạn của người dùng"
    )


class ChatHistoryResponse(BaseModel):
    """Response cho /chat (GET) endpoint."""

    assessment_id: str
    messages: list
    message_count: int
    has_analysis: bool
    current_session_id: Optional[str] = Field(default=None, description="Session ID hiện tại")
    is_closed: bool = Field(default=False, description="Phiên chat này đã hoàn tất đóng")
    can_extend: bool = Field(default=False, description="Phiên chat có thể gia hạn")
    user_extended: bool = Field(default=False, description="Phiên chat đã được gia hạn")


class ChatSummaryResponse(BaseModel):
    """Response cho /chat/summary endpoint."""

    assessment_id: str
    user_id: str
    message_count: int
    has_analysis: bool
    aggregated_stress_level: Optional[float] = None
    aggregated_burnout_signal: Optional[float] = None
    detected_signals: list
    keywords: list
    last_message_at: Optional[str] = None


# ==========================================
# Dependency
# ==========================================

def get_chat_repo() -> ChatHistoryRepository:
    return get_chat_history_repository()


def get_chat_session_repo() -> ChatSessionRepository:
    return get_chat_session_repository()


def get_assessment_repo() -> AssessmentSessionRepository:
    return get_assessment_session_repository()


# ==========================================
# v2.1: State machine pure function
# Đây là SINGLE SOURCE OF TRUTH cho stage (B1).
# Generator nhận stage từ route, KHÔNG tự suy ra.
# ==========================================

# Initial STA path: 3 turns, or 4 for fatigued users; explicit extension +3.
HARD_CAP_USER_TURNS = 7

# Q-C / Q-D: Crisis KHÔNG bị đóng bởi turn cap
# Khi crisis_active=true, route BYPASS turn cap ở bước tính stage.
# Khi crisis_active=false nhưng session cũ từng có crisis, reset về
# greeting_and_probe để user tiếp tục bình thường (nếu còn turn budget).


def is_fatigued_short_message(message: str) -> bool:
    """Phát hiện user trả lời quá ngắn ở Turn 1 (kiệt sức)."""
    msg = (message or "").lower().strip()
    if len(msg) > 15:
        return False
    keywords = [
        "mệt", "met", "không biết", "khong biet", "thôi", "thoi",
        "bình thường", "binh thuong", "ổn", "ok",
    ]
    return any(w in msg for w in keywords)


def decide_stage(
    current_turn_count: int,
    is_crisis_active: bool,
    is_fatigued_short: bool,
    was_extended: bool,
    new_msg_is_crisis: bool,
    user_extended: bool = False,
) -> tuple[str, bool, bool, Optional[bool]]:
    """B1: Pure function quyết stage. Trả (stage, is_completed, can_reply, next_is_extended).

    Q6: Happy path 3 turns, extended path 4 turns.
    STA User-Driven Extension: Nếu user_extended=True, cho phép chat tiếp tới max 6-7 turns (Hard Cap tối hậu).
    Q-C: Crisis KHÔNG bị hard cap. Khi msg mới có crisis, set crisis_support
         ngay bất kể turn hiện tại.
    Q-D: Khi session từng crisis (is_crisis_active=true) mà msg mới OK,
         cho phép tiếp tục bình thường, stage tính theo turn.
    """
    if new_msg_is_crisis:
        return "crisis_support", False, True, None
    base_end = 4 if (was_extended or is_fatigued_short) else 3
    if user_extended and current_turn_count > base_end:
        offset = current_turn_count - base_end
        stage = {1: "clarifying_cause", 2: "reflect_and_support"}.get(offset, "wrapping_up")
        return stage, offset >= 3, offset < 3, was_extended
    if current_turn_count <= 1:
        return "greeting_and_probe", False, True, False
    if current_turn_count == 2:
        return ("clarifying_cause", False, True, True) if is_fatigued_short else ("reflect_and_support", False, True, False)
    if current_turn_count < base_end:
        return "reflect_and_support", False, True, was_extended
    return "wrapping_up", True, False, was_extended


def _build_idempotent_replay(
    existing_user_msg: dict,
    chat_session_repo: ChatSessionRepository,
    chat_repo: Optional[ChatHistoryRepository] = None,
) -> dict:
    """Q5: Trả response giống hệt cho request retry cùng client_message_id.

    Đọc lại assistant message kế tiếp trong assessment (theo created_at).
    Trả về payload với cờ idempotent_replay=True để client biết.
    """
    from app.modules.chat.repositories.chat_history_repository import (
        get_chat_history_repository,
    )
    chat_repo = chat_repo or get_chat_history_repository()
    assessment_id = existing_user_msg.get("assessment_id")
    session_id = existing_user_msg.get("session_id")

    # Tìm assistant message gần nhất sau user message
    history = chat_repo.get_messages_by_session(session_id, limit=1000) if session_id else chat_repo.get_messages_by_assessment(assessment_id, limit=1000)
    user_idx = None
    for i, m in enumerate(history):
        if m.get("id") == existing_user_msg.get("id"):
            user_idx = i
            break

    assistant_msg = None
    if user_idx is not None:
        for j in range(user_idx + 1, len(history)):
            if history[j].get("role") == "user":
                break
            if history[j].get("role") == "assistant":
                assistant_msg = history[j]
                break

    sess = None
    if session_id:
        try:
            sess = chat_session_repo.get_session(session_id)
        except Exception:
            pass

    can_reply = bool(sess and sess.status == "active") if sess else False
    current_stage = getattr(sess, "current_stage", None) if sess else None
    user_turn_count = getattr(sess, "user_turn_count", 0) if sess else 0
    is_completed = sess.status == "closed" if sess else True

    return {
        "user_message": ChatMessageResponse(
            message_id=existing_user_msg.get("id", "idempotent_user"),
            role="user",
            content=existing_user_msg.get("content", ""),
            created_at=existing_user_msg.get("created_at").isoformat()
            if hasattr(existing_user_msg.get("created_at"), "isoformat")
            else str(existing_user_msg.get("created_at", "")),
            session_id=session_id,
            can_reply=can_reply,
        ).model_dump(),
        "assistant_message": ChatMessageResponse(
            message_id=assistant_msg.get("id", "idempotent_asst") if assistant_msg else "",
            role="assistant",
            content=assistant_msg.get("content", "") if assistant_msg else "",
            created_at=assistant_msg.get("created_at").isoformat()
            if assistant_msg and hasattr(assistant_msg.get("created_at"), "isoformat")
            else str(assistant_msg.get("created_at", "")) if assistant_msg else "",
            session_id=session_id,
            can_reply=can_reply,
        ).model_dump() if assistant_msg else None,
        "is_session_completed": is_completed,
        "session_status": "closed" if is_completed else "active",
        "current_stage": current_stage,
        "user_turn_count": user_turn_count,
        "micro_action_offered": getattr(sess, "micro_action_offered", None) if sess else None,
        "primary_cause": getattr(sess, "primary_cause", None) if sess else None,
        "can_extend": _session_state(sess, chat_session_repo).get("can_extend", False),
        "user_extended": bool(sess and sess.user_extended),
        "is_fallback": bool(assistant_msg and assistant_msg.get("is_fallback")),
        "finish_reason": assistant_msg.get("finish_reason") if assistant_msg else None,
        "idempotent_replay": True,
    }


# ==========================================
# Endpoints
# ==========================================

def _owned_assessment(assessment_id, user, assessment_repo):
    assessment = assessment_repo.get(assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    if assessment.get("user_id") != user["uid"]:
        raise HTTPException(403, "Not authorized")
    return assessment


async def _release_claim(ledger, claim):
    try:
        await asyncio.to_thread(ledger.release, claim)
    except Exception:
        # A committed reply stays valid even if a subsequent cleanup read fails.
        # Unfinished claims expire and cannot overwrite a newer worker's turn.
        logger.warning("Unable to release chat operation claim")


def _latest_session(repo, assessment_id):
    sessions = repo.get_sessions_by_assessment(assessment_id, limit=1)
    return sessions[0] if sessions else None


def _session_state(session, repo):
    if not session:
        return {"status": "none", "can_reply": False, "can_extend": False,
                "user_extended": False, "current_stage": None, "user_turn_count": 0,
                "is_crisis_active": False, "is_expired": False}
    valid, reason = repo._is_session_valid(session)
    closed = session.status != "active"
    return {
        "status": "closed" if closed else ("active" if valid else "expired"),
        "session_id": session.id,
        "can_reply": not closed and valid,
        "can_extend": bool(valid and session.current_stage == "wrapping_up"
                           and not session.user_extended
                           and session.closed_reason == "completed_wrap_up"),
        "user_extended": session.user_extended,
        "current_stage": session.current_stage, "user_turn_count": session.user_turn_count,
        "is_crisis_active": session.is_crisis_active, "is_extended": session.is_extended,
        "is_expired": not valid, "expired_reason": reason,
    }


def _message_payload(ident, role, content, session_id, now, **metadata):
    return ChatMessageResponse(message_id=ident, role=role, content=content,
                               created_at=now.isoformat(), session_id=session_id, **metadata).model_dump()


@router.post("/{assessment_id}/chat", response_model=dict)
async def send_chat_message(
    assessment_id: str, request: ChatMessageRequest,
    user: dict = Depends(get_current_user),
    chat_repo: ChatHistoryRepository = Depends(get_chat_repo),
    chat_session_repo: ChatSessionRepository = Depends(get_chat_session_repo),
    assessment_repo: AssessmentSessionRepository = Depends(get_assessment_repo),
):
    assessment = _owned_assessment(assessment_id, user, assessment_repo)
    is_crisis, crisis_response = evaluate_crisis_safety(request.message)
    ledger = ChatRequestRepository(chat_repo.db)
    try:
        claim = await asyncio.to_thread(ledger.claim, assessment_id, user["uid"],
                                        request.client_message_id or uuid4().hex, "send", request.message)
    except ChatRequestConflict as exc:
        # Never withhold immediate safety support behind a busy chat worker.
        if is_crisis:
            return {"assistant_message": _message_payload("safety-pending", "assistant", crisis_response,
                    None, datetime.now(timezone.utc), can_reply=True), "current_stage": "crisis_support",
                    "is_session_completed": False, "session_status": "crisis_support", "persistence_pending": True}
        raise HTTPException(409, {"code": str(exc), "message": "Tin nhắn đang được xử lý. Hãy thử lại cùng tin nhắn."})
    if "response" in claim:
        return {**claim["response"], "idempotent_replay": True}
    try:
        # Compatibility with requests stored before the operation ledger existed.
        if request.client_message_id:
            existing = chat_repo.get_by_client_message_id(assessment_id, request.client_message_id)
            if existing:
                if existing.get("content") != request.message:
                    raise HTTPException(409, {"code": "MESSAGE_ID_REUSED"})
                replay = _build_idempotent_replay(existing, chat_session_repo, chat_repo)
                await asyncio.to_thread(ledger.complete, claim, replay)
                return replay

        latest = _latest_session(chat_session_repo, assessment_id)
        if latest and latest.status == "closed" and latest.closed_reason not in {"idle_timeout", "max_duration"} and not is_crisis:
            raise HTTPException(409, {"code": "CHAT_SESSION_CLOSED", **_session_state(latest, chat_session_repo)})
        result = chat_session_repo.find_or_create_session(assessment_id, user["uid"])
        session = chat_session_repo.get_session(result.session_id)
        if not session:
            raise HTTPException(409, {"code": "CHAT_SESSION_CHANGED"})
        before = session.user_turn_count
        now = datetime.now(timezone.utc)
        if not request.message.strip() or request.message.strip() in {".", "..", "...", "....", "....."}:
            response = {"assistant_message": _message_payload("punctuation", "assistant",
                "Tôi vẫn đang ở đây lắng nghe bạn. Khi nào sẵn sàng, bạn cứ nhắn nhé.", session.id, now),
                "user_message": _message_payload("punctuation-user", "user", request.message, session.id, now),
                "is_session_completed": False, "session_status": "active", "can_extend": False,
                "user_extended": session.user_extended, "is_fallback": False}
            await asyncio.to_thread(ledger.complete, claim, response)
            return response

        fatigued = is_fatigued_short_message(request.message) if before == 0 else session.was_fatigued_turn1
        stage, completed, can_reply, extended = decide_stage(before + 1, session.is_crisis_active,
            fatigued, session.is_extended, is_crisis, session.user_extended)
        turn = before if is_crisis else before + 1
        topic, action = session.primary_cause, session.micro_action_offered
        fallback, finish = False, "CRISIS_SUPPORT" if is_crisis else None
        facts = []
        if is_crisis:
            content = crisis_response
        else:
            history = chat_repo.get_messages_by_session(session.id, limit=50)
            survey = await asyncio.to_thread(_build_survey_context_sync, assessment_id, user["uid"])
            generator = get_chat_response_generator()
            response = await asyncio.to_thread(generator.generate_response,
                user_message=request.message, stage=stage, conversation_history=history,
                survey_context=survey, session_id=session.id, assessment_id=assessment_id,
                message_count=turn, primary_cause=topic, micro_action=action)
            content, fallback, finish = response.content, response.is_fallback, response.finish_reason
            if stage == "reflect_and_support" and response.follow_up_topic not in (None, "general"):
                topic, action = response.follow_up_topic, response.micro_action
            facts = get_probing_questions_service().extract_facts(request.message)
            if finish == "USER_STOPPED":
                completed, can_reply = True, False
        can_extend = bool(completed and stage == "wrapping_up" and not session.user_extended and finish != "USER_STOPPED")
        ui_action = {"type": "offer_extension"} if can_extend else None
        metadata = dict(can_reply=can_reply, can_extend=can_extend, user_extended=session.user_extended, ui_action=ui_action)
        user_ref, assistant_ref = chat_repo.collection.document(), chat_repo.collection.document()
        # Firestore breaks equal timestamp ties by document ID. Keep the pair
        # ordered even though both documents are committed in one transaction.
        assistant_time = max(datetime.now(timezone.utc), now + timedelta(microseconds=1))
        payload = {
            "user_message": _message_payload(user_ref.id, "user", request.message, session.id, now, **metadata),
            "assistant_message": _message_payload(assistant_ref.id, "assistant", content, session.id, assistant_time,
                is_fallback=fallback, finish_reason=finish, **metadata),
            "is_session_completed": completed, "session_status": "closed" if completed else "active",
            "current_stage": stage, "user_turn_count": turn, "can_extend": can_extend,
            "user_extended": session.user_extended, "ui_action": ui_action,
            "micro_action_offered": action, "primary_cause": topic,
            "is_fallback": fallback, "finish_reason": finish,
        }
        common = {"assessment_id": assessment_id, "user_id": user["uid"], "session_id": session.id, "analysis": None}
        updates = {"current_stage": stage, "user_turn_count": turn, "message_count": session.message_count + 2,
                   "is_extended": session.is_extended if extended is None else extended,
                   "is_crisis_active": is_crisis, "was_fatigued_turn1": fatigued,
                   "last_activity_at": assistant_time, "updated_at": assistant_time,
                   "primary_cause": topic, "micro_action_offered": action}
        if facts:
            updates.update(context_facts=firestore.ArrayUnion(facts), last_analysis_confidence=0.7)
        if completed:
            updates.update(status="closed", closed_at=assistant_time,
                closed_reason="manual" if finish == "USER_STOPPED" else ("max_turns_completed" if session.user_extended else "completed_wrap_up"),
                summary=content[:300])
        writes = [
            (user_ref, {**common, "role": "user", "content": request.message, "created_at": now, "client_message_id": request.client_message_id}, False),
            (assistant_ref, {**common, "role": "assistant", "content": content,
                "created_at": assistant_time, "response_to": user_ref.id, "is_fallback": fallback, "finish_reason": finish}, False),
            (chat_session_repo.collection.document(session.id), updates, True),
        ]
        await asyncio.to_thread(ledger.complete, claim, payload, writes,
            (chat_session_repo.collection.document(session.id), before))
        if not assessment.get("status_detail", {}).get("has_chat"):
            # Peripheral assessment marker must not invalidate a committed reply.
            try:
                assessment_repo.mark_chat_started(assessment_id)
            except Exception:
                logger.warning("Unable to update assessment chat marker")
        return payload
    except ChatRequestConflict as exc:
        raise HTTPException(409, {"code": str(exc)})
    finally:
        await _release_claim(ledger, claim)


@router.get("/{assessment_id}/chat", response_model=ChatHistoryResponse)
async def get_chat_history(
    assessment_id: str, limit: int = 50, user: dict = Depends(get_current_user),
    chat_repo: ChatHistoryRepository = Depends(get_chat_repo),
    chat_session_repo: ChatSessionRepository = Depends(get_chat_session_repo),
    assessment_repo: AssessmentSessionRepository = Depends(get_assessment_repo),
):
    _owned_assessment(assessment_id, user, assessment_repo)
    session = _latest_session(chat_session_repo, assessment_id)
    state = _session_state(session, chat_session_repo)
    limit = max(1, min(limit, 100))
    messages = (chat_repo.get_messages_by_session(session.id, limit=limit) if session
                else chat_repo.get_messages_by_assessment(assessment_id, limit=limit))
    return ChatHistoryResponse(assessment_id=assessment_id, messages=messages,
        message_count=len(messages), has_analysis=any(m.get("analysis") for m in messages),
        current_session_id=session.id if session else None,
        is_closed=state["status"] in {"closed", "expired"},
        can_extend=state["can_extend"], user_extended=state["user_extended"])


@router.get("/{assessment_id}/chat/state", response_model=dict)
async def get_chat_state(
    assessment_id: str, user: dict = Depends(get_current_user),
    chat_session_repo: ChatSessionRepository = Depends(get_chat_session_repo),
    assessment_repo: AssessmentSessionRepository = Depends(get_assessment_repo),
):
    _owned_assessment(assessment_id, user, assessment_repo)
    return _session_state(_latest_session(chat_session_repo, assessment_id), chat_session_repo)


@router.get("/{assessment_id}/chat/summary", response_model=ChatSummaryResponse)
async def get_chat_summary(
    assessment_id: str,
    user: dict = Depends(get_current_user),
    chat_repo: ChatHistoryRepository = Depends(get_chat_repo),
):
    """Lấy tóm tắt session chat của một assessment."""
    user_id = user["uid"]

    summary = chat_repo.get_session_summary(assessment_id)

    if not summary:
        raise HTTPException(status_code=404, detail="No chat history found")

    if summary.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this chat")

    return ChatSummaryResponse(
        assessment_id=summary.assessment_id,
        user_id=summary.user_id,
        message_count=summary.message_count,
        has_analysis=summary.has_analysis,
        aggregated_stress_level=summary.aggregated_stress_level,
        aggregated_burnout_signal=summary.aggregated_burnout_signal,
        detected_signals=summary.detected_signals,
        keywords=summary.keywords,
        last_message_at=str(summary.last_message_at) if summary.last_message_at else None,
    )


@router.delete("/{assessment_id}/chat", response_model=dict)
async def delete_chat_history(
    assessment_id: str,
    user: dict = Depends(get_current_user),
    chat_repo: ChatHistoryRepository = Depends(get_chat_repo),
    chat_session_repo: ChatSessionRepository = Depends(get_chat_session_repo),
    assessment_repo: AssessmentSessionRepository = Depends(get_assessment_repo),
):
    """Xóa lịch sử chat, chat session và assessment session của một assessment."""
    user_id = user["uid"]

    # Check authorization
    summary = chat_repo.get_session_summary(assessment_id)
    if summary and summary.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this chat")

    # Xóa tất cả messages
    count = chat_repo.delete_by_assessment(assessment_id)
    logger.info("Deleted %d messages for assessment %s", count, assessment_id)

    # Xóa chat session document
    chat_session_repo.delete_session(assessment_id)
    logger.info("Deleted chat session for %s", assessment_id)

    # Xóa assessment session (nếu tồn tại)
    assessment = assessment_repo.get(assessment_id)
    logger.info("Assessment exists: %s, user_id match: %s", bool(assessment), assessment.get("user_id") == user_id if assessment else False)
    if assessment and assessment.get("user_id") == user_id:
        assessment_repo.delete(assessment_id)
        logger.info("Deleted assessment %s", assessment_id)
    else:
        logger.warning("Assessment %s not deleted (not found or not owner)", assessment_id)

    # STA Compact: AccumulatedAnalysisService đã được loại bỏ (state chỉ còn
    # trên Firestore qua messages[].analysis và chat_session.used_topics).
    # used_topics sẽ tự reset khi session mới được tạo (create_session).

    return {"message": f"Deleted {count} messages and sessions", "assessment_id": assessment_id}


@router.post("/{assessment_id}/chat/extend", response_model=dict)
async def extend_chat_session(
    assessment_id: str, user: dict = Depends(get_current_user),
    chat_repo: ChatHistoryRepository = Depends(get_chat_repo),
    chat_session_repo: ChatSessionRepository = Depends(get_chat_session_repo),
    assessment_repo: AssessmentSessionRepository = Depends(get_assessment_repo),
):
    _owned_assessment(assessment_id, user, assessment_repo)
    ledger = ChatRequestRepository(chat_repo.db)
    try:
        claim = await asyncio.to_thread(ledger.claim, assessment_id, user["uid"], uuid4().hex, "extend")
    except ChatRequestConflict as exc:
        raise HTTPException(409, {"code": str(exc)})
    try:
        session = _latest_session(chat_session_repo, assessment_id)
        state = _session_state(session, chat_session_repo)
        if session and session.user_extended:
            return {"success": state["can_reply"], **state, "message": "Phiên này đã được gia hạn trước đó."}
        if not state["can_extend"]:
            raise HTTPException(409, {"code": "CHAT_CANNOT_EXTEND", **state})
        now = datetime.now(timezone.utc)
        content = "Mình vẫn ở đây lắng nghe. Bạn có thể tiếp tục chia sẻ trong 3 lượt trao đổi tiếp theo nhé."
        message = chat_repo.collection.document()
        payload = {"success": True, "session_id": session.id, "session_status": "active",
            "user_extended": True, "can_reply": True, "can_extend": False,
            "message": "Phiên trò chuyện đã được gia hạn thêm 3 lượt.",
            "assistant_message": _message_payload(message.id, "assistant", content, session.id, now)}
        updates = {"status": "active", "user_extended": True, "closed_at": None,
            "closed_reason": None, "last_activity_at": now, "updated_at": now}
        await asyncio.to_thread(ledger.complete, claim, payload, [
            (chat_session_repo.collection.document(session.id), updates, True),
            (message, {"assessment_id": assessment_id, "user_id": user["uid"], "session_id": session.id,
                "role": "assistant", "content": content, "created_at": now, "analysis": None}, False)])
        return payload
    finally:
        await _release_claim(ledger, claim)


@router.post("/{assessment_id}/chat/close", response_model=dict)
async def close_chat_session(
    assessment_id: str, user: dict = Depends(get_current_user),
    chat_session_repo: ChatSessionRepository = Depends(get_chat_session_repo),
    assessment_repo: AssessmentSessionRepository = Depends(get_assessment_repo),
):
    _owned_assessment(assessment_id, user, assessment_repo)
    ledger = ChatRequestRepository(chat_session_repo.db)
    try:
        claim = await asyncio.to_thread(ledger.claim, assessment_id, user["uid"], uuid4().hex, "close")
    except ChatRequestConflict as exc:
        raise HTTPException(409, {"code": str(exc)})
    try:
        session = _latest_session(chat_session_repo, assessment_id)
        now = datetime.now(timezone.utc)
        writes = []
        if session:
            writes.append((chat_session_repo.collection.document(session.id), {
                "status": "closed", "closed_reason": "manual", "closed_at": session.closed_at or now,
                "summary": session.summary or "Người dùng chủ động hoàn thành phiên để nghỉ ngơi.",
                "updated_at": now}, True))
        payload = {"success": True, "message": "Đã hoàn tất phiên trò chuyện.",
            "session_status": "closed", "can_reply": False, "can_extend": False}
        await asyncio.to_thread(ledger.complete, claim, payload, writes)
        return payload
    finally:
        await _release_claim(ledger, claim)


# ==========================================
# STA Compact: Endpoint cá nhân hóa câu chào
# ==========================================

def _build_survey_context_sync(assessment_id: str, user_id: str) -> Optional[dict]:
    """Helper: build survey_context từ khảo sát gần nhất (sync, dùng cho greeting)."""
    try:
        from app.modules.survey.repositories.survey_history_repository import (
            get_survey_history_repository,
        )
        from app.modules.user.services.user_profile_service import get_profile_service
        from app.modules.burnout.helpers.industry_archetypes import (
            resolve_industry_context,
        )
        from app.modules.burnout.helpers.matrix_resolver import (
            resolve_burnout_archetype,
        )

        profile = get_profile_service().get_profile(user_id) or {}
        job_title = profile.get("job_title")
        industry_code = profile.get("industry_code")
        ind_ctx = resolve_industry_context(
            industry_code=industry_code, job_title=job_title
        )

        survey_repo = get_survey_history_repository()
        survey_doc = survey_repo.get_by_assessment(assessment_id)
        if not survey_doc:
            recent_s = survey_repo.list_by_user(user_id, limit=1)
            if recent_s:
                survey_doc = recent_s[0]

        if not survey_doc:
            return None

        s_data = survey_doc.get("survey") or {}
        if s_data.get("survey_type") in ("daily_checkin", "olbi_periodic"):
            from app.modules.survey.services.questionnaire_scoring import engine_survey
            s_data = engine_survey(s_data)
        ai_insight = (survey_doc.get("analysis_result") or {}).get("ai_insight") or {}
        quick_data = s_data.get("quick_overload_data") or {}
        rec_data = s_data.get("recovery") or {}
        reasons = s_data.get("overload_reasons") or quick_data.get("reasons") or []

        ex_score = 3.0
        if s_data.get("exhaustion"):
            v = [float(val) for val in s_data["exhaustion"].values() if val is not None]
            if v:
                ex_score = sum(v) / len(v)

        dis_score = 2.5
        if s_data.get("disengagement"):
            v = [float(val) for val in s_data["disengagement"].values() if val is not None]
            if v:
                dis_score = sum(v) / len(v)

        daily_stats = {
            "job_demands": 3.0,
            "sleep_hours": s_data.get("sleep_hours") or rec_data.get("sleep_hours") or 7.0,
            "recovery_score": s_data.get("recovery_score") or rec_data.get("recovery_score") or 3,
            "quick_overload": s_data.get("quick_overload") or quick_data.get("rating") or 2,
            "overload_reasons": reasons,
            "overtime_hours": s_data.get("overtime_hours") or 0.0,
        }
        archetype = resolve_burnout_archetype(ex_score, dis_score, daily_stats)

        return {
            "job_title": job_title or ind_ctx.typical_roles[0],
            "industry_name": ind_ctx.name,
            "archetype_name": "Hai chiều OLBI; chưa xác định hình mẫu" if s_data.get("survey_type") == "olbi_periodic" else f"{archetype.icon} {archetype.name}",
            "reflection_question": ai_insight.get("reflection_question", ""),
            "overload_reasons": reasons,
            "sleep_hours": None if s_data.get("survey_type") == "olbi_periodic" else daily_stats["sleep_hours"],
            "recovery_score": None if s_data.get("survey_type") == "olbi_periodic" else daily_stats["recovery_score"],
        }
    except Exception:
        return None


@router.get("/{assessment_id}/chat/initial-greeting", response_model=dict)
async def get_initial_greeting(
    assessment_id: str,
    user: dict = Depends(get_current_user),
    chat_session_repo: ChatSessionRepository = Depends(get_chat_session_repo),
    assessment_repo: AssessmentSessionRepository = Depends(get_assessment_repo),
):
    """STA Compact: Sinh câu chào cá nhân hóa từ dữ liệu khảo sát.

    Frontend gọi endpoint này khi user mở màn hình chat lần đầu (sau khi
    hoàn thành survey). Trả về 1 câu chào data-driven + 1 câu hỏi trọng tâm,
    KHÔNG chứa các câu sáo rỗng kiểu "Bạn cảm thấy thế nào?".

    Endpoint KHÔNG lưu message vào DB, chỉ trả về text để frontend hiển thị.
    """
    user_id = user["uid"]

    # Verify ownership
    assessment = assessment_repo.get(assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if assessment.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    # Lấy survey context
    survey_context = _build_survey_context_sync(assessment_id, user_id)

    # Chọn 1 probing question phù hợp (ưu tiên survey_context vì user chưa nói gì)
    from app.modules.chat.services.probing_questions import (
        get_probing_questions_service,
    )
    probe = get_probing_questions_service().get_probing_question(
        user_message="",  # Turn 1: chưa có user message
        survey_context=survey_context,
        assessment_id=assessment_id,
    )

    # Sinh câu chào qua Gemini (1 lần duy nhất, không gọi analyze_chat_text)
    greeting_text = None
    if survey_context and probe:
        try:
            generator = get_chat_response_generator()
            from app.modules.chat.services.probing_questions import (
                STA_QUESTION_CATALOG,
            )
            response = await asyncio.to_thread(
                generator.generate_response,
                user_message="(Đây là lượt mở đầu phiên - hãy chào và đặt câu hỏi trọng tâm)",
                analysis_context=None,
                conversation_history=[],
                message_count=1,
                survey_context=survey_context,
                stage="greeting_and_probe",
                assessment_id=assessment_id,
            )
            greeting_text = response.content
        except Exception as exc:
            logger.warning("Failed to generate initial greeting: %s", exc)

    # Fallback an toàn (vẫn phản ánh data, KHÔNG dùng câu sáo rỗng)
    if not greeting_text:
        if survey_context and probe:
            archetype = survey_context.get("archetype_name", "")
            reasons = ", ".join(survey_context.get("overload_reasons", [])) or "áp lực công việc"
            greeting_text = (
                f"Chào bạn, qua khảo sát hôm nay tôi nhận thấy bạn đang ở trạng thái "
                f"{archetype or 'căng thẳng'}, với các tín hiệu chính: {reasons}. "
                f"{probe.question}"
            )
        else:
            greeting_text = (
                "Chào bạn, hôm nay tôi ở đây để lắng nghe bạn. "
                "Qua khảo sát gần nhất, điều gì trong công việc đang tạo áp lực lớn nhất cho bạn?"
            )

    return {
        "greeting": greeting_text,
        "initial_probe_topic": probe.topic if probe else None,
        "session_status": "pending",  # Frontend sẽ trigger /chat sau khi user gửi
    }
