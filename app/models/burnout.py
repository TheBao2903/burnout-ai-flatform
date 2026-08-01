"""
==============================================================
File: burnout.py

Chức năng:
- Định nghĩa model BurnoutFactor và BurnoutResult.
- BurnoutResult là KẾT QUẢ CUỐI CÙNG của Burnout Engine.
- Tổng hợp tất cả các factor để đưa ra đánh giá tổng quan.

Được sử dụng tại:
- Burnout Engine (output cuối cùng)
- API Layer (trả kết quả cho client)
- Dashboard (hiển thị kết quả)
- Report Generation (dùng cho monthly report)

Luồng dữ liệu:
Emotion + Survey + Chat → Burnout Engine → BurnoutResult → Client
                                            ↓
                                    Recommendations
==============================================================
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class BurnoutFactor(BaseModel):
    """
    Domain Model cho một yếu tố ảnh hưởng đến Burnout.

    Mỗi factor có tên và percentage đóng góp vào burnout tổng.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "factor": "emotion",
                "percentage": 35.5,
                "details": {
                    "dominant_emotion": "sad",
                    "sad_score": 45.0
                }
            }
        }
    )

    factor: str = Field(
        ...,
        description="Tên factor: emotion, sleep, workload, stress, chat"
    )

    percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Tỷ lệ đóng góp của factor vào burnout tổng (%)"
    )

    details: Optional[dict] = Field(
        default=None,
        description="Chi tiết bổ sung của factor (tùy loại)"
    )


class BurnoutResult(BaseModel):
    """
    Domain Model cho kết quả đánh giá Burnout cuối cùng.

    Tổng hợp tất cả inputs (emotion, survey, chat) thành một kết quả.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "burnout_score": 72.5,
                "confidence": 0.89,
                "risk_level": "high",
                "factors": [
                    {"factor": "emotion", "percentage": 35.0, "details": {"dominant_emotion": "sad"}},
                    {"factor": "workload", "percentage": 25.0, "details": {"working_hour": 12}},
                    {"factor": "sleep", "percentage": 20.0, "details": {"sleep_hour": 4}},
                    {"factor": "stress", "percentage": 20.0, "details": {"stress_level": 8}}
                ],
                "recommendations": [
                    "Nên nghỉ ngơi 1-2 ngày",
                    "Giảm giờ làm xuống 8h/ngày"
                ],
                "analyzed_at": "2024-01-20T10:15:00Z"
            }
        }
    )

    burnout_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Điểm burnout tổng (0-100)"
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Độ tin cậy của kết quả (0-1)"
    )

    risk_level: Literal["low", "medium", "high", "critical"] = Field(
        ...,
        description="Mức độ rủi ro burnout"
    )

    factors: List[BurnoutFactor] = Field(
        default_factory=list,
        description="Danh sách các factor và tỷ lệ đóng góp"
    )

    recommendations: List[str] = Field(
        default_factory=list,
        description="Danh sách khuyến nghị cho user"
    )

    analyzed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm phân tích"
    )
