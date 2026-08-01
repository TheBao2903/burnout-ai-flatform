"""
==============================================================
File: assessment_question.py

Chức năng:
- Định nghĩa AssessmentQuestion - một câu hỏi trong bộ đánh giá.
- Hỗ trợ nhiều loại question type.

Đặc điểm:
- Mỗi Question thuộc về một Template.
- Có weight để tính điểm cuối cùng.
- Có order để sắp xếp thứ tự hiển thị.

Được sử dụng tại:
- Assessment Service (render câu hỏi)
- Assessment Form (hiển thị cho user)
- Burnout Engine (tính điểm với weight)

Luồng dữ liệu:
AssessmentTemplate
      ↓
AssessmentQuestion[]
      ↓
User trả lời
      ↓
AssessmentAnswer[]
==============================================================
"""

from datetime import datetime
from typing import List, Optional, Literal, Union

from pydantic import BaseModel, Field, ConfigDict


class QuestionOption(BaseModel):
    """
    Option cho câu hỏi multiple_choice hoặc single_choice.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "value": "never",
                "label": "Không bao giờ",
                "score": 0
            }
        }
    )

    value: str = Field(
        ...,
        description="Giá trị của option"
    )

    label: str = Field(
        ...,
        description="Nhãn hiển thị cho user"
    )

    score: float = Field(
        default=0.0,
        description="Điểm số tương ứng với option này"
    )


class AssessmentQuestion(BaseModel):
    """
    Domain Model cho một câu hỏi trong bộ đánh giá.

    Ví dụ:
    - "Bạn ngủ bao nhiêu tiếng mỗi đêm?" (number, 0-24)
    - "Bạn có hài lòng với công việc không?" (boolean)
    - "Mức độ stress của bạn?" (scale, 1-10)
    - "Bạn cảm thấy thế nào?" (text)
    - "Bạn thường làm gì để giảm stress?" (multiple_choice)
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "q_burnout_001",
                "template_id": "tmpl_burnout_v1",
                "question": "Bạn ngủ bao nhiêu tiếng mỗi đêm?",
                "description": "Tính trung bình số giờ ngủ trong tuần qua",
                "question_type": "number",
                "category": "sleep",
                "required": True,
                "order": 1,
                "options": None,
                "min_value": 0,
                "max_value": 24,
                "weight": 1.5
            }
        }
    )

    id: str = Field(
        ...,
        description="Unique identifier của câu hỏi"
    )

    template_id: str = Field(
        ...,
        description="ID của template chứa câu hỏi này"
    )

    question: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Nội dung câu hỏi"
    )

    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Mô tả chi tiết hoặc hướng dẫn trả lời"
    )

    question_type: Literal["number", "boolean", "scale", "text", "multiple_choice", "single_choice"] = Field(
        ...,
        description="Loại câu hỏi"
    )

    category: Literal["sleep", "workload", "stress", "emotion", "work_life", "support", "general"] = Field(
        ...,
        description="Danh mục câu hỏi để group các factors"
    )

    required: bool = Field(
        default=True,
        description="Câu hỏi có bắt buộc trả lời hay không"
    )

    order: int = Field(
        ...,
        ge=1,
        description="Thứ tự hiển thị câu hỏi"
    )

    options: Optional[List[QuestionOption]] = Field(
        default=None,
        description="Danh sách options cho multiple_choice hoặc single_choice"
    )

    min_value: Optional[float] = Field(
        default=None,
        description="Giá trị tối thiểu cho number hoặc scale"
    )

    max_value: Optional[float] = Field(
        default=None,
        description="Giá trị tối đa cho number hoặc scale"
    )

    weight: float = Field(
        default=1.0,
        ge=0.0,
        description="Hệ số nhân khi tính điểm burnout (dùng trong Burnout Engine)"
    )
