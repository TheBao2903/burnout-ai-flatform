"""
==============================================================
File: embedding_document.py

Chức năng:
- Định nghĩa EmbeddingDocument - dữ liệu chuẩn bị gửi sang Embedding Model.
- Chuẩn bị data để tạo vector embedding.

Đặc điểm:
- KHÔNG chứa vector thực tế.
- Chỉ chứa metadata và input_text để gửi sang Embedding Model.
- Vector sẽ do OpenAI/BGE/SentenceTransformer sinh ra.

Được sử dụng tại:
- Embedding Service (gọi Embedding Model)
- Knowledge Pipeline (chuẩn bị data trước khi embedding)

Luồng dữ liệu:
KnowledgeDocument
      ↓
EmbeddingDocument (thêm metadata)
      ↓
Embedding Model ──→ Vector + Metadata
      ↓
VectorPayload
      ↓
Qdrant
==============================================================
"""

from datetime import datetime
from typing import Dict, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict


class EmbeddingDocument(BaseModel):
    """
    Domain Model chuẩn bị data trước khi gửi sang Embedding Model.

    Chứa:
    - knowledge_id: Link đến KnowledgeDocument
    - input_text: Text để tạo embedding
    - metadata: Payload đi kèm vector
    - embedding info: Model và provider

    KHÔNG chứa vector thực tế.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "emb_001",
                "knowledge_id": "know_001",
                "embedding_provider": "openai",
                "embedding_model": "text-embedding-3-small",
                "input_text": "Người dùng có dấu hiệu thiếu ngủ kéo dài và áp lực công việc cao. Stress level: high, Burnout risk: high. Primary factor: sleep, Secondary factor: workload.",
                "metadata": {
                    "knowledge_id": "know_001",
                    "source": "user_session",
                    "document_type": "burnout_case",
                    "title": "Case Study: Sleep Deprivation",
                    "keywords": ["sleep", "workload", "burnout"],
                    "tags": ["sleep", "workload", "high_stress"],
                    "session_id": "session_abc123"
                },
                "created_at": "2024-01-20T10:16:00Z"
            }
        }
    )

    id: str = Field(
        ...,
        description="Unique identifier của embedding document"
    )

    knowledge_id: str = Field(
        ...,
        description="ID của KnowledgeDocument gốc"
    )

    embedding_provider: Literal["openai", "bge", "sentence_transformer"] = Field(
        ...,
        description="Provider của embedding model"
    )

    embedding_model: str = Field(
        ...,
        description="Tên model: text-embedding-3-small, BGE-M3, etc."
    )

    input_text: str = Field(
        ...,
        min_length=1,
        description="Text để gửi sang Embedding Model (đã được chuẩn hóa)"
    )

    metadata: Dict = Field(
        ...,
        description="Payload đi kèm vector khi lưu vào Qdrant"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm tạo embedding document"
    )
