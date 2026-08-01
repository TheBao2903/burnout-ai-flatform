"""
==============================================================
File: __init__.py

Chức năng:
- Export tất cả Domain Models ra ngoài package.
- Single source of truth cho tất cả models.

Cách sử dụng:
    from app.models import User, Session, EmotionResult, ...
==============================================================
"""

# ==========================================
# AUTH MODELS
# ==========================================
from .auth import (
    AuthProvider,
    RegisterRequest,
    LoginRequest,
    GoogleLoginRequest,
    AuthResponse,
    AuthSession,
    TokenPayload,
    TokenBlacklist,
    UserBanInfo,
)

# ==========================================
# USER & SESSION MODELS
# ==========================================
from .user import User
from .session import Session

# ==========================================
# ASSESSMENT MODELS
# ==========================================
from .assessment_template import AssessmentTemplate
from .assessment_question import AssessmentQuestion, QuestionOption
from .assessment_answer import AssessmentAnswer
from .assessment_result import AssessmentResult

# ==========================================
# INPUT MODELS (DeepFace, Survey, Chat)
# ==========================================
from .emotion import EmotionResult, EmotionScores
from .survey import SurveyResult
from .chat import ChatResult, ChatMessage

# ==========================================
# BURNOUT ENGINE MODELS
# ==========================================
from .burnout import BurnoutResult, BurnoutFactor
from .burnout_engine_input import BurnoutEngineInput
from .burnout_engine_output import BurnoutEngineOutput

# ==========================================
# INSIGHT & RECOMMENDATION MODELS
# ==========================================
from .insight import InsightResult
from .recommendation import Recommendation

# ==========================================
# KNOWLEDGE PIPELINE MODELS
# ==========================================
from .knowledge_document import KnowledgeDocument
from .embedding_document import EmbeddingDocument
from .vector_payload import VectorPayload

# ==========================================
# DASHBOARD & NOTIFICATION MODELS
# ==========================================
from .timeline import Timeline
from .notification import Notification
from .report import Report


__all__ = [
    # Auth
    "AuthProvider",
    "RegisterRequest",
    "LoginRequest",
    "GoogleLoginRequest",
    "AuthResponse",
    "AuthSession",
    "TokenPayload",
    "TokenBlacklist",
    "UserBanInfo",

    # User & Session
    "User",
    "Session",

    # Assessment
    "AssessmentTemplate",
    "AssessmentQuestion",
    "QuestionOption",
    "AssessmentAnswer",
    "AssessmentResult",

    # Input
    "EmotionResult",
    "EmotionScores",
    "SurveyResult",
    "ChatResult",
    "ChatMessage",

    # Burnout Engine
    "BurnoutResult",
    "BurnoutFactor",
    "BurnoutEngineInput",
    "BurnoutEngineOutput",

    # Insight & Recommendation
    "InsightResult",
    "Recommendation",

    # Knowledge Pipeline
    "KnowledgeDocument",
    "EmbeddingDocument",
    "VectorPayload",

    # Dashboard & Notification
    "Timeline",
    "Notification",
    "Report",
]
