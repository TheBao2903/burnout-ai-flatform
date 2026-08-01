"""
==============================================================
File: emotion.py

Chức năng:
- Định nghĩa model EmotionResult - kết quả phân tích cảm xúc từ DeepFace.
- Chuyển đổi output từ DeepFace thành domain model chuẩn.
- Phục vụ Burnout Engine tính toán Burnout Score.

Được sử dụng tại:
- DeepFace Integration (convert raw output)
- Burnout Engine (lấy cảm xúc để tính score)
- API Layer (trả kết quả cho client)

Luồng dữ liệu:
DeepFace → EmotionResult → Burnout Engine → BurnoutResult
                ↓
        Dashboard (hiển thị cảm xúc)
==============================================================
"""

from datetime import datetime
from typing import Optional, Dict

from pydantic import BaseModel, Field, ConfigDict


class EmotionScores(BaseModel):
    """
    Chi tiết điểm số của từng cảm xúc.

    Mỗi giá trị là percentage (0-100).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "happy": 65.5,
                "sad": 10.2,
                "neutral": 15.0,
                "fear": 2.1,
                "angry": 3.3,
                "surprise": 1.5,
                "disgust": 2.4
            }
        }
    )

    happy: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Mức độ hạnh phúc (%)"
    )

    sad: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Mức độ buồn (%)"
    )

    neutral: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Mức độ trung lập (%)"
    )

    fear: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Mức độ sợ hãi (%)"
    )

    angry: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Mức độ tức giận (%)"
    )

    surprise: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Mức độ bất ngờ (%)"
    )

    disgust: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Mức độ ghê tởm (%)"
    )


class EmotionResult(BaseModel):
    """
    Domain Model cho kết quả phân tích cảm xúc từ DeepFace.

    Đại diện cho cảm xúc được phân tích từ ảnh khuôn mặt.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "emotions": {
                    "happy": 65.5,
                    "sad": 10.2,
                    "neutral": 15.0,
                    "fear": 2.1,
                    "angry": 3.3,
                    "surprise": 1.5,
                    "disgust": 2.4
                },
                "dominant_emotion": "happy",
                "confidence": 0.87,
                "age": 28,
                "gender": "Man",
                "image_url": "https://storage.example.com/uploads/session_123/frame_1.jpg",
                "analyzed_at": "2024-01-20T10:05:30Z"
            }
        }
    )

    emotions: EmotionScores = Field(
        default_factory=EmotionScores,
        description="Điểm số của từng cảm xúc"
    )

    dominant_emotion: str = Field(
        ...,
        description="Cảm xúc chiếm ưu thế nhất"
    )

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Độ tin cậy của kết quả phân tích (0-1)"
    )

    age: Optional[int] = Field(
        default=None,
        ge=0,
        le=120,
        description="Tuổi ước tính từ khuôn mặt"
    )

    gender: Optional[str] = Field(
        default=None,
        description="Giới tính ước tính: Man, Woman"
    )

    image_url: Optional[str] = Field(
        default=None,
        description="URL của ảnh đã phân tích"
    )

    analyzed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm phân tích"
    )
