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
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.deps import get_current_user
from app.modules.chat.repositories.chat_history_repository import (
    ChatHistoryRepository,
    get_chat_history_repository,
)
from app.modules.chat.repositories.chat_session_repository import (
    ChatSessionRepository,
    get_chat_session_repository,
)
from app.modules.assessment.services.ai_service import (
    AssessmentService,
    get_assessment_service,
)
from app.modules.assessment.repositories.assessment_session_repository import (
    AssessmentSessionRepository,
    get_assessment_session_repository,
)
from app.modules.chat.services.chat_response_generator import (
    ChatResponseGenerator,
    ChatAnalysisContext,
    get_chat_response_generator,
    evaluate_crisis_safety,
)
from app.modules.chat.services.conversation_stages import (
    ConversationStagesService,
    get_conversation_stages_service,
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
    session_id: Optional[str] = Field(default=None, description="Session ID")
    session_message: Optional[str] = Field(
        default=None,
        description="Thông báo về session (VD: session mới đã được tạo)"
    )
    ui_action: Optional[dict] = Field(
        default=None,
        description="Hành động gợi ý giao diện (VD: decision_buttons tại Gatekeeper Lượt 4)"
    )
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


def get_assessment_svc() -> AssessmentService:
    from app.modules.assessment.services.ai_service import get_assessment_service
    return get_assessment_service()


def get_assessment_repo() -> AssessmentSessionRepository:
    return get_assessment_session_repository()


# ==========================================
# v2.1: State machine pure function
# Đây là SINGLE SOURCE OF TRUTH cho stage (B1).
# Generator nhận stage từ route, KHÔNG tự suy ra.
# ==========================================

# Hard cap — Q6: tối đa 4 lượt user cho luồng mở rộng
HARD_CAP_USER_TURNS = 4

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
    # Crisis mới ưu tiên tuyệt đối
    if new_msg_is_crisis:
        return "crisis_support", False, True, None

    if current_turn_count <= 1:
        return "greeting_and_probe", False, True, False
    if current_turn_count == 2:
        if is_fatigued_short:
            return "clarifying_cause", False, True, True  # mở rộng tự động (fatigued)
        return "reflect_and_support", False, True, False
    if current_turn_count == 3:
        if was_extended:
            return "reflect_and_support", False, True, True
        if user_extended:
            return "clarifying_cause", False, True, False
        return "wrapping_up", True, False, False
    if current_turn_count == 4:
        if was_extended:
            if user_extended:
                return "clarifying_cause", False, True, True
            return "wrapping_up", True, False, True
        if user_extended:
            return "reflect_and_support", False, True, False
        return "wrapping_up", True, False, False
    if current_turn_count == 5:
        if was_extended and user_extended:
            return "reflect_and_support", False, True, True
        if user_extended:
            return "wrapping_up", True, False, False
        return "wrapping_up", True, False, False
    if current_turn_count == 6:
        if was_extended and user_extended:
            return "wrapping_up", True, False, True
        return "wrapping_up", True, False, False

    # HARD CAP (kể cả đã gia hạn hay crisis đã clear - tối đa 7 turns)
    return "wrapping_up", True, False, was_extended


def _build_idempotent_replay(
    existing_user_msg: dict,
    chat_session_repo: ChatSessionRepository,
) -> dict:
    """Q5: Trả response giống hệt cho request retry cùng client_message_id.

    Đọc lại assistant message kế tiếp trong assessment (theo created_at).
    Trả về payload với cờ idempotent_replay=True để client biết.
    """
    from app.modules.chat.repositories.chat_history_repository import (
        get_chat_history_repository,
    )
    chat_repo = get_chat_history_repository()
    assessment_id = existing_user_msg.get("assessment_id")
    session_id = existing_user_msg.get("session_id")

    # Tìm assistant message gần nhất sau user message
    history = chat_repo.get_messages_by_assessment(assessment_id, limit=50)
    user_idx = None
    for i, m in enumerate(history):
        if m.get("id") == existing_user_msg.get("id"):
            user_idx = i
            break

    assistant_msg = None
    if user_idx is not None:
        for j in range(user_idx + 1, len(history)):
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
        "idempotent_replay": True,
    }


# ==========================================
# Endpoints
# ==========================================

