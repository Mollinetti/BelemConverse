"""mvp-1: the catalog build turns the raw export into a clean, verified catalog.

One test per fix. Inputs are the hand-written rows in
tests/fixtures/catalog_raw_sample.csv (20 rows); every expected value below is
derived by hand from those rows.
"""

import json
import sqlite3

import pytest

ALL_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@pytest.fixture
def db(built_catalog):
    conn = sqlite3.connect(built_catalog)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def report(built_catalog):
    return json.loads((built_catalog.parent / "cleaning_report.json").read_text(encoding="utf-8"))


def place(db, place_id):
    row = db.execute("SELECT * FROM places WHERE placeId = ?", (place_id,)).fetchone()
    assert row is not None, f"{place_id} missing from catalog"
    return row


def place_ids(db):
    return {r["placeId"] for r in db.execute("SELECT placeId FROM places")}


def every_day(start, end):
    return {day: {"is_closed": False, "ranges": [{"start": start, "end": end}]} for day in ALL_DAYS}


# --- identity ----------------------------------------------------------------


def test_no_duplicate_place_ids(db):
    total, distinct = db.execute("SELECT count(*), count(DISTINCT placeId) FROM places").fetchone()
    assert total == distinct == 16


def test_duplicates_merge_categories_and_keep_most_reviews(db):
    bar = place(db, "ChIJdupBarParque")
    assert set(json.loads(bar["categories"])) == {"Bar", "Pub"}
    assert bar["reviewsCount"] == 1284
    assert bar["phone"] == "(91) 3222-2222"  # fields come from the more-reviewed row


def test_null_place_id_dropped(db):
    assert db.execute("SELECT count(*) FROM places WHERE placeId IS NULL OR placeId = ''").fetchone()[0] == 0
    titles = {r["title"] for r in db.execute("SELECT title FROM places")}
    assert "Lugar Sem Identificador" not in titles


# --- text repair -------------------------------------------------------------


def test_city_state_normalized(db):
    broken = place(db, "ChIJcityStateBroken")
    assert broken["municipality"] == "Belém"
    assert broken["state"] == "PA"
    assert db.execute(
        "SELECT count(*) FROM places WHERE municipality LIKE '%?%' OR state LIKE '%?%'"
    ).fetchone()[0] == 0
    assert {r["state"] for r in db.execute("SELECT DISTINCT state FROM places")} == {"PA"}
    assert {r["municipality"] for r in db.execute("SELECT DISTINCT municipality FROM places")} == {"Belém"}


def test_garbled_title_repaired_from_raw(db):
    repaired = place(db, "ChIJconvRepairable")
    assert repaired["title"] == "Tudo Conveniência Boaventura"
    assert repaired["title_raw"] == "Tudo Conveni?ncia Boaventura"
    assert repaired["needs_review"] == 0


def test_unrepairable_title_flagged_needs_review(db):
    flagged = place(db, "ChIJconvUnrepairable")
    assert flagged["title"] == "Conveni?ncia AmPm - Ipiranga"
    assert flagged["needs_review"] == 1
    flagged_ids = {r["placeId"] for r in db.execute("SELECT placeId FROM places WHERE needs_review = 1")}
    assert flagged_ids == {"ChIJconvUnrepairable"}


def test_titles_title_cased_with_exceptions(db):
    assert place(db, "ChIJtitleCaps")["title"] == "Restaurante do Pará"
    assert place(db, "ChIJtitleCaps")["title_raw"] == "RESTAURANTE DO PARÁ"
    assert place(db, "ChIJtitleLower")["title"] == "Bar da Praça"
    # Mixed-case titles are someone's deliberate spelling; leave them alone.
    assert place(db, "ChIJcityStateBroken")["title"] == "Café Imaginário"
    assert place(db, "ChIJdupBarParque")["title"] == "Bar do Parque"


def test_address_unified(db):
    assert place(db, "ChIJconvRepairable")["address"] == "Av. Boaventura da Silva, 1200 - Umarizal, Belém - PA"
    assert place(db, "ChIJconvUnrepairable")["address"] == "Av. Almirante Barroso, 3000 - Marco, Belém - PA"
    assert place(db, "ChIJtitleCaps")["address"] == "Tv. Padre Eutíquio, 500 - Batista Campos, Belém - PA"
    assert place(db, "ChIJhours12h")["address"] == "Rua Exemplo, 100 - Belém - PA"


# --- opening hours -----------------------------------------------------------


