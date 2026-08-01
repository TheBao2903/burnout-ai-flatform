"""
==============================================================
File: burnout_engine_output.py

Chức năng:
- Định nghĩa BurnoutEngineOutput - output của Burnout Engine.
- Chứa kết quả cuối cùng từ Burnout Engine.

Đặc điểm:
- Bao gồm BurnoutResult (điểm số) và InsightResult (nhận định AI).
- Hai thành phần độc lập nhưng cùng được sinh từ Engine.

Được sử dụng tại:
- Burnout Engine (sinh output)
- Session Service (lưu kết quả)
- API Layer (trả kết quả cho client)
- Dashboard (hiển thị kết quả)

Luồng dữ liệu:
BurnoutEngineInput
      ↓
Burnout Engine
      ↓
BurnoutEngineOutput
      ├── BurnoutResult ──→ Dashboard, Report
      └── InsightResult ──→ Knowledge Pipeline
==============================================================
"""

from pydantic import BaseModel, Field, ConfigDict

from .burnout import BurnoutResult
from .insight import InsightResult


class BurnoutEngineOutput(BaseModel):
    """
    Domain Model làm Output từ Burnout Engine.

    Chứa hai thành phần chính:
    - burnout: Kết quả điểm số và factors
    - insight: Nhận định và phân tích chi tiết
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "burnout": {
                    "burnout_score": 72.5,
                    "confidence": 0.89,
                    "risk_level": "high",
                    "factors": [
                        {"factor": "emotion", "percentage": 35.0},
                        {"factor": "sleep", "percentage": 30.0},
                        {"factor": "workload", "percentage": 20.0},
                        {"factor": "stress", "percentage": 15.0}
                    ],
                    "recommendations": [
                        "Nên nghỉ ngơi 1-2 ngày",
                        "Cải thiện giấc ngủ"
                    ]
                },
                "insight": {
                    "id": "insight_001",
                    "session_id": "session_abc123",
                    "summary": "Người dùng có dấu hiệu burnout ở mức cao, chủ yếu do thiếu ngủ và áp lực công việc.",
                    "primary_factor": "sleep",
                    "secondary_factor": "workload",
                    "stress_level": "high",
                    "burnout_risk": "high",
                    "confidence": 0.85
                }
            }
        }
    )

    burnout: BurnoutResult = Field(
        ...,
        description="Kết quả điểm số burnout và các factors"
    )

    insight: InsightResult = Field(
        ...,
        description="Nhận định chi tiết về tình trạng của user"
    )
