"""mvp-1: the tour feature is removed from chat.

Tour phrases must route like any other place question: the intent classifier
has no tour label, the planner never emits a tour intent, and no tour entry
points remain for the API to call.
"""

import pytest

from belem_converse.classifiers.intent_classifier_TFIDF_simple import (
    SimpleTFIDFIntentClassifier,
)
from belem_converse.core.query_planner import QueryPlanner

TOUR_QUERY = "monte um roteiro de um dia em Belém"


@pytest.fixture(scope="module")
def trained_classifier():
    classifier = SimpleTFIDFIntentClassifier()
    classifier.train()
    return classifier


def test_intent_classifier_cannot_predict_tour_planning(trained_classifier):
    # A stale pickle that still carries the label would also fail here.
    assert "tour_planning" not in trained_classifier.intent_classifier.classes_


def test_classifier_model_version_is_3_0():
    # The bump is what forces existing installs to retrain without the label.
    assert SimpleTFIDFIntentClassifier.MODEL_VERSION == "3.0"


@pytest.mark.parametrize("with_classifier", [False, True], ids=["keyword-fallback", "classifier"])
def test_planner_does_not_route_tour_queries(with_classifier, trained_classifier):
    planner = QueryPlanner(intent_classifier=trained_classifier if with_classifier else None)

    plan = planner.create_query_plan(TOUR_QUERY)

    assert plan.intent != "tour_planning"


def test_core_exports_no_tour_planner():
    import belem_converse.core as core

    assert not hasattr(core, "TourPlanner")


def test_routes_have_no_tour_branch():
    import api.routes as routes

    assert not hasattr(routes, "_is_tour_planning_query")
