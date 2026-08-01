"""
==============================================================
File: assessment_result.py

Chức năng:
- Định nghĩa AssessmentResult - kết quả hoàn thành của một bộ đánh giá.
- Chứa danh sách tất cả câu trả lời của user trong Session.

Đặc điểm:
- Một Session có thể có một AssessmentResult.
- Chứa toàn bộ answers của user.
- Đánh dấu completed khi user hoàn thành.

Được sử dụng tại:
- Assessment Service (lưu kết quả assessment)
- Burnout Engine (lấy answers để tính điểm)
- Analytics (phân tích kết quả assessment)

Luồng dữ liệu:
AssessmentTemplate
      ↓
AssessmentQuestion[]
      ↓
AssessmentAnswer[]
      ↓
AssessmentResult ─────────────────────────────────────┐
      ↓                                                │
AssessmentResult + EmotionResult ──→ BurnoutEngineInput │
      ↓                                                │
SurveyResult ───────────────────────────────────────────┘
      ↓
ChatResult
==============================================================
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict

from .assessment_answer import AssessmentAnswer


class AssessmentResult(BaseModel):
    """
    Domain Model cho kết quả hoàn thành của một bộ đánh giá.

    Chứa toàn bộ câu trả lời của user cho bộ câu hỏi.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "session_id": "session_abc123",
                "answers": [
                    {
                        "id": "ans_001",
                        "session_id": "session_abc123",
                        "question_id": "q_burnout_001",
                        "answer": 5.0,
                        "answered_at": "2024-01-20T10:05:00Z"
                    },
                    {
                        "id": "ans_002",
                        "session_id": "session_abc123",
                        "question_id": "q_burnout_002",
                        "answer": True,
                        "answered_at": "2024-01-20T10:06:00Z"
                    }
                ],
                "completed": True,
                "completed_at": "2024-01-20T10:10:00Z"
            }
        }
    )

    session_id: str = Field(
        ...,
        description="ID của session chứa kết quả đánh giá"
    )

    answers: List[AssessmentAnswer] = Field(
        default_factory=list,
        description="Danh sách tất cả câu trả lời của user"
    )

    completed: bool = Field(
        default=False,
        description="User đã hoàn thành assessment hay chưa"
    )

    completed_at: Optional[datetime] = Field(
        default=None,
        description="Thời điểm user hoàn thành assessment"
    )
