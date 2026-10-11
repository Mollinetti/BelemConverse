"""mvp-1: retrieval stays fast on a catalog the size of Belém's.

The spec targets a median backend time of 100 ms excluding the model. A real
catalog has ~2,900 places but only a few hundred distinct category strings and
hours strings, so per-request work must scale with those, not with the place
count. Bounds are generous (several times the fixed cost) so the tests catch
an order-of-magnitude regression without being sensitive to machine speed.
"""

import time

import pytest

from belem_converse.classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier
from belem_converse.core.category_matcher import CategoryMatcher
from belem_converse.core.place_cache import PlaceCache
from belem_converse.core.ranking_engine import RankingEngine
from belem_converse.core.unified_retriever import UnifiedRetriever

PLACE_COUNT = 3000
CATEGORIES = [f"Specialty shop {i}" for i in range(36)] + ["Restaurant", "Bar", "Cafe", "Açaí shop"]
HOURS = [
    "Monday-Sunday: 8 AM to 6 PM",
    "Monday-Friday: 9 AM to 5 PM; Saturday-Sunday: Closed",
    "Monday-Sunday: 6 PM to 2 AM",
    "Monday-Saturday: 11 AM to 3 PM, 6 PM to 11 PM; Sunday: Closed",
    "Monday-Sunday: Open 24 hours",
    "Tuesday-Sunday: 7 AM to 1 PM",
]
BUDGET_S = 0.5


@pytest.fixture(scope="module")
def retriever():
    places = [
        {
            "placeId": f"place-{i}",
            "title": f"Lugar {i}",
            "categories": [CATEGORIES[i % len(CATEGORIES)]],
            "categoryName": CATEGORIES[i % len(CATEGORIES)],
            "place_type": "other",
            "location": {"lat": -1.45 + (i % 100) * 1e-4, "lng": -48.49 + (i // 100) * 1e-4},
            "totalScore": 4.0 + (i % 10) / 10,
            "reviewsCount": i % 500,
            "businessTime": HOURS[i % len(HOURS)],
        }
        for i in range(PLACE_COUNT)
    ]
    classifier = SimpleTFIDFIntentClassifier()
    classifier.train()
    return UnifiedRetriever(
        place_cache=PlaceCache(places),
        category_matcher=CategoryMatcher(classifier),
        ranking_engine=RankingEngine(),
    )


def timed(retriever, slots):
    start = time.perf_counter()
    retriever.retrieve({"intent": "find_places", "slots": slots})
    return time.perf_counter() - start


def test_category_filter_without_location_is_fast(retriever):
    # No location means no radius to narrow the candidates: every place is matched.
    assert timed(retriever, {"categories": ["restaurant"]}) < BUDGET_S


def test_open_now_filter_is_fast(retriever):
    assert timed(retriever, {"open_now": True}) < BUDGET_S
