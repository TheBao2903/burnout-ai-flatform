"""Recommendation routes."""
from app.modules.recommendation.routes.recommendation import (
    router,
    user_profile_router,
    weather_router,
)

__all__ = [
    "router",
    "user_profile_router",
    "weather_router",
]
