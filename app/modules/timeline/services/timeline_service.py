"""
==============================================================
File: timeline_service.py

TimelineService - Aggregate emotion + assessment theo ngay.

Moi diem timeline = 1 ngay co data:
- date (YYYY-MM-DD)
- emotion_count: so emotion docs trong ngay
- avg_burnout_score: diem burnout TB (tu assessments noi linked)
- dominant_emotion: emotion xuat hien nhieu nhat trong ngay
- risk_level: max risk_level trong ngay
- sample_emotion_ids: list emotion_id (toi da 5)

Pure function over raw data (mock-friendly), no IO.
Sprint 23.
==============================================================
"""

import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.modules.timeline.models.timeline import Timeline

logger = logging.getLogger("burnout.timeline")


def _parse_date(dt: Any) -> Optional[str]:
    """Parse datetime/iso string -> 'YYYY-MM-DD' hoac None."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.date().isoformat()
    if isinstance(dt, str):
        # Co the co 'Z' cuoi
        s = dt.rstrip("Z")
        try:
            return datetime.fromisoformat(s).date().isoformat()
        except ValueError:
            return None
    return None


class TimelineService:
    """Service aggregate timeline data cho dashboard."""

    def aggregate(
        self,
        emotions: List[Dict[str, Any]],
        assessments: Optional[List[Dict[str, Any]]] = None,
        days: int = 7,
    ) -> List[Timeline]:
        """Build timeline tu raw emotion + assessment docs.

        Args:
            emotions: list[dict] emotion docs. Moi dict co:
                - 'id' (str, optional)
                - 'analyzed_at' (datetime or ISO string)
                - 'dominant_emotion' (str)
            assessments: list[dict] assessment docs. Moi dict co:
                - 'emotion_id' (FK)
                - 'risk_level' (str)
                - 'analyzed_at' (optional, fallback neu khong co emotion match)
            days: so ngay (default 7) - gioi han window.

        Returns:
            list[Timeline] sorted by date asc.
        """
        assessments = assessments or []
        if not emotions:
            return []

        # Index assessments by emotion_id
        assess_by_emotion: Dict[str, Dict[str, Any]] = {}
        for a in assessments:
            eid = a.get("emotion_id")
            if eid:
                assess_by_emotion[eid] = a

        # Nhom emotions theo ngay
        by_date: Dict[str, List[Dict[str, Any]]] = {}
        for e in emotions:
            d = _parse_date(e.get("analyzed_at") or e.get("created_at"))
            if d is None:
                continue
            by_date.setdefault(d, []).append(e)

        # Build Timeline cho moi ngay (trong window)
        cutoff = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
        result: List[Timeline] = []
        for d in sorted(by_date.keys()):
            if d < cutoff:
                continue
            group = by_date[d]
            # dominant emotion
            dom_counter = Counter(
                e.get("dominant_emotion", "unknown") for e in group
            )
            dom_emotion = dom_counter.most_common(1)[0][0] if dom_counter else "unknown"
            # avg burnout_score (tu assessment linked)
            scores: List[float] = []
            risk_levels: List[str] = []
            sample_ids: List[str] = []
            for e in group:
                eid = e.get("id") or e.get("doc_id")
                if eid and len(sample_ids) < 5:
                    sample_ids.append(eid)
                if eid and eid in assess_by_emotion:
                    a = assess_by_emotion[eid]
                    if "burnout_score" in a:
                        scores.append(float(a["burnout_score"]))
                    if "risk_level" in a:
                        risk_levels.append(str(a["risk_level"]))
            avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
            # risk_level: max severity
            risk = self._max_risk(risk_levels) if risk_levels else "unknown"

            result.append(
                Timeline(
                    session_id=d,  # reuse field lam date key
                    user_id=group[0].get("user_id", ""),
                    burnout_score=avg_score,
                    risk_level=risk if risk in ("low", "medium", "high", "critical") else "medium",
                    dominant_emotion=dom_emotion,
                    timestamp=datetime.fromisoformat(d),
                )
            )
        return result

    @staticmethod
    def _max_risk(risks: List[str]) -> str:
        if not risks:
            return "unknown"
        order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        return max(risks, key=lambda r: order.get(r, -1))


# ==========================================
# Singleton
# ==========================================

_timeline_service: Optional[TimelineService] = None


def get_timeline_service() -> TimelineService:
    global _timeline_service
    if _timeline_service is None:
        _timeline_service = TimelineService()
    return _timeline_service
