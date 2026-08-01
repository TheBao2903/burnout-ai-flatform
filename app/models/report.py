"""
==============================================================
File: report.py

Chức năng:
- Định nghĩa model Report - báo cáo tổng hợp theo tháng.
- Tổng hợp dữ liệu từ nhiều Sessions trong tháng.

Được sử dụng tại:
- Report Service (tạo monthly report)
- API Layer (trả report cho client)
- Dashboard (hiển thị tổng hợp)
- Analytics (phân tích trends)

Luồng dữ liệu:
Timeline Data (Monthly) → Report Service → Report → Client/Dashboard
                                    ↓
                            Analytics
==============================================================
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class Report(BaseModel):
    """
    Domain Model cho báo cáo tổng hợp theo tháng.

    Tổng hợp các chỉ số burnout trong một tháng.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "report_jan2024",
                "user_id": "user_123",
                "month": "2024-01",
                "average_burnout": 58.5,
                "highest_score": 78.0,
                "lowest_score": 35.0,
                "total_sessions": 12,
                "dominant_emotions": {
                    "sad": 45,
                    "neutral": 30,
                    "happy": 25
                },
                "created_at": "2024-02-01T00:00:00Z"
            }
        }
    )

    id: str = Field(
        ...,
        description="Unique identifier của report"
    )

    user_id: str = Field(
        ...,
        description="ID của user được tạo report"
    )

    month: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}$",
        description="Tháng báo cáo theo định dạng YYYY-MM"
    )

    average_burnout: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Điểm burnout trung bình trong tháng"
    )

    highest_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Điểm burnout cao nhất trong tháng"
    )

    lowest_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Điểm burnout thấp nhất trong tháng"
    )

    total_sessions: int = Field(
        default=0,
        ge=0,
        description="Tổng số phiên đánh giá trong tháng"
    )

    dominant_emotions: Optional[dict] = Field(
        default=None,
        description="Tổng hợp cảm xúc chiếm ưu thế trong tháng"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm tạo report"
    )
