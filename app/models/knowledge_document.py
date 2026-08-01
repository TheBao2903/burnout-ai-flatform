"""
==============================================================
File: knowledge_document.py

Chức năng:
- Định nghĩa KnowledgeDocument - tri thức đã được chuẩn hóa.
- Dùng cho Knowledge Pipeline: Insight → Knowledge → Embedding → Qdrant.

Đặc điểm:
- Không chứa vector thực tế.
- Sau khi tạo KnowledgeDocument, sẽ được chuyển thành EmbeddingDocument.
- EmbeddingDocument được gửi sang Embedding Model để sinh vector.

Được sử dụng tại:
- Burnout Engine (tạo Knowledge từ Insight)
- Knowledge Service (quản lý knowledge)
- RAG Service (truy vấn knowledge)

Luồng dữ liệu:
BurnoutEngineOutput
      ↓
InsightResult
      ↓
KnowledgeDocument ──→ EmbeddingDocument ──→ Vector
      ↓                       ↓
  Qdrant (metadata)    Embedding Model
==============================================================
"""

from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict


class KnowledgeDocument(BaseModel):
    """
    Domain Model cho tri thức đã được chuẩn hóa.

    Có thể được tạo từ:
    - WHO Guidelines
    - APA Articles
    - User Session Insights
    - Research Papers
    - Recommendations

    Sau đó được:
    1. Chuyển thành EmbeddingDocument
    2. Gửi sang Embedding Model
    3. Index vào Qdrant
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "know_001",
                "source": "user_session",
                "document_type": "burnout_case",
                "title": "Case Study: Sleep Deprivation and High Workload",
                "content": "Người dùng ngủ 4-5 tiếng/đêm, làm việc 11-12 tiếng/ngày, OT thường xuyên. Có dấu hiệu burnout ở mức cao...",
                "keywords": ["sleep deprivation", "high workload", "overtime", "burnout"],
                "tags": ["sleep", "workload", "burnout", "case_study"],
                "language": "vi",
                "created_at": "2024-01-20T10:15:00Z"
            }
        }
    )

    id: str = Field(
        ...,
        description="Unique identifier của knowledge document"
    )

    source: Literal["who", "apa", "user_session", "research_paper", "recommendation", "system"] = Field(
        ...,
        description="Nguồn gốc của document"
    )

    document_type: Literal["burnout_case", "knowledge", "recommendation", "guideline", "research"] = Field(
        ...,
        description="Loại document"
    )

    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Tiêu đề của document"
    )

    content: str = Field(
        ...,
        min_length=1,
        description="Nội dung chính của document (để tạo embedding)"
    )

    keywords: List[str] = Field(
        default_factory=list,
        description="Từ khóa quan trọng"
    )

    tags: List[str] = Field(
        default_factory=list,
        description="Tags để phân loại và filter"
    )

    language: str = Field(
        default="vi",
        description="Ngôn ngữ của document: vi, en"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm tạo document"
    )
