"""
==============================================================
File: chat_vector.py

Chức năng:
- Model lưu metadata của Chat để Semantic Search trong Qdrant.
- Dùng để tìm những cuộc hội thoại tương tự.

Đặc điểm:
- Không lưu toàn bộ messages (chỉ lưu đoạn text đã chuẩn hóa).
- Content là đoạn text để tạo Embedding.
- Dùng để AI tìm hội thoại tương tự trong quá khứ.

Được sử dụng tại:
- Chat Service (index chat sau khi session kết thúc)
- Similarity Search (tìm hội thoại tương tự)
- RAG Service (lấy context từ chat cũ)

Moved from app/ai_models/chat_vector.py (Sprint 18b refactor).
==============================================================
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict

from app.modules.knowledge.models.base_vector import BaseVector


class ChatVector(BaseVector):
    """
    Model lưu metadata của Chat trong Qdrant.

    Ví dụ:
    - User chat về việc ngủ không đủ giấc
    - User chat về deadline quá nhiều
    - User chat về mệt mỏi với công việc

    Lưu ý:
    - Không lưu toàn bộ messages list
    - Chỉ lưu content đã được chuẩn hóa
    - Summary và keywords dùng làm metadata để filter
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "chat_vec_user123_session001",
                "source": "user_chat",
                "session_id": "session_abc123",
                "user_id": "user_123",
                "content": "Em mệt quá, công việc nhiều, ngủ không đủ giấc, deadline chồng chất...",
                "summary": "Người dùng chia sẻ về tình trạng mệt mỏi do công việc và thiếu ngủ",
                "keywords": ["mệt", "công việc", "ngủ", "deadline", "stress"],
                "stress_level": "medium",
                "burnout_signal": "medium",
                "created_at": "2024-01-20T10:15:00Z",
                "embedding_model": "text-embedding-004"
            }
        }
    )

    session_id: str = Field(
        ...,
        description="ID của session chứa cuộc hội thoại"
    )

    user_id: str = Field(
        ...,
        description="ID của user thực hiện cuộc hội thoại"
    )

    content: str = Field(
        ...,
        description="Đoạn text đã được chuẩn hóa từ cuộc hội thoại để tạo embedding"
    )

    summary: str = Field(
        ...,
        description="Tóm tắt nội dung cuộc hội thoại"
    )

    keywords: List[str] = Field(
        default_factory=list,
        description="Từ khóa quan trọng từ cuộc hội thoại"
    )

    stress_level: Literal["low", "medium", "high"] = Field(
        ...,
        description="Mức độ stress được đánh giá từ cuộc hội thoại"
    )

    burnout_signal: Literal["none", "low", "medium", "high"] = Field(
        ...,
        description="Tín hiệu burnout được phát hiện từ cuộc hội thoại"
    )