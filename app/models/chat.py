"""
==============================================================
File: chat.py

Chức năng:
- Định nghĩa ChatMessage - đại diện cho một tin nhắn trong hội thoại.
- Định nghĩa ChatResult - lưu toàn bộ cuộc hội thoại của MỘT Session.

Đặc điểm:
- Mỗi Session chỉ có MỘT ChatResult.
- ChatResult lưu toàn bộ messages (User + Assistant).
- Sau khi Session kết thúc, GPT đọc messages → sinh summary, keywords, stress_level, burnout_signal.

Được sử dụng tại:
- Chat Interface (lưu tin nhắn)
- OpenAI Integration (sinh phân tích sau session)
- Burnout Engine (lấy signals để tính score)

Luồng dữ liệu:
Session Start
      ↓
Chat Interface → ChatMessage (User) → ChatMessage (Assistant) → ...
      ↓
Session End
      ↓
GPT Analysis → ChatResult (summary, keywords, stress_level, burnout_signal)
      ↓
Burnout Engine → BurnoutResult
==============================================================
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class ChatMessage(BaseModel):
    """
    Domain Model cho một tin nhắn trong cuộc hội thoại.

    Đại diện cho một message đơn lẻ (User hoặc Assistant).
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "role": "user",
                "content": "Em mệt quá, không biết sao mà luôn căng thẳng.",
                "created_at": "2024-01-20T10:05:00Z"
            }
        }
    )

    role: Literal["user", "assistant"] = Field(
        ...,
        description="Vai trò của người gửi: user hoặc assistant"
    )

    content: str = Field(
        ...,
        min_length=1,
        description="Nội dung tin nhắn"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm gửi tin nhắn"
    )


class ChatResult(BaseModel):
    """
    Domain Model cho kết quả phân tích chat của MỘT Session.

    Lưu toàn bộ cuộc hội thoại và kết quả phân tích của GPT.
    Mỗi Session chỉ có một ChatResult duy nhất.

    Ví dụ cuộc hội thoại:
    - User: "Em mệt."
    - Assistant: "Bạn ngủ bao nhiêu tiếng?"
    - User: "Khoảng 4 tiếng."
    - Assistant: "Bạn có làm thêm giờ không?"
    - User: "Có, suốt tuần luôn."
    - ...

    Sau Session kết thúc, GPT đọc toàn bộ messages và sinh:
    - summary: Tóm tắt cuộc hội thoại
    - keywords: Từ khóa quan trọng
    - stress_level: Mức độ stress
    - burnout_signal: Tín hiệu burnout
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "session_id": "session_abc123",
                "messages": [
                    {
                        "role": "user",
                        "content": "Em mệt quá",
                        "created_at": "2024-01-20T10:05:00Z"
                    },
                    {
                        "role": "assistant",
                        "content": "Bạn ơi, bạn có muốn chia sẻ thêm không?",
                        "created_at": "2024-01-20T10:05:05Z"
                    },
                    {
                        "role": "user",
                        "content": "Công việc nhiều quá, ngủ không đủ giấc.",
                        "created_at": "2024-01-20T10:05:30Z"
                    }
                ],
                "summary": "Người dùng đang bày tỏ sự mệt mỏi do công việc quá nhiều và ngủ không đủ giấc. Có dấu hiệu stress và burnout ở mức độ trung bình.",
                "keywords": ["mệt", "công việc nhiều", "ngủ không đủ", "áp lực"],
                "stress_level": "medium",
                "burnout_signal": "medium",
                "analyzed_at": "2024-01-20T10:15:00Z"
            }
        }
    )

    session_id: str = Field(
        ...,
        description="ID của session chứa cuộc hội thoại này"
    )

    messages: List[ChatMessage] = Field(
        default_factory=list,
        description="Danh sách toàn bộ tin nhắn trong cuộc hội thoại"
    )

    summary: str = Field(
        ...,
        description="Tóm tắt cuộc hội thoại do GPT sinh"
    )

    keywords: List[str] = Field(
        default_factory=list,
        description="Các từ khóa quan trọng được trích xuất từ cuộc hội thoại"
    )

    stress_level: Literal["low", "medium", "high"] = Field(
        ...,
        description="Mức độ stress được đánh giá từ cuộc hội thoại"
    )

    burnout_signal: Literal["none", "low", "medium", "high"] = Field(
        ...,
        description="Tín hiệu burnout được phát hiện từ cuộc hội thoại"
    )

    analyzed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm GPT phân tích và sinh kết quả"
    )
