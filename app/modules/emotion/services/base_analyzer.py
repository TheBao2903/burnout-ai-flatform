"""
==============================================================
File: base_analyzer.py

BaseEmotionAnalyzer - Abstract interface cho emotion analyzer.

De dang thay the analyzer khac (MediaPipe, InsightFace, FER+,
OpenFace, ...) chi can viet class moi implement BaseEmotionAnalyzer
va truyen vao EmotionService qua constructor.
==============================================================
"""

from abc import ABC, abstractmethod

from app.modules.emotion.models.emotion import EmotionResult


class EmotionAnalysisError(Exception):
    """Exception khi analyzer gap loi."""
    pass


class BaseEmotionAnalyzer(ABC):
    """Interface cho emotion analyzer."""

    @abstractmethod
    def analyze(self, image_bytes: bytes) -> EmotionResult:
        """
        Phan tich anh va tra EmotionResult.

        Args:
            image_bytes: Anh dau vao (jpg/png/webp).

        Returns:
            EmotionResult. Neu khong nhan dien duoc, tra EmotionResult
            voi dominant_emotion="Unknown" va confidence=0.0.
        """
        raise NotImplementedError