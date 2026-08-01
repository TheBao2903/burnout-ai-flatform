"""
==============================================================
File: survey.py

Chức năng:
- Định nghĩa model SurveyResult - kết quả khảo sát từ user.
- Thu thập các chỉ số sinh lý và lối sống ảnh hưởng đến burnout.

Được sử dụng tại:
- Survey Form (Frontend submit)
- API Layer (nhận và validate data)
- Burnout Engine (lấy survey để tính score)

Luồng dữ liệu:
Survey Form → SurveyResult → Burnout Engine → BurnoutResult
==============================================================
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class SurveyResult(BaseModel):
    """
    Domain Model cho kết quả khảo sát của user.

    Thu thập các thông tin về giấc ngủ, giờ làm việc, deadline...
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "sleep_hour": 5.5,
                "working_hour": 10.0,
                "overtime": 3,
                "deadline": "high",
                "work_day": 6,
                "heart_rate": 85
            }
        }
    )

    sleep_hour: float = Field(
        ...,
        ge=0.0,
        le=24.0,
        description="Số giờ ngủ trung bình mỗi đêm"
    )

    working_hour: float = Field(
        ...,
        ge=0.0,
        le=24.0,
        description="Số giờ làm việc mỗi ngày"
    )

    overtime: int = Field(
        default=0,
        ge=0,
        le=24,
        description="Số giờ làm thêm mỗi ngày"
    )

    deadline: str = Field(
        ...,
        description="Mức độ deadline: low, medium, high, extreme"
    )

    work_day: int = Field(
        ...,
        ge=1,
        le=7,
        description="Số ngày làm việc trong tuần"
    )

    heart_rate: Optional[int] = Field(
        default=None,
        ge=30,
        le=220,
        description="Nhịp tim trung bình (bpm) - optional"
    )

    # Backend-only fields
    submitted_at: Optional[datetime] = Field(
        default=None,
        description="Thời điểm submit khảo sát (backend generated)"
    )
