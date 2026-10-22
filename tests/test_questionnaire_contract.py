"""Regression tests for scoring, raw storage, timelines and API validation."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock
import asyncio

import pytest
from pydantic import ValidationError

from app.modules.survey.services.questionnaire_scoring import (
    POSITIVE, VERSIONS, score_questionnaire,
)
from app.modules.survey.services.questionnaire_history import (
    daily_records, latest_olbi, questionnaire_status,
)
from app.modules.survey.services.survey_analysis_service import SurveyAnalysisService


def answers(kind="olbi_periodic", risk=1):
    periodic = kind == "olbi_periodic"
    result = {"survey_type": kind, "questionnaire_version": VERSIONS[kind]}
    for group, prefix in (("exhaustion", "e"), ("disengagement", "d")):
        result[group] = {f"{prefix}{i}": 5 - risk if periodic and f"{prefix}{i}" in POSITIVE[group] else risk
                         for i in range(1, 9 if periodic else 4)}
    if not periodic:
        result["job_demands"] = {"jd1": 1, "jd2": 3, "jd3": 5}
    return result


@pytest.mark.parametrize("kind,maximum", [("olbi_periodic", 4), ("daily_checkin", 5)])
@pytest.mark.parametrize("extreme", ["low", "high"])
def test_scoring_extremes_and_engine_agree(kind, maximum, extreme):
    from app.modules.burnout.services.burnout_input_builder import BurnoutInputBuilder
    from app.modules.burnout.services.burnout_engine import get_burnout_engine
    payload = answers(kind, risk=1 if extreme == "low" else maximum)
    original = deepcopy(payload)
    scores = score_questionnaire(payload)
    quick = SurveyAnalysisService.analyze(payload)
    built = BurnoutInputBuilder("assessment", "user", survey={"survey": payload}).build()
    result = get_burnout_engine().analyze(built).burnout
    assert scores["risk_score"] == (0 if extreme == "low" else 100)
    assert quick.risk_score == result.burnout_score == scores["risk_score"]
    assert quick.risk_level == result.risk_level == extreme
    assert result.burnout_core.exhaustion.score == scores["means"]["exhaustion"]
    assert result.data_sufficiency == "sufficient"
    assert payload == original
    if kind == "olbi_periodic":
        assert result.context.recovery.sleep_hours is None
        assert result.context.recovery.recovery_perception is None
        assert {factor.factor for factor in result.factors} == {"exhaustion", "disengagement"}
    assert built.to_dict()["survey"] == payload


def test_every_positive_item_is_reversed_once():
    baseline = answers()
    for group, keys in POSITIVE.items():
        assert len(keys) == 4
        for key in keys:
            changed = deepcopy(baseline)
            changed[group][key] = 1
            assert score_questionnaire(changed)["means"][group] == 1 + 3 / 8


@pytest.mark.parametrize("model_name", ["AnalyzeRequest", "SurveySubmitRequest"])
@pytest.mark.parametrize("invalid", [0, 5, 2.5, True, "2", None])
def test_olbi_rejects_invalid_answers(model_name, invalid):
    from app.modules.survey.routes import survey_history
    payload = answers()
    payload["exhaustion"]["e1"] = invalid
    with pytest.raises(ValidationError):
        getattr(survey_history, model_name)(**payload)


@pytest.mark.parametrize("kind", list(VERSIONS))
def test_missing_and_extra_answers_rejected(kind):
    from app.modules.survey.routes.survey_history import SurveySubmitRequest
    payload = answers(kind)
    del payload["exhaustion"]["e1"]
    with pytest.raises(ValidationError):
        SurveySubmitRequest(**payload)
    payload = answers(kind)
    payload["exhaustion"]["e99"] = 3
    with pytest.raises(ValidationError):
        SurveySubmitRequest(**payload)


def test_olbi_does_not_accept_or_inject_sleep_recovery_or_demands():
    from app.modules.survey.routes.survey_history import AnalyzeRequest, SurveySubmitRequest
    for model in (AnalyzeRequest, SurveySubmitRequest):
        clean = model(**answers()).model_dump(exclude_none=True)
        assert "sleep_hours" not in clean
        assert "recovery" not in clean
        assert "job_demands" not in clean
        assert "working_hours" not in clean
        for field, value in (("sleep_hours", 7), ("recovery", {"recovery_score": 3}),
                             ("job_demands", {"jd1": 3})):
            with pytest.raises(ValidationError):
                model(**{**answers(), field: value})


def test_daily_demands_do_not_change_core_ed_score():
    payload = answers("daily_checkin", 3)
    first = SurveyAnalysisService.analyze(payload)
    payload["job_demands"] = {"jd1": 5, "jd2": 5, "jd3": 5}
    payload["recovery"] = {"sleep_hours": 3, "recovery_score": 1}
    second = SurveyAnalysisService.analyze(payload)
    assert first.risk_score == second.risk_score == 50
    assert any(f.code == "JOB_DEMANDS" for f in second.factors)


NOW = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)


def record(timestamp, kind="daily_checkin", risk=3):
    return {"completed_at": timestamp, "survey": answers(kind, risk)}


def test_daily_calendar_excludes_olbi_old_records_and_duplicates():
    earlier = record(NOW - timedelta(hours=2))
    latest = record(NOW)
    records = [earlier, record(NOW, "olbi_periodic"), record(NOW - timedelta(days=8)), latest]
    assert daily_records(records, now=NOW) == [latest]


def test_day_boundary_is_utc_plus_seven():
    midnight = datetime(2026, 10, 22, 0, 30, tzinfo=timezone(timedelta(hours=7)))
    assert daily_records([record(midnight - timedelta(hours=1)), record(midnight)], days=1, now=midnight) == [record(midnight)]


def test_rolling_stats_use_all_nine_items_and_calendar_days():
    now = datetime.now(timezone.utc)
    data = answers("daily_checkin")
    data["disengagement"] = {"d1": 1, "d2": 3, "d3": 5}
    records = [{"completed_at": now, "survey": data}, record(now, "olbi_periodic"), record(now - timedelta(days=8))]
    stats = SurveyAnalysisService.compute_rolling_stats(records)
    assert stats["total_surveys"] == 1
    assert stats["dimensions"]["disengagement"]["average"] == 3
    assert stats["dimensions"]["job_demands"]["average"] == 3


def test_overload_requires_three_distinct_consecutive_days():
    now = datetime.now(timezone.utc)
    def overloaded(time):
        result = record(time, risk=4)
        result["survey"]["sleep_hours"] = 5
        return result
    assert SurveyAnalysisService.check_allostatic_overload([overloaded(now)] * 3) is None
    assert SurveyAnalysisService.check_allostatic_overload([overloaded(now - timedelta(days=i)) for i in (0, 1, 3)]) is None
    assert SurveyAnalysisService.check_allostatic_overload([overloaded(now - timedelta(days=i)) for i in (0, 1, 2)]) is not None


def test_baseline_due_date_and_no_future_baseline():
    old = record(NOW - timedelta(days=15), "olbi_periodic")
    future = record(NOW + timedelta(days=1), "olbi_periodic")
    assert latest_olbi([old, future], at=NOW) == old
    assert questionnaire_status([old], now=NOW)["is_due"]
    fresh = record(NOW - timedelta(days=1), "olbi_periodic")
    assert not questionnaire_status([old, fresh], now=NOW)["is_due"]
    assert questionnaire_status([], now=NOW)["is_due"]


def test_ai_fallback_does_not_invent_sleep_or_historical_trend():
    from app.modules.survey.services.survey_ai_interpreter import SurveyAIInterpreter
    result = SurveyAIInterpreter()._generate_fallback({
        "survey_type": "olbi_periodic", "sleep_hours": None, "recovery_score": None,
        "exhaustion_level": "low", "disengagement_level": "high",
        "previous_comparison": "Chưa có lần khảo sát cùng loại để so sánh.",
    })
    assert "giấc ngủ" not in result.contributing_factors_text
    assert "Chưa có" in result.change_text
    assert "gắn kết hiện cao" in result.current_state_text


def test_submit_keeps_raw_answers_and_server_scores(monkeypatch):
    from app.modules.survey.routes import survey_history as routes
    from app.modules.emotion.repositories import emotion_repository
    from app.modules.chat.repositories import chat_history_repository
    from app.modules.burnout.repositories import burnout_repository
    emotion_repo = MagicMock()
    emotion_repo.list_by_assessment.return_value = []
    chat_repo = MagicMock()
    chat_repo.get_messages_by_assessment.return_value = []
    monkeypatch.setattr(emotion_repository, "get_emotion_repository", lambda: emotion_repo)
    monkeypatch.setattr(chat_history_repository, "get_chat_history_repository", lambda: chat_repo)
    burnout_repo = MagicMock()
    burnout_repo.list_by_user.return_value = []
    monkeypatch.setattr(burnout_repository, "get_burnout_repository", lambda: burnout_repo)
    repo = MagicMock()
    repo.get_by_assessment.return_value = None
    repo.save.return_value = "record"
    payload = answers()
    repo.get_by_id.side_effect = lambda _: {"id": "record", "created_at": NOW, "completed_at": NOW,
                                           "survey": repo.save.call_args.kwargs["survey"]}
    response = asyncio.run(routes.submit_survey("assessment", routes.SurveySubmitRequest(**payload), {"uid": "user"}, repo))
    stored = repo.save.call_args.kwargs["survey"]
    assert stored["exhaustion"] == payload["exhaustion"]
    assert len(stored["exhaustion"]) == len(stored["disengagement"]) == 8
    assert stored["questionnaire_scores"]["risk_score"] == 0
    assert response.analysis_result["risk_score"] == 0
    assert "sleep_hours" not in response.survey
    burnout_repo.save.assert_called_once()
    dashboard_result = burnout_repo.save.call_args.kwargs["result"]
    assert dashboard_result["burnout_score"] == 0
    assert dashboard_result["survey_type"] == "olbi_periodic"
    assert isinstance(dashboard_result["insight"], dict)
    assert all(isinstance(item, dict) for item in dashboard_result["recommendations"])


def test_retry_same_answers_does_not_write_again():
    from app.modules.survey.repositories.survey_history_repository import SurveyHistoryRepository
    repo = SurveyHistoryRepository.__new__(SurveyHistoryRepository)
    repo.collection = MagicMock()
    repo.get_by_assessment = MagicMock(return_value={
        "id": "existing", "user_id": "user", "survey": answers(), "status": "completed"})
    assert repo.save("assessment", "user", answers()) == "existing"
    repo.collection.document.assert_not_called()


@pytest.mark.parametrize("kind", list(VERSIONS))
def test_analysis_route_uses_correct_dimensions_and_no_fabricated_olbi_context(kind, monkeypatch):
    from app.modules.survey.routes import survey_history as routes
    from app.modules.user.services import user_profile_service
    from app.modules.survey.services.survey_ai_interpreter import SurveyAIInterpreter
    profile = MagicMock()
    profile.get_profile.return_value = {}
    monkeypatch.setattr(user_profile_service, "get_profile_service", lambda: profile)
    interpreter = SurveyAIInterpreter()
    interpreter.generate_insight = MagicMock(side_effect=interpreter._generate_fallback)
    monkeypatch.setattr(routes, "get_survey_ai_interpreter", lambda: interpreter)
    repo = MagicMock()
    repo.get_recent_completed_surveys.return_value = []
    repo.get_completed_questionnaires.return_value = []
    payload = answers(kind)
    response = asyncio.run(routes.analyze_survey(routes.AnalyzeRequest(**payload), {"uid": "user"}, repo))
    assert response.risk_score == score_questionnaire(payload)["risk_score"]
    assert response.questionnaire_scores["scale_max"] == (4 if kind == "olbi_periodic" else 5)
    evidence = interpreter.generate_insight.call_args.args[0]
    if kind == "olbi_periodic":
        assert evidence["sleep_hours"] is None
        assert evidence["recovery_score"] is None
        assert evidence["quick_overload"] is None
        assert "chỉ có hai chiều OLBI" in evidence["archetype_name"]


def test_dashboard_daily_analytics_do_not_consume_olbi():
    from app.modules.dashboard.routes.dashboard import _compute_sta_analytics
    result = asyncio.run(_compute_sta_analytics([record(datetime.now(timezone.utc), "olbi_periodic")], 7))
    assert result["sta_core"] is None
    assert result["sta_trend"] == []


def test_burnout_repository_preserves_questionnaire_metadata_and_updates_existing():
    from app.modules.burnout.repositories.burnout_repository import BurnoutRepository
    repo = BurnoutRepository.__new__(BurnoutRepository)
    repo.collection = MagicMock()
    repo.get_by_assessment = MagicMock(return_value={"id": "existing", "user_id": "user"})
    scores = score_questionnaire(answers())
    repo.save("user", {"survey_type": "olbi_periodic", "questionnaire_scores": scores,
                       "burnout_core": {"exhaustion": {"score": 1}}, "burnout_score": 0}, "assessment")
    stored = repo.collection.document.return_value.update.call_args.args[0]
    assert stored["questionnaire_scores"] == scores
    assert stored["survey_type"] == "olbi_periodic"
    assert stored["burnout_core"]["exhaustion"]["score"] == 1
    repo.collection.document.return_value.set.assert_not_called()


def olbi_record(days_ago=0, risk=3, identity=None):
    payload = answers("olbi_periodic", risk)
    payload["questionnaire_scores"] = score_questionnaire(payload)
    return {"id": identity or f"olbi_{days_ago}", "assessment_id": identity or f"olbi_{days_ago}",
            "user_id": "user", "status": "completed", "completed_at": NOW - timedelta(days=days_ago),
            "survey": payload}


def test_olbi_progress_empty_and_single_point_have_no_invented_change():
    from app.modules.dashboard.services.olbi_progress import build_olbi_progress
    empty = build_olbi_progress([], now=NOW)
    assert empty["points"] == []
    assert empty["direction"] == "insufficient_data"
    single = build_olbi_progress([olbi_record()], now=NOW)
    assert single["comparisons"]["exhaustion"]["baseline"] == 3
    assert single["comparisons"]["exhaustion"]["change_from_baseline"] is None
    assert single["points"][0]["change_from_previous"]["exhaustion"] is None


def test_olbi_timeline_comparisons_follow_visible_window():
    from app.modules.dashboard.services.olbi_progress import build_olbi_progress
    records = [olbi_record(0, 1), olbi_record(120, 4), olbi_record(14, 3)]
    result = build_olbi_progress(records, days=90, now=NOW)
    assert result["total_records"] == 3
    assert result["visible_records"] == 2
    assert [p["sequence"] for p in result["points"]] == [2, 3]
    assert result["comparisons"]["exhaustion"] == {
        "baseline": 3, "latest": 1, "change_from_baseline": -2, "change_from_previous": -2}
    assert result["direction"] == "decreasing"
    assert "giảm 2.00" in result["summary"]
    assert result["points"][0]["change_from_previous"]["exhaustion"] is None


@pytest.mark.parametrize("case", ["daily", "legacy", "partial", "wrong_scale", "wrong_version", "invalid_score", "missing_raw", "future", "in_progress"])
def test_olbi_progress_excludes_incompatible_and_daily_data(case):
    from app.modules.dashboard.services.olbi_progress import build_olbi_progress
    invalid = olbi_record(identity="invalid")
    survey = invalid["survey"]
    if case == "daily":
        invalid["survey"] = answers("daily_checkin")
    elif case == "legacy":
        del survey["survey_type"]
    elif case == "partial":
        del survey["questionnaire_scores"]["means"]["exhaustion"]
    elif case == "wrong_scale":
        survey["questionnaire_scores"]["scale_max"] = 5
    elif case == "wrong_version":
        survey["questionnaire_version"] = "old-demo"
    elif case == "invalid_score":
        survey["questionnaire_scores"]["means"]["disengagement"] = float("nan")
    elif case == "missing_raw":
        del survey["disengagement"]["d8"]
    elif case == "future":
        invalid["completed_at"] = NOW + timedelta(days=1)
    else:
        invalid["status"] = "in_progress"
    result = build_olbi_progress([invalid, olbi_record()], now=NOW)
    assert result["total_records"] == 1
    assert result["points"][0]["id"] == "olbi_0"


@pytest.mark.parametrize("direction,first,latest", [("increasing", 1, 4), ("unchanged", 3, 3)])
def test_olbi_summary_direction(direction, first, latest):
    from app.modules.dashboard.services.olbi_progress import build_olbi_progress
    result = build_olbi_progress([olbi_record(14, first), olbi_record(0, latest)], now=NOW)
    assert result["direction"] == direction


def test_olbi_mixed_dimensions_are_not_called_recovered():
    from app.modules.dashboard.services.olbi_progress import build_olbi_progress
    last = olbi_record(0, 3)
    last["survey"]["questionnaire_scores"]["means"]["disengagement"] = 1
    result = build_olbi_progress([olbi_record(14, 2), last], now=NOW)
    assert result["direction"] == "mixed"
    assert "tăng 1.00" in result["summary"]
    assert "giảm 1.00" in result["summary"]


def test_olbi_window_uses_local_calendar_and_excludes_old_baseline():
    from app.modules.dashboard.services.olbi_progress import build_olbi_progress
    earliest = olbi_record(100)
    boundary = olbi_record(identity="boundary")
    boundary["completed_at"] = datetime(2026, 7, 24, 17, tzinfo=timezone.utc)  # 25 July UTC+7: day 90
    older = deepcopy(boundary)
    older["id"] = older["assessment_id"] = "older"
    older["completed_at"] -= timedelta(seconds=1)
    result = build_olbi_progress([earliest, boundary, older], days=90, now=NOW)
    assert [point["id"] for point in result["points"]] == ["boundary"]
    assert result["total_records"] == 3
    empty_window = build_olbi_progress([earliest], days=90, now=NOW)
    assert empty_window["points"] == []
    assert empty_window["comparisons"]["exhaustion"]["latest"] is None


def test_olbi_duplicate_assessments_use_latest_record():
    from app.modules.dashboard.services.olbi_progress import build_olbi_progress
    old = olbi_record(14, 4, "same")
    new = olbi_record(0, 2, "same")
    new["id"] = "new_document"
    result = build_olbi_progress([new, old], now=NOW)
    assert result["total_records"] == 1
    assert result["points"][0]["id"] == "new_document"


def test_olbi_endpoint_uses_authenticated_owner_and_validates_window(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.dashboard.routes import dashboard as routes
    from app.core.deps import get_current_user
    repo = MagicMock()
    repo.get_completed_questionnaires.return_value = [olbi_record()]
    monkeypatch.setattr(routes, "get_survey_history_repository", lambda: repo)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: {"uid": "authenticated-user"}
    with TestClient(app) as client:
        result = client.get("/api/v1/dashboard/olbi-history?days=90&user_id=someone-else")
        assert result.status_code == 200
        repo.get_completed_questionnaires.assert_called_with("authenticated-user")
        assert client.get("/api/v1/dashboard/olbi-history?days=0").status_code == 422
        assert client.get("/api/v1/dashboard/olbi-history?days=all").status_code == 422
        assert client.get("/api/v1/dashboard/olbi-history").json()["period_days"] is None
        for endpoint in ("olbi-history", "burnout-analytics", "analytics"):
            assert client.get(f"/api/v1/dashboard/{endpoint}?start_date=2026-09-01").status_code == 422
            assert client.get(f"/api/v1/dashboard/{endpoint}?start_date=2026-09-02&end_date=2026-09-01").status_code == 422
        historical = client.get("/api/v1/dashboard/olbi-history?start_date=2026-09-01&end_date=2026-09-30").json()
        assert historical["start_date"] == "2026-09-01"
        assert historical["end_date"] == "2026-09-30"
        assert historical["points"] == []
        assert historical["comparisons"]["exhaustion"]["latest"] is None


def test_daily_dashboard_does_not_fallback_to_periodic_olbi(monkeypatch):
    from app.modules.dashboard.routes import dashboard as routes
    from app.modules.user.services import user_profile_service
    burnout_repo = MagicMock()
    burnout_repo.list_by_user.return_value = [{"survey_type": "olbi_periodic", "burnout_score": 80,
                                              "analyzed_at": datetime.utcnow(), "risk_level": "high"}]
    survey_repo = MagicMock()
    survey_repo.list_by_user.return_value = [olbi_record()]
    other_repo = MagicMock()
    other_repo.list_by_user.return_value = []
    profile_service = MagicMock()
    profile_service.get_profile.return_value = {}
    monkeypatch.setattr(routes, "get_burnout_repo", lambda: burnout_repo)
    monkeypatch.setattr(routes, "get_survey_repo", lambda: survey_repo)
    monkeypatch.setattr(routes, "get_emotion_repo", lambda: other_repo)
    monkeypatch.setattr(routes, "get_chat_repo", lambda: other_repo)
    monkeypatch.setattr(user_profile_service, "get_profile_service", lambda: profile_service)
    response = asyncio.run(routes.get_burnout_analytics(days=30, user_id=None, user={"uid": "user"}))
    assert response.current is None
    assert response.sta_core is None
    assert response.burnout_trend == []
    assert response.warnings == []


def test_exact_historical_window_scopes_olbi_chart_and_comparisons():
    from app.modules.dashboard.services.olbi_progress import build_olbi_progress
    records = [olbi_record(120, 4), olbi_record(30, 3), olbi_record(20, 2), olbi_record(0, 1)]
    result = build_olbi_progress(records, start_date=date(2026, 9, 1), end_date=date(2026, 10, 5), now=NOW)
    assert [point["id"] for point in result["points"]] == ["olbi_30", "olbi_20"]
    assert result["comparisons"]["exhaustion"] == {
        "baseline": 3, "latest": 2, "change_from_baseline": -1, "change_from_previous": -1}
    assert result["points"][0]["change_from_previous"]["exhaustion"] is None
    assert result["start_date"] == "2026-09-01"
    assert result["end_date"] == "2026-10-05"
    assert result["period_days"] == 35


def test_calendar_date_window_includes_full_end_day_utc_plus_seven():
    from app.modules.dashboard.services.date_window import date_window, in_window
    window = date_window(date(2026, 9, 1), date(2026, 9, 1))
    assert in_window("2026-08-31T17:00:00Z", window)
    assert in_window("2026-09-01T16:59:59.999999Z", window)
    assert not in_window("2026-08-31T16:59:59.999999Z", window)
    assert not in_window("2026-09-01T17:00:00Z", window)


@pytest.mark.parametrize("start,end", [(date(2026, 9, 1), None), (None, date(2026, 9, 2)),
                                      (date(2026, 9, 2), date(2026, 9, 1))])
def test_invalid_date_windows_rejected(start, end):
    from app.modules.dashboard.services.date_window import date_window
    with pytest.raises(ValueError):
        date_window(start, end)


def test_daily_historical_window_does_not_use_today_or_out_of_range_fallback(monkeypatch):
    from app.modules.dashboard.routes import dashboard as routes
    from app.modules.user.services import user_profile_service
    burnout_repo = MagicMock()
    burnout_repo.list_by_user.return_value = []
    survey_repo = MagicMock()
    inside = {"id": "inside", "assessment_id": "inside", "status": "completed",
              "completed_at": "2026-09-01T10:00:00Z", "survey": answers("daily_checkin", 2)}
    outside = {"id": "outside", "status": "completed", "completed_at": "2026-10-21T10:00:00Z",
               "survey": answers("daily_checkin", 5)}
    survey_repo.get_completed_questionnaires.return_value = [outside, inside]
    other = MagicMock()
    other.list_by_user.return_value = []
    profile = MagicMock()
    profile.get_profile.return_value = {}
    monkeypatch.setattr(routes, "get_burnout_repo", lambda: burnout_repo)
    monkeypatch.setattr(routes, "get_survey_repo", lambda: survey_repo)
    monkeypatch.setattr(routes, "get_emotion_repo", lambda: other)
    monkeypatch.setattr(routes, "get_chat_repo", lambda: other)
    monkeypatch.setattr(user_profile_service, "get_profile_service", lambda: profile)
    response = asyncio.run(routes.get_burnout_analytics(days=30, user_id=None, user={"uid": "user"},
                                                       start_date=date(2026, 9, 1), end_date=date(2026, 9, 1)))
    assert response.sta_core["exhaustion"]["score"] == 2
    assert len(response.sta_trend) == 1
    assert response.sta_trend[0]["date"] == "2026-09-01"
    empty = asyncio.run(routes.get_burnout_analytics(days=30, user_id=None, user={"uid": "user"},
                                                    start_date=date(2026, 8, 1), end_date=date(2026, 8, 1)))
    assert empty.current is None
    assert empty.sta_core is None


def test_dashboard_activity_uses_exact_selected_dates(monkeypatch):
    from app.modules.dashboard.routes import dashboard as routes
    repo = MagicMock()
    repo.list_by_user.return_value = []
    emotion_repo = MagicMock()
    emotion_repo.list_by_user.return_value = [
        {"id": "inside", "created_at": "2026-08-31T17:00:00Z", "dominant_emotion": "happy", "confidence": 0.8},
        {"id": "outside", "created_at": "2026-09-01T17:00:00Z", "dominant_emotion": "sad", "confidence": 0.9}]
    firebase = MagicMock()
    firebase.db.collection.return_value.where.return_value.order_by.return_value.limit.return_value.stream.return_value = []
    monkeypatch.setattr(routes, "get_burnout_repo", lambda: repo)
    monkeypatch.setattr(routes, "get_assessment_repo", lambda: repo)
    monkeypatch.setattr(routes, "get_emotion_repo", lambda: emotion_repo)
    monkeypatch.setattr(routes, "get_firebase", lambda: firebase)
    response = asyncio.run(routes.get_user_dashboard_analytics(user={"uid": "user"},
                            start_date=date(2026, 9, 1), end_date=date(2026, 9, 1)))
    assert response.total_emotion_analyses == 1
    assert response.emotion_distribution == {"happy": 1}
    assert response.emotions_trend == [{"date": "2026-09-01", "count": 1}]
