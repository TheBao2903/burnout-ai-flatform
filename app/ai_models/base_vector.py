"""
==============================================================
File: base_vector.py

Chức năng:
- Định nghĩa BaseVector - model cha cho tất cả Vector models.
- Chứa các trường chung dùng chung cho tất cả vectors.

Đặc điểm:
- Tất cả Vector models đều kế thừa từ BaseVector.
- Không chứa vector thực tế (vector do OpenAI/Embedding model sinh).
- Chỉ mô tả metadata đi kèm vector.

Được sử dụng tại:
- Vector Service (tạo payload cho Qdrant)
- Search Service (parse kết quả từ Qdrant)
- Embedding Service (gắn metadata với vector)
==============================================================
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class BaseVector(BaseModel):
    """
    Base Model cho tất cả Vector models.

    Chứa các trường chung dùng cho mọi loại vector.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "vec_001",
                "source": "who",
                "created_at": "2024-01-20T10:00:00Z",
                "embedding_model": "text-embedding-3-small"
            }
        }
    )

    id: str = Field(
        ...,
        description="Unique identifier của vector"
    )

    source: str = Field(
        ...,
        description="Nguồn gốc của vector: who, apa, user_chat, survey, burnout_result"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm tạo vector"
    )

    embedding_model: Optional[str] = Field(
        default=None,
        description="Model dùng để tạo embedding: text-embedding-3-small, BGE-M3, etc."
    )
