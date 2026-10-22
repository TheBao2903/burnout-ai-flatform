"""Versioned questionnaire contracts and deterministic scoring.

OLBI: Demerouti, Mostert & Bakker (2010), doi:10.1037/a0019408,
appendix. Responses here run from disagree=1 to agree=4, therefore
positive statements are reversed. Vietnamese wording is a reference translation.
The display bands below are application conventions, not clinical cutoffs.
"""
from copy import deepcopy
from typing import Literal, Optional

from pydantic import BaseModel, model_validator

VERSIONS = {"daily_checkin": "sta-daily-9-v1", "olbi_periodic": "olbi-16-4pt-vi-v1"}
POSITIVE = {"exhaustion": {"e3", "e5", "e7", "e8"},
            "disengagement": {"d1", "d4", "d7", "d8"}}


def validate_answers(data):
    kind = data.get("survey_type")
    if kind not in VERSIONS:
        return
    if data.get("questionnaire_version") != VERSIONS[kind]:
        raise ValueError("Unsupported questionnaire version")
    periodic = kind == "olbi_periodic"
    groups = {"exhaustion": ("e", 8 if periodic else 3),
              "disengagement": ("d", 8 if periodic else 3)}
    if not periodic:
        groups["job_demands"] = ("jd", 3)
    for group, (prefix, count) in groups.items():
        answers = data.get(group)
        expected = {f"{prefix}{i}" for i in range(1, count + 1)}
        if not isinstance(answers, dict) or set(answers) != expected:
            raise ValueError(f"{group}: answer all {count} items")
        if any(type(v) is not int or not 1 <= v <= (4 if periodic else 5)
               for v in answers.values()):
            raise ValueError(f"{group}: invalid response scale")
    if periodic:
        for field in ("sleep_hours", "recovery_score", "recovery", "job_demands",
                      "quick_overload", "quick_overload_data", "overload_reasons",
                      "working_hours", "overtime_hours", "has_deadline", "work_changes",
                      "work_days_per_week", "stress_level", "motivation_level",
                      "heart_rate", "work_satisfaction", "consecutive_work_days", "rest_days",
                      "has_overtime_today", "overtime_hours_today", "current_deadline_pressure"):
            if data.get(field) not in (None, {}, []):
                raise ValueError(f"OLBI does not collect {field}")
    else:
        recovery = data.get("recovery") or {}
        if not isinstance(recovery, dict):
            raise ValueError("Invalid recovery data")
        for key, maximum in (("sleep_hours", 24), ("recovery_score", 5)):
            value = recovery.get(key)
            if value is not None:
                minimum = 0 if key == "sleep_hours" else 1
                if type(value) not in (int, float) or not minimum <= value <= maximum:
                    raise ValueError(f"Invalid {key}")
                if data.get(key) is not None and data[key] != value:
                    raise ValueError(f"Conflicting {key}")
        quick = data.get("quick_overload_data") or {}
        if not isinstance(quick, dict):
            raise ValueError("Invalid overload data")
        rating = quick.get("rating")
        if rating is not None and (type(rating) is not int or not 1 <= rating <= 5):
            raise ValueError("Invalid overload rating")
        if rating is not None and data.get("quick_overload") is not None and rating != data["quick_overload"]:
            raise ValueError("Conflicting overload rating")


class QuestionnaireRequest(BaseModel):
    # None preserves unversioned clients; explicit protocols always validate fully.
    survey_type: Optional[Literal["daily_checkin", "olbi_periodic"]] = None
    questionnaire_version: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def validate_questionnaire(cls, data):
        if isinstance(data, dict):
            validate_answers(data)
        return data

    @model_validator(mode="after")
    def clear_periodic_defaults(self):
        if self.survey_type:
            for field in ("working_hours", "overtime_hours", "has_deadline", "work_days_per_week",
                          "stress_level", "motivation_level", "sleep_hours"):
                if hasattr(self, field) and field not in self.model_fields_set:
                    setattr(self, field, None)
        if self.survey_type == "olbi_periodic":
            for field in ("sleep_hours", "recovery_score", "recovery", "job_demands",
                          "quick_overload", "quick_overload_data", "working_hours",
                          "overtime_hours", "has_deadline", "work_changes",
                          "work_days_per_week", "stress_level", "motivation_level"):
                if hasattr(self, field):
                    setattr(self, field, None)
        return self


def dimension_level(mean, maximum=5):
    normalized = (mean - 1) / (maximum - 1)
    return "low" if normalized <= 1 / 3 else "medium" if normalized <= 2 / 3 else "high"


def score_questionnaire(data):
    """Never trust client-computed means. Keep raw answers untouched."""
    validate_answers(data)
    periodic = data["survey_type"] == "olbi_periodic"
    maximum = 4 if periodic else 5
    means = {}
    for group in ("exhaustion", "disengagement", "job_demands"):
        answers = data.get(group)
        if answers and not (periodic and group == "job_demands"):
            values = [5 - value if periodic and key in POSITIVE[group] else value
                      for key, value in answers.items()]
            means[group] = sum(values) / len(values)
    core = (means["exhaustion"] + means["disengagement"]) / 2
    return {"means": means, "scale_max": maximum,
            "risk_score": round((core - 1) / (maximum - 1) * 100, 1),
            "risk_level": dimension_level(core, maximum),
            "levels": {key: dimension_level(value, maximum) for key, value in means.items()},
            "scoring_version": "core-ed-v1", "bands": "application_reference"}


def engine_survey(data):
    """Adapt raw OLBI to the engine's legacy 1–5 core without losing originals."""
    result = deepcopy(data)
    scores = score_questionnaire(data)
    for group, prefix in (("exhaustion", "e"), ("disengagement", "d")):
        mean = scores["means"][group]
        equivalent = 1 + (mean - 1) * 4 / (scores["scale_max"] - 1)
        result[group] = {f"{prefix}{i}": equivalent for i in range(1, 4)}
    result["questionnaire_scores"] = scores
    return result
