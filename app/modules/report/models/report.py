"""
==============================================================
File: report.py

Report Models - Bao cao tong hop.
==============================================================
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class Report(BaseModel):
    """Bao cao tong hop theo thang."""

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
                "dominant_emotions": {"sad": 45, "neutral": 30, "happy": 25},
                "created_at": "2024-02-01T00:00:00Z"
            }
        }
    )

    id: str = Field(..., description="Unique ID")
    user_id: str = Field(..., description="ID cua user")
    month: str = Field(..., description="Thang bao cao: YYYY-MM")
    average_burnout: float = Field(..., ge=0.0, le=100.0, description="Diem TB")
    highest_score: float = Field(..., ge=0.0, le=100.0, description="Diem cao nhat")
    lowest_score: float = Field(..., ge=0.0, le=100.0, description="Diem thap nhat")
    total_sessions: int = Field(default=0, ge=0, description="Tong so phien")
    dominant_emotions: Optional[dict] = Field(default=None, description="Tong hop cam xuc")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Thoi diem tao")
