"""Audit regressions. No credentials, production writes or external AI calls."""

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import RLock
from types import SimpleNamespace as NS
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from google.cloud import firestore

from app.modules.chat.models.chat_session import ChatSession
from app.modules.chat.repositories.chat_history_repository import ChatHistoryRepository
from app.modules.chat.repositories.chat_session_repository import ChatSessionRepository
from app.modules.chat.repositories.chat_request_repository import ChatRequestRepository, ChatRequestConflict
from app.modules.chat.routes import chat_history as api
from app.modules.chat.services import probing_questions as probing
from app.modules.chat.services.chat_response_generator import ChatResponse, ChatResponseGenerator, evaluate_crisis_safety


class MemoryDB:
    def __init__(self):
        self.rows = {}
        self.lock = RLock()

    def collection(self, name):
        return Collection(self, name)

    def transaction(self):
        return Transaction(self)


class Document:
    def __init__(self, db, path):
        self.db, self.path = db, path
        self.id = path.split("/")[-1]

    def collection(self, name):
        return Collection(self.db, self.path + "/" + name)

    def get(self, transaction=None):
        if transaction:
            assert not transaction.writes, "Firestore requires reads before writes"
        data = deepcopy(self.db.rows.get(self.path))
        return NS(id=self.id, exists=data is not None, to_dict=lambda: deepcopy(data))

    def set(self, data, merge=False):
        value = deepcopy(self.db.rows.get(self.path, {})) if merge else {}
        for key, item in data.items():
            if isinstance(item, firestore.ArrayUnion):
                value[key] = list(dict.fromkeys(value.get(key, []) + list(item.values)))
            else:
                value[key] = deepcopy(item)
        self.db.rows[self.path] = value

    def update(self, data):
        self.set(data, True)


class Collection:
    def __init__(self, db, path, filters=(), order=None, cap=None):
        self.db, self.path, self.filters, self.order, self.cap = db, path, filters, order, cap

    def document(self, ident=None):
        return Document(self.db, self.path + "/" + (ident or uuid4().hex))

    def where(self, field, op, value):
        assert op == "=="
        return Collection(self.db, self.path, self.filters + ((field, value),), self.order, self.cap)

    def order_by(self, field, direction):
        return Collection(self.db, self.path, self.filters, (field, direction), self.cap)

    def limit(self, cap):
        return Collection(self.db, self.path, self.filters, self.order, cap)

    def stream(self):
        paths = [p for p, d in self.db.rows.items() if p.rsplit("/", 1)[0] == self.path
                 and all(d.get(k) == v for k, v in self.filters)]
        if self.order:
            field, direction = self.order
            def key(path):
                value = self.db.rows[path].get(field)
                stamp = value.replace(tzinfo=timezone.utc).timestamp() if value.tzinfo is None else value.timestamp()
                return stamp, path
            paths.sort(key=key, reverse=direction == firestore.Query.DESCENDING)
        for path in paths[:self.cap]:
            yield Document(self.db, path).get()


class Transaction:
    def __init__(self, db):
        self.db, self.writes = db, []

    def set(self, ref, data, merge=False):
        self.writes.append((ref, data, merge))

    def update(self, ref, data):
        self.set(ref, data, True)

    def delete(self, ref):
        self.writes.append((ref, None, False))


@pytest.fixture
def stores(monkeypatch):
    def transactional(fn):
        def run(tx):
            with tx.db.lock:
                result = fn(tx)
                for ref, data, merge in tx.writes:
                    if data is None:
                        tx.db.rows.pop(ref.path, None)
                    else:
                        ref.set(data, merge)
                return result
        return run
    monkeypatch.setattr(firestore, "transactional", transactional)
    db = MemoryDB()
    sessions = ChatSessionRepository.__new__(ChatSessionRepository)
    sessions.db, sessions.collection = db, db.collection("sessions")
    sessions.settings = NS(max_session_hours=5, idle_timeout_minutes=60)
    history = ChatHistoryRepository.__new__(ChatHistoryRepository)
    history.db, history.collection = db, db.collection("history")
    assessment = Mock()
    assessment.get.return_value = {"user_id": "owner", "status_detail": {"has_chat": True}}
    probe = probing.ProbingQuestionsService(session_repo=sessions)
    monkeypatch.setattr(probing, "get_probing_questions_service", lambda: probe)
    monkeypatch.setattr(api, "get_probing_questions_service", lambda: probe)
    monkeypatch.setattr(api, "_build_survey_context_sync", lambda *args: None)
    generator = Mock()
    generator.generate_response.return_value = ChatResponse("Phản hồi theo bối cảnh.", None, "workload",
        micro_action="Tạm gác một việc chưa gấp.")
    monkeypatch.setattr(api, "get_chat_response_generator", lambda: generator)
    return NS(db=db, sessions=sessions, history=history, assessment=assessment, generator=generator, probe=probe)


