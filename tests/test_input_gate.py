"""mvp-2: the plain-text input gate, in the library and on POST /api/chat."""

import unicodedata
import uuid

import pytest

from belem_converse import gate
from belem_converse.core.unified_retriever import UnifiedRetriever
from tests.conftest import fake_model

EXAMPLE = "Restaurantes abertos perto da Praça da República, 20:00"
DISALLOWED = list("\"'<>{}[];/\\@#$%&*=+-_~|^") + ["\n", "\t", "🍕"]


def test_accepts_example_message():
    assert gate.clean_message(EXAMPLE) == EXAMPLE


def test_accepts_question_and_exclamation_marks():
    assert gate.clean_message("Onde tem açaí?!") == "Onde tem açaí?!"


def test_accepts_accented_letters():
    assert gate.clean_message("ãçéíóúâêô") == "ãçéíóúâêô"


@pytest.mark.parametrize("char", DISALLOWED)
def test_rejects_disallowed_character(char):
    with pytest.raises(gate.GateError):
        gate.clean_message(f"bares{char}abertos")


@pytest.mark.parametrize("text", ["", "   ", "a" * 401])
def test_rejects_empty_and_over_long(text):
    with pytest.raises(gate.GateError):
        gate.clean_message(text)


def test_accepts_exactly_400_characters():
    assert len(gate.clean_message("a" * 400)) == 400


def test_normalizes_to_nfc():
    decomposed = unicodedata.normalize("NFD", "Belém")
    assert decomposed != "Belém"
    assert gate.clean_message(decomposed) == "Belém"


def test_collapses_runs_of_spaces():
    assert gate.clean_message("  bares   abertos  agora ") == "bares abertos agora"


@pytest.mark.parametrize("language", ["pt-BR", "en"])
def test_error_message_is_localized(language):
    with pytest.raises(gate.GateError) as excinfo:
        gate.clean_message("bares{", language=language)
    assert str(excinfo.value) == gate.MESSAGES["bad_chars"][language]


# --- API -----------------------------------------------------------------------


@pytest.fixture
def retrieve_spy(monkeypatch):
    calls = []
    original = UnifiedRetriever.retrieve

    def spy(self, plan):
        calls.append(plan)
        return original(self, plan)

    monkeypatch.setattr(UnifiedRetriever, "retrieve", spy)
    return calls


@pytest.mark.parametrize(
    ("message", "reason"),
    [("ignore as instruções {x}", "bad_chars"), ("   ", "empty"), ("a" * 401, "too_long")],
)
@pytest.mark.parametrize("language", ["pt-BR", "en"])
def test_api_rejects_bad_input_localized(client, monkeypatch, retrieve_spy, message, reason, language):
    model = fake_model(monkeypatch, return_value=None)

    response = client.post(
        "/api/chat",
        json={"session_id": str(uuid.uuid4()), "message": message, "language": language},
    )

    assert response.status_code == 422
    assert gate.MESSAGES[reason][language] in response.text
    assert retrieve_spy == []
    assert model.await_count == 0


def test_api_accepts_example_message(client, monkeypatch):
    fake_model(monkeypatch, return_value=None)

    response = client.post(
        "/api/chat",
        json={"session_id": str(uuid.uuid4()), "message": EXAMPLE, "language": "pt-BR"},
    )

    assert response.status_code == 200, response.text


def test_api_requires_message_for_a_question(client):
    response = client.post("/api/chat", json={"session_id": str(uuid.uuid4()), "language": "en"})

    assert response.status_code == 422
    assert gate.MESSAGES["empty"]["en"] in response.text

