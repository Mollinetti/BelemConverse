"""mvp-1: OSM validation marks each catalog place confirmed or unconfirmed.

Confirmation is informational: nothing is deleted, and places whose OSM
coordinates are more than 150 m away are listed for review.
"""

import json
import sqlite3

import pytest
import requests

from belem_converse.ingest.osm_fetcher import OSMPlace
from belem_converse.tools.build_catalog import SCHEMA
from belem_converse.tools.validate_osm import validate

# 1e-5 degrees of latitude ≈ 1.113 m, so these shifts are ≈ 40 m and ≈ 400 m.
SHIFT_40M = 0.000359
SHIFT_400M = 0.003593

CATALOG = [
    ("ChIJveroPeso", "Mercado Ver-o-Peso", -1.4521, -48.5030),
    ("ChIJdocas", "Estação das Docas", -1.4497, -48.5012),
    ("ChIJlanches", "Lanches do Zé", -1.4600, -48.4900),
]


class StubFetcher:
    """Returns fixed OSM features; same names as two catalog places."""

    def fetch(self, categories=None, progress_callback=None):
        return [
            OSMPlace(osm_id=111, osm_type="node", name="Mercado Ver-o-Peso",
                     latitude=-1.4521 + SHIFT_40M, longitude=-48.5030, category="marketplace"),
            OSMPlace(osm_id=222, osm_type="way", name="Estação das Docas",
                     latitude=-1.4497 + SHIFT_400M, longitude=-48.5012, category="attraction"),
        ]


@pytest.fixture
def catalog(tmp_path):
    path = tmp_path / "places.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT INTO places (placeId, title, categories, place_type, municipality, lat, lng) "
        "VALUES (?, ?, '[]', 'other', 'Belém', ?, ?)",
        CATALOG,
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture(autouse=True)
def no_http(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("validate_osm made an HTTP request")

    monkeypatch.setattr(requests.sessions.Session, "request", refuse)


def osm_columns(path):
    conn = sqlite3.connect(path)
    rows = conn.execute("SELECT placeId, osm_verified, osm_id FROM places ORDER BY rowid").fetchall()
    conn.close()
    return rows


def test_places_marked_confirmed_or_unconfirmed(catalog):
    validate(catalog, fetcher=StubFetcher())

    assert osm_columns(catalog) == [
        ("ChIJveroPeso", 1, "node/111"),
        ("ChIJdocas", 1, "way/222"),
        ("ChIJlanches", 0, None),
    ]


def test_report_lists_only_far_matches_as_coordinate_mismatch(catalog):
    report = validate(catalog, fetcher=StubFetcher())

    assert [m["placeId"] for m in report["coordinate_mismatch"]] == ["ChIJdocas"]
    assert 390 <= report["coordinate_mismatch"][0]["distance_m"] <= 410
    assert report["verified"] == 2
    assert report["unverified"] == 1
    saved = json.loads((catalog.parent / "osm_report.json").read_text(encoding="utf-8"))
    assert saved == report


def test_empty_fetch_keeps_existing_verification(catalog):
    # OSMFetcher.fetch() returns [] when every Overpass endpoint fails.
    validate(catalog, fetcher=StubFetcher())

    class DownFetcher:
        def fetch(self, categories=None, progress_callback=None):
            return []

    with pytest.raises(RuntimeError):
        validate(catalog, fetcher=DownFetcher())

    assert [row[1] for row in osm_columns(catalog)] == [1, 1, 0]


def test_validation_deletes_nothing(catalog):
    validate(catalog, fetcher=StubFetcher())

    assert [row[0] for row in osm_columns(catalog)] == ["ChIJveroPeso", "ChIJdocas", "ChIJlanches"]
