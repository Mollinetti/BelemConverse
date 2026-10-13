"""mvp-2: fair use — 20 messages per visitor per 10 minutes, and a daily model cap."""

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import api.routes as routes
from belem_converse.limits import DailyCap, RateLimiter
from tests.conftest import fake_model
from tests.test_sessions import FakeClock


def test_twenty_hits_then_denied():
    limiter = RateLimiter(max_hits=20, window_s=600, clock=FakeClock())

    assert all(limiter.hit("a") for _ in range(20))
    assert limiter.hit("a") is False


def test_allowed_again_after_window():
    clock = FakeClock()
    limiter = RateLimiter(max_hits=20, window_s=600, clock=clock)
    for _ in range(21):
        limiter.hit("a")

    clock.now += 600

    assert limiter.hit("a") is True


def test_keys_are_counted_separately():
    limiter = RateLimiter(max_hits=1, window_s=600, clock=FakeClock())

    assert limiter.hit("a") and limiter.hit("b")
    assert not limiter.hit("a")


def test_idle_visitors_are_forgotten():
    clock = FakeClock()
    limiter = RateLimiter(max_hits=20, window_s=600, clock=clock, max_keys=10)
    for i in range(10):
        limiter.hit(f"old{i}")
    clock.now += 600

    limiter.hit("new")

    assert len(limiter) == 1


# --- API -----------------------------------------------------------------------


def see_more(client, forwarded_for):
    return client.post(
        "/api/chat",
        json={"session_id": str(uuid.uuid4()), "action": "more", "language": "pt-BR"},
        headers={"X-Forwarded-For": forwarded_for},
    )


def test_twenty_first_message_is_rate_limited(client):
    responses = [see_more(client, "1.2.3.4, 10.0.0.1") for _ in range(21)]

    assert 429 not in [r.status_code for r in responses[:20]]
    assert responses[20].status_code == 429
    assert responses[20].json()["code"] == "rate_limited"


def test_other_visitor_is_unaffected(client):
    for _ in range(21):
        see_more(client, "1.2.3.4, 10.0.0.1")

    assert see_more(client, "1.2.3.4, 10.0.0.2").status_code != 429


def test_left_most_value_is_ignored(client):
    for i in range(20):
        see_more(client, f"9.9.9.{i}, 10.0.0.1")

    assert see_more(client, "8.8.8.8, 10.0.0.1").status_code == 429


def test_socket_address_without_forwarded_header(client):
    for _ in range(20):
        client.post(
            "/api/chat",
            json={"session_id": str(uuid.uuid4()), "action": "more", "language": "pt-BR"},
        )

    response = client.post(
        "/api/chat", json={"session_id": str(uuid.uuid4()), "action": "more", "language": "pt-BR"}
    )
    assert response.status_code == 429


def test_rate_limited_request_does_not_consume_a_turn(client, monkeypatch):
    fake_model(monkeypatch, return_value=None)
    monkeypatch.setattr(routes, "rate_limiter", RateLimiter(max_hits=1))
    session_id = str(uuid.uuid4())
    body = {"session_id": session_id, "message": "bares", "language": "pt-BR"}
    client.post("/api/chat", json=body)

    assert client.post("/api/chat", json=body).status_code == 429

    monkeypatch.setattr(routes, "rate_limiter", RateLimiter())
    assert client.post("/api/chat", json=body).json()["turns_left"] == 2


# --- daily model cap -------------------------------------------------------------


def test_daily_cap_falls_back_to_template(client, monkeypatch):
    monkeypatch.setenv("LLM_DAILY_CAP", "2")
    monkeypatch.setattr(routes, "daily_cap", DailyCap())
    model = fake_model(
        monkeypatch, side_effect=lambda question, places, language, **kw: f"**{places[0]['title']}**"
    )

    responses = [
        client.post(
            "/api/chat",
            json={"session_id": str(uuid.uuid4()), "message": "lugares bem avaliados",
                  "language": "pt-BR"},
        )
        for _ in range(3)
    ]

    assert [r.status_code for r in responses] == [200, 200, 200]
    assert [r.json()["debug"]["answer_source"] for r in responses] == ["llm", "llm", "template"]
    assert responses[2].json()["results"]
    assert model.await_count == 2


def test_daily_cap_resets_on_a_new_city_day():
    belem = ZoneInfo("America/Belem")
    now = [datetime(2026, 10, 13, 23, 59, tzinfo=belem)]
    cap = DailyCap(cap=1, clock=lambda: now[0])
    assert cap.take() is True
    assert cap.take() is False

    now[0] += timedelta(minutes=2)  # 00:01 the next day in Belém

    assert cap.take() is True


def test_daily_cap_reads_the_environment(monkeypatch):
    monkeypatch.setenv("LLM_DAILY_CAP", "7")
    assert DailyCap().cap == 7
    monkeypatch.setenv("LLM_DAILY_CAP", "lots")
    assert DailyCap().cap == 800
    monkeypatch.delenv("LLM_DAILY_CAP")
    assert DailyCap().cap == 800
