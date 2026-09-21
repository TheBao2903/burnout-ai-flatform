"""
Services package for Report module.
"""

from app.modules.report.services.report_service import (
    ReportService,
    get_report_service,
)

__all__ = ["ReportService", "get_report_service"]
