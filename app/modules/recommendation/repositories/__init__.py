"""Recommendation repositories."""
from app.modules.recommendation.repositories.recommendation_repository import (
    RecommendationHistoryRepository,
    RecommendationInteractionRepository,
    UserRecommendationProfileRepository,
    PlaceInteractionRepository,
    get_recommendation_history_repository,
    get_recommendation_interaction_repository,
    get_user_recommendation_profile_repository,
    get_place_interaction_repository,
)

__all__ = [
    "RecommendationHistoryRepository",
    "RecommendationInteractionRepository",
    "UserRecommendationProfileRepository",
    "PlaceInteractionRepository",
    "get_recommendation_history_repository",
    "get_recommendation_interaction_repository",
    "get_user_recommendation_profile_repository",
    "get_place_interaction_repository",
]
