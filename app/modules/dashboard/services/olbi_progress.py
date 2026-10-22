"""Read-only OLBI timeline; never mix daily scores or infer clinical recovery."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite

from app.modules.survey.services.questionnaire_history import record_time
from app.modules.dashboard.services.date_window import date_window, in_window
from app.modules.survey.services.questionnaire_scoring import VERSIONS, validate_answers

DIMENSIONS = ("exhaustion", "disengagement")
LABELS = {"exhaustion": "Cạn kiệt năng lượng", "disengagement": "Mất gắn kết"}


def _valid_scores(survey):
    try:
        validate_answers(survey)
        scores = survey["questionnaire_scores"]
        return (survey.get("questionnaire_version") == VERSIONS["olbi_periodic"]
                and scores.get("scale_max") == 4
                and scores.get("scoring_version") == "core-ed-v1"
                and all(type(scores["means"][key]) in (int, float)
                        and isfinite(scores["means"][key])
                        and 1 <= scores["means"][key] <= 4 for key in DIMENSIONS))
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def build_olbi_progress(records, days=None, now=None, start_date=None, end_date=None):
    now = now or datetime.now(timezone.utc)
    window = date_window(start_date, end_date, days, now)
    eligible = {}
    excluded = 0
    for record in records:
        survey = record.get("survey") or {}
        if survey.get("survey_type") != "olbi_periodic":
            continue
        timestamp = record_time(record)
        if (record.get("status") != "completed" or timestamp is None or timestamp > now
                or not record.get("id") or not _valid_scores(survey)):
            if in_window(timestamp, window):
                excluded += 1
            continue
        identity = record.get("assessment_id") or record["id"]
        if identity not in eligible or timestamp > record_time(eligible[identity]):
            eligible[identity] = record

    ordered = sorted(eligible.values(), key=lambda item: (record_time(item), item["id"]))
    all_points = []
    for index, record in enumerate(ordered):
        survey = record["survey"]
        scores = survey["questionnaire_scores"]["means"]
        if not in_window(record_time(record), window):
            continue
        previous = all_points[-1] if all_points else None
        all_points.append({
            "id": record["id"], "assessment_id": record.get("assessment_id"),
            "sequence": index + 1, "completed_at": record_time(record).isoformat(),
            "timestamp": int(record_time(record).timestamp() * 1000),
            "exhaustion": scores["exhaustion"], "disengagement": scores["disengagement"],
            "change_from_previous": {key: round(scores[key] - previous[key], 4) if previous else None
                                     for key in DIMENSIONS},
        })

    first = all_points[0] if all_points else None
    latest = all_points[-1] if all_points else None
    previous = all_points[-2] if len(all_points) >= 2 else None
    comparisons = {}
    for key in DIMENSIONS:
        comparisons[key] = {
            "baseline": first[key] if first else None,
            "latest": latest[key] if latest else None,
            "change_from_baseline": round(latest[key] - first[key], 4) if previous else None,
            "change_from_previous": round(latest[key] - previous[key], 4) if previous else None,
        }
    if previous:
        parts = []
        for key in DIMENSIONS:
            delta = comparisons[key]["change_from_baseline"]
            displayed = Decimal(str(abs(delta))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            parts.append(f"{LABELS[key]} {'giảm' if delta < 0 else 'tăng'} {displayed} điểm"
                         if delta else f"{LABELS[key]} không đổi")
        summary = "So với lần OLBI đầu tiên trong khoảng đã chọn: " + "; ".join(parts) + "."
        deltas = [comparisons[key]["change_from_baseline"] for key in DIMENSIONS]
        direction = ("decreasing" if all(d <= 0 for d in deltas) and any(d < 0 for d in deltas)
                     else "increasing" if all(d >= 0 for d in deltas) and any(d > 0 for d in deltas)
                     else "unchanged" if all(d == 0 for d in deltas) else "mixed")
    else:
        summary = ("Khoảng đã chọn có một lần OLBI. Cần ít nhất hai lần đánh giá trong cùng khoảng để so sánh."
                   if first else "Không có đánh giá OLBI định kỳ trong khoảng đã chọn.")
        direction = "insufficient_data"

    points = all_points
    return {
        "period_days": window[2] if window else None, "scale_max": 4, "total_records": len(ordered),
        "start_date": window[0].astimezone(timezone(timedelta(hours=7))).date().isoformat() if window else None,
        "end_date": (window[1].astimezone(timezone(timedelta(hours=7))) - timedelta(days=1)).date().isoformat() if window else None,
        "visible_records": len(points), "excluded_records": excluded, "points": points,
        "baseline_at": first["completed_at"] if first else None,
        "latest_at": latest["completed_at"] if latest else None,
        "comparisons": comparisons, "direction": direction, "summary": summary,
        "next_due_at": None,
    }
