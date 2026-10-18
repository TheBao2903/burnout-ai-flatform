"""
==============================================================
File: survey_analysis_service.py

SurveyAnalysisService - Phân tích survey data và trả về kết quả.

Tách biệt analysis logic khỏi frontend.
Frontend chỉ submit survey data, backend tính toán và trả về kết quả.

Analysis bao gồm:
- risk_score (0-100)
- risk_level (low/medium/high/critical)
- factors (danh sách các factor có vấn đề)
- summary (tóm tắt tình trạng)
- recommendations (danh sách khuyến nghị cải thiện)
==============================================================
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("burnout.survey.analysis")

# ==========================================
# Analysis Versioning
# ==========================================

ANALYSIS_VERSION = "v1"

# ==========================================
# Factor Definitions
# ==========================================

FACTOR_CODES = {
    "SLEEP_DEPRIVATION": "sleep",
    "WORK_OVERLOAD": "workload",
    "EXCESSIVE_OVERTIME": "overtime",
    "HIGH_STRESS": "stress",
    "LOW_MOTIVATION": "motivation",
    "INSUFFICIENT_REST": "rest",
    "LONG_CONSECUTIVE_WORK": "consecutive",
    "LOW_WORK_SATISFACTION": "satisfaction",
    "HIGH_DEADLINE_PRESSURE": "deadline",
    "PHYSICAL_HEALTH_CONCERN": "health",
}

# ==========================================
# Thresholds & Weights
# ==========================================

# Risk score thresholds
RISK_THRESHOLDS = {
    "critical": 80,
    "high": 60,
    "medium": 40,
    "low": 0,
}

# Factor weights for risk score calculation
FACTOR_WEIGHTS = {
    "SLEEP_DEPRIVATION": 20,
    "WORK_OVERLOAD": 25,
    "EXCESSIVE_OVERTIME": 15,
    "HIGH_STRESS": 20,
    "LOW_MOTIVATION": 10,
    "INSUFFICIENT_REST": 10,
    "LONG_CONSECUTIVE_WORK": 10,
    "LOW_WORK_SATISFACTION": 10,
    "HIGH_DEADLINE_PRESSURE": 15,
    "PHYSICAL_HEALTH_CONCERN": 15,
}

# Severity thresholds (score values that trigger factor)
SEVERITY_THRESHOLDS = {
    "high": 70,
    "medium": 40,
    "low": 20,
}


# ==========================================
# Recommendations Templates (by factor)
# ==========================================

RECOMMENDATION_TEMPLATES: Dict[str, List[Dict[str, str]]] = {
    "SLEEP_DEPRIVATION": [
        {
            "title": "Cải thiện giấc ngủ",
            "description": "Ngủ đủ 7-8 tiếng mỗi đêm giúp giảm 30% nguy cơ burnout.",
            "priority": "high",
        },
        {
            "title": "Tạo routine trước khi ngủ",
            "description": "Tránh màn hình 1 tiếng trước khi ngủ. Thay bằng đọc sách hoặc thiền.",
            "priority": "medium",
        },
    ],
    "WORK_OVERLOAD": [
        {
            "title": "Ưu tiên công việc",
            "description": "Sử dụng ma trận Eisenhower để phân loại công việc theo mức độ quan trọng và khẩn cấp.",
            "priority": "high",
        },
        {
            "title": "Micro-break mỗi giờ",
            "description": "Nghỉ 5-10 phút mỗi 50-90 phút làm việc giúp tăng năng suất 30%.",
            "priority": "medium",
        },
    ],
    "EXCESSIVE_OVERTIME": [
        {
            "title": "Giảm tăng ca",
            "description": "Tăng ca nhiều cần được bù đắp bằng nghỉ ngơi. Cố gắng giảm dần tăng ca.",
            "priority": "high",
        },
        {
            "title": "Thương lượng deadline",
            "description": "Nếu tăng ca kéo dài, hãy trao đổi với quản lý về deadline hợp lý hơn.",
            "priority": "medium",
        },
    ],
    "HIGH_STRESS": [
        {
            "title": "Thực hành deep breathing",
            "description": "Hít vào 4 giây, giữ 7 giây, thở ra 8 giây. Lặp lại 3-4 lần khi cảm thấy stress cao.",
            "priority": "high",
        },
        {
            "title": "Tìm kiếm hỗ trợ",
            "description": "Nếu stress kéo dài, hãy trao đổi với quản lý hoặc tìm hỗ trợ tâm lý chuyên nghiệp.",
            "priority": "medium",
        },
    ],
    "LOW_MOTIVATION": [
        {
            "title": "Tìm ý nghĩa trong công việc",
            "description": "Xác định lại mục tiêu nghề nghiệp và tìm kiếm thử thách mới.",
            "priority": "medium",
        },
        {
            "title": "Khen thưởng bản thân",
            "description": "Đặt mục tiêu nhỏ và tự thưởng khi hoàn thành để duy trì động lực.",
            "priority": "low",
        },
    ],
    "INSUFFICIENT_REST": [
        {
            "title": "Lên lịch nghỉ ngơi",
            "description": "Đặt lịch nghỉ ngơi cố định mỗi tuần và tuân thủ nghiêm ngặt.",
            "priority": "high",
        },
    ],
    "LONG_CONSECUTIVE_WORK": [
        {
            "title": "Nghỉ ngơi sau chuỗi làm việc",
            "description": "Sau 5-6 ngày làm việc liên tiếp, hãy nghỉ ít nhất 1-2 ngày để phục hồi.",
            "priority": "high",
        },
    ],
    "LOW_WORK_SATISFACTION": [
        {
            "title": "Đánh giá lại công việc",
            "description": "Xác định điều gì khiến bạn không hài lòng và tìm cách cải thiện hoặc thay đổi.",
            "priority": "medium",
        },
    ],
    "HIGH_DEADLINE_PRESSURE": [
        {
            "title": "Quản lý deadline",
            "description": "Chia nhỏ deadline lớn thành các milestone nhỏ hơn để giảm áp lực.",
            "priority": "high",
        },
        {
            "title": "Giao tiếp với quản lý",
            "description": "Thông báo sớm cho quản lý nếu deadline không khả thi để điều chỉnh kịp thời.",
            "priority": "medium",
        },
    ],
    "PHYSICAL_HEALTH_CONCERN": [
        {
            "title": "Kiểm tra sức khỏe định kỳ",
            "description": "Nếu nhịp tim hoặc các chỉ số sức khỏe bất thường, hãy đi khám bác sĩ.",
            "priority": "high",
        },
    ],
}

# ==========================================
# Summary Templates
# ==========================================

SUMMARY_TEMPLATES = {
    "critical": "Tình trạng burnout nghiêm trọng. Bạn cần nghỉ ngơi ngay lập tức và tìm kiếm sự hỗ trợ chuyên môn.",
    "high": "Nguy cơ burnout cao. Cần thay đổi lối sống và tìm cách giảm áp lực công việc ngay.",
    "medium": "Có dấu hiệu mệt mỏi. Nên cân bằng giữa công việc và cuộc sống để tránh tình trạng xấu hơn.",
    "low": "Tình trạng ổn định. Hãy duy trì lối sống lành mạnh và thói quen tốt hiện tại.",
}


# ==========================================
# Analysis Result Models
# ==========================================

class AnalysisFactor:
    """Một factor được phát hiện từ survey data."""

    def __init__(
        self,
        code: str,
        score: float,
        severity: str,
        title: str,
        description: str,
    ):
        self.code = code
        self.score = score
        self.severity = severity  # low, medium, high
        self.title = title
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "score": self.score,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
        }


class SurveyAnalysisResult:
    """Kết quả phân tích survey."""

    def __init__(
        self,
        risk_score: float,
        risk_level: str,
        summary: str,
        factors: List[AnalysisFactor],
        recommendations: List[Dict[str, str]],
    ):
        self.risk_score = risk_score
        self.risk_level = risk_level
        self.summary = summary
        self.factors = factors
        self.recommendations = recommendations
        self.analysis_version = ANALYSIS_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "summary": self.summary,
            "factors": [f.to_dict() for f in self.factors],
            "recommendations": self.recommendations,
            "analysis_version": self.analysis_version,
        }


# ==========================================
# Analysis Service
# ==========================================

class SurveyAnalysisService:
    """Service phân tích survey data."""

    @staticmethod
    def analyze(survey_data: Dict[str, Any]) -> SurveyAnalysisResult:
        """Phân tích survey data và trả về kết quả.

        Args:
            survey_data: Dict chứa các trường survey

        Returns:
            SurveyAnalysisResult với risk_score, risk_level, factors, summary
        """
        # Extract STA values if provided
        exhaustion = survey_data.get("exhaustion") or {}
        disengagement = survey_data.get("disengagement") or {}
        job_demands = survey_data.get("job_demands") or {}
        recovery = survey_data.get("recovery") or {}
        quick_overload_data = survey_data.get("quick_overload_data") or {}
        work_changes = survey_data.get("work_changes") or {}

        # Extract values with defaults (prioritize STA structured inputs)
        sleep_hours = recovery.get("sleep_hours", survey_data.get("sleep_hours", 7))
        working_hours = survey_data.get("working_hours", 8)
        overtime_hours = work_changes.get("overtime_hours", survey_data.get("overtime_hours", 0))
        has_deadline = work_changes.get("has_deadline", survey_data.get("has_deadline", "low"))
        work_days_per_week = survey_data.get("work_days_per_week", 5)
        stress_level = survey_data.get("stress_level", 5)
        motivation_level = survey_data.get("motivation_level", 5)
        consecutive_work_days = survey_data.get("consecutive_work_days", 0)
        rest_days = survey_data.get("rest_days", 2)
        work_satisfaction = survey_data.get("work_satisfaction", 5)
        heart_rate = survey_data.get("heart_rate")

        # Calculate factor scores
        factors: List[AnalysisFactor] = []
        total_weighted_score = 0.0
        total_weight = 0.0

        # --- STA Dimension Evaluation (OLBI Core & JD-R) ---
        e_vals = [float(v) for k, v in exhaustion.items() if isinstance(v, (int, float))]
        if e_vals:
            mean_e = sum(e_vals) / len(e_vals)
            e_score = ((mean_e - 1.0) / 4.0) * 100.0
            if e_score >= 40:
                factors.append(AnalysisFactor(
                    code="EXHAUSTION",
                    score=e_score,
                    severity="high" if e_score >= 70 else "medium",
                    title="Mức độ Kiệt sức cao (OLBI Exhaustion)",
                    description="Cảm giác mệt mỏi và cạn kiệt năng lượng sau khi làm việc ở mức đáng chú ý.",
                ))
            total_weighted_score += e_score * 30
            total_weight += 30

        d_vals = [float(v) for k, v in disengagement.items() if isinstance(v, (int, float))]
        if d_vals:
            mean_d = sum(d_vals) / len(d_vals)
            d_score = ((mean_d - 1.0) / 4.0) * 100.0
            if d_score >= 40:
                factors.append(AnalysisFactor(
                    code="DISENGAGEMENT",
                    score=d_score,
                    severity="high" if d_score >= 70 else "medium",
                    title="Suy giảm gắn kết (OLBI Disengagement)",
                    description="Cảm xúc gắn kết và ý nghĩa công việc đang có dấu hiệu giảm sút.",
                ))
            total_weighted_score += d_score * 30
            total_weight += 30

        jd_vals = [float(v) for k, v in job_demands.items() if isinstance(v, (int, float))]
        if jd_vals:
            mean_jd = sum(jd_vals) / len(jd_vals)
            jd_score = ((mean_jd - 1.0) / 4.0) * 100.0
            if jd_score >= 40:
                factors.append(AnalysisFactor(
                    code="JOB_DEMANDS",
                    score=jd_score,
                    severity="high" if jd_score >= 70 else "medium",
                    title="Áp lực công việc cao (Job Demands)",
                    description="Khối lượng công việc và áp lực thời gian gấp đang ở mức cao.",
                ))
            total_weighted_score += jd_score * 20
            total_weight += 20

        if recovery.get("recovery_score") is not None:
            rec_val = float(recovery["recovery_score"])
            rec_score = ((5.0 - rec_val) / 4.0) * 100.0
            if rec_val <= 2:
                factors.append(AnalysisFactor(
                    code="POOR_RECOVERY",
                    score=rec_score,
                    severity="high" if rec_val == 1 else "medium",
                    title="Khả năng phục hồi kém",
                    description="Thời gian nghỉ ngơi chưa giúp bạn tái tạo đủ năng lượng cho công việc.",
                ))
            total_weighted_score += rec_score * 20
            total_weight += 20

        if quick_overload_data.get("overload_rating") is not None:
            ol_val = float(quick_overload_data["overload_rating"])
            if ol_val >= 4:
                reasons = quick_overload_data.get("reasons", [])
                reason_str = ", ".join(reasons) if reasons else "áp lực dồn nén"
                factors.append(AnalysisFactor(
                    code="WORK_OVERLOAD",
                    score=ol_val * 20.0,
                    severity="high",
                    title="Cảm giác quá tải công việc",
                    description=f"Đang cảm thấy quá tải: {reason_str}.",
                ))

        # SLEEP_DEPRIVATION
        if sleep_hours < 6:
            score = 100 - (sleep_hours * 10)  # <6h: score 40-60
            severity = "high" if sleep_hours < 4 else "medium"
            factors.append(AnalysisFactor(
                code="SLEEP_DEPRIVATION",
                score=score,
                severity=severity,
                title="Ngủ không đủ giấc",
                description=f"Ngủ {sleep_hours}h/ngày - ít hơn mức khuyến nghị 7-8h.",
            ))
            total_weighted_score += score * FACTOR_WEIGHTS["SLEEP_DEPRIVATION"]
            total_weight += FACTOR_WEIGHTS["SLEEP_DEPRIVATION"]
        elif sleep_hours < 7:
            factors.append(AnalysisFactor(
                code="SLEEP_DEPRIVATION",
                score=30,
                severity="low",
                title="Ngủ hơi thiếu",
                description=f"Ngủ {sleep_hours}h/ngày - nên ngủ thêm 1 tiếng.",
            ))
            total_weighted_score += 30 * FACTOR_WEIGHTS["SLEEP_DEPRIVATION"]
            total_weight += FACTOR_WEIGHTS["SLEEP_DEPRIVATION"]

        # WORK_OVERLOAD
        if working_hours > 10:
            score = min(100, (working_hours - 8) * 15)  # >8h: score tăng dần
            severity = "high" if working_hours > 12 else "medium"
            factors.append(AnalysisFactor(
                code="WORK_OVERLOAD",
                score=score,
                severity=severity,
                title="Làm việc quá tải",
                description=f"Làm việc {working_hours}h/ngày - vượt mức khuyến nghị 8h.",
            ))
            total_weighted_score += score * FACTOR_WEIGHTS["WORK_OVERLOAD"]
            total_weight += FACTOR_WEIGHTS["WORK_OVERLOAD"]
        elif working_hours > 8:
            factors.append(AnalysisFactor(
                code="WORK_OVERLOAD",
                score=30,
                severity="low",
                title="Làm việc hơi nhiều",
                description=f"Làm việc {working_hours}h/ngày - nên giảm xuống 8h.",
            ))
            total_weighted_score += 30 * FACTOR_WEIGHTS["WORK_OVERLOAD"]
            total_weight += FACTOR_WEIGHTS["WORK_OVERLOAD"]

        # EXCESSIVE_OVERTIME
        if overtime_hours > 3:
            score = min(100, overtime_hours * 20)  # >3h: score 60-80
            severity = "high" if overtime_hours > 6 else "medium"
            factors.append(AnalysisFactor(
                code="EXCESSIVE_OVERTIME",
                score=score,
                severity=severity,
                title="Tăng ca nhiều",
                description=f"Tăng ca {overtime_hours}h/tuần - cần được bù đắp bằng nghỉ ngơi.",
            ))
            total_weighted_score += score * FACTOR_WEIGHTS["EXCESSIVE_OVERTIME"]
            total_weight += FACTOR_WEIGHTS["EXCESSIVE_OVERTIME"]

        # HIGH_STRESS
        if stress_level >= 8:
            score = stress_level * 10  # 80-100
            factors.append(AnalysisFactor(
                code="HIGH_STRESS",
                score=score,
                severity="high",
                title="Mức stress cao",
                description=f"Stress {stress_level}/10 - cần được giải tỏa ngay lập tức.",
            ))
            total_weighted_score += score * FACTOR_WEIGHTS["HIGH_STRESS"]
            total_weight += FACTOR_WEIGHTS["HIGH_STRESS"]
        elif stress_level >= 6:
            factors.append(AnalysisFactor(
                code="HIGH_STRESS",
                score=50,
                severity="medium",
                title="Mức stress trung bình-cao",
                description=f"Stress {stress_level}/10 - nên tìm cách thư giãn.",
            ))
            total_weighted_score += 50 * FACTOR_WEIGHTS["HIGH_STRESS"]
            total_weight += FACTOR_WEIGHTS["HIGH_STRESS"]

        # LOW_MOTIVATION
        if motivation_level < 4:
            score = (5 - motivation_level) * 20  # motivation < 4
            factors.append(AnalysisFactor(
                code="LOW_MOTIVATION",
                score=score,
                severity="high" if motivation_level < 3 else "medium",
                title="Động lực thấp",
                description=f"Động lực {motivation_level}/10 - cần tìm kiếm nguồn cảm hứng mới.",
            ))
            total_weighted_score += score * FACTOR_WEIGHTS["LOW_MOTIVATION"]
            total_weight += FACTOR_WEIGHTS["LOW_MOTIVATION"]

        # INSUFFICIENT_REST
        if rest_days < 1:
            factors.append(AnalysisFactor(
                code="INSUFFICIENT_REST",
                score=70,
                severity="high",
                title="Nghỉ ngơi không đủ",
                description="Cần ít nhất 1 ngày nghỉ mỗi tuần để phục hồi.",
            ))
            total_weighted_score += 70 * FACTOR_WEIGHTS["INSUFFICIENT_REST"]
            total_weight += FACTOR_WEIGHTS["INSUFFICIENT_REST"]
        elif rest_days < 2:
            factors.append(AnalysisFactor(
                code="INSUFFICIENT_REST",
                score=40,
                severity="medium",
                title="Nghỉ ngơi hơi ít",
                description="Nên có 2 ngày nghỉ mỗi tuần để cân bằng cuộc sống.",
            ))
            total_weighted_score += 40 * FACTOR_WEIGHTS["INSUFFICIENT_REST"]
            total_weight += FACTOR_WEIGHTS["INSUFFICIENT_REST"]

        # LONG_CONSECUTIVE_WORK
        if consecutive_work_days and consecutive_work_days >= 6:
            factors.append(AnalysisFactor(
                code="LONG_CONSECUTIVE_WORK",
                score=80,
                severity="high",
                title="Làm việc liên tiếp nhiều ngày",
                description=f"Đã làm {consecutive_work_days} ngày liên tiếp - cần nghỉ ngay.",
            ))
            total_weighted_score += 80 * FACTOR_WEIGHTS["LONG_CONSECUTIVE_WORK"]
            total_weight += FACTOR_WEIGHTS["LONG_CONSECUTIVE_WORK"]
        elif consecutive_work_days and consecutive_work_days >= 5:
            factors.append(AnalysisFactor(
                code="LONG_CONSECUTIVE_WORK",
                score=50,
                severity="medium",
                title="Làm việc liên tiếp nhiều ngày",
                description=f"Đã làm {consecutive_work_days} ngày liên tiếp - nên nghỉ sớm.",
            ))
            total_weighted_score += 50 * FACTOR_WEIGHTS["LONG_CONSECUTIVE_WORK"]
            total_weight += FACTOR_WEIGHTS["LONG_CONSECUTIVE_WORK"]

        # LOW_WORK_SATISFACTION
        if work_satisfaction and work_satisfaction < 4:
            score = (5 - work_satisfaction) * 20
            factors.append(AnalysisFactor(
                code="LOW_WORK_SATISFACTION",
                score=score,
                severity="medium",
                title="Mức hài lòng công việc thấp",
                description=f"Hài lòng {work_satisfaction}/10 - cần xem xét lại công việc.",
            ))
            total_weighted_score += score * FACTOR_WEIGHTS["LOW_WORK_SATISFACTION"]
            total_weight += FACTOR_WEIGHTS["LOW_WORK_SATISFACTION"]

        # HIGH_DEADLINE_PRESSURE
        if has_deadline == "extreme":
            factors.append(AnalysisFactor(
                code="HIGH_DEADLINE_PRESSURE",
                score=90,
                severity="high",
                title="Áp lực deadline cực đoan",
                description="Deadline cực đoan cần được quản lý tốt hơn để tránh burnout.",
            ))
            total_weighted_score += 90 * FACTOR_WEIGHTS["HIGH_DEADLINE_PRESSURE"]
            total_weight += FACTOR_WEIGHTS["HIGH_DEADLINE_PRESSURE"]
        elif has_deadline == "high":
            factors.append(AnalysisFactor(
                code="HIGH_DEADLINE_PRESSURE",
                score=60,
                severity="medium",
                title="Áp lực deadline cao",
                description="Cường độ công việc cao - hãy tìm cách giảm áp lực.",
            ))
            total_weighted_score += 60 * FACTOR_WEIGHTS["HIGH_DEADLINE_PRESSURE"]
            total_weight += FACTOR_WEIGHTS["HIGH_DEADLINE_PRESSURE"]

        # PHYSICAL_HEALTH_CONCERN
        if heart_rate and heart_rate > 100:
            factors.append(AnalysisFactor(
                code="PHYSICAL_HEALTH_CONCERN",
                score=70,
                severity="high",
                title="Nhịp tim cao bất thường",
                description=f"Nhịp tim {heart_rate} bpm - nên kiểm tra sức khỏe.",
            ))
            total_weighted_score += 70 * FACTOR_WEIGHTS["PHYSICAL_HEALTH_CONCERN"]
            total_weight += FACTOR_WEIGHTS["PHYSICAL_HEALTH_CONCERN"]

        # Calculate risk score (weighted average)
        if total_weight > 0:
            risk_score = min(100, total_weighted_score / total_weight)
        else:
            risk_score = 0.0

        # Round risk score
        risk_score = round(risk_score, 1)

        # Determine risk level
        risk_level = "low"
        if risk_score >= RISK_THRESHOLDS["critical"]:
            risk_level = "critical"
        elif risk_score >= RISK_THRESHOLDS["high"]:
            risk_level = "high"
        elif risk_score >= RISK_THRESHOLDS["medium"]:
            risk_level = "medium"

        # Get summary
        summary = SUMMARY_TEMPLATES[risk_level]

        # Generate recommendations based on factors
        recommendations = []
        for factor in factors:
            templates = RECOMMENDATION_TEMPLATES.get(factor.code, [])
            for tmpl in templates[:2]:  # Max 2 per factor
                recommendations.append({
                    "code": factor.code,
                    "title": tmpl["title"],
                    "description": tmpl["description"],
                    "priority": tmpl["priority"],
                    "severity": factor.severity,
                })

        # Limit recommendations
        recommendations = recommendations[:10]

        return SurveyAnalysisResult(
            risk_score=risk_score,
            risk_level=risk_level,
            summary=summary,
            factors=factors,
            recommendations=recommendations,
        )

    @staticmethod
    def compute_rolling_stats(surveys: List[Dict], days: int = 7) -> Dict:
        """Compute rolling stats and trends."""
        stats = {
            'period_days': days,
            'total_surveys': len(surveys),
            'dimensions': {
                'exhaustion': {'current': None, 'average': None, 'trend': 'stable', 'values': []},
                'disengagement': {'current': None, 'average': None, 'trend': 'stable', 'values': []},
                'job_demands': {'current': None, 'average': None, 'trend': 'stable', 'values': []},
                'recovery': {'current': None, 'average': None, 'trend': 'stable', 'values': []},
                'sleep': {'current': None, 'average': None, 'trend': 'stable', 'values': []}
            },
            'overall_trend': 'stable',
            'computed_at': datetime.utcnow().isoformat()
        }
        if not surveys:
            return stats

        dim_vals = {'exhaustion': [], 'disengagement': [], 'job_demands': [], 'recovery': [], 'sleep': []}

        for record in surveys:
            s_data = record.get('survey', {})
            # Exhaustion
            exh = s_data.get('exhaustion', {})
            e_vals = [float(exh[k]) for k in ['e1', 'e2', 'e3'] if k in exh and exh[k] is not None]
            if e_vals:
                dim_vals['exhaustion'].append(sum(e_vals) / len(e_vals))
            
            # Disengagement
            dis = s_data.get('disengagement', {})
            if 'd1' in dis and dis['d1'] is not None:
                dim_vals['disengagement'].append(float(dis['d1']))
                
            # Job Demands
            jd = s_data.get('job_demands', {})
            jd_vals = [float(jd[k]) for k in ['jd1', 'jd2'] if k in jd and jd[k] is not None]
            if jd_vals:
                dim_vals['job_demands'].append(sum(jd_vals) / len(jd_vals))
                
            # Recovery
            rec = s_data.get('recovery', {})
            if rec.get('recovery_score') is not None:
                dim_vals['recovery'].append(float(rec['recovery_score']))
            elif s_data.get('recovery_score') is not None:
                dim_vals['recovery'].append(float(s_data['recovery_score']))
                
            # Sleep
            if rec.get('sleep_hours') is not None:
                dim_vals['sleep'].append(float(rec['sleep_hours']))
            elif s_data.get('sleep_hours') is not None:
                dim_vals['sleep'].append(float(s_data['sleep_hours']))

        for key, vals in dim_vals.items():
            if not vals:
                continue
            avg = sum(vals) / len(vals)
            curr = vals[0]
            trend = 'stable'
            
            last_3 = vals[:3]
            prev_4 = vals[3:7]
            if len(last_3) > 0 and len(prev_4) > 0:
                avg_last_3 = sum(last_3) / len(last_3)
                avg_prev_4 = sum(prev_4) / len(prev_4)
                diff = avg_last_3 - avg_prev_4
                if diff > 0.3:
                    trend = 'increasing'
                elif diff < -0.3:
                    trend = 'decreasing'
                    
            stats['dimensions'][key] = {
                'current': round(curr, 2),
                'average': round(avg, 2),
                'trend': trend,
                'values': [round(v, 2) for v in vals]
            }
            
        return stats

    @staticmethod
    def check_allostatic_overload(surveys: List[Dict]) -> Optional[Dict]:
        """Check for continuous allostatic overload based on recent surveys."""
        if len(surveys) < 3:
            return None
            
        recent_3 = surveys[:3]
        exh_vals = []
        sleep_vals = []
        
        for record in recent_3:
            s_data = record.get('survey', {})
            
            # Exhaustion
            exh = s_data.get('exhaustion', {})
            e_vals = [float(exh[k]) for k in ['e1', 'e2', 'e3'] if k in exh and exh[k] is not None]
            if e_vals:
                exh_vals.append(sum(e_vals) / len(e_vals))
                
            # Sleep
            rec = s_data.get('recovery', {})
            sleep = None
            if rec.get('sleep_hours') is not None:
                sleep = float(rec['sleep_hours'])
            elif s_data.get('sleep_hours') is not None:
                sleep = float(s_data['sleep_hours'])
            if sleep is not None:
                sleep_vals.append(sleep)
                
        if len(exh_vals) == 3 and len(sleep_vals) == 3:
            exh_mean = sum(exh_vals) / 3
            sleep_mean = sum(sleep_vals) / 3
            
            if all(v >= 4.0 for v in exh_vals) and all(v < 6.0 for v in sleep_vals):
                return {
                    'type': 'allostatic_overload',
                    'severity': 'critical',
                    'title': 'Cảnh báo quá tải kéo dài',
                    'message': 'Bạn đang trong trạng thái kiệt sức kéo dài với giấc ngủ không đủ. Hãy ưu tiên nghỉ ngơi và tìm kiếm hỗ trợ.',
                    'consecutive_days': 3,
                    'details': {
                        'avg_exhaustion': round(exh_mean, 2),
                        'avg_sleep': round(sleep_mean, 2)
                    }
                }
        return None


# ==========================================
# Singleton
# ==========================================

_survey_analysis_service: Optional[SurveyAnalysisService] = None


def get_survey_analysis_service() -> SurveyAnalysisService:
    """Get SurveyAnalysisService singleton."""
    global _survey_analysis_service
    if _survey_analysis_service is None:
        _survey_analysis_service = SurveyAnalysisService()
    return _survey_analysis_service