def send(stores, ident, message="Khối lượng công việc quá tải"):
    return api.send_chat_message("assessment", api.ChatMessageRequest(message=message, client_message_id=ident),
        {"uid": "owner"}, stores.history, stores.sessions, stores.assessment)


def test_ledger_claim_replay_and_changed_content(stores):
    ledger = ChatRequestRepository(stores.db)
    claim = ledger.claim("a", "u", "id", "send", "hello")
    with pytest.raises(ChatRequestConflict, match="CHAT_REQUEST_PENDING"):
        ledger.claim("a", "u", "id", "send", "hello")
    ledger.complete(claim, {"assistant_message": {"content": "answer"}, "is_fallback": True})
    assert ledger.claim("a", "u", "id", "send", "hello")["response"]["is_fallback"] is True
    with pytest.raises(ChatRequestConflict, match="MESSAGE_ID_REUSED"):
        ledger.claim("a", "u", "id", "send", "different")


def test_expired_worker_cannot_commit_or_release_new_claim(stores):
    ledger = ChatRequestRepository(stores.db)
    old = ledger.claim("a", "u", "id", "send")
    old["lock"].update({"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)})
    new = ledger.claim("a", "u", "id", "send")
    with pytest.raises(ChatRequestConflict, match="CHAT_REQUEST_EXPIRED"):
        ledger.complete(old, {"wrong": True})
    ledger.release(old)
    assert new["lock"].get().to_dict()["owner"] == new["owner"]


def test_full_lifecycle_extension_replay_and_closed_state(stores):
    async def scenario():
        first = await send(stores, "one")
        await send(stores, "two")
        closed = await send(stores, "three")
        assert closed["is_session_completed"] and closed["can_extend"]
        before = len(list(stores.sessions.collection.stream()))
        replay = await send(stores, "one")
        assert replay["assistant_message"] == first["assistant_message"]
        assert len(list(stores.sessions.collection.stream())) == before
        state = await api.get_chat_state("assessment", {"uid": "owner"}, stores.sessions, stores.assessment)
        assert state["status"] == "closed" and state["can_extend"] and state["user_turn_count"] == 3
        with pytest.raises(HTTPException) as exc:
            await send(stores, "no-reopen")
        assert exc.value.status_code == 409
        extended = await api.extend_chat_session("assessment", {"uid": "owner"}, stores.history, stores.sessions, stores.assessment)
        assert extended["session_id"] == first["user_message"]["session_id"]
        for number in (4, 5, 6):
            response = await send(stores, str(number))
            assert response["is_session_completed"] is (number == 6)
        with pytest.raises(HTTPException):
            await send(stores, "still-no-reopen")
    asyncio.run(scenario())


def test_concurrent_same_id_does_not_increment_twice(stores):
    import time
    def slow(**kwargs):
        time.sleep(.06)
        return ChatResponse("answer", None, None)
    stores.generator.generate_response.side_effect = slow
    async def scenario():
        replies = await asyncio.gather(send(stores, "same"), send(stores, "same"), return_exceptions=True)
        assert sum(isinstance(r, HTTPException) and r.status_code == 409 for r in replies) == 1
        replay = await send(stores, "same")
        assert replay["idempotent_replay"]
    asyncio.run(scenario())
    assert len(list(stores.history.collection.stream())) == 2
    assert api._latest_session(stores.sessions, "assessment").user_turn_count == 1


def test_generation_failure_leaves_turn_and_messages_uncommitted(stores):
    stores.generator.generate_response.side_effect = RuntimeError("unexpected implementation failure")
    with pytest.raises(RuntimeError):
        asyncio.run(send(stores, "retry-me"))
    assert not list(stores.history.collection.stream())
    assert api._latest_session(stores.sessions, "assessment").user_turn_count == 0
    stores.generator.generate_response.side_effect = None
    assert asyncio.run(send(stores, "retry-me"))["user_turn_count"] == 1


def test_manual_close_is_readable_and_not_extendable(stores):
    async def scenario():
        await send(stores, "one")
        await api.close_chat_session("assessment", {"uid": "owner"}, stores.sessions, stores.assessment)
        state = await api.get_chat_state("assessment", {"uid": "owner"}, stores.sessions, stores.assessment)
        assert state["status"] == "closed" and not state["can_extend"]
        with pytest.raises(HTTPException):
            await api.extend_chat_session("assessment", {"uid": "owner"}, stores.history, stores.sessions, stores.assessment)
    asyncio.run(scenario())
    assert api._latest_session(stores.sessions, "assessment").closed_reason == "manual"
    legacy = ChatSession(id="s", assessment_id="a", user_id="u", closed_reason="manual_user_decision")
    assert legacy.closed_reason == "manual"
    with pytest.raises(ValueError):
        stores.sessions.close_session(legacy.id, "typo")


def test_foreign_empty_history_rejected_before_query(stores):
    stores.assessment.get.return_value = {"user_id": "someone-else"}
    with pytest.raises(HTTPException) as exc:
        asyncio.run(api.get_chat_history("assessment", 50, {"uid": "owner"}, stores.history, stores.sessions, stores.assessment))
    assert exc.value.status_code == 403
    assert stores.db.rows == {}


@pytest.mark.parametrize("message", [
    "Tôi không tự tử trước đây, nhưng bây giờ tôi muốn chết.",
    "Hôm nay mệt chết đi được, tôi chỉ muốn ngủ một giấc không bao giờ dậy nữa.",
    "Tôi không có ý định tự tử, nhưng tôi muốn tự làm đau mình.",
])
def test_positive_crisis_signal_survives_unrelated_exclusion(message):
    assert evaluate_crisis_safety(message)[0]


@pytest.mark.parametrize("message", ["Tôi không muốn chết đâu", "Hôm nay mệt chết đi được", "Tôi không có ý định tự tử", "Mình muốn từ từ giải quyết công việc"])
def test_denials_and_colloquial_alone_are_not_crisis(message):
    assert not evaluate_crisis_safety(message)[0]


@pytest.mark.parametrize("message", ["Mình chỉ thấy mệt thôi, nên nghỉ bao lâu?", "Công việc không ngừng dồn tới", "Cảm ơn, mình muốn hỏi thêm"])
def test_stop_words_inside_request_do_not_end_chat(stores, message):
    assert not stores.probe.detect_user_wants_to_stop(message)


def test_same_grounded_topic_and_action_reused_for_fallback(stores, monkeypatch):
    generator = ChatResponseGenerator()
    monkeypatch.setattr(generator, "_generate_with_gemini", Mock(side_effect=RuntimeError("offline")))
    a = generator.generate_response("Khối lượng công việc quá tải", "reflect_and_support")
    b = generator.generate_response("Khối lượng công việc quá tải", "reflect_and_support")
    assert a.follow_up_topic == b.follow_up_topic == "workload"
    assert a.micro_action == b.micro_action and a.micro_action in a.content
    result = generator.generate_response("Mình muốn nói chuyện", "reflect_and_support")
    assert result.follow_up_topic is None


def test_survey_greeting_uses_valid_generator_signature(stores, monkeypatch):
    monkeypatch.setattr(api, "_build_survey_context_sync", lambda *a: {"overload_reasons": ["deadline"]})
    real_signature = Mock(spec=ChatResponseGenerator)
    def generate(**kwargs):
        import inspect
        inspect.signature(ChatResponseGenerator.generate_response).bind(None, **kwargs)
        return ChatResponse("warm greeting", None, None)
    real_signature.generate_response.side_effect = generate
    monkeypatch.setattr(api, "get_chat_response_generator", lambda: real_signature)
    response = asyncio.run(api.get_initial_greeting("assessment", {"uid": "owner"}, stores.sessions, stores.assessment))
    assert response["greeting"] == "warm greeting"


def test_history_is_latest_and_isolated_by_session(stores):
    base = datetime(2026, 10, 30, tzinfo=timezone.utc)
    for number in range(60):
        stores.history.collection.document(str(number)).set({"session_id": "current", "assessment_id": "a", "content": str(number), "created_at": base + timedelta(seconds=number)})
    stores.history.collection.document("foreign").set({"session_id": "previous", "created_at": base + timedelta(days=1)})
    messages = stores.history.get_messages_by_session("current", limit=6)
    assert [m["content"] for m in messages] == list(map(str, range(54, 60)))


@pytest.mark.parametrize("field", ["session_id", "assessment_id"])
def test_missing_history_index_falls_back_without_losing_recent_messages(field):
    from google.api_core.exceptions import FailedPrecondition
    repo = ChatHistoryRepository.__new__(ChatHistoryRepository)
    repo.collection = Mock()
    filtered = repo.collection.where.return_value
    def missing_index():
        raise FailedPrecondition("The query requires an index. You can create it here")
        yield  # The real error is raised while consuming the stream.
    filtered.order_by.return_value.limit.return_value.stream.side_effect = missing_index
    base = datetime(2026, 10, 14, tzinfo=timezone.utc)
    docs = []
    for number in reversed(range(60)):
        data = {"created_at": base + timedelta(seconds=number), "content": str(number)}
        docs.append(NS(id=str(number), to_dict=lambda data=data: data))
    filtered.stream.return_value = iter(docs)
    messages = repo._get_recent_messages(field, "owned", 6)
    assert [m["content"] for m in messages] == list(map(str, range(54, 60)))
    repo.collection.where.assert_called_once_with(field, "==", "owned")
    filtered.stream.assert_called_once_with()


def test_history_does_not_hide_other_firestore_failures():
    from google.api_core.exceptions import FailedPrecondition
    repo = ChatHistoryRepository.__new__(ChatHistoryRepository)
    repo.collection = Mock()
    filtered = repo.collection.where.return_value
    filtered.order_by.return_value.limit.return_value.stream.side_effect = FailedPrecondition("Database is unavailable")
    with pytest.raises(FailedPrecondition, match="Database is unavailable"):
        repo.get_messages_by_session("s")
    filtered.stream.assert_not_called()


def test_deploy_config_includes_both_recent_chat_history_indexes():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "firebase.json").read_text(encoding="utf-8"))
    indexes = json.loads((root / config["firestore"]["indexes"]).read_text(encoding="utf-8"))["indexes"]
    for field in ("session_id", "assessment_id"):
        assert any(index["collectionGroup"] == "chat_history" and index["fields"] == [
            {"fieldPath": field, "order": "ASCENDING"},
            {"fieldPath": "created_at", "order": "DESCENDING"},
        ] for index in indexes)


