"""
Survey Repositories - Database access layer for survey module.
"""

from app.modules.survey.repositories.survey_history_repository import (
    SurveyHistoryRepository,
    get_survey_history_repository,
)

__all__ = [
    "SurveyHistoryRepository",
    "get_survey_history_repository",
]
