"""
Assessment Routes - API endpoints for assessment module.
"""

from app.modules.assessment.routes.assessment import router as assessment_router
from app.modules.assessment.routes.assessment_session import router as assessment_session_router

__all__ = ["assessment_router", "assessment_session_router"]
