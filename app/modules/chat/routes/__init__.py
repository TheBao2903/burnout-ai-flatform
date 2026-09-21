"""
Chat Routes - API endpoints for chat module.
"""

from app.modules.chat.routes.chat_history import router as chat_history_router

__all__ = ["chat_history_router"]
