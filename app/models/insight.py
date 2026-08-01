"""
==============================================================
File: insight.py

Chức năng:
- Định nghĩa InsightResult - nhận định chi tiết về tình trạng burnout.
- Đây là OUTPUT từ AI/GPT, không phải kết luận bệnh.

Đặc điểm:
- Insight CHỈ mô tả nguyên nhân, yếu tố, nhận định.
- Không đưa ra chẩn đoán y khoa.
- Dùng để hiểu rõ hơn về tình trạng user.

Được sử dụng tại:
- Burnout Engine (sinh insight)
- Knowledge Pipeline (index insight để RAG)
- Dashboard (hiển thị insight cho user)
- RAG Service (context cho GPT)

Lưu ý:
- Insight được sinh bởi AI (GPT-4).
- Sau đó được chuẩn hóa vào KnowledgeDocument.
- KnowledgeDocument được index vào Qdrant.
==============================================================
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class InsightResult(BaseModel):
    """
    Domain Model cho kết quả nhận định của AI.

    Insight không phải kết luận bệnh.
    Chỉ mô tả nguyên nhân, yếu tố, và nhận định về tình trạng burnout.

    Ví dụ:
    - summary: "Người dùng có dấu hiệu thiếu ngủ kéo dài và áp lực công việc cao."
    - primary_factor: "sleep"
    - secondary_factor: "workload"
    - stress_level: "high"
    - burnout_risk: "high"
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "insight_001",
                "session_id": "session_abc123",
                "summary": "Người dùng có dấu hiệu thiếu ngủ kéo dài (4-5 tiếng/đêm) và áp lực công việc cao (OT 3-4 tiếng/ngày). Cảm xúc chiếm ưu thế là 'sad' và 'neutral', cho thấy trạng thái mệt mỏi và kiệt sức. Ngoài ra, từ cuộc hội thoại, user thể hiện sự lo lắng về deadline và khối lượng công việc.",
                "primary_factor": "sleep",
                "secondary_factor": "workload",
                "stress_level": "high",
                "burnout_risk": "high",
                "confidence": 0.85,
                "created_at": "2024-01-20T10:15:00Z"
            }
        }
    )

    id: str = Field(
        ...,
        description="Unique identifier của insight"
    )

    session_id: str = Field(
        ...,
        description="ID của session tạo ra insight này"
    )

    summary: str = Field(
        ...,
        min_length=1,
        description="Tóm tắt nhận định về tình trạng burnout (do GPT sinh)"
    )

    primary_factor: str = Field(
        ...,
        description="Yếu tố chính gây burnout: sleep, workload, emotion, stress"
    )

    secondary_factor: str = Field(
        ...,
        description="Yếu tố phụ ảnh hưởng đến burnout"
    )

    stress_level: Literal["low", "medium", "high"] = Field(
        ...,
        description="Mức độ stress được đánh giá"
    )

    burnout_risk: Literal["low", "medium", "high"] = Field(
        ...,
        description="Mức độ rủi ro burnout"
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Độ tin cậy của insight (0-1)"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm tạo insight"
    )
