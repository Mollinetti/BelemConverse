"""mvp-1: "abertos" asks for places open now, unless another time is named.

"restaurantes abertos perto da Estação das Docas" (the spec's acceptance
question) must filter by opening hours even without "agora". A named time
("hoje", "amanhã", "domingo", "às 22h") means a different moment, and the
filter can only judge the present.
"""

import pytest

from belem_converse.classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier
from belem_converse.core.query_planner import QueryPlanner


@pytest.fixture(scope="module")
def planner():
    classifier = SimpleTFIDFIntentClassifier()
    classifier.train()
    return QueryPlanner(intent_classifier=classifier)


@pytest.mark.parametrize("message", [
    "restaurantes abertos perto da Estação das Docas",
    "farmácia aberta perto de mim",
    "tem algum bar aberto?",
    "padarias abertas no Umarizal",
    "Restaurants open near Estação das Docas",
])
def test_open_adjective_means_open_now(planner, message):
    assert planner.extract_open_now(message, "pt-BR") is True


@pytest.mark.parametrize("message", [
    "farmacia aberta hoje",  # today, not now
    "restaurante aberto amanhã",
    "bar aberto domingo à noite",
    "padaria aberta às 6h",
    "restaurante fechado agora",
    "balada com show ao vivo essa noite com open bar",
    "restaurantes perto da Estação das Docas",
])
def test_other_times_and_no_open_word_do_not_filter(planner, message):
    assert planner.extract_open_now(message, "pt-BR") is None
