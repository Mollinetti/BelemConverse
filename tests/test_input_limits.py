"""mvp-3 F09/F10: bounded filter fields, and no visitor location or raw input in the logs."""

import logging
import uuid

import pytest


def post(client, **fields):
    return client.post(
        "/api/chat",
        json={"session_id": str(uuid.uuid4()), "message": "lugares bem avaliados",
              "language": "pt-BR", **fields},
    )


@pytest.mark.parametrize(
    "filters",
    [
        {"city": "x" * 101},
        {"neighborhood": "x" * 101},
        {"placeType": ["restaurant"] * 11},
        {"placeType": ["x" * 51]},
    ],
)
def test_oversized_filters_are_rejected(client, filters):
    assert post(client, filters=filters).status_code == 422


def test_ordinary_filters_still_work(client):
    filters = {"city": "Belém", "neighborhood": "Nazaré", "placeType": ["restaurant", "cafe"]}

    assert post(client, filters=filters).status_code == 200


def test_logs_hold_no_visitor_location_or_raw_now(client, caplog):
    caplog.set_level(logging.INFO)

    response = post(
        client,
        userLocation={"lat": -1.4558123, "lng": -48.4902456},
        nowIso="2026-10-25T10:00:00Z\nFORGED LOG LINE",
    )

    assert response.status_code == 200
    assert "-1.4558123" not in caplog.text
    assert "-48.4902456" not in caplog.text
    assert "FORGED" not in caplog.text
