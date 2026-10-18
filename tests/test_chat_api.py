"""mvp-1: POST /api/chat — retrieve, summarize once, never break.

The catalog is the hand-written fixture built by ``built_catalog``; the model
is replaced by an AsyncMock except where the real, unconfigured client is the
point of the test.
"""

import asyncio
import time
import uuid

import httpx
import pytest

import api.dependencies as deps
import api.routes as routes
from api.main import app
from belem_converse.catalog import load_places
from belem_converse.core.unified_retriever import UnifiedRetriever
from tests.conftest import fake_model

TEMPLATE_PREFIX = "Aqui estão os lugares encontrados"
NO_RESULTS_PREFIX = "Não encontrei lugares"


def ask(client, message):
    response = client.post(
        "/api/chat", json={"session_id": str(uuid.uuid4()), "message": message, "language": "pt-BR"}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_llm_answer_used_once(client, monkeypatch):
    sent = []

    def answer(question, places, language, **kwargs):
        sent.append([p["title"] for p in places])
        return f"Recomendo **{places[0]['title']}**."

    model = fake_model(monkeypatch, side_effect=answer)

    # Matches 15 of the 16 fixture places, so the response must be cut to 5.
    body = ask(client, "lugares bem avaliados")

    titles = [r["title"] for r in body["results"]]
    assert len(titles) == 5
    assert model.await_count == 1
    assert sent == [titles]
    assert body["answer"] == f"Recomendo {titles[0]}."
    assert body["debug"]["answer_source"] == "llm"


def test_ungrounded_answer_falls_back(client, monkeypatch):
    fake_model(monkeypatch, return_value="Experimente o **Bar Inventado**, o melhor da cidade.")

    body = ask(client, "lugares bem avaliados")

    assert body["answer"].startswith(TEMPLATE_PREFIX)
    assert "Bar Inventado" not in body["answer"]
    assert body["debug"]["answer_source"] == "template"


def test_no_llm_returns_template(client, monkeypatch):
    fake_model(monkeypatch, return_value=None)

    body = ask(client, "lugares bem avaliados")

    assert body["answer"].startswith(TEMPLATE_PREFIX)
    assert body["results"]
    assert body["debug"]["answer_source"] == "template"


def test_unconfigured_model_answers_with_template(client):
    # The real client with no LLM_* variables set: no request, template answer.
    body = ask(client, "lugares bem avaliados")

    assert body["answer"].startswith(TEMPLATE_PREFIX)
    assert body["debug"]["answer_source"] == "template"


def test_no_results_skips_model(client, monkeypatch):
    model = fake_model(monkeypatch, return_value="should not be used")

    body = ask(client, "academia de musculação")

    assert body["results"] == []
    assert body["answer"].startswith(NO_RESULTS_PREFIX)
    assert model.await_count == 0


def test_tour_query_returns_places(client, monkeypatch):
    fake_model(monkeypatch, return_value=None)

    body = ask(client, "monte um roteiro de um dia em Belém")

    assert body["results"]
    assert "roteiro" not in body["answer"].lower()
    assert "itiner" not in body["answer"].lower()


@pytest.mark.parametrize(
    "message",
    ["me indica lugares bons em Belém", "o que tem para fazer aqui?", "me mostra tudo"],
)
def test_questions_without_categories_are_answered(client, monkeypatch, message):
    # The planner gives these a place_type list and no categories.
    fake_model(monkeypatch, return_value=None)

    body = ask(client, message)

    assert body["answer"]


@pytest.mark.parametrize("path", ["/api/ingest/csv", "/api/clear-history"])
def test_removed_endpoints_are_gone(client, path):
    assert client.post(path).status_code == 404


def test_health_ready(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_distances_do_not_leak_between_visitors(client, monkeypatch):
    fake_model(monkeypatch, return_value=None)
    located = client.post(
        "/api/chat",
        json={"session_id": str(uuid.uuid4()),
              "message": "lugares bem avaliados perto de mim", "language": "pt-BR",
              "userLocation": {"lat": -1.4527, "lng": -48.4914}},
    ).json()
    assert any(r["distanceKm"] is not None for r in located["results"])

    # A second visitor who shares no location must not see the first one's distances.
    body = ask(client, "lugares bem avaliados perto de mim")

    assert all(r["distanceKm"] is None for r in body["results"])
    assert "km away" not in body["answer"]


def test_model_deadline_counts_from_request_start(client, monkeypatch):
    model = fake_model(monkeypatch, return_value=None)
    before = time.monotonic()

    ask(client, "lugares bem avaliados")

    started_at = model.await_args.kwargs["started_at"]
    assert before <= started_at <= time.monotonic()


def test_slow_retrieval_does_not_block_other_requests(built_catalog, monkeypatch):
    monkeypatch.setattr(deps, "_catalog", load_places(built_catalog))
    for attr in ("_place_cache", "_category_matcher", "_ranking_engine", "_retriever"):
        monkeypatch.setattr(routes, attr, None)
    fake_model(monkeypatch, return_value=None)
    original = UnifiedRetriever.retrieve
    entered = {}

    def slow_retrieve(self, plan):
        entered["at"] = time.perf_counter()
        time.sleep(1.0)
        return original(self, plan)

    monkeypatch.setattr(UnifiedRetriever, "retrieve", slow_retrieve)

    async def scenario():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            chat = asyncio.create_task(
                http.post("/api/chat", json={"session_id": str(uuid.uuid4()),
                                       "message": "lugares bem avaliados", "language": "pt-BR"})
            )
            while "at" not in entered:  # wait until the chat request is inside retrieval
                await asyncio.sleep(0.01)
            health = await http.get("/api/health")
            # Measured from when retrieval began: a blocked event loop cannot even
            # resume this coroutine until the 1 s of retrieval is over.
            waited_s = time.perf_counter() - entered["at"]
            chat_response = await chat
            return health.status_code, waited_s, chat_response.status_code

    health_status, waited_s, chat_status = asyncio.run(scenario())

    assert (health_status, chat_status) == (200, 200)
    assert waited_s < 0.5


def test_model_crash_returns_template(client, monkeypatch):
    fake_model(monkeypatch, side_effect=RuntimeError("provider client blew up"))

    body = ask(client, "lugares bem avaliados")

    assert body["answer"].startswith(TEMPLATE_PREFIX)
    assert body["debug"]["answer_source"] == "template"
