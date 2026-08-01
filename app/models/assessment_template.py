"""
==============================================================
File: assessment_template.py

Chức năng:
- Định nghĩa AssessmentTemplate - đại diện cho một bộ câu hỏi đánh giá.
- Hỗ trợ nhiều loại assessment: Burnout, Stress, Anxiety, Depression...

Đặc điểm:
- Một Template có nhiều Questions.
- Có thể activate/deactivate template.
- Hỗ trợ versioning.

Được sử dụng tại:
- Assessment Service (quản lý templates)
- Session Start (lấy template để bắt đầu assessment)
- Admin Dashboard (quản lý assessments)

Luồng dữ liệu:
AssessmentTemplate → AssessmentQuestion[] → AssessmentAnswer[] → AssessmentResult
                                             ↓
                                     BurnoutEngineInput
==============================================================
"""

from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict


class AssessmentTemplate(BaseModel):
    """
    Domain Model cho một bộ câu hỏi đánh giá.

    Ví dụ:
    - Burnout Assessment (MBI - Maslach Burnout Inventory)
    - Stress Assessment (PSS - Perceived Stress Scale)
    - Sleep Quality Assessment
    - Depression Screening (PHQ-9)
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "tmpl_burnout_v1",
                "title": "Burnout Assessment",
                "description": "Đánh giá mức độ kiệt sức (Burnout) dựa trên MBI",
                "version": "1.0.0",
                "category": "burnout",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00Z"
            }
        }
    )

    id: str = Field(
        ...,
        description="Unique identifier của template"
    )

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Tiêu đề bộ câu hỏi"
    )

    description: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Mô tả chi tiết về bộ câu hỏi"
    )

    version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+$",
        description="Phiên bản template theo semver: 1.0.0"
    )

    category: Literal["burnout", "stress", "anxiety", "depression", "sleep", "mental_health"] = Field(
        ...,
        description="Danh mục của assessment"
    )

    is_active: bool = Field(
        default=True,
        description="Template có đang được sử dụng hay không"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm tạo template"
    )
