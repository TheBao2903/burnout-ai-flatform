"""
==============================================================
File: emotion.py

Emotion Models - Ket qua phan tich cam xuc tu DeepFace.
==============================================================
"""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


class EmotionScores(BaseModel):
    """Chi tiet diem so cua tung cam xuc (0-100%)."""

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

    happy: float = Field(default=0.0, ge=0, le=100, description="Muc do hanh phuc (%)")
    sad: float = Field(default=0.0, ge=0, le=100, description="Muc do buon (%)")
    neutral: float = Field(default=0.0, ge=0, le=100, description="Muc do trung lap (%)")
    fear: float = Field(default=0.0, ge=0, le=100, description="Muc do so hai (%)")
    angry: float = Field(default=0.0, ge=0, le=100, description="Muc do tuc gian (%)")
    surprise: float = Field(default=0.0, le=100, description="Muc do bat ngo (%)")
    disgust: float = Field(default=0.0, ge=0, le=100, description="Muc do ghe tom (%)")


class EmotionResult(BaseModel):
    """
    Ket qua phan tich cam xuc tu DeepFace.

    IMPORTANT: confidence la raw model score, khong phai psychological certainty.
    Su dung reliability_level de hieu do tin cay cua ket qua.
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

    emotions: EmotionScores = Field(default_factory=EmotionScores, description="Diem so cam xuc")
    dominant_emotion: str = Field(..., description="Cảm xúc chiếm ưu thế nhất")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Raw model score (0-1)")
    age: Optional[int] = Field(default=None, ge=0, le=120, description="Tuoi uoc tinh")
    gender: Optional[str] = Field(default=None, description="Gioi tinh: Man, Woman")
    image_url: Optional[str] = Field(default=None, description="URL anh da phan tich")
    analyzed_at: datetime = Field(default_factory=datetime.utcnow, description="Thoi diem phan tich")

    # Additional metadata (not in Pydantic schema but used internally)
    face_confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Face detection confidence"
    )
    reliability_level: Optional[str] = Field(
        default=None,
        description="System reliability: high/medium/low"
    )
    face_count: Optional[int] = Field(
        default=None, ge=0,
        description="So luong face phat hien"
    )
    detector_used: Optional[str] = Field(
        default=None,
        description="Face detector backend su dung"
    )
    warnings: Optional[List[str]] = Field(
        default=None,
        description="Warnings ve chat luong phan tich"
    )
