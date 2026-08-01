"""
==============================================================
File: assessment_answer.py

Chức năng:
- Định nghĩa AssessmentAnswer - câu trả lời của user cho một câu hỏi.
- Lưu trữ giá trị answer tùy theo question_type.

Đặc điểm:
- Một Answer thuộc về một Session và một Question.
- Answer có thể là number, string, boolean, list...

Được sử dụng tại:
- Assessment Form (lưu câu trả lời)
- Assessment Service (tổng hợp answers)
- Burnout Engine (tính điểm từ answers)

Luồng dữ liệu:
AssessmentQuestion
      ↓
User trả lời
      ↓
AssessmentAnswer
      ↓
AssessmentResult
==============================================================
"""

from datetime import datetime
from typing import Optional, Union, List

from pydantic import BaseModel, Field, ConfigDict


class AssessmentAnswer(BaseModel):
    """
    Domain Model cho câu trả lời của user.

    Answer có thể là:
    - number: 7.5
    - boolean: True
    - scale: 7
    - text: "Em cảm thấy rất mệt..."
    - single_choice: "high"
    - multiple_choice: ["work", "sleep", "family"]
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "ans_001",
                "session_id": "session_abc123",
                "question_id": "q_burnout_001",
                "answer": 5.0,
                "answered_at": "2024-01-20T10:05:00Z"
            }
        }
    )

    id: str = Field(
        ...,
        description="Unique identifier của câu trả lời"
    )

    session_id: str = Field(
        ...,
        description="ID của session thực hiện đánh giá"
    )

    question_id: str = Field(
        ...,
        description="ID của câu hỏi được trả lời"
    )

    answer: Union[float, bool, str, List[str], None] = Field(
        ...,
        description="Giá trị câu trả lời (tùy question_type)"
    )

    answered_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm user trả lời"
    )
