"""Calendar-day selection for daily check-ins; OLBI has its own timeline."""
from datetime import datetime, timedelta, timezone

LOCAL_TIMEZONE = timezone(timedelta(hours=7))


def record_time(record):
    value = record.get("completed_at") or record.get("created_at")
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def daily_records(records, days=7, now=None):
    """Most recent check-in per local day within an inclusive calendar window."""
    today = (now or datetime.now(timezone.utc)).astimezone(LOCAL_TIMEZONE).date()
    by_day = {}
    for record in records:
        if record.get("survey", {}).get("survey_type") == "olbi_periodic":
            continue
        timestamp = record_time(record)
        if timestamp is None:
            continue
        day = timestamp.astimezone(LOCAL_TIMEZONE).date()
        if not today - timedelta(days=days - 1) <= day <= today:
            continue
        if day not in by_day or timestamp > record_time(by_day[day]):
            by_day[day] = record
    return [by_day[day] for day in sorted(by_day, reverse=True)]


def latest_olbi(records, at=None):
    at = at or datetime.now(timezone.utc)
    candidates = [record for record in records
                  if record.get("survey", {}).get("survey_type") == "olbi_periodic"
                  and record_time(record) is not None and record_time(record) <= at]
    return max(candidates, key=record_time) if candidates else None


def questionnaire_status(records, now=None):
    now = now or datetime.now(timezone.utc)
    latest = latest_olbi(records, now)
    next_due = record_time(latest) + timedelta(days=14) if latest else None
    return {"latest_olbi": latest, "interval_days": 14,
            "next_due_at": next_due.isoformat() if next_due else None,
            "is_due": next_due is None or next_due <= now,
            "today_completed": bool(daily_records(records, days=1, now=now))}
