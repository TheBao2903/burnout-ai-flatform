"""
Chat Repositories - Database access layer for chat module.
"""

from app.modules.chat.repositories.chat_history_repository import (
    ChatHistoryRepository,
    get_chat_history_repository,
)

__all__ = [
    "ChatHistoryRepository",
    "get_chat_history_repository",
]
