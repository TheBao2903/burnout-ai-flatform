"""
==============================================================
File: chat_history.py

Chat History Routes - API endpoints cho chat history.

POST /api/v1/assessments/{id}/chat     - Gui tin nhan chat
GET  /api/v1/assessments/{id}/chat     - Lay lich su chat
GET  /api/v1/assessments/{id}/chat/summary - Tom tat session chat
==============================================================
"""

import logging
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
)
from app.modules.chat.services.conversation_stages import (
    ConversationStagesService,
    get_conversation_stages_service,
)
from app.modules.chat.services.accumulated_analysis import (
    get_accumulated_analysis_service,
)

logger = logging.getLogger("burnout.chat.routes")

router = APIRouter(prefix="/api/v1/assessments", tags=["Chat"])


# ==========================================
# Request/Response Models
# ==========================================

class ChatMessageRequest(BaseModel):
    """Request body cho /chat endpoint."""

    message: str = Field(..., min_length=1, max_length=2000, description="Nội dung tin nhắn")
    analyze: bool = Field(default=True, description="Có phân tích bằng AI không")


class ChatMessageResponse(BaseModel):
    """Response cho /chat endpoint."""

    message_id: str
    role: str
    content: str
    analysis: Optional[dict] = None
    created_at: str
    session_id: Optional[str] = Field(default=None, description="Session ID")
    session_message: Optional[str] = Field(
        default=None,
        description="Thông báo về session (VD: session mới đã được tạo)"
    )


class ChatHistoryResponse(BaseModel):
    """Response cho /chat (GET) endpoint."""

    assessment_id: str
    messages: list
    message_count: int
    has_analysis: bool
    current_session_id: Optional[str] = Field(default=None, description="Session ID hiện tại")


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
# Endpoints
# ==========================================

