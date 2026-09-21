"""
==============================================================
File: __init__.py

Export tat ca Domain Models tu cac modules.
==============================================================
"""

# ==========================================
# AUTH MODELS (from auth module)
# ==========================================
from app.modules.auth.models import (
    UserRole,
    LoginAction,
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    PasswordChangeRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    AdminUserResponse,
    User,
    Session,
)

# ==========================================
# USER MODELS (from user module)
# ==========================================
from app.modules.user.models import (
    Gender,
    UpdateProfileRequest,
    ChangeEmailRequest,
    UserProfileResponse,
)

# ==========================================
# EMOTION MODELS (from emotion module)
# ==========================================
from app.modules.emotion.models import EmotionScores, EmotionResult

# ==========================================
# CHAT MODELS (from chat module)
# ==========================================
from app.modules.chat.models import ChatMessage, ChatResult

# ==========================================
# BURNOUT MODELS (from burnout module)
# ==========================================
from app.modules.burnout.models import (
    BurnoutFactor,
    BurnoutResult,
    BurnoutEngineInput,
    BurnoutEngineOutput,
)

# ==========================================
# SURVEY MODELS (from survey module)
# ==========================================
from app.modules.survey.models import SurveyResult

# ==========================================
# ASSESSMENT MODELS (from assessment module)
# ==========================================
from app.modules.assessment.models import (
    AssessmentTemplate,
    AssessmentQuestion,
    QuestionOption,
    AssessmentAnswer,
    AssessmentResult,
)

# ==========================================
# NOTIFICATION MODELS (from notification module)
# ==========================================
from app.modules.notification.models import Notification

# ==========================================
# TIMELINE MODELS (from timeline module)
# ==========================================
from app.modules.timeline.models import Timeline

# ==========================================
# REPORT MODELS (from report module)
# ==========================================
from app.modules.report.models import Report

# ==========================================
# RECOMMENDATION MODELS (from recommendation module)
# ==========================================
from app.modules.recommendation.models import Recommendation

# ==========================================
# KNOWLEDGE MODELS (from knowledge module)
# ==========================================
from app.modules.knowledge.models import InsightResult, KnowledgeDocument, VectorPayload


__all__ = [
    # Auth
    "UserRole",
    "LoginAction",
    "RegisterRequest",
    "LoginRequest",
    "AuthResponse",
    "PasswordChangeRequest",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    "AdminCreateUserRequest",
    "AdminUpdateUserRequest",
    "AdminUserResponse",
    "User",
    "Session",

    # User
    "Gender",
    "UpdateProfileRequest",
    "ChangeEmailRequest",
    "UserProfileResponse",

    # Emotion
    "EmotionScores",
    "EmotionResult",

    # Chat
    "ChatMessage",
    "ChatResult",

    # Burnout
    "BurnoutFactor",
    "BurnoutResult",
    "BurnoutEngineInput",
    "BurnoutEngineOutput",

    # Survey
    "SurveyResult",

    # Assessment
    "AssessmentTemplate",
    "AssessmentQuestion",
    "QuestionOption",
    "AssessmentAnswer",
    "AssessmentResult",

    # Notification
    "Notification",

    # Timeline
    "Timeline",

    # Report
    "Report",

    # Recommendation
    "Recommendation",

    # Knowledge
    "InsightResult",
    "KnowledgeDocument",
    "VectorPayload",
]
