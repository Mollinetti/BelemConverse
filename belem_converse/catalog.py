"""Read the place catalog built by ``python -m belem_converse.tools.build_catalog``."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def load_places(path: Path | str) -> list[dict]:
    """All places in the catalog, as the dicts the retriever and ranker read."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Place catalog not found at {path}. "
            "Build it with: python -m belem_converse.tools.build_catalog"
        )
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM places ORDER BY rowid").fetchall()
    finally:
        conn.close()
    return [_to_place(row) for row in rows]


def _to_place(row: sqlite3.Row) -> dict:
    return {
        "placeId": row["placeId"],
        "title": row["title"],
        "categories": json.loads(row["categories"]),
        "categoryName": row["categoryName"],
        "place_type": row["place_type"],
        "address": row["address"],
        "neighborhood": row["neighborhood"],
        "city": row["municipality"],
        "state": row["state"],
        "location": {"lat": row["lat"], "lng": row["lng"]},
        "phone": row["phone"],
        "website": row["website"],
        "url": row["url"],
        "totalScore": row["rating"],
        "reviewsCount": row["reviewsCount"],
        "isSponsored": bool(row["is_sponsored"]),
        "businessTime": row["hours_raw"],
    }
