"""
==============================================================
File: vector_payload.py

Chức năng:
- Định nghĩa VectorPayload - payload lưu trong Qdrant.
- Model cuối cùng trong Knowledge Pipeline.

Đặc điểm:
- Chứa payload và metadata để lưu vào Qdrant.
- Vector thực tế không nằm trong model này.
- Qdrant sẽ lưu vector riêng, payload này đi kèm.

Được sử dụng tại:
- Embedding Service (tạo payload sau khi có vector)
- Qdrant Integration (upsert vào Qdrant)

Luồng dữ liệu:
EmbeddingDocument + Vector (từ Model)
      ↓
VectorPayload
      ↓
Qdrant (upsert point)
==============================================================
"""

from datetime import datetime
from typing import Dict, Literal

from pydantic import BaseModel, Field, ConfigDict


class VectorPayload(BaseModel):
    """
    Domain Model cho payload lưu trong Qdrant.

    Payload này đi kèm với vector trong Qdrant.
    Vector thực tế do Embedding Model sinh, không nằm trong model này.

    Qdrant sẽ lưu:
    - point_id: unique ID
    - vector: embedding vector (float array)
    - payload: VectorPayload này
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "point_id": "point_001",
                "knowledge_id": "know_001",
                "collection_name": "burnout_knowledge",
                "payload": {
                    "id": "know_001",
                    "source": "user_session",
                    "document_type": "burnout_case",
                    "title": "Case Study: Sleep Deprivation",
                    "keywords": ["sleep", "workload", "burnout"],
                    "tags": ["sleep", "workload"],
                    "session_id": "session_abc123",
                    "burnout_score": 72.5,
                    "stress_level": "high",
                    "primary_factor": "sleep"
                },
                "created_at": "2024-01-20T10:16:00Z"
            }
        }
    )

    point_id: str = Field(
        ...,
        description="Unique ID của point trong Qdrant"
    )

    knowledge_id: str = Field(
        ...,
        description="ID của KnowledgeDocument gốc"
    )

    collection_name: Literal["burnout_knowledge", "burnout_case_memory", "recommendations"] = Field(
        ...,
        description="Tên collection trong Qdrant"
    )

    payload: Dict = Field(
        ...,
        description="Metadata payload đi kèm vector (từ EmbeddingDocument.metadata)"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm tạo payload"
    )