def test_response_timestamps_always_include_timezone():
    result = api.ChatMessageResponse(message_id="x", role="assistant", content="x", created_at="2026-10-30T05:00:00")
    assert result.created_at.endswith("+00:00")


def test_crisis_reopens_closed_session_and_replays_without_duplicate(stores):
    async def scenario():
        await send(stores, "1")
        await send(stores, "2")
        closed = await send(stores, "3")
        calls = stores.generator.generate_response.call_count
        crisis = await send(stores, "safety", "Tôi không tự tử trước đây, nhưng bây giờ tôi muốn chết.")
        assert crisis["current_stage"] == "crisis_support" and not crisis["is_session_completed"]
        assert crisis["user_turn_count"] == 0
        assert crisis["user_message"]["session_id"] != closed["user_message"]["session_id"]
        assert stores.generator.generate_response.call_count == calls
        count = len(list(stores.history.collection.stream()))
        replay = await send(stores, "safety", "Tôi không tự tử trước đây, nhưng bây giờ tôi muốn chết.")
        assert replay["assistant_message"] == crisis["assistant_message"]
        assert len(list(stores.history.collection.stream())) == count
    asyncio.run(scenario())


def test_busy_worker_does_not_block_immediate_safety_support(stores):
    ledger = ChatRequestRepository(stores.db)
    claim = ledger.claim("assessment", "owner", "pending", "send", "work")
    result = asyncio.run(send(stores, "safety", "Tôi muốn chết"))
    assert result["persistence_pending"] and result["current_stage"] == "crisis_support"
    stores.generator.generate_response.assert_not_called()
    ledger.release(claim)


