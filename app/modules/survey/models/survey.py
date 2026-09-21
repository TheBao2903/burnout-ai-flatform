"""
==============================================================
File: survey.py

Survey Models - Ket qua khao sat.
==============================================================
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class SurveyResult(BaseModel):
    """Ket qua khao sat cua user."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "sleep_hour": 5.5,
                "working_hour": 10.0,
                "overtime": 3,
                "deadline": "high",
                "work_day": 6,
                "heart_rate": 85,
                "submitted_at": "2024-01-20T10:05:00Z"
            }
        }
    )

    sleep_hour: float = Field(..., ge=0.0, le=24.0, description="So gio ngu")
    working_hour: float = Field(..., ge=0.0, le=24.0, description="So gio lam viec")
    overtime: int = Field(default=0, ge=0, le=24, description="So gio lam them")
    deadline: str = Field(..., description="Muc do deadline: low, medium, high, extreme")
    work_day: int = Field(..., ge=1, le=7, description="So ngay lam viec/tuan")
    heart_rate: Optional[int] = Field(default=None, ge=30, le=220, description="Nhip tim (bpm)")
    submitted_at: Optional[datetime] = Field(default=None, description="Thoi diem submit")
