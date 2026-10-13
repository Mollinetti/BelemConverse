"""mvp-1: "open now" is judged on Belém's clock, not the server's.

A server runs on UTC, three hours ahead of Belém (America/Belem, UTC-3, no
daylight saving). A place open 08:00-12:00 is open at 13:30 UTC (10:30 in
Belém) and closed at 16:30 UTC (13:30 in Belém).
"""

from datetime import datetime, timezone

import pytest

import belem_converse.core.unified_retriever as unified_retriever
from belem_converse.classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier
from belem_converse.core.category_matcher import CategoryMatcher
from belem_converse.core.place_cache import PlaceCache
from belem_converse.core.ranking_engine import RankingEngine
from belem_converse.core.unified_retriever import UnifiedRetriever

MORNING_CAFE = {
    "placeId": "ChIJmorningCafe",
    "title": "Café da Manhã",
    "categories": ["Cafe"],
    "categoryName": "Cafe",
    "place_type": "restaurant",
    "location": {"lat": -1.4527, "lng": -48.4914},
    "totalScore": 4.6,
    "reviewsCount": 80,
    "businessTime": "Monday-Sunday: 8 AM to 12 PM",
}


def frozen_clock(instant_utc):
    """A datetime class whose now() is pinned to one instant, honouring tz."""

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:  # naive "now" is the server's local time; servers run on UTC
                return instant_utc.replace(tzinfo=None)
            return instant_utc.astimezone(tz)

    return FrozenDatetime


@pytest.fixture(scope="module")
def retriever():
    classifier = SimpleTFIDFIntentClassifier()
    classifier.train()
    return UnifiedRetriever(
        place_cache=PlaceCache([MORNING_CAFE]),
        category_matcher=CategoryMatcher(classifier),
        ranking_engine=RankingEngine(),
    )


def open_now_ids(retriever):
    result = retriever.retrieve({"intent": "find_places", "slots": {"open_now": True}})
    return {p["placeId"] for p in result.places}


def test_open_now_uses_belem_time_morning(retriever, monkeypatch):
    # Sunday 13:30 UTC = 10:30 in Belém: inside 08:00-12:00.
    monkeypatch.setattr(
        unified_retriever, "datetime", frozen_clock(datetime(2026, 10, 11, 13, 30, tzinfo=timezone.utc))
    )
    assert open_now_ids(retriever) == {"ChIJmorningCafe"}


def test_open_now_uses_belem_time_afternoon(retriever, monkeypatch):
    # Sunday 16:30 UTC = 13:30 in Belém: after closing.
    monkeypatch.setattr(
        unified_retriever, "datetime", frozen_clock(datetime(2026, 10, 11, 16, 30, tzinfo=timezone.utc))
    )
    assert open_now_ids(retriever) == set()


# --- how "open now" is judged from businessTime ------------------------------
# 2026-10-09 is a Friday; Belém is UTC-3, so Belém time = UTC - 3 h.


@pytest.fixture(scope="module")
def classifier():
    model = SimpleTFIDFIntentClassifier()
    model.train()
    return model


def open_now_status(classifier, monkeypatch, business_time, belem_time):
    """{placeId: openNowStatus} for one place with ``business_time`` at ``belem_time``."""
    place = {**MORNING_CAFE, "businessTime": business_time}
    retriever = UnifiedRetriever(
        place_cache=PlaceCache([place]),
        category_matcher=CategoryMatcher(classifier),
        ranking_engine=RankingEngine(),
    )
    utc = belem_time.replace(tzinfo=timezone.utc) + (datetime(2000, 1, 1, 3) - datetime(2000, 1, 1))
    monkeypatch.setattr(unified_retriever, "datetime", frozen_clock(utc))
    result = retriever.retrieve({"intent": "find_places", "slots": {"open_now": True}})
    return {p["placeId"]: p.get("openNowStatus") for p in result.places}


def test_open_place_is_labelled_open(classifier, monkeypatch):
    status = open_now_status(classifier, monkeypatch, "Monday-Sunday: 8 AM to 12 PM", datetime(2026, 10, 9, 10, 30))
    assert status == {"ChIJmorningCafe": "open"}


