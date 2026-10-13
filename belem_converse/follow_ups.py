"""Suggested follow-up questions: 2–3 one-tap chips after each answer.

Each chip is an ordinary question (it must pass the input gate and the
planner must read it as the filter or category it names). Chips for filters
already applied are skipped; one chip always suggests another kind of place.
"""

from __future__ import annotations

import unicodedata

from belem_converse.cities import get_city_config

CHIPS = {
    "open_now": {"pt-BR": "Abertos agora", "en": "Open now"},
    "closest": {"pt-BR": "Mais perto de mim", "en": "Closest to me"},
    "top_rated": {"pt-BR": "Mais bem avaliados", "en": "Top rated"},
}
# The kind of place to suggest after each one; anything else gets restaurants.
# Only restaurants, cafés and bars are suggested: the catalog has no açaí or
# ice-cream types, so those chips would find nothing or just cafés again.
SIBLING = {
    "restaurant": "cafe",
    "cafe": "bar",
    "bar": "restaurant",
    "acai": "cafe",
    "ice_cream": "cafe",
    "hotel": "restaurant",
}
DEFAULT_SIBLING = "restaurant"


def canonical(categories: list[str]) -> str | None:
    """The first planner category SIBLING knows, folded ("açaí" → "acai")."""
    for category in categories:
        folded = unicodedata.normalize("NFD", category.lower())
        key = "".join(c for c in folded if unicodedata.category(c) != "Mn").replace(" ", "_")
        if key in SIBLING:
            return key
    return None


def build(slots: dict, language: str, has_location: bool) -> list[str]:
    lang = "en" if language == "en" else "pt-BR"
    labels = get_city_config().category_labels
    first = SIBLING.get(canonical(slots.get("categories") or []), DEFAULT_SIBLING)
    second = SIBLING[first]
    candidates = [
        None if slots.get("open_now") else CHIPS["open_now"][lang],
        CHIPS["closest"][lang]
        if has_location and not slots.get("proximity_intent_detected")
        else None,
        labels.get(first, {}).get(lang),
        None if slots.get("min_rating") else CHIPS["top_rated"][lang],
        labels.get(second, {}).get(lang),
    ]
    return [chip for chip in candidates if chip][:3]