def test_expired_session_gets_clean_context(stores):
    first = asyncio.run(send(stores, "1"))
    old_id = first["user_message"]["session_id"]
    stores.sessions.collection.document(old_id).update({
        "last_activity_at": datetime.now(timezone.utc) - timedelta(minutes=65),
    })
    second = asyncio.run(send(stores, "2"))
    assert second["user_message"]["session_id"] != old_id
    assert second["user_turn_count"] == 1
    assert stores.generator.generate_response.call_args.kwargs["conversation_history"] == []


def test_http_contract_and_input_bounds(stores):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.get_current_user] = lambda: {"uid": "owner"}
    app.dependency_overrides[api.get_chat_repo] = lambda: stores.history
    app.dependency_overrides[api.get_chat_session_repo] = lambda: stores.sessions
    app.dependency_overrides[api.get_assessment_repo] = lambda: stores.assessment
    with TestClient(app) as client:
        path = "/api/v1/assessments/assessment/chat"
        assert client.post(path, json={"message": "x" * 1001}).status_code == 422
        response = client.post(path, json={"message": "Khối lượng công việc quá tải", "client_message_id": "http"})
        assert response.status_code == 200
        assert response.json()["assistant_message"]["created_at"].endswith("+00:00")
        history = client.get(path).json()
        assert history["message_count"] == 2
        assert [m["role"] for m in history["messages"]] == ["user", "assistant"]
        assert history["messages"][0]["created_at"] < history["messages"][1]["created_at"]
        stores.assessment.get.return_value = {"user_id": "other"}
        assert client.get(path).status_code == 403
