"""
==============================================================
File: burnout_engine.py

BurnoutEngine - Phân tích Burnout theo chuẩn khoa học (STA) và JD-R / OLBI.

NGUYÊN TẮC THIẾT KẾ:
1. Burnout Core: Exhaustion (E1-E3) + Disengagement (D1-D3) trên thang Likert 1-5.
2. Context:
   - Job Demands (JD1-JD3)
   - Job Resources (JR1-JR4)
   - Six Areas of Worklife
   - Recovery: Đối chiếu số giờ ngủ thực tế và cảm nhận hồi phục.
3. Supporting Signals:
   - AI Chat: Trích xuất context tags (workload, deadline, lack of support, conflict...).
   - DeepFace: Cảm xúc khuôn mặt là tín hiệu hỗ trợ (không tính điểm trực tiếp).
4. Data Sufficiency & Data Quality:
   - Không dùng trọng số tùy tiện (30% sleep, 25% workload...).
   - Đánh giá tính đầy đủ và hợp lệ. Thiếu Core -> insufficient_data, không chẩn đoán bừa.
5. Interpretation:
   - Nhận định khoa học tổng hợp bối cảnh, không khẳng định cứng "Bạn bị burnout".
6. Tương thích ngược:
   - Hỗ trợ BurnoutEngineInput cũ, tính toán burnout_score và factors cho các bài test hồi quy.
==============================================================
"""

import logging
from typing import Any, Dict, List, Optional

from app.modules.burnout.helpers.completeness import (
    evaluate_data_quality,
    evaluate_data_sufficiency,
    calculate_data_completeness,
)
from app.modules.burnout.helpers.scoring import (
    calculate_dimension_trend,
    calculate_mean_score,
    calculate_recovery_status,
    calculate_sleep_score,
    calculate_workload_score,
    calculate_stress_score,
    calculate_emotion_score,
    calculate_behavior_score,
)
from app.modules.burnout.helpers.weights import (
    get_burnout_signal_status,
    get_dimension_level,
    get_risk_level,
)
from app.modules.burnout.models.burnout import (
    BurnoutCoreResult,
    BurnoutEngineOutput,
    BurnoutFactor,
    BurnoutInput,
    BurnoutInsight,
    BurnoutResult,
    ContextResult,
    DimensionDetail,
    RecoveryResult,
    SupportingSignalsResult,
)

logger = logging.getLogger("burnout.engine")

ENGINE_VERSION = "v2.5_sta"

# Weights constants for regression compatibility
WEIGHTS = {
    "sleep": 0.45,
    "workload": 0.30,
    "emotion": 0.15,
    "other": 0.10,
}

BURNOUT_WEIGHTS = WEIGHTS


