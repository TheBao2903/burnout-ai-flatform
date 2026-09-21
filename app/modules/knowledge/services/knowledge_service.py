"""
==============================================================
File: knowledge_service.py

KnowledgeService - RAG cho knowledge base (WHO/APA docs).

Phan biet voi Sprint 18b 'case_memory' (snapshots cua user):
- 'burnout_knowledge': tri thuc tong hop (cu nhieu user).
- 'burnout_case_memory': lich su rieng cua 1 user.

Collection: 'burnout_knowledge', 768 dims cosine.
Fail-soft: Qdrant down / no results -> tra list rong.
==============================================================
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.modules.assessment.services.embedding_service import EmbeddingService
from app.modules.assessment.services.qdrant_service import (
    COLLECTION_NAME as CASE_MEMORY_COLLECTION,  # noqa: F401 - re-export neu can
)

logger = logging.getLogger("burnout.knowledge")

KNOWLEDGE_COLLECTION = "burnout_knowledge"


# ==========================================
# Seed data (tri thuc tong hop WHO/APA/generic)
# ==========================================

KNOWLEDGE_SEED: List[Dict[str, Any]] = [
    {
        "id": "k_who_burnout_2019",
        "source": "who",
        "title": "WHO: Burnout is an occupational phenomenon",
        "content": (
            "WHO phan loai burnout (ICD-11) la hien tuong nghe nghiep, "
            "khong phai benh ly. Dau hieu chinh: (1) kiet suc nang luong "
            "(exhaustion), (2) khoang cach tam ly voi cong viec (cynicism), "
            "(3) hieu qua cong tac giam (inefficacy). Nguyen nhan: qua tai "
            "cong viec, thieu tu chu, khong duoc ghi nhan."
        ),
        "keywords": ["burnout", "who", "definition", "icd-11"],
        "tags": ["burnout", "definition"],
    },
    {
        "id": "k_apa_sleep_2020",
        "source": "apa",
        "title": "APA: Sleep deprivation and emotional regulation",
        "content": (
            "APA cho biet ngu du 7-9 tieng moi dem can thiet de dieu chinh "
            "cam xuc. Ngu < 6 tieng tang 30% nguy co lo au / tram cam. "
            "Thieu ngu lam giam kha nang nhan dien positive emotion, "
            "tang tieu cuc. Loi khuyen: dat lich ngu co dinh, tranh caffeine "
            "sau 14h, phong ngu toi + am thanh thap."
        ),
        "keywords": ["sleep", "apa", "emotion", "regulation"],
        "tags": ["sleep", "emotion"],
    },
    {
        "id": "k_generic_workload_40h",
        "source": "system",
        "title": "Workload: 40-hour week baseline",
        "content": (
            "40 gio / tuan (~8 gio / ngay) la moc baseline lam viec. Tren "
            "50 gio / tuan nguy co burnout tang gap 2-3 lan (Stanford "
            "study). Tren 60 gio / tuan he thong mien dich va stress "
            "hormone tang dot bien. Loi khuyen: chan deadline, phan bo "
            "task, xin ho tro neu qua tai."
        ),
        "keywords": ["workload", "hours", "baseline"],
        "tags": ["workload"],
    },
    {
        "id": "k_generic_coping",
        "source": "system",
        "title": "Stress coping strategies",
        "content": (
            "Chien luoc doi pho stress hieu qua: (1) thiet ke hoat dong "
            "physical (30 phut / ngay), (2) mindfulness / tho nhiep 10 phut, "
            "(3) ket noi xa hoi (noi chuyen voi ban/nguoi than), (4) viet "
            "nhat ky cam xuc. Khong nen dung chat kich thich / ruou bia / "
            "overwork de 'giai toa'."
        ),
        "keywords": ["stress", "coping", "self-care"],
        "tags": ["stress", "self_care"],
    },
    {
        "id": "k_generic_emotion_labeling",
        "source": "system",
        "title": "Emotion labeling reduces intensity",
        "content": (
            "Nghien cuu Lieberman (2007): dat ten cam xuc chinh xac "
            "('affect labeling') giam hoat dong amygdala ~50%. Loi khuyen: "
            "moi ngay ghi 1-2 cau ve cam xuc chinh, khong can phan tich "
            "sau, chi can label: 'toi dang buon', 'toi dang met'."
        ),
        "keywords": ["emotion", "labeling", "amygdala"],
        "tags": ["emotion"],
    },
    {
        "id": "k_who_self_report_stress",
        "source": "who",
        "title": "WHO: Self-reported stress as risk indicator",
        "content": (
            "WHO khuyen nghi self-report stress (thang 1-10 hoac low/medium/"
            "high) la indicator quan trong cho nguy co burnout. Ket hop "
            "voi behavioral data (sleep, workload) cho HINH ANH toan dien. "
            "Neu self-report stress = high keo dai > 2 tuan, nen gap "
            "chuyen gia y te."
        ),
        "keywords": ["stress", "self-report", "who", "indicator"],
        "tags": ["stress", "risk_indicator"],
    },
    {
        "id": "k_generic_recovery",
        "source": "system",
        "title": "Recovery micro-breaks during work",
        "content": (
            "Micro-break moi 50-90 phut lam viec tang productivity 30% "
            "(DeskTime study). Micro-break la nghi 5-10 phut, di lai, "
            "uong nuoc, khong dung man hinh. Nen ap dung Pomodoro (25 phut "
            "lam / 5 phut nghi)."
        ),
        "keywords": ["recovery", "break", "pomodoro", "productivity"],
        "tags": ["workload", "self_care"],
    },
    {
        "id": "k_generic_high_risk_signs",
        "source": "system",
        "title": "Critical: When to seek professional help",
        "content": (
            "Dau hieu CAN GAP CHUYEN GIA Y TE: (1) tu sat / tu lam hai, "
            "(2) mat ngu keo dai > 2 tuan, (3) hoang soang / tan cong hoang "
            "loan, (4) tram cam ro ret, (5) dung chat / ruou qua muc. "
            "KHONG can xau ho khi can ho tro - day la dau hieu binh "
            "thuong cua suc khoe tam than."
        ),
        "keywords": ["help", "professional", "crisis", "suicide"],
        "tags": ["risk_indicator", "high_risk"],
    },
]


# ==========================================
# Service
# ==========================================

class KnowledgeService:
    """Service thao tac knowledge base + RAG search."""

    def __init__(
        self,
        qdrant_service: Any,
        embedding_service: EmbeddingService,
        collection_name: str = KNOWLEDGE_COLLECTION,
    ):
        """
        Args:
            qdrant_service: QdrantService instance.
            embedding_service: EmbeddingService instance (text -> vector).
            collection_name: Qdrant collection (default 'burnout_knowledge').
        """
        self._qdrant = qdrant_service
        self._embedding = embedding_service
        self._collection = collection_name

    @property
    def collection_name(self) -> str:
        return self._collection

    def ensure_collection(self) -> None:
        """Tao collection neu chua co (call Qdrant)."""
        # Reuse Qdrant signature nhung override collection name
        try:
            from qdrant_client.http.models import Distance, VectorParams
            client = self._qdrant._get_client()
            if client is None:
                return
            existing = client.get_collections()
            names = {c.name for c in existing.collections}
            if self._collection not in names:
                client.create_collection(
                    collection_name=self._collection,
                    vectors_config=VectorParams(size=768, distance=Distance.COSINE),
                )
                logger.info("Created Qdrant collection '%s'", self._collection)
            else:
                logger.debug("Qdrant collection '%s' da ton tai", self._collection)
        except Exception as exc:
            logger.warning("ensure_collection '%s' failed: %s", self._collection, exc)

    async def upsert_knowledge(self, doc: Dict[str, Any]) -> Optional[str]:
        """Embed knowledge doc + upsert vao Qdrant.

        Args:
            doc: dict co 'id', 'content' (text se embed), 'source', 'title',
                 'keywords', 'tags' (optional).
        Returns:
            point_id neu thanh cong, None neu fail.
        """
        try:
            # Build text cho embedding (title + content + keywords)
            keywords = doc.get("keywords", [])
            text = (
                f"Title: {doc.get('title', '')}\n"
                f"Source: {doc.get('source', '')}\n"
                f"Content: {doc.get('content', '')}\n"
                f"Keywords: {', '.join(keywords) if keywords else ''}"
            )
            vector = await self._embedding.embed(text)
            return await self._index_vector(doc, vector)
        except Exception as exc:
            logger.warning("upsert_knowledge failed: %s", exc)
            return None

    async def _index_vector(self, doc: Dict[str, Any], vector: List[float]) -> Optional[str]:
        """Helper: chi upsert, fail-soft."""
        try:
            client = self._qdrant._get_client()
            if client is None:
                return None
            from qdrant_client.http.models import PointStruct
            # Point_id: deterministic tu doc.id
            import uuid as _uuid
            point_id = str(_uuid.uuid5(_uuid.NAMESPACE_OID, doc["id"]))
            payload = {
                "knowledge_id": doc["id"],
                "source": doc.get("source"),
                "title": doc.get("title"),
                "content": doc.get("content"),
                "keywords": doc.get("keywords", []),
                "tags": doc.get("tags", []),
                "created_at": datetime.utcnow().isoformat() + "Z",
            }
            client.upsert(
                collection_name=self._collection,
                points=[PointStruct(id=point_id, vector=vector, payload=payload)],
            )
            return point_id
        except Exception as exc:
            logger.warning("Knowledge index upsert failed: %s", exc)
            return None

    async def search(
        self,
        query_text: str,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Search top-K knowledge docs gan voi query.

        Args:
            query_text: text query (thuong la emotion JSON + context).
            top_k: so docs tra ve (default 3).

        Returns:
            list[dict] payloads (empty list neu fail hoac khong co).
        """
        try:
            vector = await self._embedding.embed(query_text)
        except Exception as exc:
            logger.warning("Knowledge search: embed failed: %s", exc)
            return []

        try:
            client = self._qdrant._get_client()
            if client is None:
                return []
            from qdrant_client.http import models
            results = client.search(
                collection_name=self._collection,
                query_vector=vector,
                limit=top_k,
                with_payload=True,
            )
            return [hit.payload for hit in results]
        except Exception as exc:
            logger.warning("Knowledge search failed: %s", exc)
            return []

    async def seed_all(self) -> Tuple[int, int]:
        """Seed toan bo KNOWLEDGE_SEED vao Qdrant.

        Returns:
            (success_count, fail_count).
        """
        self.ensure_collection()
        ok, fail = 0, 0
        for doc in KNOWLEDGE_SEED:
            pid = await self.upsert_knowledge(doc)
            if pid:
                ok += 1
            else:
                fail += 1
        logger.info("Knowledge seed: %d ok, %d fail", ok, fail)
        return (ok, fail)


# ==========================================
# Singleton
# ==========================================

_knowledge_service: Optional[KnowledgeService] = None


def get_knowledge_service() -> KnowledgeService:
    """Lazy singleton."""
    global _knowledge_service
    if _knowledge_service is None:
        from app.modules.assessment.services.embedding_service import (
            get_embedding_service,
        )
        from app.modules.assessment.services.qdrant_service import (
            get_qdrant_service,
        )
        _knowledge_service = KnowledgeService(
            qdrant_service=get_qdrant_service(),
            embedding_service=get_embedding_service(),
        )
    return _knowledge_service