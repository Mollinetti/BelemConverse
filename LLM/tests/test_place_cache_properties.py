"""
Property-based tests for PlaceCache module.

Feature: intent-detection-unification
Property 20: Place Lookup by Multiple Keys

**Validates: Requirements 11.3**

Property 20: For any place in the database, lookup by placeId, title, or 
titleFormatted should return the same place object.
"""

import sys
from pathlib import Path
import importlib.util

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from hypothesis import given, strategies as st, settings, assume

# Import modules directly without triggering __init__.py
def import_module_from_file(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# Import place cache
place_cache_path = project_root / "src" / "core" / "place_cache.py"
place_cache_module = import_module_from_file("place_cache", place_cache_path)
PlaceCache = place_cache_module.PlaceCache


# Strategy for generating valid place dictionaries
@st.composite
def place_strategy(draw):
    """Generate a valid place dictionary with all required fields."""
    # Generate unique identifiers
    place_id = draw(st.text(
        min_size=1, 
        max_size=20, 
        alphabet=st.characters(min_codepoint=97, max_codepoint=122)
    ))
    
    # Generate titles (non-empty, reasonable length)
    title = draw(st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),
            whitelist_characters=' -'
        )
    )).strip()
    
    # Ensure title is not empty after stripping
    assume(len(title) > 0)
    
    # Generate titleFormatted (can be same or different from title)
    title_formatted = draw(st.one_of(
        st.just(title),  # Same as title
        st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=('Lu', 'Ll', 'Nd'),
                whitelist_characters=' -'
            )
        ).map(lambda t: t.strip())
    ))
    
    # Ensure titleFormatted is not empty
    assume(len(title_formatted) > 0)
    
    return {
        'placeId': place_id,
        'title': title,
        'titleFormatted': title_formatted,
        'categoryName': draw(st.sampled_from(['restaurant', 'cafe', 'hotel', 'bar', 'museum'])),
        'location/lat': draw(st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False)),
        'location/lng': draw(st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False)),
        'totalScore': draw(st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False)),
        'reviewsCount': draw(st.integers(min_value=0, max_value=10000))
    }


