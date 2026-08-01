"""
==============================================================
File: timeline.py

Chức năng:
- Định nghĩa model Timeline - dữ liệu cho Dashboard theo thời gian.
- Tổng hợp kết quả để hiển thị chart và trend.

Được sử dụng tại:
- Dashboard (hiển thị chart burnout theo thời gian)
- Report Generation (lấy data cho monthly report)
- Analytics (phân tích xu hướng)

Luồng dữ liệu:
Session + BurnoutResult → Timeline Entry → Dashboard Chart
                                    ↓
                            Monthly Report
==============================================================
"""

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field, ConfigDict


class Timeline(BaseModel):
    """
    Domain Model cho một điểm dữ liệu trên Timeline.

    Đại diện cho kết quả đánh giá tại một thời điểm.
    Dùng để hiển thị chart và phân tích xu hướng.
    """

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

    session_id: str = Field(
        ...,
        description="ID của session tạo ra timeline entry này"
    )

    user_id: str = Field(
        ...,
        description="ID của user thực hiện đánh giá"
    )

    burnout_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Điểm burnout tại thời điểm này"
    )

    risk_level: Literal["low", "medium", "high", "critical"] = Field(
        ...,
        description="Mức độ rủi ro tại thời điểm này"
    )

    dominant_emotion: str = Field(
        ...,
        description="Cảm xúc chiếm ưu thế tại thời điểm này"
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm ghi nhận"
    )
