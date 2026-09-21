"""
==============================================================
File: qdrant_service.py

QdrantService - Upsert + search emotion snapshots vao Qdrant
(collection 'burnout_case_memory', 768 dims cosine).

Dung cho Sprint 18b (index emotion snapshots) va Sprint 19
(RAG: top-K similar snapshots cho assessment prompt).

Fail-soft: Qdrant down / unreachable -> log warning, return
empty, app tiep tuc binh thuong.

Singleton qua get_qdrant_service().
==============================================================
"""

import logging
import uuid
from datetime import datetime
from typing import Any, List, Optional

from app.core.settings import get_settings

logger = logging.getLogger("burnout.qdrant")


# ==========================================
# Constants
# ==========================================

# Collection name - khoi tao 1 lan, sau do dung mac dinh trong settings
COLLECTION_NAME = "burnout_case_memory"


# ==========================================
# Errors (for soft-fail visibility only)
# ==========================================

class QdrantUnavailableError(RuntimeError):
    """Internal marker; thuong khong raise - chi log warning."""


# ==========================================
# Service
# ==========================================

class QdrantService:
    """Service thao tac voi Qdrant vector DB."""

    def __init__(self, client_factory=None):
        """
        Args:
            client_factory: Optional callable() -> qdrant_client.QdrantClient (cho test mock).
        """
        self._client = None
        self._client_factory = client_factory
        # Track flag: collection created (tranh get_collections() nhieu lan)
        self._collection_ensured = False

    def _get_client(self):
        """Lazy init QdrantClient (fail-soft: log + return None)."""
        if self._client is not None:
            return self._client

        if self._client_factory is not None:
            self._client = self._client_factory()
            return self._client

        try:
            from qdrant_client import QdrantClient
            s = get_settings().qdrant
            self._client = QdrantClient(
                host=s.host,
                port=s.port,
                api_key=s.api_key or None,  # None neu self-host khong auth
                timeout=s.timeout_seconds,
            )
            logger.info("Qdrant client initialized (host=%s, port=%d)", s.host, s.port)
            return self._client
        except Exception as exc:
            logger.warning("Qdrant client init failed: %s", exc)
            self._client = None
            return None

    def _ensure_collection(self) -> None:
        """Tao collection neu chua co. Idempotent."""
        client = self._get_client()
        if client is None:
            return
        if self._collection_ensured:
            return
        try:
            from qdrant_client.http.models import Distance, VectorParams
            s = get_settings().qdrant
            collection_name = s.collection_name or COLLECTION_NAME

            existing = client.get_collections()
            existing_names = {c.name for c in existing.collections}
            if collection_name not in existing_names:
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=s.vector_size,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info("Created Qdrant collection '%s'", collection_name)
            else:
                logger.debug("Qdrant collection '%s' da ton tai", collection_name)
            self._collection_ensured = True
        except Exception as exc:
            logger.warning("Qdrant ensure_collection failed: %s", exc)

    def upsert_emotion_snapshot(
        self,
        user_id: str,
        emotion_id: str,
        vector: List[float],
        snapshot: dict,
        risk_level: str,
        generated_at: datetime,
    ) -> Optional[str]:
        """Upsert 1 emotion snapshot vao collection.

        Args:
            user_id: Firebase uid.
            emotion_id: Firestore emotion doc id (dung lam FK + UUID5).
            vector: list[float] 768 dim.
            snapshot: dict (emotions, dominant, confidence, age, gender).
            risk_level: "low" | "medium" | "high" | "unknown".
            generated_at: datetime UTC.

        Returns:
            point_id (UUID5 string) neu thanh cong, None neu fail.

        Fail-soft: exception -> log warning, return None.
        """
        client = self._get_client()
        if client is None:
            return None

        try:
            from qdrant_client.http.models import PointStruct
            s = get_settings().qdrant
            collection_name = s.collection_name or COLLECTION_NAME

            # UUID5 deterministic tu emotion_id -> idempotent khi retry
            point_id = str(uuid.uuid5(uuid.NAMESPACE_OID, emotion_id))

            payload = {
                "user_id": user_id,
                "emotion_id": emotion_id,
                "dominant_emotion": snapshot.get("dominant_emotion"),
                "confidence": snapshot.get("confidence"),
                "risk_level": risk_level,
                "emotions": snapshot.get("emotions", {}) or {},
                "age": snapshot.get("age"),
                "gender": snapshot.get("gender"),
                "embedding_model": get_settings().google_ai_embed.model,
                "created_at": generated_at.isoformat() + "Z",
            }

            client.upsert(
                collection_name=collection_name,
                points=[PointStruct(id=point_id, vector=vector, payload=payload)],
            )
            logger.info(
                "Upserted Qdrant point %s for emotion %s (user=%s, risk=%s)",
                point_id, emotion_id, user_id, risk_level,
            )
            return point_id
        except Exception as exc:
            logger.warning("Qdrant upsert failed (tiep tuc): %s", exc)
            return None

    def search_similar(
        self,
        user_id: str,
        query_vector: List[float],
        top_k: int = 5,
    ) -> List[dict]:
        """Top-K similar emotion snapshots cho user (RAG, Sprint 19).

        Args:
            user_id: filter theo user (payload FieldCondition).
            query_vector: vector 768 dim.
            top_k: so luong snapshot tra ve.

        Returns:
            list[dict] payloads (empty list neu fail).
        """
        client = self._get_client()
        if client is None:
            return []

        try:
            from qdrant_client.http import models
            s = get_settings().qdrant
            collection_name = s.collection_name or COLLECTION_NAME

            results = client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=models.Filter(must=[
                    models.FieldCondition(
                        key="user_id",
                        match=models.MatchValue(value=user_id),
                    )
                ]),
                limit=top_k,
                with_payload=True,
            )
            return [hit.payload for hit in results]
        except Exception as exc:
            logger.warning("Qdrant search failed (tra list rong): %s", exc)
            return []


# ==========================================
# Singleton
# ==========================================

_qdrant_service: Optional[QdrantService] = None


def get_qdrant_service() -> QdrantService:
    """Lay QdrantService singleton."""
    global _qdrant_service
    if _qdrant_service is None:
        _qdrant_service = QdrantService()
    return _qdrant_service
