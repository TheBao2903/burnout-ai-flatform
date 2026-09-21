"""
Services package for Burnout module.
"""

from app.modules.burnout.services.burnout_engine import (
    BurnoutEngine,
    get_burnout_engine,
)

__all__ = ["BurnoutEngine", "get_burnout_engine"]


def __getattr__(name):
    """Lazy import cho BurnoutService (tranh import cycle voi repository)."""
    if name == "BurnoutService":
        from app.modules.burnout.services.burnout_service import BurnoutService
        return BurnoutService
    if name == "get_burnout_service":
        from app.modules.burnout.services.burnout_service import (
            get_burnout_service,
        )
        return get_burnout_service
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