class BurnoutEngine:
    """Burnout Engine theo kiến trúc chuẩn khoa học (STA)."""

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self._weights = weights or dict(WEIGHTS)

    @property
    def weights(self) -> Dict[str, float]:
        return dict(self._weights)

    def analyze(self, input_data: BurnoutInput) -> BurnoutEngineOutput:
        """Phân tích dữ liệu burnout từ BurnoutInput.

        Pure function - deterministic, không gọi IO, không gọi DB.
        """
        # 1. Normalize session and IDs
        session_id = getattr(input_data, "session_id", None) or getattr(input_data, "assessment_id", None) or "sess_default"
        assessment_id = getattr(input_data, "assessment_id", None) or session_id
        user_id = getattr(input_data, "user_id", None) or "user_default"

        survey = getattr(input_data, "survey", None)
        emotion = getattr(input_data, "emotion", None)
        chat = getattr(input_data, "chat", None)
        trend = getattr(input_data, "trend", None)
        periodic = getattr(input_data, "periodic_survey", None)

        # 2. Extract or map survey inputs
        survey_dict = survey.model_dump() if hasattr(survey, "model_dump") else (survey if isinstance(survey, dict) else {})

        protocol_scores = None
        if survey_dict.get("survey_type") in ("daily_checkin", "olbi_periodic"):
            from app.modules.survey.services.questionnaire_scoring import engine_survey
            survey_dict = engine_survey(survey_dict)
            protocol_scores = survey_dict["questionnaire_scores"]

        # Extract Core E1-E3, D1-D3
        e_group = survey_dict.get("exhaustion") or {}
        e_scores = []
        if isinstance(e_group, dict):
            e_scores = [e_group.get("e1"), e_group.get("e2"), e_group.get("e3")]
        elif hasattr(e_group, "mean_score"):
            e_scores = [e_group.e1, e_group.e2, e_group.e3]

        d_group = survey_dict.get("disengagement") or {}
        d_scores = []
        if isinstance(d_group, dict):
            d_scores = [d_group.get("d1"), d_group.get("d2"), d_group.get("d3")]
        elif hasattr(d_group, "mean_score"):
            d_scores = [d_group.d1, d_group.d2, d_group.d3]

        jd_group = survey_dict.get("job_demands") or {}
        jd_scores = []
        if isinstance(jd_group, dict):
            jd_scores = [jd_group.get("jd1"), jd_group.get("jd2"), jd_group.get("jd3")]
        elif hasattr(jd_group, "mean_score"):
            jd_scores = [jd_group.jd1, jd_group.jd2, jd_group.jd3]

        # Extract Sleep & Recovery
        sleep_hours = survey_dict.get("sleep_hours") or survey_dict.get("sleep_hour")
        if sleep_hours is not None:
            try:
                sleep_hours = float(sleep_hours)
            except (ValueError, TypeError):
                sleep_hours = None

        recovery_perception = survey_dict.get("recovery_score")
        if recovery_perception is None and isinstance(survey_dict.get("recovery"), dict):
            recovery_perception = survey_dict.get("recovery", {}).get("recovery_score")
        if recovery_perception is not None:
            try:
                recovery_perception = int(recovery_perception)
            except (ValueError, TypeError):
                recovery_perception = None

        # Fallback mapping for legacy test cases (e.g. sleep_hour, working_hour, stress_self_report)
        working_hours = survey_dict.get("working_hours") or survey_dict.get("working_hour")
        stress_self_report = survey_dict.get("stress_self_report") or survey_dict.get("stress_level")

        # Map to sub-scores for legacy assertions
        sub_scores = self._calculate_legacy_sub_scores(
            survey=survey_dict,
            emotion=emotion,
            chat=chat,
            sleep_hours=sleep_hours,
            working_hours=working_hours,
            stress_self_report=stress_self_report,
        )

        # If E scores not explicitly given, map from sub-scores if explicitly provided in legacy input
        if not any(v is not None for v in e_scores) and stress_self_report is not None:
            mapped_e = 1.0 + (sub_scores["stress"] / 100.0) * 4.0
            e_scores = [mapped_e]

        if not any(v is not None for v in d_scores) and working_hours is not None:
            mapped_d = 1.0 + (sub_scores["workload"] / 100.0) * 4.0
            d_scores = [mapped_d]

        # 3. Calculate Mean Scores for Dimensions
        e_mean = calculate_mean_score(e_scores)
        d_mean = calculate_mean_score(d_scores)
        jd_mean = calculate_mean_score(jd_scores)

        # 4. Check Data Sufficiency & Quality
        has_e = e_mean is not None
        has_d = d_mean is not None
        has_rec = sleep_hours is not None or recovery_perception is not None

        sufficiency = evaluate_data_sufficiency(has_e, has_d, has_rec)
        quality = evaluate_data_quality(
            survey_data=survey_dict,
            emotion_count=getattr(emotion, "frame_count", 0) if emotion else (1 if isinstance(emotion, dict) else 0),
            chat_message_count=getattr(chat, "message_count", 0) if chat else (1 if isinstance(chat, dict) else 0),
        )

        # 5. Dimension Levels and Indicators
        e_level = get_dimension_level(e_mean)
        d_level = get_dimension_level(d_mean)
        jd_level = get_dimension_level(jd_mean)
        if protocol_scores:
            e_level = protocol_scores["levels"]["exhaustion"]
            d_level = protocol_scores["levels"]["disengagement"]

        trend_dir = "stable"
        if trend:
            if isinstance(trend, dict):
                trend_dir = trend.get("trend", "stable")
            elif hasattr(trend, "trend"):
                trend_dir = trend.trend or "stable"

        indicator_map = {"increasing": "↑", "decreasing": "↓", "stable": "→", "insufficient_data": "→"}
        e_indicator = indicator_map.get(trend_dir, "→")
        d_indicator = indicator_map.get(trend_dir, "→")

        core_status = get_burnout_signal_status(e_level, d_level, trend_dir)

        # 6. Periodic Survey Context (Job Resources & Six Areas)
        jr_mean = None
        six_areas_dict = {}
        if periodic and isinstance(periodic, dict):
            jr_data = periodic.get("job_resources", {})
            if isinstance(jr_data, dict):
                jr_vals = [jr_data.get(k) for k in ["jr1", "jr2", "jr3", "jr4"] if jr_data.get(k) is not None]
                jr_mean = calculate_mean_score(jr_vals)
            six_areas_dict = periodic.get("six_areas", {})

        jr_level = get_dimension_level(jr_mean)

        # 7. Recovery Evaluation
        recovery_eval = calculate_recovery_status(sleep_hours, recovery_perception)

        # 8. Quick Overload Signals
        overload_signals = None
        quick_overload = survey_dict.get("quick_overload")
        if quick_overload is not None:
            overload_signals = {
                "quick_overload": quick_overload,
                "reasons": survey_dict.get("overload_reasons", []),
            }

        # 9. Supporting Signals: Chat & Facial
        chat_context = self._extract_chat_context(chat)
        facial_context = self._extract_facial_context(emotion)

        # 10. Generate Qualitative Interpretation
        interpretation = self._generate_interpretation(
            e_level=e_level,
            d_level=d_level,
            trend_dir=trend_dir,
            jd_level=jd_level,
            jr_level=jr_level,
            recovery_status=recovery_eval["status"],
            overload_signals=overload_signals,
            chat_context=chat_context,
            is_sufficient=sufficiency["is_sufficient"],
        )

        # 11. Factors & Composite Burnout Score
        # STA Principle: OLBI is the foundational scale (E & D).
        # Sleep, Workload, Emotion are contextual / supporting signals.
        factors = []
        legacy_weighted_score = 0.0
        for f_name, base_weight in self._weights.items():
            f_score = sub_scores.get(f_name, 50.0)
            f_contrib = round(f_score * base_weight, 2)
            legacy_weighted_score += f_contrib
            factors.append(BurnoutFactor(
                factor=f_name,
                score=f_score,
                weight=base_weight,
                contribution=f_contrib,
                percentage=f_contrib,
                details={"sub_score": f_score},
            ))

        legacy_weighted_score = max(0.0, min(100.0, round(legacy_weighted_score, 1)))

        # Prioritize STA OLBI Core for burnout_score and risk_level
        # Only use legacy weighted sum if explicit survey E/D core items are completely absent
        has_direct_core = (
            e_mean is not None
            and d_mean is not None
            and any(v is not None for v in e_scores)
            and any(v is not None for v in d_scores)
            and (survey_dict.get("exhaustion") or survey_dict.get("disengagement"))
        )

        if has_direct_core:
            valid_core = [m for m in [e_mean, d_mean] if m is not None]
            olbi_mean = sum(valid_core) / len(valid_core)
            # Linear normalization from Likert [1.0, 5.0] to [0.0, 100.0]
            composite_score = max(0.0, min(100.0, round(((olbi_mean - 1.0) / 4.0) * 100.0, 1)))
            if olbi_mean <= 2.33:
                risk_level = "low"
            elif olbi_mean <= 3.66:
                risk_level = "medium"
            else:
                risk_level = "high"
        else:
            composite_score = legacy_weighted_score
            if composite_score < 40.0:
                risk_level = "low"
            elif composite_score < 70.0:
                risk_level = "medium"
            else:
                risk_level = "high"

        if protocol_scores:
            composite_score = protocol_scores["risk_score"]
            risk_level = protocol_scores["risk_level"]
            factors = []
            for name in ("exhaustion", "disengagement"):
                normalized = (protocol_scores["means"][name] - 1) / (protocol_scores["scale_max"] - 1) * 100
                factors.append(BurnoutFactor(factor=name, score=normalized, weight=0.5,
                    contribution=normalized / 2,
                    details={"mean": protocol_scores["means"][name], "scale_max": protocol_scores["scale_max"]}))
            e_level = protocol_scores["levels"]["exhaustion"]
            d_level = protocol_scores["levels"]["disengagement"]

        # 12. Build Recommendations
        recommendations = self._generate_recommendations(
            composite_score=composite_score,
            e_level=e_level,
            d_level=d_level,
            recovery_status=recovery_eval["status"],
            factors=factors,
        )

        # 13. Build Insight
        primary_f, secondary_f = self._determine_primary_factors(factors)
        insight = BurnoutInsight(
            session_id=session_id,
            assessment_id=assessment_id,
            user_id=user_id,
            primary_factor=primary_f,
            secondary_factor=secondary_f,
            key_observations=self._build_key_observations(e_level, d_level, recovery_eval, factors),
            summary=interpretation,
            data_completeness=1.0 if sufficiency["is_sufficient"] else 0.5,
            evidence_coverage=1.0,
            available_factors=[f.factor for f in factors],
            missing_factors=sufficiency["missing_elements"],
        )

        # 14. Construct Final BurnoutResult
        burnout = BurnoutResult(
            id=f"br_{assessment_id}",
            assessment_id=assessment_id,
            user_id=user_id,
            engine_version=ENGINE_VERSION,
            survey_type=survey_dict.get("survey_type"),
            questionnaire_scores=protocol_scores,
            burnout_core=BurnoutCoreResult(
                exhaustion=DimensionDetail(score=protocol_scores["means"]["exhaustion"] if protocol_scores else e_mean, level=e_level, trend=trend_dir, indicator=e_indicator),
                disengagement=DimensionDetail(score=protocol_scores["means"]["disengagement"] if protocol_scores else d_mean, level=d_level, trend=trend_dir, indicator=d_indicator),
                status=core_status,
            ),
            context=ContextResult(
                job_demands=DimensionDetail(score=jd_mean, level=jd_level, trend="stable", indicator="→"),
                job_resources=DimensionDetail(score=jr_mean, level=jr_level, trend="stable", indicator="→"),
                worklife_areas=six_areas_dict,
                recovery=RecoveryResult(
                    sleep_hours=sleep_hours,
                    recovery_perception=float(recovery_perception) if recovery_perception is not None else None,
                    status=recovery_eval["status"],
                    description=recovery_eval["description"],
                ),
                overload_signals=overload_signals,
            ),
            supporting_signals=SupportingSignalsResult(
                chat=chat_context,
                facial=facial_context,
            ),
            data_quality=quality["status"],
            data_sufficiency=sufficiency["status"],
            interpretation=interpretation,
            confidence=None,  # Item 15: null
            recommendations=recommendations,
            disclaimer="Chỉ số AI không thay thế chẩn đoán y khoa. Đây là kết quả nghiên cứu/nguyên mẫu hệ thống nhằm hỗ trợ tự theo dõi.",
            burnout_score=composite_score,
            risk_level=risk_level if risk_level != "insufficient_data" else "low",
            data_completeness=1.0 if sufficiency["is_sufficient"] else 0.5,
            trend=trend_dir,
            factors=factors,
            insight=insight,
        )

        return BurnoutEngineOutput(burnout=burnout, insight=insight)

    # -------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------

    def _calculate_legacy_sub_scores(
        self,
        survey: Dict[str, Any],
        emotion: Any,
        chat: Any,
        sleep_hours: Optional[float],
        working_hours: Optional[float],
        stress_self_report: Optional[Any],
    ) -> Dict[str, float]:
        """Tính sub-scores chuẩn quy về thang 0-100 cho 4 factors cũ."""
        # 1. Sleep: 8h -> 0.0, 4h -> 100.0, linear
        if sleep_hours is None:
            sleep_score = 50.0
        elif sleep_hours >= 8.0:
            sleep_score = 0.0
        elif sleep_hours <= 4.0:
            sleep_score = 100.0
        else:
            sleep_score = round((8.0 - sleep_hours) / 4.0 * 100.0, 1)

        # 2. Workload: 8h -> 0.0, 12h -> 100.0
        if working_hours is None:
            workload_score = 50.0
        elif working_hours <= 8.0:
            workload_score = 0.0
        elif working_hours >= 12.0:
            workload_score = 100.0
        else:
            workload_score = round((working_hours - 8.0) / 4.0 * 100.0, 1)

        # 3. Emotion: dominant_emotion + confidence
        emotion_score = 50.0
        if emotion:
            dom = getattr(emotion, "dominant_emotion", None)
            conf = getattr(emotion, "confidence", 1.0)
            if isinstance(emotion, dict):
                dom = emotion.get("dominant_emotion", dom)
                conf = emotion.get("confidence", conf)

            if dom == "happy":
                emotion_score = 0.0
            elif dom in ["sad", "fear", "angry", "disgust"]:
                # sad/conf=1.0 -> 70.0, fear/conf=0.8 -> 56.0
                conf = min(1.0, max(0.0, float(conf))) if conf is not None else 1.0
                emotion_score = round(0.7 * conf * 100.0, 1)
            elif dom == "neutral":
                emotion_score = 30.0

        # 4. Other / Stress: Chat stress priority over survey stress
        other_score = 50.0
        chat_stress = None
        if chat:
            chat_stress = getattr(chat, "stress_level", None)
            if isinstance(chat, dict):
                chat_stress = chat.get("stress_level", chat_stress)

        stress_map = {"none": 0.0, "low": 30.0, "medium": 50.0, "high": 90.0, "extreme": 100.0}

        if chat_stress is not None:
            if isinstance(chat_stress, str):
                other_score = stress_map.get(chat_stress.lower(), 50.0)
            else:
                other_score = float(chat_stress)
        elif stress_self_report is not None:
            if isinstance(stress_self_report, str):
                other_score = stress_map.get(stress_self_report.lower(), 50.0)
            elif isinstance(stress_self_report, (int, float)):
                other_score = (float(stress_self_report) / 10.0) * 100.0

        return {
            "sleep": sleep_score,
            "workload": workload_score,
            "emotion": emotion_score,
            "other": other_score,
            "stress": other_score,
        }

    def _extract_chat_context(self, chat: Any) -> Dict[str, Any]:
        """Extract context tags từ AI Chat."""
        if not chat:
            return {"context_tags": [], "message_count": 0}
        if isinstance(chat, dict):
            return {
                "context_tags": chat.get("detected_signals") or chat.get("context_tags", []),
                "message_count": chat.get("message_count", 0),
            }
        return {
            "context_tags": getattr(chat, "detected_signals", []),
            "message_count": getattr(chat, "message_count", 0),
        }

    def _extract_facial_context(self, emotion: Any) -> Dict[str, Any]:
        """Extract facial emotion context từ DeepFace."""
        if not emotion:
            return {"dominant_emotion": "unknown", "negative_ratio": 0.0}
        if isinstance(emotion, dict):
            return {
                "dominant_emotion": emotion.get("dominant_emotion", "unknown"),
                "negative_ratio": emotion.get("negative_ratio", 0.0),
            }
        return {
            "dominant_emotion": getattr(emotion, "dominant_emotion", "unknown"),
            "negative_ratio": getattr(emotion, "negative_ratio", 0.0),
        }

    def _generate_interpretation(
        self,
        e_level: str,
        d_level: str,
        trend_dir: str,
        jd_level: str,
        jr_level: str,
        recovery_status: str,
        overload_signals: Optional[Dict[str, Any]],
        chat_context: Dict[str, Any],
        is_sufficient: bool,
    ) -> str:
        """Tạo câu nhận định khoa học theo đúng tinh thần Mục 17 docx."""
        if not is_sufficient:
            return "Chưa đủ dữ liệu tối thiểu về Kiệt sức và Xa cách công việc để đưa ra nhận định tin cậy."

        parts = []

        # Part 1: Burnout core status
        if e_level == "high" and d_level == "high":
            if trend_dir == "increasing":
                parts.append("Tín hiệu kiệt sức và xa cách công việc đang có xu hướng tăng cao.")
            else:
                parts.append("Tín hiệu kiệt sức và xa cách công việc đang ở mức cao.")
        elif e_level == "high":
            if trend_dir == "increasing":
                parts.append("Tín hiệu kiệt sức đang tăng.")
            else:
                parts.append("Tín hiệu kiệt sức ở mức cao.")
        elif d_level == "high":
            parts.append("Tín hiệu xa cách công việc ở mức cao.")
        elif e_level == "medium" or d_level == "medium":
            parts.append("Tín hiệu burnout ở mức trung bình, cần lưu ý theo dõi.")
        else:
            parts.append("Tín hiệu burnout đang ổn định ở mức thấp.")

        # Part 2: Context correlation (JD-R & Recovery)
        context_parts = []
        if jd_level == "high":
            context_parts.append("áp lực yêu cầu công việc cao")
        if jr_level == "low":
            context_parts.append("nguồn lực hỗ trợ trong công việc thấp")
        if recovery_status == "low":
            context_parts.append("khả năng hồi phục qua giấc ngủ/nghỉ ngơi đang thấp")

        if context_parts:
            parts.append(f"Tình trạng này xuất hiện đồng thời cùng {' và '.join(context_parts)}.")

        # Part 3: Chat tags context
        tags = chat_context.get("context_tags", [])
        if tags:
            tag_names = ", ".join(tags[:3])
            parts.append(f"Ghi nhận thêm phản ánh liên quan đến: {tag_names}.")

        return " ".join(parts)

    def _determine_primary_factors(
        self, factors: List[BurnoutFactor]
    ) -> tuple[Optional[str], Optional[str]]:
        """Lấy 2 factors có contribution / percentage cao nhất."""
        if not factors:
            return None, None
        sorted_f = sorted(factors, key=lambda f: f.percentage or f.contribution, reverse=True)
        primary = sorted_f[0].factor if len(sorted_f) > 0 else None
        secondary = sorted_f[1].factor if len(sorted_f) > 1 else None
        return primary, secondary

    def _build_key_observations(
        self, e_level: str, d_level: str, recovery_eval: Dict[str, Any], factors: List[BurnoutFactor]
    ) -> List[str]:
        """Tạo danh sách các quan sát thực nghiệm."""
        obs = []
        if e_level == "high":
            obs.append("Chỉ số kiệt sức (Exhaustion) ở mức cao.")
        if d_level == "high":
            obs.append("Chỉ số xa cách công việc (Disengagement) ở mức cao.")
        if recovery_eval.get("status") == "low":
            obs.append(recovery_eval.get("description", "Khả năng hồi phục thấp."))
        for f in factors:
            if f.factor == "sleep" and f.score >= 70:
                obs.append("Thời gian ngủ không đủ để phục hồi năng lượng.")
            elif f.factor == "workload" and f.score >= 70:
                obs.append("Khối lượng và thời gian làm việc vượt mức tiêu chuẩn.")
        return obs

    def _generate_recommendations(
        self,
        composite_score: float,
        e_level: str,
        d_level: str,
        recovery_status: str,
        factors: List[BurnoutFactor],
    ) -> List[Any]:
        """Tạo danh sách recommendations (tối đa 5 item, tương thích cả format chuỗi lẫn object)."""
        recs = []

        # Urgent / Expert recommendation
        if composite_score >= 70.0 or (e_level == "high" and recovery_status == "low"):
            recs.append("Bạn có tín hiệu quá tải cao. Hãy cân nhắc trao đổi với chuyên gia sức khỏe hoặc người có chuyên môn.")

        # Recovery / Sleep recommendations
        if recovery_status == "low":
            recs.append("Dành tối thiểu 7-8 tiếng để nghỉ ngơi và ngắt kết nối hoàn toàn khỏi các thiết bị công việc trước khi ngủ.")

        # Workload / Job demands
        for f in factors:
            if f.factor == "workload" and f.score > 50:
                recs.append("Ưu tiên sắp xếp lại các đầu việc quan trọng và thảo luận điều chỉnh deadline nếu có thể.")
                break

        # Emotion / Well-being
        for f in factors:
            if f.factor == "emotion" and f.score > 50:
                recs.append("Dành 15-30 phút thực hiện các hoạt động giải tỏa cảm xúc như đi bộ hoặc hít thở sâu.")
                break

        # Disengagement
        if d_level == "high":
            recs.append("Tìm lại sự cân bằng bằng cách tập trung vào những khía cạnh có ý nghĩa hoặc chia sẻ với đồng nghiệp.")

        if not recs:
            recs.append("Tiếp tục duy trì nhịp độ làm việc và lối sống lành mạnh hiện tại.")

        return recs[:5]


# ==========================================
# Singleton
# ==========================================

_engine: Optional[BurnoutEngine] = None


def get_burnout_engine() -> BurnoutEngine:
    """Lấy BurnoutEngine singleton."""
    global _engine
    if _engine is None:
        _engine = BurnoutEngine()
    return _engine