@router.post("/{assessment_id}/chat", response_model=dict)
async def send_chat_message(
    assessment_id: str,
    request: ChatMessageRequest,
    user: dict = Depends(get_current_user),
    chat_repo: ChatHistoryRepository = Depends(get_chat_repo),
    chat_session_repo: ChatSessionRepository = Depends(get_chat_session_repo),
    assessment_service: AssessmentService = Depends(get_assessment_svc),
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

    # 3. Find or create session
    session_result = chat_session_repo.find_or_create_session(assessment_id, user_id)
    session_id = session_result.session_id
    session_message = session_result.message

    logger.info(
        "Chat session: %s (is_new=%s) for assessment %s",
        session_id, session_result.is_new, assessment_id
    )

    # 4. Add greeting for new session
    stages_service = get_conversation_stages_service()
    greeting_message = None
    if session_result.is_new:
        greeting_message = stages_service.get_greeting_message()

    # 4. Get conversation history for context
    history = chat_repo.get_messages_by_assessment(assessment_id, limit=50)
    history_for_ai = [{"role": m.get("role"), "content": m.get("content", "")} for m in history]
    message_count = len([m for m in history if m.get("role") == "user"])

    # 5. Save user message
    analysis_data = None
    ai_model = None
    assistant_content = None

    # 6. AI analysis neu duoc yeu cau
    if request.analyze:
        try:
            # Run AI analysis
            analysis_result = await assessment_service.analyze_chat_text(
                request.message, user_id=user_id
            )

            if analysis_result:
                analysis_data = analysis_result
                ai_model = analysis_result.get("ai_model", "unknown")

                # Build ChatAnalysisContext
                stress_score = analysis_result.get("stress_level", {}).get("score", 0)
                burnout_score = analysis_result.get("burnout_related_signal", {}).get("score", 0)
                fatigue_score = analysis_result.get("fatigue_signal", {}).get("score", 0)
                detected_signals = analysis_result.get("detected_signals", [])
                keywords = analysis_result.get("keywords", [])
                sentiment = "negative" if stress_score > 60 else "neutral"

                analysis_context = ChatAnalysisContext(
                    stress_score=stress_score,
                    burnout_score=burnout_score,
                    fatigue_score=fatigue_score,
                    detected_signals=detected_signals,
                    keywords=keywords,
                    sentiment=sentiment,
                )

                # Use ChatResponseGenerator for AI-powered response
                response_generator = get_chat_response_generator()

                # Add to accumulated analysis
                accumulated_service = get_accumulated_analysis_service()
                accumulated = accumulated_service.add_analysis(assessment_id, analysis_result)

                logger.info(
                    "Accumulated analysis: msg_count=%d, avg_stress=%.1f, avg_burnout=%.1f, trend=%s",
                    accumulated.message_count,
                    accumulated.avg_stress,
                    accumulated.avg_burnout,
                    accumulated.trend.direction,
                )

                # Build enhanced analysis context với accumulated stats
                analysis_context = ChatAnalysisContext(
                    stress_score=accumulated.avg_stress,
                    burnout_score=accumulated.avg_burnout,
                    fatigue_score=accumulated.avg_fatigue,
                    detected_signals=accumulated.unique_signals,
                    keywords=keywords,
                    sentiment="negative" if accumulated.avg_stress > 60 else "neutral",
                )

                # Generate response với accumulated context
                chat_response = response_generator.generate_response(
                    user_message=request.message,
                    analysis_context=analysis_context,
                    conversation_history=history_for_ai,
                    message_count=accumulated.message_count,
                )

                assistant_content = chat_response.content

                # Update analysis_data với accumulated info để lưu vào message
                analysis_data["accumulated"] = {
                    "message_count": accumulated.message_count,
                    "avg_stress": accumulated.avg_stress,
                    "avg_burnout": accumulated.avg_burnout,
                    "trend": accumulated.trend.direction,
                    "severity_alert": accumulated.trend.severity_alert,
                }

                logger.info(
                    "Chat AI response generated for assessment %s: accumulated_msg=%d, avg_stress=%.1f, burnout=%.1f",
                    assessment_id, accumulated.message_count, accumulated.avg_stress, accumulated.avg_burnout
                )
        except Exception as exc:
            logger.warning("Chat AI response generation failed: %s", exc)
            # Fallback message
            assistant_content = "Cam on ban da chia se! Toi dang lang nghe. Ban co muon chia se them ve dieu gi khong?"

    # 7. Save user message
    user_message_id = chat_repo.save_message(
        assessment_id=assessment_id,
        user_id=user_id,
        role="user",
        content=request.message,
        analysis=analysis_data,
        ai_model=ai_model,
        session_id=session_id,
    )

    # Update session
    chat_session_repo.increment_message_count(session_id)
    chat_session_repo.update_last_activity(session_id)

    # 8. Save assistant response message
    assistant_message_id = None
    if assistant_content:
        try:
            assistant_message_id = chat_repo.save_message(
                assessment_id=assessment_id,
                user_id=user_id,
                role="assistant",
                content=assistant_content,
                analysis=None,
                ai_model=ai_model,
                session_id=session_id,
            )
            chat_session_repo.update_last_activity(session_id)
        except Exception as exc:
            logger.warning("Failed to save assistant message: %s", exc)

    # 9. Get messages de tra ve
    messages = chat_repo.get_messages_by_assessment(assessment_id, limit=100)
    user_msg = next((m for m in messages if m.get("id") == user_message_id), None)

    assistant_msg = None
    if assistant_message_id:
        assistant_msg = next((m for m in messages if m.get("id") == assistant_message_id), None)

    if not user_msg:
        raise HTTPException(status_code=500, detail="Failed to save message")

    # 10. Handle greeting for new session
    greeting_msg = None
    if greeting_message:
        # Save greeting as assistant message
        greeting_msg_id = chat_repo.save_message(
            assessment_id=assessment_id,
            user_id=user_id,
            role="assistant",
            content=greeting_message,
            analysis=None,
            ai_model=None,
            session_id=session_id,
        )
        # Get greeting message data
        greeting_msg = next(
            (m for m in chat_repo.get_messages_by_assessment(assessment_id, limit=100)
             if m.get("id") == greeting_msg_id),
            None
        )

    return {
        "user_message": ChatMessageResponse(
            message_id=user_message_id,
            role="user",
            content=user_msg.get("content", ""),
            analysis=analysis_data,
            created_at=str(user_msg.get("created_at", "")),
            session_id=session_id,
            session_message=session_message,
        ).model_dump(),
        "assistant_message": ChatMessageResponse(
            message_id=assistant_message_id or "",
            role="assistant",
            content=assistant_content or greeting_message or "...",
            analysis=None,
            created_at=str(assistant_msg.get("created_at", "")) if assistant_msg else str(greeting_msg.get("created_at", "")) if greeting_msg else "",
            session_id=session_id,
            session_message=None,
        ).model_dump() if (assistant_content or greeting_message) else None,
    }


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

    return ChatHistoryResponse(
        assessment_id=assessment_id,
        messages=messages,
        message_count=len(messages),
        has_analysis=has_analysis,
        current_session_id=current_session_id,
    )


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

    # Clear accumulated analysis history
    accumulated_service = get_accumulated_analysis_service()
    accumulated_service.clear_history(assessment_id)
    logger.info("Cleared accumulated analysis for %s", assessment_id)

    return {"message": f"Deleted {count} messages and sessions", "assessment_id": assessment_id}
