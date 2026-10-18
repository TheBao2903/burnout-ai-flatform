"""
==============================================================
File: burnout_service.py

BurnoutService - Orchestrator: validate input, goi engine, save Firestore.
KHONG sua algorithm - chi la wrapper cho BurnoutEngine.
Sprint 22: wire recommendation engine.
==============================================================
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.modules.burnout.models.burnout import (
    BurnoutEngineOutput,
    BurnoutEngineInput,
    BurnoutInput,
)
from app.modules.burnout.services.burnout_engine import BurnoutEngine
from app.modules.burnout.repositories.burnout_repository import BurnoutRepository
from app.modules.recommendation.models.recommendation import Recommendation

logger = logging.getLogger("burnout.service")


class BurnoutService:
    """Orchestrator cho BurnoutEngine."""

    def __init__(
        self,
        engine: BurnoutEngine,
        repository: Optional[BurnoutRepository] = None,
        recommendation_engine: Optional[Any] = None,
    ):
        """
        Args:
            engine: BurnoutEngine instance.
            repository: optional BurnoutRepository (de save Firestore).
            recommendation_engine: optional RecommendationEngine (Sprint 22).
        """
        self._engine = engine
        self._repository = repository
        self._recommendation_engine = recommendation_engine

    async def analyze_and_save(
        self,
        user_id: str,
        input_data: BurnoutEngineInput,
        emotion_id: Optional[str] = None,
    ) -> BurnoutEngineOutput:
        """Chay engine + save Firestore (best-effort, fail-soft).

        Args:
            user_id: Firebase uid.
            input_data: BurnoutEngineInput.
            emotion_id: optional FK emotion doc.

        Returns:
            BurnoutEngineOutput (same as engine.analyze).
        """
        # Engine la pure function, chay sync (khong can to_thread)
        output = self._engine.analyze(input_data)

        # Save Firestore (best-effort)
        if self._repository is not None:
            try:
                await asyncio.to_thread(
                    self._repository.save,
                    user_id=user_id,
                    output=output,
                    emotion_id=emotion_id,
                )
            except Exception as exc:
                logger.warning(
                    "Save burnout to Firestore failed (tiep tuc tra response): %s",
                    exc,
                )
        return output

    def get_recommendations(
        self,
        burnout: BurnoutEngineOutput,
        emotion: Optional[Any] = None,
    ) -> List[Recommendation]:
        """Sinh Recommendations tu BurnoutEngineOutput (sync, optional RAG).

        Args:
            burnout: BurnoutEngineOutput.
            emotion: optional EmotionResult (de build RAG query text).

        Returns:
            list[Recommendation] (empty neu fail).
        """
        if self._recommendation_engine is None:
            return []
        try:
            rag_query = None
            if emotion is not None and hasattr(
                self._recommendation_engine, "_build_emotion_rag_query"
            ):
                try:
                    rag_query = (
                        self._recommendation_engine._build_emotion_rag_query(emotion)
                    )
                except Exception:
                    rag_query = None
            return self._recommendation_engine.generate(
                burnout.burnout, rag_query_text=rag_query,
            )
        except Exception as exc:
            logger.warning("Generate recommendations failed: %s", exc)
            return []

    async def get_recommendations_async(
        self,
        burnout: BurnoutEngineOutput,
        emotion: Optional[Any] = None,
    ) -> List[Recommendation]:
        """Async version: rule-based + RAG-driven (Sprint 27)."""
        if self._recommendation_engine is None:
            return []
        if not hasattr(self._recommendation_engine, "generate_async"):
            return self.get_recommendations(burnout, emotion)
        try:
            return await self._recommendation_engine.generate_async(
                burnout.burnout, emotion=emotion,
            )
        except Exception as exc:
            logger.warning("Async generate recommendations failed: %s", exc)
            return self.get_recommendations(burnout, emotion)

    def get_latest(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Lay burnout result moi nhat cua user (sync)."""
        if self._repository is None:
            return None
        try:
            results = self._repository.list_by_user(
                user_id=user_id, latest_only=True,
            )
            return results[0] if results else None
        except Exception as exc:
            logger.warning("Get latest burnout failed: %s", exc)
            return None

    def get_history(self, user_id: str, limit: int = 20) -> list:
        """Lay lich su burnout cua user (sync)."""
        if self._repository is None:
            return []
        try:
            return self._repository.list_by_user(
                user_id=user_id, limit=limit, latest_only=False,
            )
        except Exception as exc:
            logger.warning("Get burnout history failed: %s", exc)
            return []


# ==========================================
# Singleton
# ==========================================

_burnout_service: Optional[BurnoutService] = None


def get_burnout_service() -> BurnoutService:
    """Lay BurnoutService singleton.

    Lazy import repository de tranh import cycle.
    Sprint 22: wire recommendation engine.
    """
    global _burnout_service
    if _burnout_service is None:
        from app.modules.burnout.repositories.burnout_repository import (
            get_burnout_repository,
        )
        from app.modules.burnout.services.burnout_engine import get_burnout_engine
        try:
            from app.modules.recommendation.services import (
                get_recommendation_engine,
            )
            rec_engine = get_recommendation_engine()
        except Exception:
            rec_engine = None
        _burnout_service = BurnoutService(
            engine=get_burnout_engine(),
            repository=get_burnout_repository(),
            recommendation_engine=rec_engine,
        )
    return _burnout_service
