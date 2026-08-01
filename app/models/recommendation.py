"""
==============================================================
File: recommendation.py

Chức năng:
- Định nghĩa model Recommendation - khuyến nghị cá nhân hóa.
- Được tạo dựa trên BurnoutResult và Profile của user.

Được sử dụng tại:
- Burnout Engine (sinh recommendations)
- API Layer (trả recommendations)
- Notification System (gửi reminder)

Luồng dữ liệu:
BurnoutResult + User Profile → Recommendation Engine → Recommendation
                                                ↓
                                    User nhận notification
==============================================================
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class Recommendation(BaseModel):
    """
    Domain Model cho một khuyến nghị cá nhân hóa.

    Dựa trên burnout score và factors để đưa ra lời khuyên phù hợp.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "title": "Cải thiện giấc ngủ",
                "description": "Bạn chỉ ngủ 4-5 tiếng mỗi đêm. Hãy cố gắng ngủ đủ 7-8 tiếng để phục hồi năng lượng.",
                "priority": "high"
            }
        }
    )

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Tiêu đề khuyến nghị"
    )

    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Mô tả chi tiết khuyến nghị"
    )

    priority: Literal["low", "medium", "high", "urgent"] = Field(
        default="medium",
        description="Mức độ ưu tiên của khuyến nghị"
    )

    target_factor: Optional[str] = Field(
        default=None,
        description="Factor mà khuyến nghị này hướng đến: emotion, sleep, workload, stress"
    )
