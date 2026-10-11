"""Mark which catalog places OpenStreetMap also knows about.

    python -m belem_converse.tools.validate_osm [--catalog PATH]

Fetches points of interest for the city's bounding box from Overpass, matches
them to the catalog by name and distance, and writes ``osm_verified`` /
``osm_id`` into the catalog plus ``osm_report.json`` next to it. Nothing is
deleted: the flag is informational, and confirmed places whose OSM position is
more than 150 m away are listed for review.
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from pathlib import Path

from belem_converse.cities import CityConfig, get_city_config
from belem_converse.ingest.place_matcher import MatchStatus, PlaceMatcher
from belem_converse.utils.config import DATA_DIR

logger = logging.getLogger(__name__)

# A same-name OSM feature within this distance confirms the place.
MATCH_RADIUS_M = 500.0
# Confirmed places farther apart than this are reported as coordinate mismatches.
MISMATCH_M = 150.0


def _default_fetcher(city: CityConfig):
    from belem_converse.ingest.osm_fetcher import OSMFetcher

    (south, west), (north, east) = city.bounds_min, city.bounds_max
    return OSMFetcher(bbox={"south": south, "west": west, "north": north, "east": east})


def validate(catalog_path: Path | str, fetcher=None) -> dict:
    """Flag catalog places confirmed by OSM; return (and save) the report.

    ``fetcher`` is anything with ``fetch() -> list[OSMPlace]``; the default
    queries Overpass for the current city.
    """
    catalog_path = Path(catalog_path)
    fetcher = fetcher or _default_fetcher(get_city_config())
    osm_places = fetcher.fetch()

    conn = sqlite3.connect(catalog_path)
    try:
        rows = conn.execute("SELECT placeId, title, lat, lng FROM places").fetchall()
        candidates = [
            {"placeId": pid, "title": title or "", "location/lat": lat, "location/lng": lng}
            for pid, title, lat, lng in rows
            if lat is not None and lng is not None
        ]
        results = PlaceMatcher(distance_threshold_meters=MATCH_RADIUS_M).match_all(osm_places, candidates)
        matches = {r.csv_place["placeId"]: r for r in results if r.status is MatchStatus.MATCHED}

        conn.execute("UPDATE places SET osm_verified = 0, osm_id = NULL")
        conn.executemany(
            "UPDATE places SET osm_verified = 1, osm_id = ? WHERE placeId = ?",
            [(f"{r.osm_place.osm_type}/{r.osm_place.osm_id}", pid) for pid, r in matches.items()],
        )
        conn.commit()
    finally:
        conn.close()

    mismatches = sorted(
        (
            {
                "placeId": pid,
                "title": r.csv_place["title"],
                "osm_name": r.osm_place.name,
                "osm_id": f"{r.osm_place.osm_type}/{r.osm_place.osm_id}",
                "distance_m": round(r.distance_meters, 1),
            }
            for pid, r in matches.items()
            if r.distance_meters > MISMATCH_M
        ),
        key=lambda m: -m["distance_m"],
    )
    total = len(rows)
    report = {
        "catalog_rows": total,
        "osm_features": len(osm_places),
        "verified": len(matches),
        "unverified": total - len(matches),
        "match_rate": round(len(matches) / total, 3) if total else 0.0,
        "coordinate_mismatch": mismatches,
    }
    (catalog_path.parent / "osm_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--catalog", type=Path, default=None,
        help="places.sqlite (default: the current city's catalog)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    catalog = args.catalog or DATA_DIR / get_city_config().catalog_path
    report = validate(catalog)
    print(
        f"{report['verified']} of {report['catalog_rows']} places confirmed by OSM "
        f"({report['match_rate']:.1%}); {len(report['coordinate_mismatch'])} more than "
        f"{MISMATCH_M:.0f} m off. Report: {catalog.parent / 'osm_report.json'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