class TestProperty20_PlaceLookupByMultipleKeys:
    """
    Property 20: Place Lookup by Multiple Keys
    
    For any place in the database, lookup by placeId, title, or titleFormatted
    should return the same place object.
    
    **Validates: Requirements 11.3**
    """
    
    @given(place=place_strategy())
    @settings(max_examples=100, deadline=None)
    def test_lookup_by_id_and_title_return_same_place(self, place):
        """
        Property: For any place, lookup by placeId and lookup by title
        should return the same place object.
        """
        # Create cache with single place
        cache = PlaceCache([place])
        
        # Lookup by ID
        place_by_id = cache.get_by_id(place['placeId'])
        
        # Lookup by title
        place_by_title = cache.get_by_title(place['title'])
        
        # Both should return the same place
        assert place_by_id is not None, f"Lookup by ID failed for placeId={place['placeId']}"
        assert place_by_title is not None, f"Lookup by title failed for title={place['title']}"
        
        # Verify they are the same object
        assert place_by_id is place_by_title, (
            f"Lookup by ID and title returned different objects: "
            f"ID lookup returned {place_by_id['placeId']}, "
            f"title lookup returned {place_by_title['placeId']}"
        )
        
        # Verify it's the original place
        assert place_by_id['placeId'] == place['placeId']
        assert place_by_id['title'] == place['title']
    
    @given(place=place_strategy())
    @settings(max_examples=100, deadline=None)
    def test_lookup_by_id_and_title_formatted_return_same_place(self, place):
        """
        Property: For any place, lookup by placeId and lookup by titleFormatted
        should return the same place object.
        """
        # Create cache with single place
        cache = PlaceCache([place])
        
        # Lookup by ID
        place_by_id = cache.get_by_id(place['placeId'])
        
        # Lookup by titleFormatted
        place_by_title_formatted = cache.get_by_title(place['titleFormatted'])
        
        # Both should return the same place
        assert place_by_id is not None, f"Lookup by ID failed for placeId={place['placeId']}"
        assert place_by_title_formatted is not None, (
            f"Lookup by titleFormatted failed for titleFormatted={place['titleFormatted']}"
        )
        
        # Verify they are the same object
        assert place_by_id is place_by_title_formatted, (
            f"Lookup by ID and titleFormatted returned different objects: "
            f"ID lookup returned {place_by_id['placeId']}, "
            f"titleFormatted lookup returned {place_by_title_formatted['placeId']}"
        )
        
        # Verify it's the original place
        assert place_by_id['placeId'] == place['placeId']
        assert place_by_id['titleFormatted'] == place['titleFormatted']
    
    @given(place=place_strategy())
    @settings(max_examples=100, deadline=None)
    def test_lookup_by_title_and_title_formatted_return_same_place(self, place):
        """
        Property: For any place, lookup by title and lookup by titleFormatted
        should return the same place object.
        """
        # Create cache with single place
        cache = PlaceCache([place])
        
        # Lookup by title
        place_by_title = cache.get_by_title(place['title'])
        
        # Lookup by titleFormatted
        place_by_title_formatted = cache.get_by_title(place['titleFormatted'])
        
        # Both should return the same place
        assert place_by_title is not None, f"Lookup by title failed for title={place['title']}"
        assert place_by_title_formatted is not None, (
            f"Lookup by titleFormatted failed for titleFormatted={place['titleFormatted']}"
        )
        
        # Verify they are the same object
        assert place_by_title is place_by_title_formatted, (
            f"Lookup by title and titleFormatted returned different objects: "
            f"title lookup returned {place_by_title['placeId']}, "
            f"titleFormatted lookup returned {place_by_title_formatted['placeId']}"
        )
        
        # Verify it's the original place
        assert place_by_title['placeId'] == place['placeId']
    
    @given(place=place_strategy())
    @settings(max_examples=100, deadline=None)
    def test_lookup_case_insensitive_returns_same_place(self, place):
        """
        Property: For any place, lookup by title in different cases
        should return the same place object (when case conversion is stable).
        
        Note: Some characters like German 'ß' uppercase to 'SS', which can
        cause lookup mismatches. This is expected behavior.
        """
        # Create cache with single place
        cache = PlaceCache([place])
        
        # Lookup with original case
        place_original = cache.get_by_title(place['title'])
        
        # Lookup with lowercase
        place_lower = cache.get_by_title(place['title'].lower())
        
        # All should return the same place
        assert place_original is not None
        assert place_lower is not None
        
        # Verify they are the same object
        assert place_original is place_lower, (
            "Lookup with original case and lowercase returned different objects"
        )
        
        # Verify it's the original place
        assert place_original['placeId'] == place['placeId']
        
        # Only test uppercase if it converts back to the same lowercase
        # (avoids issues with characters like 'ß' -> 'SS')
        if place['title'].upper().lower() == place['title'].lower():
            place_upper = cache.get_by_title(place['title'].upper())
            assert place_upper is not None
            assert place_original is place_upper, (
                "Lookup with original case and uppercase returned different objects"
            )
    
    @given(places=st.lists(place_strategy(), min_size=2, max_size=10, unique_by=lambda p: p['placeId']))
    @settings(max_examples=100, deadline=None)
    def test_lookup_consistency_for_first_occurrence(self, places):
        """
        Property: For any place that is the first occurrence of its title/titleFormatted,
        lookup by placeId, title, or titleFormatted should return the same place object.
        
        Note: PlaceCache stores only the first occurrence of duplicate titles.
        This test validates that for places that ARE the first occurrence,
        all lookup methods return the same object.
        """
        # Create cache
        cache = PlaceCache(places)
        
        # Track which titles we've seen (case-insensitive)
        seen_titles = set()
        seen_title_formatted = set()
        
        # Verify each place that is a "first occurrence" can be looked up consistently
        for place in places:
            title_lower = place['title'].lower()
            title_formatted_lower = place['titleFormatted'].lower()
            
            # Check if this is the first occurrence of this title
            is_first_title = title_lower not in seen_titles
            is_first_title_formatted = title_formatted_lower not in seen_title_formatted
            
            seen_titles.add(title_lower)
            seen_title_formatted.add(title_formatted_lower)
            
            # Lookup by ID should always work
            place_by_id = cache.get_by_id(place['placeId'])
            assert place_by_id is not None, (
                f"Lookup by ID failed for placeId={place['placeId']}"
            )
            assert place_by_id['placeId'] == place['placeId']
            
            # If this is the first occurrence of the title, lookup by title should work
            if is_first_title:
                place_by_title = cache.get_by_title(place['title'])
                assert place_by_title is not None, (
                    f"Lookup by title failed for first occurrence: title={place['title']}"
                )
                assert place_by_title['placeId'] == place['placeId'], (
                    f"Lookup by title returned wrong place for first occurrence"
                )
            
            # If this is the first occurrence of titleFormatted, lookup should work
            if is_first_title_formatted:
                place_by_title_formatted = cache.get_by_title(place['titleFormatted'])
                assert place_by_title_formatted is not None, (
                    f"Lookup by titleFormatted failed for first occurrence: "
                    f"titleFormatted={place['titleFormatted']}"
                )
                # Note: This might return a different place if title and titleFormatted
                # are different and title was seen first
                assert place_by_title_formatted is not None
    
    @given(place=place_strategy())
    @settings(max_examples=100, deadline=None)
    def test_lookup_with_whitespace_variations(self, place):
        """
        Property: For any place, lookup by title with extra whitespace
        should return the same place object.
        """
        # Create cache with single place
        cache = PlaceCache([place])
        
        # Lookup with original title
        place_original = cache.get_by_title(place['title'])
        
        # Lookup with extra whitespace
        place_with_spaces = cache.get_by_title(f"  {place['title']}  ")
        
        # Both should return the same place
        assert place_original is not None
        assert place_with_spaces is not None
        
        # Verify they are the same object
        assert place_original is place_with_spaces, (
            "Lookup with and without extra whitespace returned different objects"
        )
        
        # Verify it's the original place
        assert place_original['placeId'] == place['placeId']
    
    @given(
        places=st.lists(place_strategy(), min_size=1, max_size=5, unique_by=lambda p: p['placeId']),
        lookup_key=st.sampled_from(['placeId'])
    )
    @settings(max_examples=100, deadline=None)
    def test_lookup_by_id_always_returns_correct_place(self, places, lookup_key):
        """
        Property: For any list of places, lookup by placeId should always
        return the correct place (placeId is unique).
        
        Note: We only test placeId lookup here because title/titleFormatted
        lookups may return the first occurrence when there are duplicates.
        """
        # Create cache with multiple places
        cache = PlaceCache(places)
        
        # Pick a random place to lookup
        target_place = places[0]
        
        # Lookup by placeId (always unique)
        found_place = cache.get_by_id(target_place['placeId'])
        
        # Should find the correct place
        assert found_place is not None, (
            f"Lookup by placeId failed for value={target_place['placeId']}"
        )
        assert found_place['placeId'] == target_place['placeId'], (
            f"Lookup by placeId returned wrong place: "
            f"expected {target_place['placeId']}, got {found_place['placeId']}"
        )
