"""mvp-1: the SQLite catalog loads into the place dicts the retriever reads."""

import pytest

from belem_converse.catalog import load_places
from belem_converse.classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier
from belem_converse.core.category_matcher import CategoryMatcher
from belem_converse.core.place_cache import PlaceCache
from belem_converse.core.ranking_engine import RankingEngine
from belem_converse.core.unified_retriever import UnifiedRetriever


@pytest.fixture
def places(built_catalog):
    return load_places(built_catalog)


def by_id(places, place_id):
    return next(p for p in places if p["placeId"] == place_id)


def test_load_places_maps_rows_to_retriever_keys(places):
    assert len(places) == 16
    bakery = by_id(places, "ChIJhours12h")
    assert bakery["title"] == "Padaria Estrela"
    assert bakery["categories"] == ["Bakery"]
    assert bakery["location"] == {"lat": -1.4527, "lng": -48.4914}
    assert bakery["totalScore"] == 4.5
    assert bakery["reviewsCount"] == 50
    assert bakery["businessTime"] == "Monday-Sunday: 8 AM to 2 PM"


def test_load_places_keeps_missing_values_missing(places):
    assert by_id(places, "ChIJzeroReviews")["totalScore"] is None
    assert by_id(places, "ChIJhoursEmpty")["businessTime"] is None


def test_place_cache_finds_loaded_place(places):
    cache = PlaceCache(places)
    assert cache.get_by_id("ChIJmosqueiro")["title"] == "Barraca da Praia do Farol"


def test_retriever_finds_restaurants_in_catalog(places):
    classifier = SimpleTFIDFIntentClassifier()
    classifier.train()
    retriever = UnifiedRetriever(
        place_cache=PlaceCache(places),
        category_matcher=CategoryMatcher(classifier),
        ranking_engine=RankingEngine(),
    )

    result = retriever.retrieve(
        {"intent": "find_places", "slots": {"categories": ["restaurant"]}, "retrieval_strategy": "structured_only"}
    )

    assert "ChIJtitleCaps" in {p["placeId"] for p in result.places}  # "Restaurante do Pará"
