"""
Dashboard Module - API endpoints for Dashboard.
"""

from app.modules.dashboard.routes.dashboard import router as dashboard_router
from app.modules.dashboard.routes.admin_dashboard import router as admin_dashboard_router

__all__ = ["dashboard_router", "admin_dashboard_router"]
