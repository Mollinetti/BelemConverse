"""mvp-2: "Ver mais" pages through the last answer's ranked list for free."""

import time
import uuid

import pytest

import api.dependencies as deps
import api.routes as routes
from belem_converse.core.unified_retriever import UnifiedRetriever
from tests.conftest import fake_model

USER = {"lat": -1.4527, "lng": -48.4914}
PLACES = [
    {
        "placeId": f"r{i:02d}",
        "title": f"Restaurante Número {i}",
        "categories": ["Restaurant"],
        "categoryName": "Restaurant",
        "place_type": "restaurant",
        "address": f"Rua {i}",
        "neighborhood": "Nazaré",
        "city": "Belém",
        "state": "PA",
        "location": {"lat": USER["lat"] + i * 0.0005, "lng": USER["lng"]},
        "phone": None,
        "website": None,
        "url": None,
        "totalScore": round(3.5 + i * 0.1, 1),  # distinct, so the order is fixed
        "reviewsCount": 100,
        "isSponsored": False,
        "businessTime": None,
    }
    for i in range(1, 13)
]


@pytest.fixture
def twelve(client, monkeypatch):
    """The client over a catalog of 12 restaurants; yields the retriever's ranked ids."""
    monkeypatch.setattr(deps, "_catalog", PLACES)
    for attr in ("_place_cache", "_category_matcher", "_ranking_engine", "_retriever"):
        monkeypatch.setattr(routes, attr, None)
    ranked = []
    original = UnifiedRetriever.retrieve

    def spy(self, plan):
        result = original(self, plan)
        ranked.append([p["placeId"] for p in result.places])
        return result

    monkeypatch.setattr(UnifiedRetriever, "retrieve", spy)
    return ranked


def post(client, session_id, **body):
    response = client.post(
        "/api/chat", json={"session_id": session_id, "language": "pt-BR", **body}
    )
    assert response.status_code == 200, response.text
    return response.json()


def ids(body):
    return [r["placeId"] for r in body["results"]]


def test_pages_in_ranked_order(client, twelve, monkeypatch):
    fake_model(monkeypatch, return_value=None)
    session_id = str(uuid.uuid4())

    first = post(client, session_id, message="restaurantes")
    second = post(client, session_id, action="more")
    third = post(client, session_id, action="more")

    order = twelve[0]
    assert len(order) == 12
    assert ids(first) == order[:5] and first["has_more"] is True
    assert ids(second) == order[5:10] and second["has_more"] is True
    assert ids(third) == order[10:12] and third["has_more"] is False


def test_see_more_is_free(client, twelve, monkeypatch):
    model = fake_model(monkeypatch, return_value=None)
    session_id = str(uuid.uuid4())
    first = post(client, session_id, message="restaurantes")

    pages = [post(client, session_id, action="more") for _ in range(2)]

    assert len(twelve) == 1  # one search, for the question
    assert model.await_count == 1
    assert [p["turns_left"] for p in pages] == [first["turns_left"]] * 2
    assert all(p["follow_ups"] == [] for p in pages)


def test_see_more_keeps_distances(client, twelve, monkeypatch):
    fake_model(monkeypatch, return_value=None)
    session_id = str(uuid.uuid4())
    post(client, session_id, message="restaurantes perto de mim", userLocation=USER)

    page = post(client, session_id, action="more")

    assert page["results"]
    assert all(r["distanceKm"] is not None for r in page["results"])


def test_see_more_without_previous_results(client):
    response = client.post(
        "/api/chat",
        json={"session_id": str(uuid.uuid4()), "action": "more", "language": "pt-BR"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "no_previous_results"


def test_see_more_is_fast(client, twelve, monkeypatch):
    fake_model(monkeypatch, return_value=None)
    session_id = str(uuid.uuid4())
    post(client, session_id, message="restaurantes")

    start = time.perf_counter()
    post(client, session_id, action="more")

    assert time.perf_counter() - start <= 0.15
