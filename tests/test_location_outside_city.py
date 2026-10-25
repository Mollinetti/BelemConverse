"""mvp-2: a visitor outside Belém cannot search by proximity.

Distances from another city are meaningless ("4,000 km away"), so a location
outside the city profile's bounds is discarded: no distance filter or sort, no
distances on the cards, no "closest to me" chip, and a question that asked for
something nearby is told why.
"""

import uuid

import pytest

from api.routes import OUTSIDE_CITY_NOTICE
from belem_converse import follow_ups
from belem_converse.cities import get_city_config
from tests.conftest import fake_model

IN_BELEM = {"lat": -1.4527, "lng": -48.4914}  # Praça da República
SAO_PAULO = {"lat": -23.5505, "lng": -46.6333}


def ask(client, message, location, language="pt-BR"):
    response = client.post(
        "/api/chat",
        json={"session_id": str(uuid.uuid4()), "message": message, "language": language,
              "userLocation": location},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_bounds_come_from_the_city_profile():
    city = get_city_config()
    assert city.is_within_bounds(IN_BELEM["lat"], IN_BELEM["lng"])
    assert not city.is_within_bounds(SAO_PAULO["lat"], SAO_PAULO["lng"])


def test_inside_belem_nearby_search_works(client, monkeypatch):
    fake_model(monkeypatch, return_value=None)

    body = ask(client, "lugares bem avaliados perto de mim", IN_BELEM)

    assert any(r["distanceKm"] is not None for r in body["results"])
    assert not body["answer"].startswith(OUTSIDE_CITY_NOTICE["pt-BR"])


@pytest.mark.parametrize(
    ("message", "language"),
    [("lugares bem avaliados perto de mim", "pt-BR"), ("best rated places near me", "en")],
)
def test_outside_belem_nearby_search_is_refused_with_a_notice(client, monkeypatch, message, language):
    model = fake_model(monkeypatch, return_value=None)

    body = ask(client, message, SAO_PAULO, language)

    assert body["answer"].startswith(OUTSIDE_CITY_NOTICE[language])
    assert body["results"], "the visitor still gets places from the whole city"
    assert all(r["distanceKm"] is None for r in body["results"])
    assert follow_ups.CHIPS["closest"][language] not in body["follow_ups"]
    sent_places = model.await_args.args[1]
    assert all(p.get("distanceKm") is None for p in sent_places)


def test_outside_belem_without_a_nearby_question_has_no_notice(client, monkeypatch):
    fake_model(monkeypatch, return_value=None)

    body = ask(client, "lugares bem avaliados", SAO_PAULO)

    assert not body["answer"].startswith(OUTSIDE_CITY_NOTICE["pt-BR"])
    assert all(r["distanceKm"] is None for r in body["results"])
    assert follow_ups.CHIPS["closest"]["pt-BR"] not in body["follow_ups"]


def test_outside_location_is_not_kept_for_see_more(client, monkeypatch):
    fake_model(monkeypatch, return_value=None)
    session_id = str(uuid.uuid4())
    client.post("/api/chat", json={"session_id": session_id, "message": "lugares perto de mim",
                                   "language": "pt-BR", "userLocation": SAO_PAULO})

    page = client.post("/api/chat", json={"session_id": session_id, "action": "more",
                                          "language": "pt-BR"}).json()

    assert all(r["distanceKm"] is None for r in page.get("results", []))
