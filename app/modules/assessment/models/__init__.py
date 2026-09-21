"""
Models package for Assessment module.

NOTE: AssessmentRecord đã được loại bỏ - AI assessment được embed vào emotion doc.
"""

from app.modules.assessment.models.assessment import (
    AssessmentTemplate,
    AssessmentQuestion,
    QuestionOption,
    AssessmentAnswer,
    AssessmentResult,
)
from app.modules.assessment.models.burnout_vector import (
    BurnoutVector,
)

__all__ = [
    "AssessmentTemplate",
    "AssessmentQuestion",
    "QuestionOption",
    "AssessmentAnswer",
    "AssessmentResult",
    "BurnoutVector",
]
