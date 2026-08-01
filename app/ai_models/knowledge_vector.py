"""
==============================================================
File: knowledge_vector.py

Chức năng:
- Model lưu metadata của tài liệu Burnout trong Qdrant.
- Dùng để semantic search tài liệu kiến thức.

Đặc điểm:
- Không lưu vector thực tế (vector do OpenAI Embedding sinh).
- Chỉ mô tả payload đi kèm vector.
- Dùng cho RAG (Retrieval Augmented Generation).

Được sử dụng tại:
- Knowledge Base Service (index tài liệu vào Qdrant)
- RAG Service (search tài liệu liên quan)
- AI Assistant (lấy context cho GPT)
==============================================================
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict

from .base_vector import BaseVector


class KnowledgeVector(BaseVector):
    """
    Model lưu metadata của tài liệu Burnout trong Qdrant.

    Ví dụ:
    - WHO Guidelines về Burnout
    - APA Articles về Stress Management
    - Papers về Sleep Hygiene
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "know_who_burnout_001",
                "source": "who",
                "knowledge_id": "KB-001",
                "title": "WHO Guidelines on Burnout",
                "category": "burnout",
                "content": "Burnout is an occupational phenomenon... classified in ICD-11 as a factor influencing health status...",
                "tags": ["burnout", "who", "occupational", "health"],
                "language": "en",
                "reference": "WHO - International Classification of Diseases 11th Revision",
                "created_at": "2024-01-15T10:00:00Z",
                "embedding_model": "text-embedding-3-small"
            }
        }
    )

    knowledge_id: str = Field(
        ...,
        description="ID của tài liệu trong Knowledge Base"
    )

    title: str = Field(
        ...,
        description="Tiêu đề tài liệu"
    )

    category: str = Field(
        ...,
        description="Danh mục: burnout, stress, sleep, mental_health, work_life, coping"
    )

    content: str = Field(
        ...,
        description="Nội dung tài liệu đã được trích xuất để tạo embedding"
    )

    tags: List[str] = Field(
        default_factory=list,
        description="Tags liên quan đến tài liệu"
    )

    language: str = Field(
        default="en",
        description="Ngôn ngữ của tài liệu: en, vi, etc."
    )

    reference: Optional[str] = Field(
        default=None,
        description="Nguồn tham khảo: WHO, APA, Paper name, etc."
    )
