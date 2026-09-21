"""Re-export storage services."""

from app.modules.storage.services.r2_service import R2Service, get_r2_service

__all__ = ["R2Service", "get_r2_service"]