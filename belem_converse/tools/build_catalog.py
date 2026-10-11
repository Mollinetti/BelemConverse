"""Build the clean place catalog from the raw Google Places export.

    python -m belem_converse.tools.build_catalog [--csv PATH] [--raw-dir DIR] [--out DIR]

Pipeline: normalize → dedupe → filter municipality → repair titles → parse
hours. Writes ``<out>/places.sqlite`` (table ``places`` plus the FTS5 index
``places_fts``) and ``<out>/cleaning_report.json``, which counts every fix and
reconciles ``input_rows == kept + merged_duplicates + dropped``.

Needs the ``tools`` extra (pandas): ``pip install -e ".[tools]"``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from belem_converse.cities import CityConfig, get_city_config
from belem_converse.ingest.csv_ingestion import CSVIngestionPipeline, PlaceTypeInference
from belem_converse.utils.business_hours_parser import BusinessHoursParser
from belem_converse.utils.config import DATA_DIR

logger = logging.getLogger(__name__)

DEFAULT_CSV = DATA_DIR / "csvs" / "combined_all_data.csv"
DEFAULT_RAW_DIR = DATA_DIR / "Raw"
DEFAULT_OUT = DATA_DIR / "belem"

ADDRESS_COLUMNS = ("address", "addressFormatted", "adressFormatted", "formattedAddress")
# A pandas Series pasted into the CSV instead of its value.
GARBAGE_HOURS_MARKERS = ("dtype: object", "Name: openingHours")
NARROW_NBSP = " "

SCHEMA = """
CREATE TABLE places (
    placeId       TEXT PRIMARY KEY,
    title         TEXT,
    title_raw     TEXT,
    categories    TEXT NOT NULL,          -- JSON array
    categoryName  TEXT,
    place_type    TEXT NOT NULL,
    address       TEXT,
    neighborhood  TEXT,
    municipality  TEXT NOT NULL,
    state         TEXT,
    lat           REAL,
    lng           REAL,
    phone         TEXT,
    website       TEXT,
    url           TEXT,
    rating        REAL,                   -- NULL when there are no reviews
    reviewsCount  INTEGER NOT NULL DEFAULT 0,
    is_sponsored  INTEGER NOT NULL DEFAULT 0,
    hours         TEXT,                   -- JSON, BusinessHours.to_dict()
    hours_raw     TEXT,
    needs_review  INTEGER NOT NULL DEFAULT 0,
    osm_verified  INTEGER NOT NULL DEFAULT 0,
    osm_id        TEXT
);
CREATE VIRTUAL TABLE places_fts USING fts5(title, content='places', content_rowid='rowid');
"""
COLUMNS = [
    "placeId", "title", "title_raw", "categories", "categoryName", "place_type",
    "address", "neighborhood", "municipality", "state", "lat", "lng", "phone",
    "website", "url", "rating", "reviewsCount", "is_sponsored", "hours",
    "hours_raw", "needs_review",
]


# --- text helpers -----------------------------------------------------------


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower().strip()


def _names(value: str, target: str) -> bool:
    """True when ``value`` names ``target``, ignoring case and accents.

    A ``?`` in ``value`` stands for one character lost to a broken encoding,
    so "Bel?m" names "Belém".
    """
    v, t = _fold(value), _fold(target)
    if "?" in v:
        return re.fullmatch(re.escape(v).replace(r"\?", "."), t) is not None
    return v == t


def _is_garbled(title: str) -> bool:
    return "?" in title or "�" in title


def _recase(title: str, exceptions: List[str]) -> str:
    """Title-case an all-lowercase or multi-word all-caps title."""
    # ponytail: single all-caps words are left alone (brands like "KFC");
    # an exceptions list per brand is the upgrade if that misfires.
    if not (title.islower() or (title.isupper() and len(title.split()) > 1)):
        return title
    words = title.lower().split(" ")
    return " ".join(
        w if (i and w in exceptions) else w[:1].upper() + w[1:] for i, w in enumerate(words)
    )


# --- loading ----------------------------------------------------------------


def _load_repairs(raw_dir: Path) -> Dict[str, str]:
    """placeId → a clean title, from any raw export under ``raw_dir``."""
    repairs: Dict[str, str] = {}
    for path in sorted(Path(raw_dir).glob("*.csv")):
        try:
            df = pd.read_csv(
                path, dtype=str, keep_default_na=False, encoding_errors="replace",
                usecols=lambda c: c in ("placeId", "title"),
            )
        except (ValueError, pd.errors.ParserError) as exc:
            logger.warning("Skipping repair source %s: %s", path.name, exc)
            continue
        if not {"placeId", "title"} <= set(df.columns):
            continue
        for place_id, title in zip(df["placeId"], df["title"]):
            title = title.strip()
            if place_id and title and not _is_garbled(title):
                repairs.setdefault(place_id, title)
    return repairs


def _record(row: pd.Series, index: int, pipeline: CSVIngestionPipeline) -> Optional[dict]:
    place = pipeline.process_row(row, index)
    if place is None:
        return None
    raw_address = (row.get("address") or "").strip()
    address = next((v for c in ADDRESS_COLUMNS if (v := (row.get(c) or "").strip())), None)
    place.update(
        _raw_city=(row.get("city") or "").strip(),
        _raw_state=(row.get("state") or "").strip(),
        _address=address,
        _address_from_alt=bool(address) and not raw_address,
    )
    return place


# --- pipeline ---------------------------------------------------------------


def _dedupe(records: List[dict]) -> tuple[List[dict], int]:
    """One record per placeId: the most-reviewed row, categories unioned."""
    groups: Dict[str, List[dict]] = {}
    for rec in records:
        groups.setdefault(rec["placeId"], []).append(rec)
    kept, merged = [], 0
    for rows in groups.values():
        keep = max(rows, key=lambda r: r["reviewsCount"] or 0)
        if len(rows) > 1:
            categories: List[str] = []
            for rec in [keep] + [r for r in rows if r is not keep]:
                categories += [c for c in rec["categories"] if c not in categories]
            keep["categories"] = categories
            keep["place_type"] = PlaceTypeInference.infer_place_type(keep["categoryName"], categories)
            merged += len(rows) - 1
        kept.append(keep)
    return kept, merged


def _in_municipality(rec: dict, city: CityConfig) -> bool:
    if not any(_names(rec["_raw_city"], name) for name in city.municipalities):
        return False
    lat, lng = rec["location"]["lat"], rec["location"]["lng"]
    return lat is None or lng is None or city.is_within_bounds(lat, lng)


def _hours(raw: Optional[str], parser: BusinessHoursParser) -> tuple[Optional[str], Optional[str], str]:
    """(hours JSON, cleaned hours_raw, outcome) for one businessTime value."""
    if raw and any(marker in raw for marker in GARBAGE_HOURS_MARKERS):
        return None, None, "garbage"
    clean = (raw or "").replace(NARROW_NBSP, " ").strip() or None
    if clean is None:
        return None, None, "unknown"
    parsed = parser.parse(clean)
    if parsed.parse_error or not any(s.time_ranges for s in parsed.schedules.values()):
        return None, clean, "unknown"
    return json.dumps(parsed.to_dict(), ensure_ascii=False), clean, "parsed"


def build(
    csv_path: Path = DEFAULT_CSV,
    raw_dir: Path = DEFAULT_RAW_DIR,
    out_dir: Path = DEFAULT_OUT,
    city: Optional[CityConfig] = None,
) -> dict:
    """Build ``places.sqlite`` and ``cleaning_report.json`` in ``out_dir``; return the report."""
    city = city or get_city_config()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    pipeline = CSVIngestionPipeline(output_dir=out_dir)
    fixes = dict.fromkeys(
        [
            "duplicates_merged", "null_place_id_dropped", "outside_municipality_dropped",
            "city_state_normalized", "addresses_unified", "titles_repaired_from_raw",
            "titles_flagged_needs_review", "titles_title_cased", "hours_parsed",
            "hours_unknown", "hours_garbage_cleared", "zero_review_ratings_nulled",
            "sponsor_flags_unified",
        ],
        0,
    )

    records = []
    for index, row in df.iterrows():
        rec = _record(row, index, pipeline)
        if rec is None:
            fixes["null_place_id_dropped"] += 1
        else:
            records.append(rec)

    records, fixes["duplicates_merged"] = _dedupe(records)

    in_city = [r for r in records if _in_municipality(r, city)]
    fixes["outside_municipality_dropped"] = len(records) - len(in_city)

    repairs = _load_repairs(raw_dir)
    parser = BusinessHoursParser()
    rows = []
    for rec in in_city:
        title_raw = rec["title"] or ""
        title, needs_review = title_raw, 0
        if _is_garbled(title_raw):
            if rec["placeId"] in repairs:
                title = repairs[rec["placeId"]]
                fixes["titles_repaired_from_raw"] += 1
            else:
                needs_review = 1
                fixes["titles_flagged_needs_review"] += 1
        recased = _recase(title, city.title_case_exceptions)
        if recased != title:
            fixes["titles_title_cased"] += 1

        if rec["_raw_city"] != city.name or rec["_raw_state"] != city.state_code:
            fixes["city_state_normalized"] += 1
        if rec["_address_from_alt"]:
            fixes["addresses_unified"] += 1

        hours, hours_raw, outcome = _hours(rec["businessTime"], parser)
        if outcome == "garbage":
            fixes["hours_garbage_cleared"] += 1
        fixes["hours_parsed" if hours else "hours_unknown"] += 1

        reviews = rec["reviewsCount"] or 0
        rating = rec["totalScore"]
        if reviews == 0 and rating is not None:
            rating = None
            fixes["zero_review_ratings_nulled"] += 1
        if rec["isSponsored"]:
            fixes["sponsor_flags_unified"] += 1

        rows.append(
            (
                rec["placeId"], recased, title_raw,
                json.dumps(rec["categories"], ensure_ascii=False), rec["categoryName"],
                rec["place_type"], rec["_address"], rec["neighborhood"], city.name,
                city.state_code, rec["location"]["lat"], rec["location"]["lng"],
                rec["phone"], rec["website"], rec["url"], rating, reviews,
                int(bool(rec["isSponsored"])), hours, hours_raw, needs_review,
            )
        )

    db_path = out_dir / "places.sqlite"
    tmp_path = out_dir / "places.sqlite.tmp"
    tmp_path.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp_path)
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            f"INSERT INTO places ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})",
            rows,
        )
        conn.execute("INSERT INTO places_fts(places_fts) VALUES('rebuild')")
        conn.commit()
    finally:
        conn.close()
    os.replace(tmp_path, db_path)

    dropped = fixes["null_place_id_dropped"] + fixes["outside_municipality_dropped"]
    report = {
        "input_rows": len(df),
        "kept": len(rows),
        "merged_duplicates": fixes["duplicates_merged"],
        "dropped": dropped,
        "fixes": fixes,
        "sources": {"csv": str(csv_path), "raw_dir": str(raw_dir)},
    }
    (out_dir / "cleaning_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="combined raw export")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR, help="raw exports used to repair titles")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    report = build(args.csv, args.raw_dir, args.out)
    print(
        f"{report['input_rows']} rows in → {report['kept']} kept, "
        f"{report['merged_duplicates']} merged, {report['dropped']} dropped"
    )
    for key, count in report["fixes"].items():
        print(f"  {key}: {count}")
    print(f"Catalog: {args.out / 'places.sqlite'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
