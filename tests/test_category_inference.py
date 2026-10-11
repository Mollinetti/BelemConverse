"""mvp-1: place_type inference matches whole words, not substrings.

The old matcher accepted a match in either direction (keyword inside the
category, or category inside the keyword), so "Barber shop" became a bar and a
two-letter fragment like "Ca" became a restaurant.
"""

import pytest

from belem_converse.ingest.csv_ingestion import PlaceTypeInference


@pytest.mark.parametrize(
    "category, expected",
    [
        ("Snack bar", "restaurant"),
        ("Wine bar", "bar"),
        ("Bar", "bar"),
        ("Hotel", "other"),
        ("Cafe", "restaurant"),
    ],
)
def test_category_name_maps_to_place_type(category, expected):
    assert PlaceTypeInference.infer_place_type(category, []) == expected


@pytest.mark.parametrize(
    "category",
    [
        # Fragments of a keyword (category inside keyword: "ca" ⊂ "cafe").
        "Ca",
        "Pu",
        "Rest",
        # A keyword inside a longer word ("bar" ⊂ "barber", "park" ⊂ "parking").
        "Barber shop",
        "Parking lot",
        "Embarcadero",
    ],
)
def test_no_category_maps_through_substring(category):
    assert PlaceTypeInference.infer_place_type(category, []) == "other"
