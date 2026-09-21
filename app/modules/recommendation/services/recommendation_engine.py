"""
==============================================================
File: recommendation_engine.py

RecommendationEngine - Sinh action list tu BurnoutResult.

Hybrid approach (Sprint 22 + Sprint 27):
1. Rule-based: tu factor -> action templates
2. RAG-driven: query Qdrant knowledge base (Sprint 21) de them 1-2
   evidence-backed khuyen nghi (WHO/APA/generic).

Mapping factor -> action templates:
- sleep:    [ngu 7-8h, rut man hinh truoc ngu, dat lich ngu co dinh]
- workload: [cat deadline, phan bo task, micro-break, xin ho tro]
- emotion:  [ghi nhat ky, gap chuyen gia, affect labeling]
- other:    [van dong, mindfulness, ket noi xa hoi]

Priority: 'urgent' neu risk=high + factor co sub_score >= 70,
          'high' neu sub_score >= 50 hoac risk=high,
          'medium' neu sub_score >= 30,
          'low' con lai.

Pure function, deterministic, optional async RAG (fail-soft).
==============================================================
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.modules.burnout.models.burnout import (
    BurnoutResult,
    BurnoutFactor,
)
from app.modules.recommendation.models.recommendation import Recommendation

logger = logging.getLogger("burnout.recommendation")


# ==========================================
# Action templates (mỗi factor: list 2-3 actions)
# ==========================================

ACTION_TEMPLATES: Dict[str, List[Dict[str, str]]] = {
    "sleep": [
        {
            "title": "Dat muc tieu ngu 7-8 tieng moi dem",
            "description": (
                "Ngu du giac giup giam 30% nguy co tram cam. "
                "Di ngu va thuc day cung mot gio moi ngay, ke ca cuoi tuan."
            ),
        },
        {
            "title": "Tao routine truoc khi ngu",
            "description": (
                "Tranh man hinh 1 tieng truoc khi ngu (dien thoai, laptop). "
                "Thay bang doc sach, nghe nhac nhe, thi binh thuong."
            ),
        },
        {
            "title": "Toi uu moi truong phong ngu",
            "description": (
                "Phong ngu toi (rem hoac mat na), nhiet do 18-22 do C, "
                "am thanh thap. Tranh caffeine sau 14h."
            ),
        },
    ],
    "workload": [
        {
            "title": "Phan bo va uu tien cong viec",
            "description": (
                "Dung ky thuat Eisenhower (Quan trong/Gap) de chia task. "
                "Lam truoc nhung viec quan trong, deadline xa thi push xuong."
            ),
        },
        {
            "title": "Ap dung micro-break moi 50-90 phut",
            "description": (
                "Nghi 5-10 phut moi 50-90 phut lam viec. "
                "Tang productivity 30% theo DeskTime study."
            ),
        },
        {
            "title": "Dam phan workload voi cap quan ly",
            "description": (
                "Neu qua tai lien tuc > 2 tuan, len lich 1-1 voi quan ly. "
                "De xuat giam deadline, giao task, hoac them nhan su ho tro."
            ),
        },
    ],
    "stress": [
        {
            "title": "Thuc hanh deep breathing 4-7-8",
            "description": (
                "Hap vao 4 giay, giu 7 giay, tho ra 8 giay. "
                "Lap lai 3-4 lan khi cam thay stress cao."
            ),
        },
        {
            "title": "Viet nhat ky stress",
            "description": (
                "Ghi lai nhung noi lo va压力 trong ngay. "
                "Giup ban hieu ro nguon goc stress va cach giai quyet."
            ),
        },
        {
            "title": "Xin ho tro khi can thiet",
            "description": (
                "Neu stress keo dai, noi chuyen voi quan ly, dong nghiep, "
                "hoac chuyen gia de duoc ho tro kip thoi."
            ),
        },
    ],
    "emotion": [
        {
            "title": "Viet nhat ky cam xuc",
            "description": (
                "Moi ngay ghi 1-2 cau ve cam xuc chinh: 'hom nay toi cam thay...'. "
                "Nghien cuu Lieberman (2007): dat ten cam xuc giam amygdala activity 50%."
            ),
        },
        {
            "title": "Gap chuyen gia tam ly",
            "description": (
                "Neu cam xuc tieu cuc keo dai > 2 tuan, hay gap chuyen gia tam ly. "
                "Day khong phai yeu dot - la cach chu dong bao ve suc khoe."
            ),
        },
        {
            "title": "Thuc hanh gratitude 5 phut moi toi",
            "description": (
                "Truoc khi ngu, ghi 3 dieu ban biet on trong ngay. "
                "Giup re-train brain focus vao positive thay vi negative."
            ),
        },
    ],
    "behavior": [
        {
            "title": "Theo doi tien trieu qua 2-4 tuan",
            "description": (
                "Neu xu huong dang tang, hay gap chuyen gia som nhat. "
                "Theo doi giup ban nhanh chong phat hien va xu ly."
            ),
        },
        {
            "title": "Dat muc tieu ngan hang tuan",
            "description": (
                "Thay vi thay doi moi thuc, dat 1-2 muc tieu nho moi tuan. "
                "Vi du: ngu som 1 dem, nghi 5 phut/gio."
            ),
        },
        {
            "title": "Van dong the chat 30 phut moi ngay",
            "description": (
                "Di bo, chay bo, yoga, boi loi - deu giam cortisol (stress hormone). "
                "Khong can gym, chi can di bo nhe sau bua com."
            ),
        },
    ],
}

# Mapping factor name trong BurnoutFactor -> key trong ACTION_TEMPLATES
FACTOR_KEY_MAP = {
    "sleep": "sleep",
    "workload": "workload",
    "stress": "stress",
    "emotion": "emotion",
    "behavior": "behavior",
}


# ==========================================
# Priority logic
# ==========================================

def _calc_priority(
    risk_level: str,
    sub_score: float,
) -> str:
    """Tinh priority tu risk_level va sub_score.

    - urgent: high risk + sub_score >= 70
    - high:   high risk hoac sub_score >= 50
    - medium: sub_score >= 30
    - low:    sub_score < 30
    """
    if risk_level == "high" and sub_score >= 70.0:
        return "urgent"
    if risk_level == "high" or sub_score >= 50.0:
        return "high"
    if sub_score >= 30.0:
        return "medium"
    return "low"


# ==========================================
# Engine
# ==========================================

class RecommendationEngine:
    """Rule-based + RAG-driven recommendation engine tu BurnoutResult."""

    def __init__(
        self,
        max_recommendations: int = 6,
        knowledge_service: Optional[Any] = None,
        rag_top_k: int = 2,
    ):
        """
        Args:
            max_recommendations: gioi han so rec tra ve (default 6).
            knowledge_service: optional KnowledgeService (Sprint 21) cho RAG.
                Neu None -> skip RAG phase (van chay rule-based).
            rag_top_k: so knowledge docs them vao (default 2).
        """
        self._max = max_recommendations
        self._knowledge_service = knowledge_service
        self._rag_top_k = rag_top_k

    @staticmethod
    def _sub_score(factor: BurnoutFactor) -> float:
        if factor.details and "sub_score" in factor.details:
            return float(factor.details["sub_score"])
        return 0.0

    def generate(
        self,
        burnout: BurnoutResult,
        custom_actions: Optional[Dict[str, List[Dict[str, str]]]] = None,
        rag_query_text: Optional[str] = None,
    ) -> List[Recommendation]:
        """Sinh danh sach Recommendation tu BurnoutResult (sync).

        Args:
            burnout: BurnoutResult tu BurnoutEngine.
            custom_actions: optional override actions theo factor key.
            rag_query_text: optional text de query knowledge RAG (sync only).
                Neu None -> skip RAG (use generate_async for auto-build).

        Returns:
            list[Recommendation] sorted by priority (urgent -> low).
        """
        actions = custom_actions or ACTION_TEMPLATES
        risk = burnout.risk_level
        recs: List[Recommendation] = []

        # Sort factors theo sub_score giam dan
        factors = sorted(
            burnout.factors,
            key=lambda f: self._sub_score(f),
            reverse=True,
        )

        # Top factor (factor te nhat) cho RAG query
        top_factor = factors[0] if factors else None

        for f in factors:
            sub = self._sub_score(f)
            if sub < 15.0:
                continue
            key = FACTOR_KEY_MAP.get(f.factor)
            if key is None:
                logger.debug("Unknown factor '%s', skip", f.factor)
                continue
            templates = actions.get(key, [])
            if not templates:
                continue
            priority = _calc_priority(risk, sub)
            n_pick = 2 if sub >= 60.0 else 1
            for tmpl in templates[:n_pick]:
                recs.append(
                    Recommendation(
                        title=tmpl["title"],
                        description=tmpl["description"],
                        priority=priority,
                        target_factor=f.factor,
                    )
                )

        # RAG-driven phase (Sprint 27): sync, optional
        if self._knowledge_service is not None and rag_query_text is not None and top_factor is not None:
            try:
                rag_recs = self._sync_rag_phase(rag_query_text, top_factor, risk)
                recs.extend(rag_recs)
            except Exception as exc:
                logger.warning("RAG phase failed (skip): %s", exc)

        # Sort theo priority
        priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        recs.sort(key=lambda r: priority_order.get(r.priority, 99))

        result = recs[: self._max]

        if not result and risk != "low":
            result.append(
                Recommendation(
                    title="Theo doi suc khoe toan dien",
                    description=(
                        "Tang cuong theo doi giac ngu, workload va cam xuc. "
                        "Neu trieu chung keo dai, gap chuyen gia y te."
                    ),
                    priority="medium",
                    target_factor=None,
                )
            )

        return result

    async def generate_async(
        self,
        burnout: BurnoutResult,
        emotion: Optional[Any] = None,
        custom_actions: Optional[Dict[str, List[Dict[str, str]]]] = None,
    ) -> List[Recommendation]:
        """Async version: full rule-based + RAG phase (build query tu emotion).

        Args:
            burnout: BurnoutResult tu BurnoutEngine.
            emotion: optional EmotionResult (de build RAG query text).
            custom_actions: optional override actions.

        Returns:
            list[Recommendation].
        """
        # Auto-build RAG query tu emotion neu co
        rag_text = None
        if emotion is not None:
            try:
                rag_text = self._build_emotion_rag_query(emotion)
            except Exception as exc:
                logger.debug("Build RAG query fail: %s", exc)

        # Tuong tu generate(), them RAG phase
        actions = custom_actions or ACTION_TEMPLATES
        risk = burnout.risk_level
        recs: List[Recommendation] = []

        factors = sorted(
            burnout.factors,
            key=lambda f: self._sub_score(f),
            reverse=True,
        )
        top_factor = factors[0] if factors else None

        for f in factors:
            sub = self._sub_score(f)
            if sub < 15.0:
                continue
            key = FACTOR_KEY_MAP.get(f.factor)
            if key is None:
                continue
            templates = actions.get(key, [])
            if not templates:
                continue
            priority = _calc_priority(risk, sub)
            n_pick = 2 if sub >= 60.0 else 1
            for tmpl in templates[:n_pick]:
                recs.append(
                    Recommendation(
                        title=tmpl["title"],
                        description=tmpl["description"],
                        priority=priority,
                        target_factor=f.factor,
                    )
                )

        # Async RAG phase
        if self._knowledge_service is not None and top_factor is not None:
            try:
                rag_recs = await self._async_rag_phase(rag_text, top_factor, risk)
                recs.extend(rag_recs)
            except Exception as exc:
                logger.warning("Async RAG phase failed (skip): %s", exc)

        priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        recs.sort(key=lambda r: priority_order.get(r.priority, 99))

        result = recs[: self._max]
        if not result and risk != "low":
            result.append(
                Recommendation(
                    title="Theo doi suc khoe toan dien",
                    description=(
                        "Tang cuong theo doi giac ngu, workload va cam xuc. "
                        "Neu trieu chung keo dai, gap chuyen gia y te."
                    ),
                    priority="medium",
                    target_factor=None,
                )
            )
        return result

    @staticmethod
    def _build_emotion_rag_query(emotion: Any) -> str:
        """Build query text tu EmotionResult de search knowledge base."""
        emotions = emotion.emotions.model_dump() if hasattr(emotion.emotions, 'model_dump') else {}
        parts = [
            f"Emotion: {emotion.dominant_emotion}",
            f"confidence: {emotion.confidence:.2f}",
        ]
        for k in ("sad", "happy", "fear", "angry", "neutral", "stress"):
            if k in emotions:
                parts.append(f"{k}={float(emotions[k]):.1f}")
        return " ".join(parts)

    def _sync_rag_phase(
        self,
        query_text: str,
        top_factor: BurnoutFactor,
        risk_level: str,
    ) -> List[Recommendation]:
        """Sync RAG: goi asyncio.run neu can. (Kho su dung neu caller khong async)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Caller dang trong async context -> khong the loop.run_until_complete
                logger.debug("Skip sync RAG (async context detected)")
                return []
            return loop.run_until_complete(
                self._async_rag_phase(query_text, top_factor, risk_level)
            )
        except RuntimeError:
            # Khong co loop, tao moi
            return asyncio.run(
                self._async_rag_phase(query_text, top_factor, risk_level)
            )

    async def _async_rag_phase(
        self,
        query_text: Optional[str],
        top_factor: BurnoutFactor,
        risk_level: str,
    ) -> List[Recommendation]:
        """Async RAG: search knowledge + convert to Recommendation."""
        if not query_text or self._knowledge_service is None:
            return []
        try:
            hits = await self._knowledge_service.search(
                query_text=query_text, top_k=self._rag_top_k,
            )
        except Exception as exc:
            logger.warning("Knowledge search failed: %s", exc)
            return []

        recs: List[Recommendation] = []
        # Priority thap hon rule-based mot bac (de khuyen nghi chuyen gia noi bat hon)
        # urgent -> high, high -> medium, ...
        priority_map = {"urgent": "high", "high": "medium", "medium": "low", "low": "low"}

        for i, hit in enumerate(hits):
            title = hit.get("title", f"Tai lieu tham khao #{i+1}")
            content = hit.get("content", "")
            source = hit.get("source", "knowledge_base")
            snippet = content[:240] + "..." if len(content) > 240 else content
            # Knowledge target_factor: prefix de phan biet rule vs RAG
            target_factor = f"knowledge:{top_factor.factor}"
            recs.append(
                Recommendation(
                    title=f"[{source.upper()}] {title}",
                    description=f"{snippet}\n\n(Tham khao y khoa/tam ly co so).",
                    priority=priority_map.get(risk_level, "low"),
                    target_factor=target_factor,
                )
            )
        return recs


# ==========================================
# Singleton
# ==========================================

_recommendation_engine: Optional[RecommendationEngine] = None


def get_recommendation_engine() -> RecommendationEngine:
    """Singleton (lazy, optional knowledge_service).

    Sprint 27: neu co the wire knowledge_service.
    """
    global _recommendation_engine
    if _recommendation_engine is None:
        ks = None
        try:
            from app.modules.knowledge.services import get_knowledge_service
            ks = get_knowledge_service()
        except Exception:
            ks = None
        _recommendation_engine = RecommendationEngine(knowledge_service=ks)
    return _recommendation_engine
