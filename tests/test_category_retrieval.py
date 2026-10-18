"""mvp-2: açaí, ice cream and restaurant questions find the right places.

Runs the real planner, matcher and retriever over the committed catalog
(catalog/belem.sqlite), so it checks what a visitor would actually see.
"""

import logging

import pytest

from belem_converse.catalog import load_places
from belem_converse.classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier
from belem_converse.core.category_matcher import CategoryMatcher
from belem_converse.core.place_cache import PlaceCache
from belem_converse.core.query_planner import QueryPlanner
from belem_converse.core.ranking_engine import RankingEngine
from belem_converse.core.unified_retriever import UnifiedRetriever
from tests.test_deploy_files import CATALOG


@pytest.fixture(scope="module")
def classifier():
    logging.disable(logging.INFO)
    clf = SimpleTFIDFIntentClassifier()
    clf.train()
    yield clf
    logging.disable(logging.NOTSET)


@pytest.fixture(scope="module")
def planner(classifier):
    return QueryPlanner(intent_classifier=classifier)


@pytest.fixture(scope="module")
def matcher(classifier):
    return CategoryMatcher(classifier)


@pytest.fixture(scope="module")
def retriever(classifier, matcher):
    return UnifiedRetriever(PlaceCache(load_places(CATALOG)), matcher, RankingEngine())


def categories(planner, message, language="pt-BR"):
    return planner.create_query_plan(message, explicit_language=language).slots["categories"] or []


def top(planner, retriever, message, language="pt-BR", n=5):
    plan = planner.create_query_plan(message, explicit_language=language)
    result = retriever.retrieve({
        "intent": plan.intent, "slots": plan.slots, "retrieval_strategy": "structured_only",
        "proximity_intent_detected": False, "language": plan.language,
    })
    return [p["categoryName"] for p in result.places[:n]]


# --- planner: keywords are whole words -----------------------------------------


@pytest.mark.parametrize(
    ("message", "stray"),
    [("sorvete", "vet"), ("perto da Praça da República", "pub"), ("algo barato", "bar"),
     ("bom teatro", "tea")],
)
def test_keywords_do_not_match_inside_other_words(planner, message, stray):
    assert stray not in categories(planner, message)


@pytest.mark.parametrize(
    ("message", "keyword"),
    [("bares", "bar"), ("restaurantes", "restaurante"), ("sorveterias", "sorveteria"),
     ("pubs", "pub"), ("cafés", "cafe")],
)
def test_plural_keywords_still_match(planner, message, keyword):
    assert keyword in categories(planner, message)


# --- matcher: açaí and ice cream are their own kinds of place ------------------


@pytest.mark.parametrize(
    ("place_category", "query", "expected"),
    [
        ("Açaí shop", "açaí", True),
        ("Cafe", "açaí", False),
        ("Bakery", "açaí", False),
        ("Ice cream shop", "ice cream", True),
        ("Ice cream shop", "sorvete", True),
        ("Ice cream shop", "sorveteria", True),
        ("Cafe", "sorvete", False),
        ("Açaí shop", "cafe", False),
        ("Coffee shop", "cafe", True),
    ],
)
def test_category_match(matcher, place_category, query, expected):
    assert matcher.matches({"categories": [place_category]}, [query]) is expected


# --- retrieval over the real catalog ---------------------------------------------


@pytest.mark.parametrize(
    ("message", "language", "category"),
    [
        ("Açaí", "pt-BR", "Açaí shop"),
        ("Onde tomar açaí", "pt-BR", "Açaí shop"),
        ("Sorvete", "pt-BR", "Ice cream shop"),
        ("Sorveterias", "pt-BR", "Ice cream shop"),
        ("Ice cream", "en", "Ice cream shop"),
    ],
)
def test_top_results_have_the_asked_category(planner, retriever, message, language, category):
    assert top(planner, retriever, message, language) == [category] * 5


def test_restaurants_come_before_shops_tagged_restaurant(planner, retriever):
    assert "Açaí shop" not in top(planner, retriever, "restaurantes", n=10)


@pytest.mark.parametrize("message", ["restaurantes", "Restaurantes abertos agora", "sorvete"])
def test_main_category_matches_come_first(planner, retriever, matcher, message):
    # Clock-independent: however many places are open now, a place matched only
    # by a secondary tag never comes before one whose main category was asked for.
    asked = categories(planner, message)
    ranked = top(planner, retriever, message, n=None)
    main = [matcher.matches({"categories": [c]}, asked) for c in ranked]

    assert main == sorted(main, reverse=True)
