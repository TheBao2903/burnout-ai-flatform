"""
==============================================================
File: burnout_vector.py

Chức năng:
- Model lưu metadata của một lần đánh giá Burnout trong Qdrant.
- Dùng để AI tìm những trường hợp tương tự trong quá khứ.

Đặc điểm:
- Lưu kết quả đánh giá burnout để similarity search.
- Dùng để tìm user có burnout pattern tương tự.
- Phục vụ recommendation system.

Được sử dụng tại:
- Burnout Engine (index kết quả sau khi đánh giá)
- Similarity Search (tìm case tương tự)
- Pattern Analysis (phân tích burnout patterns)

Moved from app/ai_models/burnout_vector.py (Sprint 18b refactor).
==============================================================
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict

from app.modules.knowledge.models.base_vector import BaseVector


class BurnoutVector(BaseVector):
    """
    Model lưu metadata của đánh giá Burnout trong Qdrant.

    Ví dụ:
    - User A có burnout_score=75, emotion=sad, factors=[sleep, workload]
    - User B có burnout_score=72, emotion=tired, factors=[workload, stress]

    → AI có thể tìm user tương tự để đưa ra recommendations phù hợp
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "burnout_vec_session001",
                "source": "burnout_result",
                "session_id": "session_abc123",
                "burnout_score": 72.5,
                "dominant_emotion": "sad",
                "stress_level": "medium",
                "factors": [
                    {"factor": "sleep", "percentage": 35.0},
                    {"factor": "workload", "percentage": 30.0},
                    {"factor": "emotion", "percentage": 20.0},
                    {"factor": "stress", "percentage": 15.0}
                ],
                "recommendation": "Nên nghỉ ngơi 1-2 ngày, cải thiện giấc ngủ",
                "created_at": "2024-01-20T10:15:00Z",
                "embedding_model": "text-embedding-004"
            }
        }
    )

    session_id: str = Field(
        ...,
        description="ID của session đánh giá"
    )

    burnout_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Điểm burnout tổng (0-100)"
    )

    dominant_emotion: str = Field(
        ...,
        description="Cảm xúc chiếm ưu thế: happy, sad, neutral, angry, etc."
    )

    stress_level: Literal["low", "medium", "high"] = Field(
        ...,
        description="Mức độ stress từ cuộc hội thoại"
    )

    factors: List[dict] = Field(
        default_factory=list,
        description="Danh sách các factors và percentage đóng góp"
    )

    recommendation: str = Field(
        ...,
        description="Khuyến nghị chính từ đánh giá này"
    )