@router.post("/{assessment_id}/chat", response_model=dict)
async def send_chat_message(
    assessment_id: str,
    request: ChatMessageRequest,
    user: dict = Depends(get_current_user),
    chat_repo: ChatHistoryRepository = Depends(get_chat_repo),
    chat_session_repo: ChatSessionRepository = Depends(get_chat_session_repo),
    # Q1: assessment_service KHÔNG còn dùng trong v2.1 (bỏ analyze_chat_text).
    # Giữ parameter để tránh vỡ DI container ở những nơi khác (route này
    # không gọi nhưng DI vẫn resolve). Có thể xóa sau khi verify
    # không còn consumer nào dùng.
    assessment_service: AssessmentService = Depends(get_assessment_svc),  # noqa: ARG001
    assessment_repo: AssessmentSessionRepository = Depends(get_assessment_repo),
):
    """
    Gửi tin nhắn chat và phân tích bằng AI.

    Flow:
    1. Verify ownership - assessment phải thuộc về user
    2. Find or create session (với session management)
    3. Save user message vào Firestore
    4. Nếu analyze=True -> gọi AI phân tích
    5. Tạo assistant response message với feedback
    6. Update session last_activity
    7. Trả cả user message và assistant response
    """
    user_id = user["uid"]

    # 1. Verify assessment ownership
    assessment = assessment_repo.get(assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if assessment.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to send message to this assessment",
        )

    # 2. Update assessment status - mark chat as started
    if not assessment.get("status_detail", {}).get("has_chat"):
        assessment_repo.mark_chat_started(assessment_id)

    # 3. Soft Boundary Check: Kiểm tra session đã đóng trước đó
    active_session = chat_session_repo.get_active_session(assessment_id)
    if active_session and active_session.status == "closed":
        # Trả về thông điệp dặn dò nghỉ ngơi định sẵn, không tạo session mới tự động
        closed_notice = "Phiên check-in hôm nay của bạn đã hoàn tất để bạn có thời gian nghỉ ngơi. Hẹn gặp lại bạn vào ngày mai nhé!"
        return {
            "user_message": ChatMessageResponse(
                message_id="closed_notice",
                role="user",
                content=request.message,
                created_at=datetime.utcnow().isoformat(),
                session_id=active_session.id,
                can_reply=False,
            ).model_dump(),
            "assistant_message": ChatMessageResponse(
                message_id="closed_assistant",
                role="assistant",
                content=closed_notice,
                created_at=datetime.utcnow().isoformat(),
                session_id=active_session.id,
                can_reply=False,
            ).model_dump(),
            "is_session_completed": True,
            "session_status": "closed",
        }

    # 4. Find or create active session
    session_result = chat_session_repo.find_or_create_session(assessment_id, user_id)
    session_id = session_result.session_id
    session_message = session_result.message

    # 5. Handle empty or punctuation-only messages (TC_D02)
    cleaned_msg = request.message.strip()
    if not cleaned_msg or cleaned_msg in [".", "..", "...", "....", "....."]:
        soft_reply = "Tôi vẫn đang ở đây lắng nghe bạn. Khi nào bạn sẵn sàng chia sẻ, cứ nhắn cho tôi nhé."
        return {
            "user_message": ChatMessageResponse(
                message_id="punct_msg",
                role="user",
                content=request.message,
                created_at=datetime.utcnow().isoformat(),
                session_id=session_id,
                can_reply=True,
            ).model_dump(),
            "assistant_message": ChatMessageResponse(
                message_id="punct_reply",
                role="assistant",
                content=soft_reply,
                created_at=datetime.utcnow().isoformat(),
                session_id=session_id,
                can_reply=True,
            ).model_dump(),
            "is_session_completed": False,
            "session_status": "active",
        }

    # 6. Pre-filter Crisis Safety Interlock (P0) TRƯỚC KHI gọi bất kỳ LLM nào
    is_crisis, crisis_response = evaluate_crisis_safety(request.message)
    if is_crisis and crisis_response:
        # Q-D: Crisis KHÔNG đóng session (GAP-4 fix). Set is_crisis_active=True
        # + stage=crisis_support. Session vẫn mở để user có thể chat tiếp
        # và nhận hỗ trợ liên tục.
        chat_session_repo.update_stage(
            session_id, "crisis_support", is_crisis_active=True
        )
        user_message_id = chat_repo.save_message(
            assessment_id=assessment_id,
            user_id=user_id,
            role="user",
            content=request.message,
            session_id=session_id,
            client_message_id=request.client_message_id,
        )
        assistant_message_id = chat_repo.save_message(
            assessment_id=assessment_id,
            user_id=user_id,
            role="assistant",
            content=crisis_response,
            session_id=session_id,
        )
        return {
            "user_message": ChatMessageResponse(
                message_id=user_message_id,
                role="user",
                content=request.message,
                created_at=datetime.utcnow().isoformat(),
                session_id=session_id,
                can_reply=True,
            ).model_dump(),
            "assistant_message": ChatMessageResponse(
                message_id=assistant_message_id,
                role="assistant",
                content=crisis_response,
                created_at=datetime.utcnow().isoformat(),
                session_id=session_id,
                can_reply=True,
            ).model_dump(),
            "is_session_completed": False,   # GAP-4: session vẫn mở
            "session_status": "crisis_support",
            "current_stage": "crisis_support",
            "user_turn_count": 0,           # Crisis không tăng turn
            "micro_action_offered": None,
            "primary_cause": None,
        }

    # 7. Q5: Idempotency check — nếu client_message_id đã tồn tại, trả về
    # response cũ thay vì xử lý lại (chống duplicate khi retry).
    if request.client_message_id:
        existing = chat_repo.get_by_client_message_id(
            assessment_id, request.client_message_id
        )
        if existing:
            logger.info(
                "Idempotent replay detected (client_msg_id=%s). Returning cached response.",
                request.client_message_id,
            )
            return _build_idempotent_replay(existing, chat_session_repo)

    # 8. Đọc flags hiện tại (is_extended, is_crisis_active, was_fatigued_turn1, user_extended) TRƯỚC khi transaction
    session_flags = chat_session_repo.get_session_flags(session_id)
    was_extended = session_flags["is_extended"]
    was_crisis_active = session_flags["is_crisis_active"]
    persisted_fatigued_turn1 = session_flags.get("was_fatigued_turn1", False)
    was_user_extended = session_flags.get("user_extended", False)

    # 9. B1: State machine pure function (single source of truth)
    current_turn_before = chat_session_repo.get_user_turn_count(session_id)
    # Ở Lượt 1: kiểm tra xem message có cực ngắn thể hiện kiệt sức không
    is_turn1_msg_fatigued = is_fatigued_short_message(request.message) if current_turn_before == 0 else False
    # Ở Lượt 2+: dùng cờ persisted_fatigued_turn1 đã ghi lại từ lượt 1
    effective_fatigued_flag = is_turn1_msg_fatigued if current_turn_before == 0 else persisted_fatigued_turn1

    current_stage, is_session_completed, can_reply, next_is_extended = decide_stage(
        current_turn_count=current_turn_before + 1,
        is_crisis_active=was_crisis_active,
        is_fatigued_short=effective_fatigued_flag,
        was_extended=was_extended,
        new_msg_is_crisis=False,  # crisis đã chặn ở step 6
        user_extended=was_user_extended,
    )

    # 10. Q5 / GAP-8: Atomic transaction — increment + update stage + flags
    # KHÔNG gọi Gemini bên trong transaction (Firestore transactions retry).
    try:
        new_turn_count = chat_session_repo.process_message_atomically(
            session_id=session_id,
            new_stage=current_stage,
            is_extended=next_is_extended,
            is_crisis_active=False,
            increment_turn=True,
            was_fatigued_turn1=is_turn1_msg_fatigued if current_turn_before == 0 else None,
        )
    except ValueError as exc:
        logger.error("Session %s disappeared: %s", session_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session not available",
        )

    # 11. Đọc history SAU khi đã commit (để dùng cho prompt)
    history = chat_repo.get_messages_by_assessment(assessment_id, limit=50)
    user_turn_count = new_turn_count

    ui_action = None

    # 12. Q1: KHÔNG gọi analyze_chat_text trong luồng chat đồng bộ.
    # `/chat/summary` sẽ trả aggregated_stress_level=null khi không có analysis.
    # Frontend Signal Panel hiển thị placeholder.
    # Xóa toàn bộ block gọi assessment_service.analyze_chat_text.

    # 13. Build survey context (giữ — vẫn dùng cho prompt greeting)
    history_for_ai = [
        {"role": m.get("role"), "content": m.get("content", "")} for m in history
    ]
    survey_context = None
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

        if survey_doc:
            s_data = survey_doc.get("survey") or {}
            if s_data.get("survey_type") in ("daily_checkin", "olbi_periodic"):
                from app.modules.survey.services.questionnaire_scoring import engine_survey
                s_data = engine_survey(s_data)
            ai_insight = (survey_doc.get("analysis_result") or {}).get(
                "ai_insight"
            ) or {}
            quick_data = s_data.get("quick_overload_data") or {}
            rec_data = s_data.get("recovery") or {}
            reasons = (
                s_data.get("overload_reasons")
                or quick_data.get("reasons")
                or []
            )

            ex_score = 3.0
            if s_data.get("exhaustion"):
                v = [
                    float(val)
                    for val in s_data["exhaustion"].values()
                    if val is not None
                ]
                if v:
                    ex_score = sum(v) / len(v)

            dis_score = 2.5
            if s_data.get("disengagement"):
                v = [
                    float(val)
                    for val in s_data["disengagement"].values()
                    if val is not None
                ]
                if v:
                    dis_score = sum(v) / len(v)

            daily_stats = {
                "job_demands": 3.0,
                "sleep_hours": s_data.get("sleep_hours")
                or rec_data.get("sleep_hours")
                or 7.0,
                "recovery_score": s_data.get("recovery_score")
                or rec_data.get("recovery_score")
                or 3,
                "quick_overload": s_data.get("quick_overload")
                or quick_data.get("rating")
                or 2,
                "overload_reasons": reasons,
                "overtime_hours": s_data.get("overtime_hours") or 0.0,
            }
            archetype = resolve_burnout_archetype(ex_score, dis_score, daily_stats)

            survey_context = {
                "job_title": job_title or ind_ctx.typical_roles[0],
                "industry_name": ind_ctx.name,
                "archetype_name": "Hai chiều OLBI; chưa xác định hình mẫu" if s_data.get("survey_type") == "olbi_periodic" else f"{archetype.icon} {archetype.name}",
                "reflection_question": ai_insight.get("reflection_question", ""),
                "overload_reasons": reasons,
                "sleep_hours": None if s_data.get("survey_type") == "olbi_periodic" else daily_stats["sleep_hours"],
                "recovery_score": None if s_data.get("survey_type") == "olbi_periodic" else daily_stats["recovery_score"],
            }
    except Exception as exc:
        logger.debug("Failed to build survey context: %s", exc)

    # 14. Gọi generator với stage ĐÃ ĐƯỢC ROUTE QUYẾT (B1)
    analysis_data = None  # Q1: không còn analysis cho chat
    ai_model = None
    assistant_content = None
    response_is_fallback = False
    response_finish_reason = None
    try:
        response_generator = get_chat_response_generator()
        chat_response = await asyncio.to_thread(
            response_generator.generate_response,
            user_message=request.message,
            stage=current_stage,                  # BẮT BUỘC từ route
            conversation_history=history_for_ai,
            survey_context=survey_context,
            session_id=session_id,
            assessment_id=assessment_id,
            message_count=user_turn_count,
        )
        assistant_content = chat_response.content
        response_is_fallback = chat_response.is_fallback
        response_finish_reason = chat_response.finish_reason
        logger.info("Chat generation stage=%s fallback=%s finish_reason=%s", current_stage, response_is_fallback, response_finish_reason)

        # 15. Context Tagging — chỉ ghi ở stage reflect_and_support
        # PR 2: Dùng cached topic từ generator (chat_response.follow_up_topic) thay vì
        # gọi lại probing_service lần 2. Tiết kiệm 1 Firestore read + 1 write.
        if current_stage == "reflect_and_support":
            try:
                cached_topic = chat_response.follow_up_topic if chat_response else None
                if cached_topic and cached_topic != "general":
                    # Lấy micro_action từ generator cache (nếu có) hoặc fallback
                    from app.modules.chat.services.probing_questions import get_probing_questions_service
                    probe_obj = get_probing_questions_service()
                    cached_question = probe_obj.get_probing_question(
                        user_message=request.message,
                        survey_context=survey_context,
                        session_id=session_id,
                        assessment_id=assessment_id,
                    )
                    if cached_question:
                        chat_session_repo.update_session_tagging(
                            session_id=session_id,
                            primary_cause=cached_topic,
                            micro_action_offered=cached_question.micro_action,
                        )
            except Exception as tag_exc:
                logger.debug("Context tagging skipped: %s", tag_exc)

        # PR 2: Lưu context_facts lên session (cho dashboard/lần sau)
        try:
            from app.modules.chat.services.probing_questions import get_probing_questions_service
            probe_svc = get_probing_questions_service()
            facts = probe_svc.extract_facts(request.message)
            if facts:
                chat_session_repo.update_context_analysis(
                    session_id=session_id,
                    context_facts=facts,
                    confidence=0.7,  # Heuristic-based, không dùng LLM
                )
        except Exception as ctx_exc:
            logger.debug("update_context_analysis skipped: %s", ctx_exc)
    except Exception as exc:
        logger.warning("Chat AI response generation failed: %s", exc)
        # Q-C: fallback do generator tự xử lý; nhưng nếu generator raise
        # exception khác (không phải Gemini), generator đã trả ChatResponse
        # rồi. Đoạn này chỉ log warning.
        if not assistant_content:
            assistant_content = "Tôi ghi nhận chia sẻ của bạn. Hãy nghỉ ngơi nhé."
            response_is_fallback = True
            response_finish_reason = "GENERATION_ERROR"

    # 16. Save user & assistant messages (Q1: bỏ analysis, Q5: truyền client_message_id)
    user_message_id = chat_repo.save_message(
        assessment_id=assessment_id,
        user_id=user_id,
        role="user",
        content=request.message,
        analysis=analysis_data,  # luôn None trong v2.1
        ai_model=ai_model,
        session_id=session_id,
        client_message_id=request.client_message_id,
    )

    assistant_message_id = None
    if assistant_content:
        assistant_message_id = chat_repo.save_message(
            assessment_id=assessment_id,
            user_id=user_id,
            role="assistant",
            content=assistant_content,
            analysis=None,
            ai_model=ai_model,
            session_id=session_id,
        )

    # 10. Đóng session nếu chạm mốc hoàn tất
    if is_session_completed:
        try:
            close_reason = "completed_wrap_up" if user_turn_count < 6 else "max_turns_completed"
            # STA Compact: đọc primary_cause + micro_action_offered đã ghi
            # ở bước Context Tagging để truyền vào close_session.
            primary_cause = None
            micro_action_offered = None
            try:
                sess = chat_session_repo.get_session(session_id)
                if sess:
                    primary_cause = getattr(sess, "primary_cause", None)
                    micro_action_offered = getattr(sess, "micro_action_offered", None)
            except Exception:
                pass
            chat_session_repo.close_session(
                session_id=session_id,
                reason=close_reason,
                summary=assistant_content[:300] if assistant_content else "Hoàn tất phiên tư vấn tự nhận thức.",
                primary_cause=primary_cause,
                micro_action_offered=micro_action_offered,
            )
            logger.info("Session %s permanently closed (%s at turn %d)", session_id, close_reason, user_turn_count)
        except Exception as exc:
            logger.warning("Failed to close session %s: %s", session_id, exc)

    # 18. Q-Ext: Kiểm tra xem phiên có thể đề xuất gia hạn không
    # Điều kiện: stage là wrapping_up VÀ chưa từng gia hạn trước đó (user_extended == False)
    can_extend = bool(current_stage == "wrapping_up" and not was_user_extended)
    ui_action = None
    if can_extend:
        ui_action = {
            "type": "offer_extension",
            "prompt": "Bạn đã thấy nhẹ lòng hơn để nghỉ ngơi chưa, hay vẫn còn điều gì muốn chia sẻ thêm?",
            "buttons": [
                {"id": "rest", "label": "Tôi đã ổn, muốn nghỉ ngơi", "action": "close"},
                {"id": "extend", "label": "Tôi muốn chia sẻ thêm (+3 lượt)", "action": "extend"},
            ],
        }

    # Response payload (Q1: bỏ field `analysis`)
    response_payload = {
        "user_message": ChatMessageResponse(
            message_id=user_message_id,
            role="user",
            content=request.message,
            created_at=datetime.utcnow().isoformat(),
            session_id=session_id,
            can_reply=can_reply,
            can_extend=can_extend,
            user_extended=was_user_extended,
            ui_action=ui_action,
        ).model_dump(),
        "assistant_message": ChatMessageResponse(
            message_id=assistant_message_id or "",
            role="assistant",
            content=assistant_content or "...",
            created_at=datetime.utcnow().isoformat(),
            session_id=session_id,
            can_reply=can_reply,
            can_extend=can_extend,
            user_extended=was_user_extended,
            ui_action=ui_action,
        ).model_dump() if assistant_content else None,
        "is_session_completed": is_session_completed,
        "session_status": "closed" if is_session_completed else "active",
        "current_stage": current_stage,
        "is_fallback": response_is_fallback,
        "finish_reason": response_finish_reason,
        "user_turn_count": user_turn_count,
        "can_extend": can_extend,
        "user_extended": was_user_extended,
        "ui_action": ui_action,
        "micro_action_offered": None,
        "primary_cause": None,
    }

    if is_session_completed:
        try:
            sess = chat_session_repo.get_session(session_id)
            if sess:
                response_payload["micro_action_offered"] = getattr(
                    sess, "micro_action_offered", None
                )
                response_payload["primary_cause"] = getattr(
                    sess, "primary_cause", None
                )
        except Exception:
            pass

    return response_payload


