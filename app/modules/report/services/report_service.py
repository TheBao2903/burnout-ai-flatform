"""
==============================================================
File: report_service.py

ReportService - Monthly aggregation cho user.

Moi report:
- id: 'report_{user_id}_{YYYY-MM}'
- user_id
- month: 'YYYY-MM'
- average_burnout, highest_score, lowest_score
- total_sessions (so emotion)
- dominant_emotions: dict {emotion: count} sorted
- session_id: optional session_id cua session
- top_factors: list factor names co weighted_contribution cao nhat TB

Pure function, no IO, no LLM.
Sprint 23.
==============================================================
"""

import logging
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.modules.report.models.report import Report

logger = logging.getLogger("burnout.report")


def _parse_month(dt: Any) -> Optional[str]:
    """Datetime/iso string -> 'YYYY-MM'."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m")
    if isinstance(dt, str):
        s = dt.rstrip("Z")
        try:
            return datetime.fromisoformat(s).strftime("%Y-%m")
        except ValueError:
            return None
    return None


class ReportService:
    """Service sinh report thang."""

    def build_monthly_report(
        self,
        user_id: str,
        emotions: List[Dict[str, Any]],
        assessments: Optional[List[Dict[str, Any]]] = None,
        month: Optional[str] = None,
    ) -> Optional[Report]:
        """Build 1 monthly report tu raw data.

        Args:
            user_id: Firebase uid.
            emotions: list emotion docs trong thang.
            assessments: optional list assessment docs (for burnout score).
            month: 'YYYY-MM', default = thang cuoi cung co data.

        Returns:
            Report neu co data, None neu khong co.
        """
        assessments = assessments or []
        if not emotions:
            return None

        # Xac dinh thang
        months_found = sorted({
            m for m in (_parse_month(e.get("analyzed_at") or e.get("created_at"))
                        for e in emotions)
            if m
        })
        if not months_found:
            return None
        target_month = month or months_found[-1]

        # Filter emotions trong thang
        month_emotions = [
            e for e in emotions
            if _parse_month(e.get("analyzed_at") or e.get("created_at")) == target_month
        ]
        if not month_emotions:
            return None

        # Index assessments by emotion_id
        assess_by_eid: Dict[str, Dict[str, Any]] = {}
        for a in assessments:
            eid = a.get("emotion_id")
            if eid:
                assess_by_eid[eid] = a

        # Tinh avg/highest/lowest burnout
        scores: List[float] = []
        dom_counter: Counter = Counter()
        factor_sums: Dict[str, List[float]] = {}

        for e in month_emotions:
            dom = e.get("dominant_emotion", "unknown")
            dom_counter[dom] += 1
            eid = e.get("id") or e.get("doc_id")
            if eid and eid in assess_by_eid:
                a = assess_by_eid[eid]
                if "burnout_score" in a:
                    scores.append(float(a["burnout_score"]))
                for f in a.get("factors", []) or []:
                    fname = f.get("factor")
                    if fname:
                        factor_sums.setdefault(fname, []).append(
                            float(f.get("percentage", 0.0))
                        )

        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        hi = max(scores) if scores else 0.0
        lo = min(scores) if scores else 0.0

        # Top factors theo mean percentage
        top_factors: List[Dict[str, Any]] = []
        for fname, vals in factor_sums.items():
            mean = round(sum(vals) / len(vals), 2)
            top_factors.append({"factor": fname, "avg_percentage": mean})
        top_factors.sort(key=lambda x: x["avg_percentage"], reverse=True)
        top_factors = top_factors[:3]  # top 3

        # dominant emotions sorted by count desc
        dom_dict = dict(dom_counter.most_common())

        report_id = f"report_{user_id}_{target_month}".replace("-", "_")
        return Report(
            id=report_id,
            user_id=user_id,
            month=target_month,
            average_burnout=avg,
            highest_score=hi,
            lowest_score=lo,
            total_sessions=len(month_emotions),
            dominant_emotions=dom_dict,
        )


# ==========================================
# Singleton
# ==========================================

_report_service: Optional[ReportService] = None


def get_report_service() -> ReportService:
    global _report_service
    if _report_service is None:
        _report_service = ReportService()
    return _report_service
