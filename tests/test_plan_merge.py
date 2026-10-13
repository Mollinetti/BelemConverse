"""mvp-2: a follow-up question refines the previous plan's slots."""

from belem_converse.core.query_planner import merge_slots


def test_follow_up_keeps_previous_filters():
    merged = merge_slots({"categories": ["bar"], "min_rating": 4}, {"open_now": True})

    assert merged == {"categories": ["bar"], "min_rating": 4, "open_now": True}


def test_new_category_returns_only_new_slots():
    new = {"categories": ["cafe"], "open_now": None}

    assert merge_slots({"categories": ["bar"], "open_now": True}, new) == new


def test_new_sort_overrides_old():
    merged = merge_slots(
        {"categories": ["bar"], "sort_preference": "rating"}, {"sort_preference": "distance"}
    )

    assert merged["sort_preference"] == "distance"


def test_unset_values_do_not_erase_old_ones():
    old = {"categories": ["bar"], "min_rating": 4, "open_now": True, "keywords": ["bares"]}

    merged = merge_slots(old, {"min_rating": None, "keywords": [], "open_now": False})

    assert merged == old


def test_no_previous_plan_returns_new_slots():
    new = {"open_now": True}

    assert merge_slots(None, new) == new


def test_inputs_are_not_modified():
    old = {"categories": ["bar"]}
    merge_slots(old, {"open_now": True})

    assert old == {"categories": ["bar"]}
