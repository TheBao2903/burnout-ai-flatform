"""Deterministic, versioned evidence for dashboard charts and AI interpretation.

Missing is never neutral/zero. Daily 1–5 and OLBI 1–4 remain separate.
Only selected-window observations are facts; current job profile is background.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
from math import isfinite

from app.modules.dashboard.services.date_window import calendar_day, date_window, in_window
from app.modules.dashboard.services.olbi_progress import build_olbi_progress
from app.modules.survey.services.questionnaire_history import daily_records, record_time
from app.modules.survey.services.questionnaire_scoring import dimension_level, validate_answers

EVIDENCE_VERSION = "dashboard-context-v2"
DAILY_LIMIT = 120


def number(value, minimum, maximum):
    return float(value) if type(value) in (int, float) and isfinite(value) and minimum <= value <= maximum else None


def first_value(*values):
    return next((value for value in values if value is not None), None)


def mean(values):
    values = [value for value in values if value is not None]
    return round(sum(values) / len(values), 4) if values else None


def summarize(samples, minimum=1, maximum=5):
    valid = [(date, value) for date, value in samples if value is not None]
    values = [value for _, value in valid]
    middle = len(values) // 2
    early = mean(values[:middle]) if middle else None
    late = mean(values[middle:]) if middle else None
    half_delta = round(late - early, 4) if early is not None else None
    trend = ("insufficient_data" if len(values) < 3 else "increasing" if half_delta >= 0.3
             else "decreasing" if half_delta <= -0.3 else "stable")
    average = mean(values)
    return {"count": len(values), "missing": len(samples) - len(values), "scale": [minimum, maximum],
            "mean": average, "min": min(values) if values else None, "max": max(values) if values else None,
            "first": values[0] if values else None, "last": values[-1] if values else None,
            "first_at": valid[0][0] if valid else None, "last_at": valid[-1][0] if valid else None,
            "change_first_last": round(values[-1] - values[0], 4) if len(values) >= 2 else None,
            "change_previous": round(values[-1] - values[-2], 4) if len(values) >= 2 else None,
            "early_half_mean": early, "late_half_mean": late, "half_delta": half_delta,
            "trend": trend, "trend_method": "chronological_half_means_application_threshold_0.3_min_3_samples",
            "level": dimension_level(average, maximum) if average is not None and minimum == 1 else None}


def sample_timeline(rows, limit=DAILY_LIMIT):
    if len(rows) <= limit:
        return rows
    indices = {round(i * (len(rows) - 1) / (limit - 1)) for i in range(limit)}
    return [rows[index] for index in sorted(indices)]


def build_dashboard_evidence(records, start_date, end_date, *, profile=None, resources=None,
                             emotions=None, chats=None, source_status=None, now=None):
    now = now or datetime.now(timezone.utc)
    window = date_window(start_date, end_date)
    scope_records = [r for r in records if r.get("status", "completed") == "completed"
                     and in_window(record_time(r), window) and record_time(r) <= now]
    daily_candidates = [r for r in scope_records if (r.get("survey") or {}).get("survey_type") != "olbi_periodic"]
    valid_daily, invalid_daily = [], 0
    for record in daily_candidates:
        raw = record.get("survey") or {}
        try:
            validate_answers(raw)
        except (ValueError, TypeError):
            invalid_daily += 1
            continue
        valid_daily.append(record)
    selected = list(reversed(daily_records(valid_daily, days=window[2], now=window[1] - timedelta(microseconds=1))))
    rows, reasons, notes, deadlines = [], Counter(), [], Counter()
    for record in selected:
        raw = record.get("survey") or {}
        recovery = raw.get("recovery") or {}
        quick = raw.get("quick_overload_data") or {}
        changes = raw.get("work_changes") or {}
        row = {"date": calendar_day(record_time(record)).isoformat(), "observed_at": record_time(record).isoformat(),
               "protocol": raw.get("questionnaire_version"), "legacy_unversioned": not bool(raw.get("survey_type")),
               "answers": {}, "exhaustion": None, "disengagement": None, "job_demands": None}
        for group, prefix in (("exhaustion", "e"), ("disengagement", "d"), ("job_demands", "jd")):
            answers = raw.get(group) or {}
            valid = {f"{prefix}{i}": number(answers.get(f"{prefix}{i}"), 1, 5) for i in range(1, 4)}
            row["answers"][group] = valid
            # Partial legacy groups are explicitly missing, not fabricated from stress.
            row[group] = mean(list(valid.values())) if all(v is not None for v in valid.values()) else None
        row["sleep_hours"] = number(first_value(raw.get("sleep_hours"), recovery.get("sleep_hours")), 0, 24)
        row["recovery_score"] = number(first_value(raw.get("recovery_score"), recovery.get("recovery_score")), 1, 5)
        row["quick_overload"] = number(first_value(raw.get("quick_overload"), quick.get("rating"), quick.get("overload_rating")), 1, 5)
        row["overtime_hours_today"] = number(first_value(raw.get("overtime_hours_today"), changes.get("overtime_hours")), 0, 24)
        if row["overtime_hours_today"] is None and first_value(raw.get("has_overtime_today"), changes.get("had_overtime")) is False:
            row["overtime_hours_today"] = 0.0
        row["deadline"] = first_value(raw.get("current_deadline_pressure"), changes.get("has_deadline"))
        if row["deadline"] in ("low", "medium", "high", "extreme"):
            deadlines[row["deadline"]] += 1
        else:
            row["deadline"] = None
        row["reasons"] = list(dict.fromkeys(str(v)[:300] for v in (raw.get("overload_reasons") or quick.get("reasons") or []) if isinstance(v, str)))
        reasons.update(row["reasons"])
        other = first_value(raw.get("other_overload_reason"), quick.get("other_reason"))
        row["user_note"] = str(other)[:1000] if other else None
        if row["user_note"] and row["user_note"] not in notes:
            notes.append(row["user_note"])
        rows.append(row)

    dimensions = {key: summarize([(row["observed_at"], row[key]) for row in rows], 0 if key == "sleep_hours" else 1,
                                24 if key == "sleep_hours" else 5)
                  for key in ("exhaustion", "disengagement", "job_demands", "sleep_hours", "recovery_score", "quick_overload")}
    overload_rows = [row for row in rows if row["quick_overload"] is not None]
    overtime_rows = [row for row in rows if row["overtime_hours_today"] is not None]
    olbi = build_olbi_progress(scope_records, start_date=start_date, end_date=end_date, now=now)
    olbi_points = olbi["points"]
    olbi["points"] = sample_timeline(olbi_points)
    olbi["timeline_sampling"] = {"total": len(olbi_points), "included": len(olbi["points"]), "method": "all_or_evenly_spaced_including_endpoints"}
    olbi_ids = {point["id"] for point in olbi_points[-2:]}
    olbi["latest_raw_answers"] = [{"observed_at": record_time(record).isoformat(),
                                  "exhaustion": record["survey"]["exhaustion"], "disengagement": record["survey"]["disengagement"]}
                                 for record in scope_records if record.get("id") in olbi_ids]

    profile = profile or {}
    profile_fields = ("job_title", "industry_code", "standard_working_hours_per_day", "work_days_per_week",
                      "average_overtime_hours_per_week")
    job_profile = {key: str(profile[key])[:200] if profile.get(key) is not None else None for key in profile_fields[:2]}
    for key, maximum in (("standard_working_hours_per_day", 24), ("work_days_per_week", 7), ("average_overtime_hours_per_week", 168)):
        job_profile[key] = number(profile.get(key), 0, maximum)
    from app.modules.burnout.helpers.industry_archetypes import resolve_industry_context
    industry = resolve_industry_context(industry_code=job_profile.get("industry_code"), job_title=job_profile.get("job_title"))
    job_profile["industry_background"] = {"name": industry.name, "vocabulary_hints": industry.vocabulary_hints,
                                           "possible_stressors_not_user_facts": industry.stressors_context}
    job_profile["temporal_scope"] = "current_profile_not_verified_for_historical_window"

    environment = []
    for record in resources or []:
        timestamp = record_time({"completed_at": record.get("submitted_at"), "created_at": record.get("created_at")})
        if not in_window(timestamp, window) or timestamp > now:
            continue
        jr = {key: number((record.get("job_resources") or {}).get(key), 1, 5) for key in ("jr1", "jr2", "jr3", "jr4")}
        areas = {key: number((record.get("six_areas") or {}).get(key), 1, 5)
                 for key in ("workload", "control", "reward", "community", "fairness", "values")}
        if not any(value is not None for value in list(jr.values()) + list(areas.values())):
            continue
        environment.append({"observed_at": timestamp.isoformat(), "job_resources": jr,
                            "job_resources_mean": mean(list(jr.values())), "six_areas": areas,
                            "scale": [1, 5], "higher_is": "more_resources_better_worklife_fit"})
    environment.sort(key=lambda row: row["observed_at"])

    def observed(timestamp):
        value = record_time({"completed_at": timestamp})
        return value is not None and value <= now and in_window(value, window)
    facial = [row for row in emotions or [] if observed(row.get("analyzed_at") or row.get("created_at"))]
    facial_counts = Counter(str(row.get("dominant_emotion")) for row in facial if row.get("dominant_emotion"))
    confidences = [number(row.get("confidence"), 0, 1) for row in facial]
    user_chats = [row for row in chats or [] if row.get("role") == "user" and observed(row.get("created_at"))]
    user_chats.sort(key=lambda row: record_time({"completed_at": row.get("created_at")}))
    analyzed_chats = [row for row in user_chats if isinstance(row.get("analysis"), dict) and row["analysis"]]
    chat_signals = Counter(str(signal)[:150] for row in analyzed_chats
                           for signal in row["analysis"].get("detected_signals", []) if isinstance(signal, str))
    chat_scores = {key: summarize([(str(row.get("created_at")), number((row["analysis"].get(key) or {}).get("score"), 0, 100)) for row in analyzed_chats], 0, 100)
                   for key in ("stress_level", "fatigue_signal", "motivation_level", "work_avoidance_signal", "sleep_problem_signal", "emotional_negative_signal", "workload_signal", "burnout_related_signal")}
    # Chat scores do not share daily/OLBI trend thresholds or application bands.
    for stats in chat_scores.values():
        stats["trend"] = "not_interpreted_secondary_model_estimates"
        stats["trend_method"] = None
    uncertainty = [number(row["analysis"].get("uncertainty"), 0, 1) for row in analyzed_chats]
    environment_summary = {group: {key: summarize([(row["observed_at"], row[group][key]) for row in environment])
                                   for key in keys} for group, keys in (
                                       ("job_resources", ("jr1", "jr2", "jr3", "jr4")),
                                       ("six_areas", ("workload", "control", "reward", "community", "fairness", "values")))}
    for group in environment_summary.values():
        for stats in group.values():
            stats["level"] = None  # Higher resources/fit are favorable; no borrowed E/D bands.
    coverage = {"daily_days": len(rows), "daily_raw_records": len(daily_candidates), "invalid_daily_records": invalid_daily,
                "daily_complete_core_days": sum(row["exhaustion"] is not None and row["disengagement"] is not None for row in rows),
                "selected_calendar_days": window[2], "daily_coverage_ratio": round(len(rows) / window[2], 4),
                "olbi_records": len(olbi_points), "environment_records": len(environment),
                "facial_records": len(facial), "chat_messages": len(user_chats), "analyzed_chat_messages": len(analyzed_chats),
                "source_status": source_status or {"surveys": "available"}}
    limitations = ["Đây là dữ liệu tự theo dõi, không phải chẩn đoán hoặc bằng chứng nhân quả.",
                   "Hồ sơ nghề nghiệp là thông tin hiện tại; áp lực thường gặp của ngành không phải sự việc người dùng đã trải qua.",
                   "Ngủ, hồi phục và quá tải có thể chứa giá trị mặc định từ giao diện cũ; không xem là phép đo khách quan."]
    if len(rows) < 3:
        limitations.append("Chưa đủ ba ngày check-in để mô tả xu hướng liên tục; hai mẫu chỉ cho phép so sánh hai thời điểm.")
    if len(olbi_points) < 2:
        limitations.append("Chưa đủ hai lần OLBI trong khoảng đã chọn để so sánh thay đổi định kỳ.")
    missing = [key for key, stats in dimensions.items() if not stats["count"]]
    if missing:
        labels = {"exhaustion": "cạn kiệt", "disengagement": "mất gắn kết", "job_demands": "yêu cầu công việc", "sleep_hours": "giờ ngủ", "recovery_score": "hồi phục", "quick_overload": "mức quá tải"}
        limitations.append("Chưa thu thập đủ: " + ", ".join(labels[key] for key in missing) + ".")
    for source, status in coverage["source_status"].items():
        if status != "available":
            label = {"surveys": "khảo sát", "profile": "hồ sơ nghề nghiệp", "work_environment": "môi trường làm việc", "facial": "ước lượng khuôn mặt", "chat": "hội thoại"}.get(source, source)
            limitations.append(f"Nguồn {label}: " + ("chỉ đọc 500 bản ghi gần nhất, có thể thiếu dữ liệu của khoảng quá khứ." if status == "recent_500_records_only" else "chưa truy cập được; không được hiểu là không có vấn đề ở nguồn này."))
    if len(environment) > 12:
        limitations.append("Chi tiết môi trường làm việc chỉ kèm 12 lần gần nhất; thống kê vẫn dùng tất cả lần trong khoảng.")
    if facial:
        limitations.append("Các mẫu khuôn mặt có thể là nhiều khung hình cùng phiên; số mẫu không phải số ngày hay độ tin cậy lâm sàng.")
    if len(rows) > DAILY_LIMIT:
        limitations.append("Chuỗi ngày được lấy mẫu đều; các thống kê vẫn tính trên toàn bộ dữ liệu trong khoảng.")
    refs = [f"daily.dimensions.{key}" for key, stats in dimensions.items() if stats["count"]]
    if overload_rows:
        refs.append("daily.overload")
    if overtime_rows:
        refs.append("daily.overtime")
    if olbi_points:
        refs.append("olbi")
    if environment:
        refs.append("work_environment")
    if facial:
        refs.append("facial_supporting_signals")
    if analyzed_chats:
        refs.append("chat_supporting_signals")
    all_dates = [row["observed_at"] for row in rows] + [point["completed_at"] for point in olbi_points]
    return {"evidence_version": EVIDENCE_VERSION,
            "window": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "timezone": "UTC+07:00", "calendar_days": window[2]},
            "coverage": coverage, "last_observation_at": max(datetime.fromisoformat(value) for value in all_dates).astimezone(timezone.utc).isoformat() if all_dates else None,
            "daily": {"scale": [1, 5], "dimensions": dimensions, "timeline": sample_timeline(rows),
                      "timeline_sampling": {"total": len(rows), "included": min(len(rows), DAILY_LIMIT), "method": "all_or_evenly_spaced_including_endpoints"},
                      "overload": {"observed_days": len(overload_rows), "high_days": sum(row["quick_overload"] >= 4 for row in overload_rows),
                                   "reason_counts": dict(reasons), "untrusted_user_notes": notes[:30]},
                      "overtime": {"observed_days": len(overtime_rows), "total_hours": round(sum(row["overtime_hours_today"] for row in overtime_rows), 2) if overtime_rows else None,
                                   "days_with_overtime": sum(row["overtime_hours_today"] > 0 for row in overtime_rows)},
                      "deadline_counts": dict(deadlines)},
            "olbi": olbi, "work_environment": environment[-12:], "work_environment_summary": environment_summary, "job_profile": job_profile,
            "facial_supporting_signals": {"count": len(facial), "distribution": dict(facial_counts), "mean_model_confidence": mean(confidences),
                                          "mean_emotion_probabilities_0_100": {key: mean([number((row.get("emotions") or {}).get(key), 0, 100) for row in facial]) for key in ("angry", "disgust", "fear", "happy", "sad", "surprise", "neutral")},
                                          "confidence_observed": sum(value is not None for value in confidences),
                                          "meaning": "model_estimates_not_self_report_not_clinical_emotion_or_recovery_measure"},
            "chat_supporting_signals": {"user_messages": len(user_chats), "analyzed_messages": len(analyzed_chats),
                                        "model_extracted_signal_counts": dict(chat_signals), "signal_scores_0_100": chat_scores,
                                        "mean_model_uncertainty": mean(uncertainty), "uncertainty_observed": sum(value is not None for value in uncertainty),
                                        "meaning": "secondary_model_estimates_no_raw_conversations_sent"},
            "scale_rules": {"daily": "1–5; higher E/D/JD worse; higher recovery better", "olbi": "1–4 after reverse scoring; higher E/D worse; raw positive items must not be averaged directly",
                            "cross_scale": "Never average daily and OLBI together or directly subtract them; discuss each trajectory separately",
                            "bands": "Application reference bands only, not validated clinical cutoffs; missing is null, never neutral"},
            "limitations": limitations, "available_evidence_refs": refs,
            "sufficiency": "no_core_data" if not coverage["daily_complete_core_days"] and not olbi_points else "limited" if coverage["daily_complete_core_days"] < 3 and len(olbi_points) < 2 else "descriptive_only"}


def daily_dashboard_view(evidence):
    """Same observed statistics for charts and AI; no AI request in the metrics path."""
    daily = evidence["daily"]
    dimensions = daily["dimensions"]
    if not dimensions["exhaustion"]["count"] or not dimensions["disengagement"]["count"]:
        return {"sta_core": None, "sta_context": None, "sta_trend": [], "synthesized_insight": None}
    sleep = dimensions["sleep_hours"]["mean"]
    recovery = dimensions["recovery_score"]["mean"]
    recovery_status = ("insufficient_data" if sleep is None and recovery is None
                       else "poor" if (sleep is not None and sleep < 6) or (recovery is not None and recovery < 2.5)
                       else "good" if sleep is not None and recovery is not None and sleep >= 7 and recovery >= 3.5
                       else "moderate")
    reason_total = sum(daily["overload"]["reason_counts"].values())
    return {"sta_core": {key: {"score": dimensions[key]["mean"], "level": dimensions[key]["level"],
                               "trend": dimensions[key]["trend"], "label": key} for key in ("exhaustion", "disengagement")},
            "sta_context": {
                "job_demands": {"score": dimensions["job_demands"]["mean"], "level": dimensions["job_demands"]["level"], "label": "Yêu cầu công việc"},
                "recovery": {"avg_sleep_hours": sleep, "avg_recovery_score": recovery, "status": recovery_status},
                "overload_stats": {"overload_count": daily["overload"]["high_days"], "total_checkins": daily["overload"]["observed_days"],
                                   "top_reasons": [{"reason": reason, "count": count, "percentage": round(count / reason_total * 100, 1)}
                                                   for reason, count in sorted(daily["overload"]["reason_counts"].items(), key=lambda item: -item[1])[:5]],
                                   "other_reasons": daily["overload"]["untrusted_user_notes"][:5]},
                "work_changes": {"total_overtime_hours": daily["overtime"]["total_hours"], "overtime_days": daily["overtime"]["days_with_overtime"]}},
            "sta_trend": [{"date": row["date"], "analyzed_at": row["observed_at"], **{key: row[key] for key in dimensions}} for row in daily["timeline"]],
            "synthesized_insight": None}
