"""mvp-1: a model answer may name only places that were retrieved.

The prompt asks the model to put place names in **bold**. is_grounded checks
each bold name against the result titles (fuzzy, ignoring case and accents)
and scans the text for any other catalog title longer than five characters.
"""

from belem_converse.llm import is_grounded, strip_markers

RESULTS = [{"title": "Estação das Docas"}, {"title": "Mercado Ver-o-Peso"}]
CATALOG = ["Estação das Docas", "Mercado Ver-o-Peso", "Bar do Parque", "Cafe"]


def test_bold_names_matching_results_are_grounded():
    answer = "Visite a **Estacao das Docas** e o **mercado ver-o-peso**, ambos abertos."
    assert is_grounded(answer, RESULTS, CATALOG) is True


def test_bold_name_not_in_results_is_not_grounded():
    answer = "Experimente o **Bar Inventado**, perto da **Estação das Docas**."
    assert is_grounded(answer, RESULTS, CATALOG) is False


def test_unbolded_catalog_place_outside_results_is_not_grounded():
    answer = "Visite a **Estação das Docas** e depois passe no Bar do Parque."
    assert is_grounded(answer, RESULTS, CATALOG) is False


def test_answer_naming_no_places_is_grounded():
    answer = "Não encontrei um lugar perfeito, mas a região do porto tem boas opções."
    assert is_grounded(answer, RESULTS, CATALOG) is True


def test_short_catalog_titles_are_ignored():
    # "Cafe" is too short to tell a place name from an ordinary word.
    answer = "A **Estação das Docas** tem um cafe gostoso."
    assert is_grounded(answer, RESULTS, CATALOG) is True


def test_result_title_containing_another_catalog_title_is_grounded():
    results = [{"title": "Cacau Show Shopping Pátio"}]
    catalog = ["Cacau Show Shopping Pátio", "Cacau Show"]
    assert is_grounded("Passe na **Cacau Show Shopping Pátio**.", results, catalog) is True


def test_strip_markers_removes_bold():
    assert strip_markers("Visite a **Estação das Docas** hoje.") == "Visite a Estação das Docas hoje."
