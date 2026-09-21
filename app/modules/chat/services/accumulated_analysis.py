"""
==============================================================
File: accumulated_analysis.py

AccumulatedAnalysisService - Quản lý accumulated scores từ nhiều messages.

Features:
- Rolling accumulation of analysis scores
- Context window (last N messages)
- Trend detection
- Aggregated statistics
==============================================================
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger("burnout.chat.accumulated")


@dataclass
class MessageAnalysis:
    """Analysis result từ một message."""
    timestamp: datetime
    stress_score: float
    burnout_score: float
    fatigue_score: float
    motivation_score: float
    detected_signals: list
    raw_data: dict


@dataclass
class TrendAnalysis:
    """Kết quả phân tích trend."""
    direction: str  # "increasing", "decreasing", "stable"
    stress_trend: float  # -1 to 1 (negative = decreasing)
    burnout_trend: float
    message_count: int
    severity_alert: Optional[str]  # "warning", "critical", None


@dataclass
class AccumulatedAnalysis:
    """Tổng hợp analysis từ nhiều messages."""
    message_count: int
    avg_stress: float
    avg_burnout: float
    avg_fatigue: float
    avg_motivation: float
    max_stress: float
    max_burnout: float
    max_fatigue: float
    all_signals: list
    unique_signals: list
    trend: TrendAnalysis
    time_span_minutes: float


class AccumulatedAnalysisService:
    """Service quản lý accumulated analysis."""

    CONTEXT_WINDOW_SIZE = 10  # Chỉ giữ 10 messages gần nhất

    def __init__(self):
        self._analysis_history = {}  # assessment_id -> list[MessageAnalysis]

    def add_analysis(
        self,
        assessment_id: str,
        analysis_data: dict,
    ) -> AccumulatedAnalysis:
        """
        Thêm analysis result và cập nhật accumulated stats.

        Args:
            assessment_id: ID của assessment
            analysis_data: Kết quả phân tích từ AI

        Returns:
            AccumulatedAnalysis với stats tổng hợp
        """
        # Initialize list nếu chưa có
        if assessment_id not in self._analysis_history:
            self._analysis_history[assessment_id] = []

        # Extract scores từ analysis_data
        stress_score = analysis_data.get("stress_level", {}).get("score", 0)
        burnout_score = analysis_data.get("burnout_related_signal", {}).get("score", 0)
        fatigue_score = analysis_data.get("fatigue_signal", {}).get("score", 0)
        motivation_score = analysis_data.get("motivation_level", {}).get("score", 50)
        detected_signals = analysis_data.get("detected_signals", [])

        # Create MessageAnalysis
        msg_analysis = MessageAnalysis(
            timestamp=datetime.utcnow(),
            stress_score=stress_score,
            burnout_score=burnout_score,
            fatigue_score=fatigue_score,
            motivation_score=motivation_score,
            detected_signals=detected_signals,
            raw_data=analysis_data,
        )

        # Add to history
        self._analysis_history[assessment_id].append(msg_analysis)

        # Trim to context window
        history = self._analysis_history[assessment_id]
        if len(history) > self.CONTEXT_WINDOW_SIZE:
            self._analysis_history[assessment_id] = history[-self.CONTEXT_WINDOW_SIZE:]

        # Calculate accumulated stats
        return self._calculate_accumulated(assessment_id)

    def _calculate_accumulated(self, assessment_id: str) -> AccumulatedAnalysis:
        """Calculate accumulated stats từ history."""
        history = self._analysis_history.get(assessment_id, [])

        if not history:
            return AccumulatedAnalysis(
                message_count=0,
                avg_stress=0,
                avg_burnout=0,
                avg_fatigue=0,
                avg_motivation=50,
                max_stress=0,
                max_burnout=0,
                max_fatigue=0,
                all_signals=[],
                unique_signals=[],
                trend=TrendAnalysis(
                    direction="stable",
                    stress_trend=0,
                    burnout_trend=0,
                    message_count=0,
                    severity_alert=None,
                ),
                time_span_minutes=0,
            )

        # Calculate averages
        n = len(history)
        avg_stress = sum(m.stress_score for m in history) / n
        avg_burnout = sum(m.burnout_score for m in history) / n
        avg_fatigue = sum(m.fatigue_score for m in history) / n
        avg_motivation = sum(m.motivation_score for m in history) / n

        # Calculate maxes
        max_stress = max(m.stress_score for m in history)
        max_burnout = max(m.burnout_score for m in history)
        max_fatigue = max(m.fatigue_score for m in history)

        # Collect signals
        all_signals = []
        for m in history:
            all_signals.extend(m.detected_signals)
        unique_signals = list(dict.fromkeys(all_signals))  # Preserve order, remove dups

        # Calculate time span
        if len(history) > 1:
            time_span = (history[-1].timestamp - history[0].timestamp).total_seconds() / 60
        else:
            time_span = 0

        # Calculate trend
        trend = self._calculate_trend(history)

        return AccumulatedAnalysis(
            message_count=n,
            avg_stress=round(avg_stress, 1),
            avg_burnout=round(avg_burnout, 1),
            avg_fatigue=round(avg_fatigue, 1),
            avg_motivation=round(avg_motivation, 1),
            max_stress=max_stress,
            max_burnout=max_burnout,
            max_fatigue=max_fatigue,
            all_signals=all_signals,
            unique_signals=unique_signals,
            trend=trend,
            time_span_minutes=round(time_span, 1),
        )

    def _calculate_trend(self, history: list) -> TrendAnalysis:
        """Calculate trend từ message history."""
        if len(history) < 2:
            return TrendAnalysis(
                direction="stable",
                stress_trend=0,
                burnout_trend=0,
                message_count=len(history),
                severity_alert=None,
            )

        n = len(history)
        half = n // 2

        # So sánh nửa đầu vs nửa cuối
        first_half = history[:half]
        second_half = history[-half:] if half > 0 else history

        if not first_half or not second_half:
            return TrendAnalysis(
                direction="stable",
                stress_trend=0,
                burnout_trend=0,
                message_count=n,
                severity_alert=None,
            )

        # Calculate averages cho mỗi nửa
        first_stress = sum(m.stress_score for m in first_half) / len(first_half)
        second_stress = sum(m.stress_score for m in second_half) / len(second_half)

        first_burnout = sum(m.burnout_score for m in first_half) / len(first_half)
        second_burnout = sum(m.burnout_score for m in second_half) / len(second_half)

        # Calculate trend (-1 to 1)
        stress_trend = (second_stress - first_stress) / 100
        burnout_trend = (second_burnout - first_burnout) / 100

        # Determine direction
        if stress_trend > 0.1 or burnout_trend > 0.1:
            direction = "increasing"
        elif stress_trend < -0.1 or burnout_trend < -0.1:
            direction = "decreasing"
        else:
            direction = "stable"

        # Severity alert
        severity_alert = None
        latest = history[-1]
        if latest.burnout_score > 80 or latest.stress_score > 85:
            severity_alert = "critical"
        elif latest.burnout_score > 60 or latest.stress_score > 70:
            severity_alert = "warning"

        return TrendAnalysis(
            direction=direction,
            stress_trend=round(stress_trend, 2),
            burnout_trend=round(burnout_trend, 2),
            message_count=n,
            severity_alert=severity_alert,
        )

    def get_accumulated(self, assessment_id: str) -> AccumulatedAnalysis:
        """Get accumulated stats cho assessment (không thêm message mới)."""
        return self._calculate_accumulated(assessment_id)

    def clear_history(self, assessment_id: str):
        """Xóa history cho assessment (khi bắt đầu session mới)."""
        if assessment_id in self._analysis_history:
            del self._analysis_history[assessment_id]

    def get_message_count(self, assessment_id: str) -> int:
        """Get số messages đã phân tích."""
        return len(self._analysis_history.get(assessment_id, []))


# Singleton
_accumulated_service: Optional[AccumulatedAnalysisService] = None


def get_accumulated_analysis_service() -> AccumulatedAnalysisService:
    """Get singleton instance."""
    global _accumulated_service
    if _accumulated_service is None:
        _accumulated_service = AccumulatedAnalysisService()
    return _accumulated_service