@pytest.mark.parametrize(
    "place_id, expected_hours, expected_raw",
    [
        ("ChIJhours12h", every_day("08:00:00", "14:00:00"), "Monday-Sunday: 8 AM to 2 PM"),
        ("ChIJhours24clock", every_day("19:00:00", "23:30:00"), "Monday-Sunday: 19:00 to 23:30"),
        ("ChIJhoursAllDay", every_day("00:00:00", "23:59:00"), "Monday-Sunday: Atendimento 24 horas"),
        ("ChIJhoursGarbage", None, None),
        ("ChIJhoursEmpty", None, None),
    ],
    ids=["12h-nnbsp", "24h-clock", "24-horas", "series-garbage", "empty"],
)
def test_hours_parsed_to_schema(db, place_id, expected_hours, expected_raw):
    row = place(db, place_id)
    hours = json.loads(row["hours"]) if row["hours"] is not None else None
    assert (hours["schedules"] if hours else None) == expected_hours
    assert row["hours_raw"] == expected_raw


def test_hours_raw_has_no_narrow_no_break_space(db):
    raws = [r["hours_raw"] for r in db.execute("SELECT hours_raw FROM places WHERE hours_raw IS NOT NULL")]
    assert raws, "expected some parsed hours"
    assert not any(" " in raw for raw in raws)


# --- ratings, sponsorship, columns ------------------------------------------


def test_zero_reviews_rating_null(db):
    zero = place(db, "ChIJzeroReviews")
    assert zero["rating"] is None
    assert zero["reviewsCount"] == 0
    assert place(db, "ChIJhours12h")["rating"] == 4.5


def test_sponsor_columns_unified(db):
    assert place(db, "ChIJsponsorUpper")["is_sponsored"] == 1
    assert place(db, "ChIJsponsorLower")["is_sponsored"] == 1
    assert place(db, "ChIJhours12h")["is_sponsored"] == 0


def test_price_column_absent(db):
    columns = {r["name"] for r in db.execute("PRAGMA table_info(places)")}
    assert "price" not in columns


def test_place_type_recomputed(db):
    assert place(db, "ChIJsnackBar")["place_type"] == "restaurant"
    assert place(db, "ChIJtitleLower")["place_type"] == "bar"
    assert place(db, "ChIJsponsorUpper")["place_type"] == "other"


# --- location filter ---------------------------------------------------------


def test_municipality_filter(db):
    ids = place_ids(db)
    assert "ChIJmosqueiro" in ids
    assert "ChIJananindeua" not in ids
    assert "ChIJoutOfBbox" not in ids


# --- search index ------------------------------------------------------------


def test_fts_finds_title(db):
    hits = {
        r["placeId"]
        for r in db.execute(
            "SELECT p.placeId FROM places_fts f JOIN places p ON p.rowid = f.rowid "
            "WHERE places_fts MATCH 'restaurante'"
        )
    }
    # "Restaurante Distante" was outside the municipality, so it is not indexed either.
    assert hits == {"ChIJtitleCaps"}


# --- report ------------------------------------------------------------------

FIX_KEYS = {
    "duplicates_merged",
    "null_place_id_dropped",
    "outside_municipality_dropped",
    "city_state_normalized",
    "addresses_unified",
    "titles_repaired_from_raw",
    "titles_flagged_needs_review",
    "titles_title_cased",
    "hours_parsed",
    "hours_unknown",
    "hours_garbage_cleared",
    "zero_review_ratings_nulled",
    "sponsor_flags_unified",
}


def test_report_counts_reconcile(report):
    assert report["input_rows"] == 20
    assert report["kept"] == 16
    assert report["merged_duplicates"] == 1
    assert report["dropped"] == 3
    assert report["input_rows"] == report["kept"] + report["merged_duplicates"] + report["dropped"]

    fixes = report["fixes"]
    assert FIX_KEYS <= set(fixes)
    assert all(isinstance(fixes[k], int) and fixes[k] >= 0 for k in FIX_KEYS)
    assert fixes["duplicates_merged"] == 1
    assert fixes["null_place_id_dropped"] == 1
    assert fixes["outside_municipality_dropped"] == 2
    assert fixes["titles_repaired_from_raw"] == 1
    assert fixes["titles_flagged_needs_review"] == 1
    assert fixes["titles_title_cased"] == 2
    assert fixes["hours_garbage_cleared"] == 1
    assert fixes["zero_review_ratings_nulled"] == 1
    assert fixes["sponsor_flags_unified"] == 2
