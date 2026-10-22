"""Shared inclusive calendar-date window, interpreted in UTC+7."""
from datetime import date, datetime, time, timedelta, timezone

from app.modules.survey.services.questionnaire_history import LOCAL_TIMEZONE, record_time


def date_window(start_date=None, end_date=None, days=None, now=None):
    now = now or datetime.now(timezone.utc)
    if (start_date is None) != (end_date is None):
        raise ValueError("start_date and end_date must be provided together")
    if start_date is None:
        if days is None:
            return None
        end_date = now.astimezone(LOCAL_TIMEZONE).date()
        start_date = end_date - timedelta(days=days - 1)
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise ValueError("Invalid calendar dates")
    count = (end_date - start_date).days + 1
    if not 1 <= count <= 3650:
        raise ValueError("Date range must contain 1 to 3650 days")
    return (datetime.combine(start_date, time.min, LOCAL_TIMEZONE).astimezone(timezone.utc),
            datetime.combine(end_date + timedelta(days=1), time.min, LOCAL_TIMEZONE).astimezone(timezone.utc), count)


def in_window(timestamp, window):
    if timestamp is None:
        return False
    normalized = record_time({"completed_at": timestamp})
    return normalized is not None and (window is None or window[0] <= normalized < window[1])


def calendar_day(timestamp):
    normalized = record_time({"completed_at": timestamp})
    return normalized.astimezone(LOCAL_TIMEZONE).date() if normalized else None
