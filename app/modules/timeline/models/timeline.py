"""
==============================================================
File: timeline.py

Timeline Models - Du lieu dashboard theo thoi gian.
==============================================================
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


class Timeline(BaseModel):
    """Diem du lieu tren timeline."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "session_id": "session_abc123",
                "user_id": "user_123",
                "burnout_score": 65.0,
                "risk_level": "high",
                "dominant_emotion": "sad",
                "timestamp": "2024-01-20T10:15:00Z"
            }
        }
    )

    session_id: str = Field(..., description="ID cua session")
    user_id: str = Field(..., description="ID cua user")
    burnout_score: float = Field(..., ge=0.0, le=100.0, description="Diem burnout")
    risk_level: Literal["low", "medium", "high", "critical"] = Field(..., description="Muc do rui ro")
    dominant_emotion: str = Field(..., description="Cảm xúc chiếm ưu")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Thoi diem")
