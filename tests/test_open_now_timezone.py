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
