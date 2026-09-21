"""
==============================================================
File: embedding_service.py

EmbeddingService - Sinh vector embedding tu Google AI Studio
(text-embedding-004, 768 dims) de luu vao Qdrant.

Fallback: khi API key rong -> EmbeddingUnavailableError
(caller skip dual-write, app tiep tuc binh thuong).

Retry: 3 lan, exponential backoff (tenacity).

Singleton qua get_embedding_service().
==============================================================
"""

import asyncio
import logging
from typing import Any, List, Optional

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.settings import get_settings
from app.modules.emotion.models.emotion import EmotionResult

logger = logging.getLogger("burnout.embedding")


# ==========================================
# Errors
# ==========================================

class EmbeddingUnavailableError(RuntimeError):
    """Raised khi embedding khong kha dung (key rong / init fail).

    Caller catch exception nay de skip dual-write vao Qdrant,
    app van tiep tuc tra response binh thuong.
    """


# ==========================================
# Service
# ==========================================

class EmbeddingService:
    """Service sinh embedding vector tu text (Google text-embedding-004)."""

    def __init__(self, client_factory=None):
        """
        Args:
            client_factory: Optional callable() -> google.genai.Client (cho test mock).
        """
        self._client = None
        self._client_factory = client_factory

    def _get_client(self):
        """Lazy init Google GenAI client (mirror ai_service.py pattern)."""
        if self._client is not None:
            return self._client

        settings = get_settings().google_ai_embed
        if not settings.api_key:
            logger.warning("GOOGLE_API_KEY rong -> Embedding skip.")
            return None

        if self._client_factory is not None:
            self._client = self._client_factory()
            return self._client

        try:
            from google import genai
            self._client = genai.Client(api_key=settings.api_key)
            logger.info(
                "Google GenAI embed client initialized (model=%s, dim=%d)",
                settings.model, settings.output_dimensionality,
            )
            return self._client
        except Exception as exc:
            logger.exception("Google GenAI embed init failed: %s", exc)
            return None

    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def embed(self, text: str) -> List[float]:
        """Embed text -> List[float] (768 dims).

        Raises:
            EmbeddingUnavailableError: khi API key rong hoac client init fail.
            Exception: cac loi khac (sau 3 lan retry).
        """
        client = self._get_client()
        if client is None:
            raise EmbeddingUnavailableError("Google GenAI embed client not available")

        settings = get_settings().google_ai_embed

        def _sync_call():
            # Import types ben trong de tranh import cycle neu co
            from google.genai import types
            resp = client.models.embed_content(
                model=settings.model,
                contents=text,
                config=types.EmbedContentConfig(
                    output_dimensionality=settings.output_dimensionality,
                    # RETRIEVAL_DOCUMENT: dung khi index vao vector DB
                    # Sprint 19 (RAG search) se dung RETRIEVAL_QUERY
                    task_type="RETRIEVAL_DOCUMENT",
                ),
            )
            return list(resp.embeddings[0].values)

        return await asyncio.to_thread(_sync_call)

    async def embed_emotion_snapshot(self, emotion: EmotionResult) -> List[float]:
        """Embed emotion snapshot (deterministic text, khong PII).

        Text format (KHONG chua image_url / analyzed_at / user_id):
            Emotion: <dominant_emotion> (confidence=<conf>)
            Scores: happy=<h> sad=<s> neutral=<n> fear=<f> angry=<a> surprise=<su> disgust=<d>
        """
        emotions = emotion.emotions.model_dump()
        text = (
            f"Emotion: {emotion.dominant_emotion} (confidence={emotion.confidence:.4f})\n"
            f"Scores: "
            f"happy={emotions.get('happy', 0):.2f} "
            f"sad={emotions.get('sad', 0):.2f} "
            f"neutral={emotions.get('neutral', 0):.2f} "
            f"fear={emotions.get('fear', 0):.2f} "
            f"angry={emotions.get('angry', 0):.2f} "
            f"surprise={emotions.get('surprise', 0):.2f} "
            f"disgust={emotions.get('disgust', 0):.2f}"
        )
        return await self.embed(text)


# ==========================================
# Singleton
# ==========================================

_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Lay EmbeddingService singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
