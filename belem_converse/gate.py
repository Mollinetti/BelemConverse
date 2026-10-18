"""The plain-text input gate: what a visitor's message may contain.

Letters (any script, with accents), digits, spaces and ``, . : ? !`` —
nothing else, at most 400 characters. Crafted punctuation, markup, newlines and emoji
never reach the planner or the model. The Flutter client applies the same
rule while typing (frontend/lib/utils/input_gate.dart).
"""

from __future__ import annotations

import unicodedata

ALLOWED_PUNCT = " ,.:?!"
MAX_LEN = 400

MESSAGES = {
    "empty": {
        "pt-BR": "Escreva uma pergunta.",
        "en": "Type a question.",
    },
    "too_long": {
        "pt-BR": f"A pergunta pode ter no máximo {MAX_LEN} caracteres.",
        "en": f"A question can be at most {MAX_LEN} characters long.",
    },
    "bad_chars": {
        "pt-BR": "Use apenas letras, números, espaços e os sinais , . : ? !",
        "en": "Use only letters, digits, spaces and the marks , . : ? !",
    },
}


class GateError(ValueError):
    """A message the gate refuses; ``str()`` is the localized explanation."""

    def __init__(self, reason: str, language: str | None = None):
        self.reason = reason
        super().__init__(MESSAGES[reason]["en" if language == "en" else "pt-BR"])


def _allowed(char: str) -> bool:
    # L* letters and N* digits, matching Dart's [\p{L}\p{N}] on the client.
    return char in ALLOWED_PUNCT or unicodedata.category(char)[0] in "LN"


def clean_message(text: str, max_len: int = MAX_LEN, language: str | None = None) -> str:
    """``text`` in NFC with runs of spaces collapsed, or GateError."""
    if len(text) > max_len * 4:  # don't normalize megabytes just to refuse them
        raise GateError("too_long", language)
    text = unicodedata.normalize("NFC", text)
    if not all(_allowed(c) for c in text):
        raise GateError("bad_chars", language)
    text = " ".join(text.split())
    if not text:
        raise GateError("empty", language)
    if len(text) > max_len:
        raise GateError("too_long", language)
    return text
