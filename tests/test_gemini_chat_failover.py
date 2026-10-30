"""Regression coverage for chat silently falling back on Gemini timeouts."""

from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from app.core.gemini_rotator import GeminiRotator
from app.modules.chat.services.chat_response_generator import ChatResponseGenerator


@pytest.fixture
def rotator(monkeypatch):
    pool = GeminiRotator()
    monkeypatch.setattr(pool, "_get_keys", lambda: ["test-key-1", "test-key-2"])
    monkeypatch.setattr(pool, "_get_models", lambda: ["primary", "backup"])
    monkeypatch.setattr(pool, "_get_client_for_key", lambda key: key)
    return pool


@pytest.mark.parametrize("error", [
    RuntimeError("504 DEADLINE_EXCEEDED"),
    RuntimeError("503 UNAVAILABLE"),
    RuntimeError("500 INTERNAL"),
    httpx.ReadTimeout("request timed out"),
    httpx.ConnectError("connection failed"),
])
def test_transient_failure_switches_model_without_retrying_every_key(rotator, error):
    calls = []

    def call(key, model):
        calls.append((key, model))
        if model == "primary":
            raise error
        return "real model reply"

    result, model, _ = rotator.execute_with_failover(call)
    assert (result, model) == ("real model reply", "backup")
    assert calls == [("test-key-1", "primary"), ("test-key-1", "backup")]
    assert all(rotator._is_cooling_down(key, "primary") for key in rotator._get_keys())


def test_quota_failure_still_tries_other_key_on_same_model(rotator):
    calls = []

    def call(key, model):
        calls.append((key, model))
        if key == "test-key-1":
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return "reply"

    assert rotator.execute_with_failover(call)[1:] == ("primary", "test-key-2")
    assert calls == [("test-key-1", "primary"), ("test-key-2", "primary")]


def test_invalid_request_does_not_repeat_across_pool(rotator):
    call = Mock(side_effect=RuntimeError("400 INVALID_ARGUMENT"))
    with pytest.raises(RuntimeError, match="INVALID_ARGUMENT"):
        rotator.execute_with_failover(call)
    assert call.call_count == 1


def test_client_uses_configured_timeout_and_disables_sdk_retry(monkeypatch):
    from app.core import gemini_rotator

    monkeypatch.setattr(gemini_rotator, "get_settings", lambda: SimpleNamespace(
        google_ai=SimpleNamespace(timeout_seconds=7),
    ))
    factory = Mock()
    monkeypatch.setattr(gemini_rotator.genai, "Client", factory)
    pool = GeminiRotator()
    pool._get_client_for_key("test-key")
    pool._get_client_for_key("test-key")
    factory.assert_called_once()
    options = factory.call_args.kwargs["http_options"]
    assert options.timeout == 7000
    assert options.retry_options.attempts == 1


@pytest.mark.parametrize("output, expected_fallback", [
    ("Bạn có muốn chia sẻ thêm không?", True),
    ("Mình nghe thấy bạn đang rất mệt vì công việc dồn dập.", False),
])
def test_stage_rejection_is_reported_as_fallback(monkeypatch, output, expected_fallback):
    from app.modules.chat.services import probing_questions

    probe = Mock()
    probe.detect_user_wants_to_stop.return_value = False
    monkeypatch.setattr(probing_questions, "get_probing_questions_service", lambda: probe)
    generator = ChatResponseGenerator()
    monkeypatch.setattr(generator, "_build_prompt", lambda **kwargs: ("prompt", None))
    monkeypatch.setattr(generator, "_generate_with_gemini", lambda prompt: (output, "STOP"))
    result = generator.generate_response("Công việc quá nhiều", stage="reflect_and_support")
    assert result.is_fallback is expected_fallback
    assert ("STAGE_VIOLATION" in result.finish_reason) is expected_fallback
