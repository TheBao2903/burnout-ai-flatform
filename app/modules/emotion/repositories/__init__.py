"""Emotion repositories."""

from app.modules.emotion.repositories.emotion_repository import (
    EmotionRepository,
    get_emotion_repository,
)

__all__ = ["EmotionRepository", "get_emotion_repository"]