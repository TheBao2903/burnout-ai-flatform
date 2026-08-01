"""
==============================================================
File: __init__.py

Chức năng:
- Export tất cả Vector Models ra ngoài package.
- Single source of truth cho tất cả vector models.

Cách sử dụng:
    from app.vector_models import (
        BaseVector,
        KnowledgeVector,
        ChatVector,
        BurnoutVector,
        SearchResult,
    )
==============================================================
"""

from .base_vector import BaseVector
from .knowledge_vector import KnowledgeVector
from .chat_vector import ChatVector
from .burnout_vector import BurnoutVector
from .search_result import (
    SearchResult,
    KnowledgeSearchResult,
    ChatSearchResult,
    BurnoutSearchResult,
)

__all__ = [
    # Base
    "BaseVector",
    # Payload Models
    "KnowledgeVector",
    "ChatVector",
    "BurnoutVector",
    # Result Models
    "SearchResult",
    "KnowledgeSearchResult",
    "ChatSearchResult",
    "BurnoutSearchResult",
]
