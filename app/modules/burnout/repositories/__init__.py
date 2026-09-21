"""
Repositories package for Burnout module.
"""

from app.modules.burnout.repositories.burnout_repository import (
    BurnoutRepository,
    get_burnout_repository,
)

__all__ = ["BurnoutRepository", "get_burnout_repository"]
