"""
==============================================================
File: search_result.py

Chức năng:
- Model trả về sau khi Qdrant Search.
- Chứa kết quả search bao gồm id, score, và payload.

Đặc điểm:
- Đây là model dùng chung cho mọi loại search.
- Payload có thể là KnowledgeVector, ChatVector, hoặc BurnoutVector.
- Score thể hiện độ tương đồng (0-1).

Được sử dụng tại:
- Qdrant Service (trả kết quả search)
- RAG Service (parse kết quả)
- Similarity Search (lấy results)

Moved from app/ai_models/search_result.py (Sprint 18b refactor).
==============================================================
"""

from typing import Any, Generic, TypeVar, Optional

from pydantic import BaseModel, Field, ConfigDict


T = TypeVar("T")


class SearchResult(BaseModel, Generic[T]):
    """
    Generic Model cho kết quả search từ Qdrant.

    Dùng chung cho mọi loại vector search.
    Payload type T có thể là KnowledgeVector, ChatVector, hoặc BurnoutVector.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "know_who_burnout_001",
                "score": 0.8923,
                "payload": {
                    "id": "know_who_burnout_001",
                    "title": "WHO Guidelines on Burnout",
                    "category": "burnout",
                    "content": "Burnout is an occupational phenomenon..."
                }
            }
        }
    )

    id: str = Field(
        ...,
        description="ID của vector được tìm thấy"
    )

    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Điểm similarity (0-1). Cao hơn = tương đồng hơn."
    )

    payload: T = Field(
        ...,
        description="Payload chứa metadata của vector"
    )


class KnowledgeSearchResult(SearchResult):
    """
    Specialized SearchResult cho Knowledge Vector.

    Payload sẽ là KnowledgeVector.
    """

    pass


class ChatSearchResult(SearchResult):
    """
    Specialized SearchResult cho Chat Vector.

    Payload sẽ là ChatVector.
    """

    pass


class BurnoutSearchResult(SearchResult):
    """
    Specialized SearchResult cho Burnout Vector.

    Payload sẽ là BurnoutVector.
    """

    pass