def test_place_without_hours_is_labelled_unknown(classifier, monkeypatch):
    status = open_now_status(classifier, monkeypatch, None, datetime(2026, 10, 9, 10, 30))
    assert status == {"ChIJmorningCafe": "unknown"}


def test_open_now_does_not_mutate_the_cached_place(classifier, monkeypatch):
    open_now_status(classifier, monkeypatch, "Monday-Sunday: 8 AM to 12 PM", datetime(2026, 10, 9, 10, 30))
    assert "openNowStatus" not in MORNING_CAFE


@pytest.mark.parametrize("belem_time, expected", [
    (datetime(2026, 10, 9, 16, 0), {"ChIJmorningCafe": "open"}),  # 4 PM
    (datetime(2026, 10, 9, 10, 0), {}),                            # 10 AM, before opening
])
def test_start_time_takes_the_end_times_meridiem(classifier, monkeypatch, belem_time, expected):
    # Google writes "3 to 9 PM" for 3 PM-9 PM.
    assert open_now_status(classifier, monkeypatch, "Monday-Sunday: 3 to 9 PM", belem_time) == expected


@pytest.mark.parametrize("belem_time, expected", [
    (datetime(2026, 10, 10, 1, 0), {"ChIJmorningCafe": "open"}),  # Saturday 1 AM: Friday night
    (datetime(2026, 10, 9, 1, 0), {}),                             # Friday 1 AM: Thursday was closed
    (datetime(2026, 10, 9, 22, 0), {"ChIJmorningCafe": "open"}),   # Friday 10 PM
])
def test_hours_past_midnight_belong_to_the_previous_day(classifier, monkeypatch, belem_time, expected):
    hours = "Monday-Thursday: Closed; Friday: 9 PM to 2 AM; Saturday-Sunday: Closed"
    assert open_now_status(classifier, monkeypatch, hours, belem_time) == expected


@pytest.mark.parametrize("belem_time, expected", [
    (datetime(2026, 10, 9, 3, 0), {"ChIJmorningCafe": "open"}),  # Friday: open 24 hours
    (datetime(2026, 10, 11, 3, 0), {}),                           # Sunday: closed
])
def test_open_24_hours_applies_only_to_its_days(classifier, monkeypatch, belem_time, expected):
    hours = "Monday-Friday: Open 24 hours; Saturday-Sunday: Closed"
    assert open_now_status(classifier, monkeypatch, hours, belem_time) == expected


def test_portuguese_24_hours_is_open_all_day(classifier, monkeypatch):
    hours = "Monday-Wednesday: 08:00 to 22:00; Thursday-Saturday: Atendimento 24 horas; Sunday: 08:00 to 22:00"
    assert open_now_status(classifier, monkeypatch, hours, datetime(2026, 10, 9, 3, 0)) == {"ChIJmorningCafe": "open"}


def test_open_places_rank_before_places_with_unknown_hours(classifier, monkeypatch):
    unknown_star = {**MORNING_CAFE, "placeId": "ChIJunknownStar", "title": "Sem Horário", "totalScore": 5.0,
                    "reviewsCount": 900, "businessTime": None}
    open_plain = {**MORNING_CAFE, "placeId": "ChIJopenPlain", "title": "Aberto Simples", "totalScore": 3.9,
                  "reviewsCount": 10}
    retriever = UnifiedRetriever(
        place_cache=PlaceCache([unknown_star, open_plain]),
        category_matcher=CategoryMatcher(classifier),
        ranking_engine=RankingEngine(),
    )
    # Friday 10:30 in Belém = 13:30 UTC: the 8 AM-12 PM place is open.
    monkeypatch.setattr(unified_retriever, "datetime", frozen_clock(datetime(2026, 10, 9, 13, 30, tzinfo=timezone.utc)))
    result = retriever.retrieve({"intent": "find_places", "slots": {"open_now": True, "sort_preference": "rating"}})
    assert [p["placeId"] for p in result.places] == ["ChIJopenPlain", "ChIJunknownStar"]
