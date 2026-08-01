"""
==============================================================
File: burnout_engine_input.py

Chức năng:
- Định nghĩa BurnoutEngineInput - input cho Burnout Engine.
- Tổng hợp tất cả dữ liệu từ các module khác.

Đặc điểm:
- Burnout Engine KHÔNG phụ thuộc Firebase, GPT, DeepFace, Qdrant.
- Chỉ làm việc với Input và Output thuần Python/Pydantic.
- Tất cả data đã được chuẩn hóa từ các module khác.

Được sử dụng tại:
- Session Service (chuẩn bị input)
- Burnout Engine (nhận input, tính toán)
- DeepFace Integration (trả EmotionResult)
- Survey Service (trả SurveyResult)
- Chat Service (trả ChatResult)

Luồng dữ liệu:
DeepFace ──→ EmotionResult ──────────────────────────┐
                                                  │
Survey Form ──→ SurveyResult ─────────────────────┤
                                                  │
Assessment ──→ AssessmentResult ──────────────────┤
                                                  │
Chat Session ──→ ChatResult ─────────────────────┤
                                                  │
All Together ──→ BurnoutEngineInput ──→ Burnout Engine
                                                  │
                                                  ▼
                                          BurnoutEngineOutput
==============================================================
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from .emotion import EmotionResult
from .survey import SurveyResult
from .chat import ChatResult
from .assessment_result import AssessmentResult


class BurnoutEngineInput(BaseModel):
    """
    Domain Model làm Input cho Burnout Engine.

    Tổng hợp tất cả kết quả từ các module:
    - Emotion (từ DeepFace)
    - Survey (từ Survey Form)
    - Assessment (từ Assessment Questions)
    - Chat (từ Chat Session)
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "session_id": "session_abc123",
                "emotion": {
                    "emotions": {
                        "happy": 20.0,
                        "sad": 45.0,
                        "neutral": 25.0,
                        "fear": 5.0,
                        "angry": 3.0,
                        "surprise": 1.0,
                        "disgust": 1.0
                    },
                    "dominant_emotion": "sad",
                    "confidence": 0.87,
                    "age": 28,
                    "gender": "Man"
                },
                "survey": {
                    "sleep_hour": 5.0,
                    "working_hour": 11.0,
                    "overtime": 3,
                    "deadline": "high",
                    "work_day": 6,
                    "heart_rate": 90
                },
                "assessment": {
                    "session_id": "session_abc123",
                    "answers": [],
                    "completed": True,
                    "completed_at": "2024-01-20T10:10:00Z"
                },
                "chat": {
                    "session_id": "session_abc123",
                    "messages": [],
                    "summary": "User chia sẻ về...",
                    "keywords": ["mệt", "công việc"],
                    "stress_level": "medium",
                    "burnout_signal": "medium"
                },
                "timestamp": "2024-01-20T10:15:00Z"
            }
        }
    )

    session_id: str = Field(
        ...,
        description="ID của session đang được đánh giá"
    )

    emotion: Optional[EmotionResult] = Field(
        default=None,
        description="Kết quả phân tích cảm xúc từ DeepFace"
    )

    survey: Optional[SurveyResult] = Field(
        default=None,
        description="Kết quả khảo sát từ Survey Form"
    )

    assessment: Optional[AssessmentResult] = Field(
        default=None,
        description="Kết quả đánh giá từ Assessment Questions"
    )

    chat: Optional[ChatResult] = Field(
        default=None,
        description="Kết quả phân tích chat từ OpenAI"
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm tạo input"
    )