@router.get("/{assessment_id}/chat", response_model=ChatHistoryResponse)
async def get_chat_history(
    assessment_id: str,
    limit: int = 50,
    user: dict = Depends(get_current_user),
    chat_repo: ChatHistoryRepository = Depends(get_chat_repo),
    chat_session_repo: ChatSessionRepository = Depends(get_chat_session_repo),
):
    """Lay lich su chat cua mot assessment."""
    user_id = user["uid"]

    messages = chat_repo.get_messages_by_assessment(assessment_id, limit=limit)

    # Filter de dam bao user chi thay message cua ho
    if messages and messages[0].get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this chat")

    has_analysis = any(m.get("analysis") for m in messages)

    # Get current active session
    current_session = chat_session_repo.get_active_session(assessment_id)

    # Kiem tra session con hop le khong - neu khong thi close va tao moi
    if current_session:
        is_valid, invalid_reason = chat_session_repo._is_session_valid(current_session)
        if not is_valid:
            logger.info(
                "Active session %s expired (reason=%s), closing",
                current_session.id, invalid_reason
            )
            chat_session_repo.close_session(
                session_id=current_session.id,
                reason=invalid_reason,
                summary=None
            )
            current_session = None

    current_session_id = current_session.id if current_session else None

    user_msgs_count = len([m for m in messages if m.get("role") == "user"])
    is_closed = (current_session is None and len(messages) > 0) or user_msgs_count >= 10
    if current_session and current_session.status != "active":
        is_closed = True

    # Xác định khả năng gia hạn
    can_extend = False
    user_extended = False
    if current_session:
        user_extended = bool(getattr(current_session, "user_extended", False))
        can_extend = bool(current_session.current_stage == "wrapping_up" and not user_extended)
    else:
        recent = chat_session_repo.get_sessions_by_assessment(assessment_id, limit=1)
        if recent:
            user_extended = bool(getattr(recent[0], "user_extended", False))
            can_extend = bool(getattr(recent[0], "current_stage", None) == "wrapping_up" and not user_extended)

    return ChatHistoryResponse(
        assessment_id=assessment_id,
        messages=messages,
        message_count=len(messages),
        has_analysis=has_analysis,
        current_session_id=current_session_id,
        is_closed=is_closed,
        can_extend=can_extend,
        user_extended=user_extended,
    )


