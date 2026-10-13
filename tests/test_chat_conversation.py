"""mvp-2: a conversation is 4 answered questions, and follow-ups refine."""

import uuid

import pytest

import api.routes as routes
from belem_converse.core.unified_retriever import UnifiedRetriever
from belem_converse.sessions import SessionStore
from tests.conftest import fake_model
from tests.test_sessions import FakeClock

QUESTION = "lugares bem avaliados"


def ask(client, session_id, message, language="pt-BR"):
    return client.post(
        "/api/chat", json={"session_id": session_id, "message": message, "language": language}
    )


@pytest.fixture
def model(monkeypatch):
    return fake_model(monkeypatch, return_value=None)


@pytest.fixture
def plans(monkeypatch):
    """The slots of every plan sent to the retriever."""
    sent = []
    original = UnifiedRetriever.retrieve

    def spy(self, plan):
        sent.append(plan["slots"])
        return original(self, plan)

    monkeypatch.setattr(UnifiedRetriever, "retrieve", spy)
    return sent


def test_turn_countdown(client, model):
    session_id = str(uuid.uuid4())

    turns_left = [ask(client, session_id, QUESTION).json()["turns_left"] for _ in range(4)]

    assert turns_left == [3, 2, 1, 0]


def test_fifth_question_is_refused(client, model):
    session_id = str(uuid.uuid4())
    for _ in range(4):
        assert ask(client, session_id, QUESTION).status_code == 200

    response = ask(client, session_id, QUESTION)

    assert response.status_code == 409
    assert response.json() == {"code": "conversation_finished", "turns_left": 0}
    assert model.await_count == 4


def test_new_session_gets_fresh_turns(client, model):
    finished = str(uuid.uuid4())
    for _ in range(4):
        ask(client, finished, QUESTION)

    assert ask(client, str(uuid.uuid4()), QUESTION).json()["turns_left"] == 3


def test_expired_session_starts_fresh(client, model, monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(routes, "sessions", SessionStore(clock=clock))
    session_id = str(uuid.uuid4())
    for _ in range(4):
        ask(client, session_id, QUESTION)

    clock.now += 30 * 60 + 1

    assert ask(client, session_id, QUESTION).json()["turns_left"] == 3


def test_rejected_input_does_not_consume_a_turn(client, model):
    session_id = str(uuid.uuid4())

    assert ask(client, session_id, "bares?").status_code == 422

    assert ask(client, session_id, QUESTION).json()["turns_left"] == 3


def test_follow_up_refines(client, model, plans):
    session_id = str(uuid.uuid4())

    ask(client, session_id, "bares bem avaliados")
    ask(client, session_id, "abertos agora")

    refined = plans[-1]
    assert "bar" in refined["categories"]
    assert refined["open_now"] is True
    assert refined["min_rating"] == plans[0]["min_rating"]


def test_new_category_starts_fresh(client, model, plans):
    session_id = str(uuid.uuid4())

    ask(client, session_id, "bares bem avaliados")
    ask(client, session_id, "abertos agora")
    ask(client, session_id, "cafés")

    fresh = plans[-1]
    assert "cafe" in fresh["categories"]
    assert "bar" not in fresh["categories"]
    assert not fresh["open_now"]
    assert fresh["min_rating"] is None
