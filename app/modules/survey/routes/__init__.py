"""
Survey Routes - API endpoints for survey module.
"""

from app.modules.survey.routes.survey_history import router as survey_history_router

__all__ = ["survey_history_router"]
