"""
==============================================================
Module: Report

Chuc nang:
- Monthly report aggregation.
- Routes: GET /api/report?month=YYYY-MM
==============================================================
"""

from app.modules.report.routes import router

__all__ = ["router"]