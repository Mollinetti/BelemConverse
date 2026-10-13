"""mvp-2: suggested follow-up questions after an answer."""

import uuid

import pytest

from belem_converse import follow_ups, gate
from belem_converse.catalog import load_places
from belem_converse.cities import get_city_config
from belem_converse.core.category_matcher import CategoryMatcher
from belem_converse.core.place_cache import PlaceCache
from belem_converse.core.ranking_engine import RankingEngine
from belem_converse.core.unified_retriever import UnifiedRetriever
from tests.conftest import fake_model
from tests.test_deploy_files import CATALOG

LANGUAGES = ["pt-BR", "en"]
CITY = get_city_config()
KNOWN_CATEGORIES = sorted(
    set(CITY.category_mappings) | set(CITY.subcategory_mappings) | set(CITY.category_labels)
)


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize(
    "slots",
    [
        {},
        {"categories": ["bar"], "min_rating": 4.0},
        {"categories": ["cafe"], "open_now": True, "min_rating": 4.5,
         "proximity_intent_detected": True},
    ],
)
@pytest.mark.parametrize("has_location", [False, True])
def test_two_or_three_chips(slots, language, has_location):
    chips = follow_ups.build(slots, language, has_location)

    assert 2 <= len(chips) <= 3
    assert len(set(chips)) == len(chips)


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("category", KNOWN_CATEGORIES)
def test_every_chip_passes_the_gate(category, language):
    for chips in (
        follow_ups.build({"categories": [category]}, language, has_location=True),
        follow_ups.build({"categories": [category]}, language, has_location=False),
    ):
        for chip in chips:
            assert gate.clean_message(chip) == chip


@pytest.mark.parametrize("language", LANGUAGES)
def test_skips_open_now_when_already_set(language):
    open_now = follow_ups.CHIPS["open_now"][language]

    assert open_now in follow_ups.build({"categories": ["bar"]}, language, False)
    assert open_now not in follow_ups.build(
        {"categories": ["bar"], "open_now": True}, language, False
    )


@pytest.mark.parametrize("language", LANGUAGES)
def test_closest_only_with_location(language):
    closest = follow_ups.CHIPS["closest"][language]

    assert closest not in follow_ups.build({"categories": ["bar"]}, language, False)
    assert closest in follow_ups.build({"categories": ["bar"]}, language, True)


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("category", list(follow_ups.SIBLING))
def test_sibling_is_never_the_current_category(category, language):
    current = CITY.category_labels.get(category, {}).get(language)

    chips = follow_ups.build({"categories": [category]}, language, False)

    labels = {names[language] for names in CITY.category_labels.values()}
    assert any(chip in labels for chip in chips)
    assert current not in chips


@pytest.mark.parametrize(
    ("spelling", "category"),
    [(["açaí"], "acai"), (["ice cream"], "ice_cream"), (["sorveteria"], "ice_cream"),
     (["pub", "bar"], "bar")],
)
def test_planner_spellings_are_recognized(spelling, category):
    # The planner returns "açaí" and "ice cream"; the sibling must still skip them.
    assert follow_ups.canonical(spelling) == category


# --- each chip, asked as a question, does what it says ------------------------


@pytest.fixture(scope="module")
def planner():
    from belem_converse.classifiers.intent_classifier_TFIDF_simple import (
        SimpleTFIDFIntentClassifier,
    )
    from belem_converse.core.query_planner import QueryPlanner

    classifier = SimpleTFIDFIntentClassifier()
    classifier.train()
    return QueryPlanner(intent_classifier=classifier)


def slots_for(planner, chip, language):
    return planner.create_query_plan(
        chip, user_location={"lat": -1.45, "lng": -48.49}, explicit_language=language
    ).slots


@pytest.mark.parametrize("language", LANGUAGES)
def test_filter_chips_set_their_filter(planner, language):
    assert slots_for(planner, follow_ups.CHIPS["open_now"][language], language)["open_now"]
    assert slots_for(planner, follow_ups.CHIPS["closest"][language], language)[
        "proximity_intent_detected"
    ]
    assert slots_for(planner, follow_ups.CHIPS["top_rated"][language], language)["min_rating"]


# Main catalog categories each suggested kind of place should bring back.
CATALOG_CATEGORIES = {
    "cafe": {"Cafe", "Bakery", "Coffee shop"},
    "acai": {"Açaí shop"},
    "ice_cream": {"Ice cream shop"},
}


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("category", sorted(set(follow_ups.SIBLING.values())))
def test_category_chips_name_their_category(planner, category, language):
    label = CITY.category_labels[category][language]

    found = slots_for(planner, label, language)["categories"] or []

    assert follow_ups.canonical(found) == category


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("category", ["acai", "ice_cream", "cafe"])
def test_category_chips_find_that_kind_of_place(planner, category, language):
    # On the real catalog, tapping the chip brings back that kind of place.
    retriever = UnifiedRetriever(
        PlaceCache(load_places(CATALOG)), CategoryMatcher(planner.intent_classifier), RankingEngine()
    )
    plan = planner.create_query_plan(CITY.category_labels[category][language], explicit_language=language)
    places = retriever.retrieve({"intent": plan.intent, "slots": plan.slots,
                                 "retrieval_strategy": "structured_only",
                                 "proximity_intent_detected": False}).places

    assert {p["categoryName"] for p in places[:5]} <= CATALOG_CATEGORIES[category]


def test_answer_carries_follow_ups(client, monkeypatch):
    fake_model(monkeypatch, return_value=None)

    body = client.post(
        "/api/chat",
        json={"session_id": str(uuid.uuid4()), "message": "bares", "language": "en"},
    ).json()

    assert body["follow_ups"] == follow_ups.build({"categories": ["bar"]}, "en", False)
