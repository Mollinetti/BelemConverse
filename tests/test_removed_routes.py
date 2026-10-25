"""mvp-3 K02: the CSV ingest and clear-history routes stay gone."""

import pytest


def test_route_table_has_no_ingest_or_clear_history(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert not [p for p in paths if "ingest" in p or "clear-history" in p]


@pytest.mark.parametrize("path", ["/api/ingest/csv", "/api/clear-history"])
def test_removed_routes_answer_404_or_405(client, path):
    assert client.post(path).status_code in (404, 405)