@router.get("/{assessment_id}/chat/state", response_model=dict)
async def get_chat_state(
    assessment_id: str,
    user: dict = Depends(get_current_user),
    chat_session_repo: ChatSessionRepository = Depends(get_chat_session_repo),
    assessment_repo: AssessmentSessionRepository = Depends(get_assessment_repo),
):
    """Q3: Trả về trạng thái phiên hiện tại (idempotent, rất nhẹ).

    Dùng cho frontend đồng bộ state khi lỗi mạng. KHÔNG tự đoán session
    đóng/mở — backend là nguồn xác thực cuối cùng.
    """
    # 1. Verify ownership
    assessment = assessment_repo.get(assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if assessment.get("user_id") != user["uid"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    # 2. Đọc session
    session = chat_session_repo.get_active_session(assessment_id)
    if not session:
        return {
            "status": "none",
            "can_reply": False,
            "can_extend": False,
            "user_extended": False,
            "current_stage": None,
            "user_turn_count": 0,
            "is_crisis_active": False,
            "is_expired": False,
        }

    # 3. Check validity (idle/max duration)
    is_valid, invalid_reason = chat_session_repo._is_session_valid(session)
    is_expired = not is_valid
    user_extended = bool(getattr(session, "user_extended", False))
    can_extend = bool(session.current_stage == "wrapping_up" and not user_extended)

    return {
        "status": "active" if (is_valid and session.status == "active") else "expired",
        "can_reply": is_valid and session.status == "active",
        "can_extend": can_extend,
        "user_extended": user_extended,
        "current_stage": session.current_stage,
        "user_turn_count": getattr(session, "user_turn_count", 0),
        "is_crisis_active": bool(getattr(session, "is_crisis_active", False)),
        "is_extended": bool(getattr(session, "is_extended", False)),
        "is_expired": is_expired,
        "expired_reason": invalid_reason,
    }


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
    assessment_id: str,
    user: dict = Depends(get_current_user),
    chat_repo: ChatHistoryRepository = Depends(get_chat_repo),
    chat_session_repo: ChatSessionRepository = Depends(get_chat_session_repo),
    assessment_repo: AssessmentSessionRepository = Depends(get_assessment_repo),
):
    """
    Gia hạn phiên trò chuyện (User-driven extension +3 lượt).
    Cho phép người dùng tiếp tục đào sâu thêm khi chưa muốn dừng ở lượt 3/4.
    """
    user_id = user["uid"]
    assessment = assessment_repo.get(assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if assessment.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this assessment",
        )

    # Tìm session gần nhất của assessment
    session = chat_session_repo.get_active_session(assessment_id)
    if not session:
        recent_sessions = chat_session_repo.get_sessions_by_assessment(assessment_id, limit=1)
        if recent_sessions:
            session = recent_sessions[0]

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No chat session found to extend",
        )

    # Kiểm tra xem session đã từng gia hạn chưa (chỉ được gia hạn 1 lần)
    if getattr(session, "user_extended", False):
        return {
            "success": False,
            "message": "Phiên này đã được gia hạn trước đó. Hãy hoàn thành các lượt trao đổi hiện tại.",
            "session_id": session.id,
            "session_status": session.status,
            "user_extended": True,
            "can_reply": session.status == "active",
        }

    # Kích hoạt gia hạn
    success = chat_session_repo.extend_session(session.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to extend chat session",
        )

    # Thêm tin nhắn mời mở rộng từ Assistant
    invite_text = (
        "Tôi luôn sẵn lòng đồng hành và lắng nghe bạn. "
        "Hãy thoải mái chia sẻ thêm về góc nhìn hay những khó khăn bạn đang trải qua nhé."
    )
    asst_msg_id = chat_repo.save_message(
        assessment_id=assessment_id,
        user_id=user_id,
        role="assistant",
        content=invite_text,
        session_id=session.id,
    )

    return {
        "success": True,
        "message": "Phiên trò chuyện đã được gia hạn thêm 3 lượt.",
        "session_id": session.id,
        "session_status": "active",
        "user_extended": True,
        "can_reply": True,
        "assistant_message": {
            "message_id": asst_msg_id,
            "role": "assistant",
            "content": invite_text,
            "created_at": datetime.utcnow().isoformat(),
            "session_id": session.id,
            "can_reply": True,
        },
    }


@router.post("/{assessment_id}/chat/close", response_model=dict)
async def close_chat_session(
    assessment_id: str,
    user: dict = Depends(get_current_user),
    chat_session_repo: ChatSessionRepository = Depends(get_chat_session_repo),
    assessment_repo: AssessmentSessionRepository = Depends(get_assessment_repo),
):
    """
    Chủ động đóng phiên trò chuyện khi người dùng chọn 'Tôi đã ổn, muốn nghỉ ngơi'.
    """
    user_id = user["uid"]
    assessment = assessment_repo.get(assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if assessment.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this assessment",
        )

    session = chat_session_repo.get_active_session(assessment_id)
    if not session:
        return {
            "success": True,
            "message": "Phiên trò chuyện đã được đóng từ trước.",
            "session_status": "closed",
        }

    chat_session_repo.close_session(
        session_id=session.id,
        reason="manual_user_decision",
        summary="Người dùng chủ động hoàn thành phiên tham vấn để nghỉ ngơi.",
    )
    return {
        "success": True,
        "message": "Đã hoàn tất phiên trò chuyện thành công.",
        "session_id": session.id,
        "session_status": "closed",
    }


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
                include_analysis_in_prompt=False,
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
