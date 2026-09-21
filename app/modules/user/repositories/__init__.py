"""
Repositories package for User module.
"""

from app.modules.user.repositories.user_profile_repository import UserProfileRepository, get_profile_repository

__all__ = ["UserProfileRepository", "get_profile_repository"]
