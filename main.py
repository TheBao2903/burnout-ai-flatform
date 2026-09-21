"""
==============================================================
main.py - Burnout AI Platform

Entry point cho FastAPI application.

Luu y:
- He thong dung custom auth (username/password + JWT HS256).
  xem app.modules.auth.routes.auth va app.core.deps.
- DeepFace SDK o external/deepface/ duoc them vao sys.path
  de su dung vendor ma khong can pip install.
==============================================================
"""

import logging
import pathlib
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.firebase import init_firebase
from app.core.settings import configure_logging, get_settings
from app.modules.assessment.routes.assessment_session import router as assessment_session_router
from app.modules.auth.routes.auth import router as auth_router
from app.modules.auth.routes.admin_users import router as admin_users_router
from app.modules.burnout import burnout_result_router
from app.modules.dashboard import dashboard_router, admin_dashboard_router
from app.modules.emotion import router as emotion_router
from app.modules.chat.routes.chat_history import router as chat_history_router
from app.modules.survey.routes.survey_history import router as survey_history_router
from app.modules.survey.routes.survey_history import survey_standalone_router
from app.modules.report import router as report_router
from app.modules.timeline import router as timeline_router
from app.modules.user import router as user_router
from app.modules.recommendation.routes.recommendation import router as recommendation_router
from app.modules.recommendation.routes.recommendation import user_profile_router as recommendation_profile_router
from app.modules.recommendation.routes.recommendation import weather_router
from app.modules.recommendation.routes.recommendation import survey_router
from app.modules.assessment.routes.admin import router as assessment_admin_router

# ==========================================
# Them vendor DeepFace vao sys.path
# ==========================================

_ROOT = pathlib.Path(__file__).resolve().parent
_EXTERNAL = _ROOT / "external"
if _EXTERNAL.exists() and str(_EXTERNAL) not in sys.path:
    sys.path.insert(0, str(_EXTERNAL))

logger = logging.getLogger("burnout")


# ==========================================
# LIFESPAN
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khoi tao tai nguyen luc startup, cleanup luc shutdown."""
    configure_logging()
    logger.info("Starting Burnout AI Platform...")

    load_dotenv()

    settings = get_settings()
    logger.info("Environment: %s", settings.server.environment)

    try:
        init_firebase()
        logger.info("Firebase initialized")
    except Exception as exc:
        logger.warning("Firebase init failed: %s. App continues without Firestore.", exc)

    # Preload DeepFace models
    _preload_deepface()

    logger.info("App started. Docs at /docs")
    yield

    logger.info("Shutting down...")


def _preload_deepface():
    """Preload DeepFace models on startup to avoid slow first request."""
    import os
    import warnings
    warnings.filterwarnings('ignore')
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

    preloaded_marker = "/root/.deepface/weights/.preloaded"
    if os.path.exists(preloaded_marker):
        logger.info("DeepFace models already preloaded")
        return

    try:
        from deepface import DeepFace
        logger.info("Preloading DeepFace models...")

        models_to_preload = ["Emotion", "Age", "Gender"]
        for model_name in models_to_preload:
            logger.info("  Loading %s model...", model_name)
            DeepFace.build_model(model_name=model_name)

        # Create marker
        os.makedirs("/root/.deepface/weights", exist_ok=True)
        with open(preloaded_marker, "w") as f:
            f.write("preloaded\n")

        logger.info("DeepFace models preloaded successfully")
    except Exception as e:
        logger.warning("DeepFace preload warning: %s", e)
        logger.warning("Models will be downloaded on first use (slower first request)")


# ==========================================
# APP
# ==========================================

settings = get_settings()

app = FastAPI(
    title="Burnout AI Platform",
    description="Nen tang AI phan tich va danh gia muc do kiet suc (burnout)",
    version="1.0.0",
    lifespan=lifespan,
)

# Routers
app.include_router(auth_router)
app.include_router(admin_users_router)
app.include_router(user_router)
app.include_router(emotion_router)

# Assessment Session - chinh thuc (Module 3)
app.include_router(assessment_session_router)  # /api/v1/assessments/* + /api/assessment/*

# Burnout Results
app.include_router(burnout_result_router)  # /api/burnout/* + /api/v1/assessments/{id}/result/*

# Dashboard, Timeline, Report
app.include_router(dashboard_router)  # /api/v1/dashboard/*
app.include_router(admin_dashboard_router)  # /api/v1/admin/dashboard/*
app.include_router(timeline_router)
app.include_router(report_router)

# Chat - /api/v1/assessments/{id}/chat
app.include_router(chat_history_router)

# Survey - /api/v1/assessments/{id}/survey + /api/survey/*
app.include_router(survey_history_router)
app.include_router(survey_standalone_router)

# Recommendations
app.include_router(recommendation_router)  # /api/v1/assessments/{id}/recommendations/*
app.include_router(recommendation_profile_router)  # /api/v1/users/me/recommendation-profile
app.include_router(weather_router)  # /api/v1/weather/*
app.include_router(survey_router)  # /api/survey/places/*

# Admin/Cache
app.include_router(assessment_admin_router)  # /api/assessment/cache/*, /api/assessment/rate-limit/*

# CORS (settings.cors.allowed_origins mac dinh ["*"])
_cors_origins = settings.cors.allowed_origins or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# Health check
# ==========================================

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "burnout-ai-platform",
        "version": "1.0.0",
    }


@app.get("/")
async def root():
    return {
        "message": "Burnout AI Platform API",
        "docs": "/docs",
        "health": "/health",
    }


# ==========================================
# Chay local
# ==========================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=True,
        log_level="info",
    )