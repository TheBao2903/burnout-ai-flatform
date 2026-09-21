"""
==============================================================
File: __init__.py

Core models package - chua cac model dung chung cho toan he thong
(SearchResult, ...).
==============================================================
"""

from app.core.models.search_result import (
    SearchResult,
    KnowledgeSearchResult,
    ChatSearchResult,
    BurnoutSearchResult,
)

__all__ = [
    "SearchResult",
    "KnowledgeSearchResult",
    "ChatSearchResult",
    "BurnoutSearchResult",
]
