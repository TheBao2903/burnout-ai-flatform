"""
==============================================================
Module: Timeline

Chuc nang:
- Timeline aggregation cho dashboard (theo ngay).
- Routes: GET /api/timeline?days=N
==============================================================
"""

from app.modules.timeline.routes import router

__all__ = ["router"]
