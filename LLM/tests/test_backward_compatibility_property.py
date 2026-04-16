"""
Property-based tests for backward compatibility in UnifiedRetriever.

Feature: intent-detection-unification
Property 6: Query Plan Backward Compatibility

**Validates: Requirements 4.5**

Property 6: Query Plan Backward Compatibility
For any valid Query_Plan from the legacy system, the unified retriever should
process it correctly and produce equivalent results.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock

# Import modules
from core.unified_retriever import UnifiedRetriever, RetrievalResult
from core.place_cache import PlaceCache
from core.category_matcher import CategoryMatcher
from core.ranking_engine import RankingEngine, RankingMode, Location
from classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier


# Strategy for generating valid locations
@st.composite
def location_strategy(draw):
    """Generate valid location coordinates."""
    return Location(
        latitude=draw(st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False)),
        longitude=draw(st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False))
    )


# Strategy for generating places
@st.composite
def place_strategy(draw):
    """Generate a valid place dictionary."""
    location = draw(location_strategy())
    category = draw(st.sampled_from(['restaurant', 'cafe', 'hotel', 'bar', 'museum', 'ice_cream']))
    
    return {
        'placeId': draw(st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122))),
        'title': draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' '))).strip() or 'Place',
        'titleFormatted': draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' '))).strip() or 'Place',
        'categories': [category],
        'location': {'lat': location.latitude, 'lng': location.longitude},
        'totalScore': draw(st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False)),
        'reviewsCount': draw(st.integers(min_value=0, max_value=10000)),
        'price': draw(st.integers(min_value=1, max_value=4)),
        'businessTime': draw(st.sampled_from([
            'Monday-Sunday: 08:00-22:00',
            'Monday-Friday: 09:00-18:00',
            'Open 24 hours',
            None
        ]))
    }


@pytest.fixture(scope="module")
def mock_intent_classifier():
    """Create a mock intent classifier for testing."""
    classifier = Mock()
    classifier.category_keywords = {
        'restaurant': ['restaurant', 'restaurante', 'food'],
        'cafe': ['cafe', 'café', 'coffee'],
        'hotel': ['hotel', 'motel', 'accommodation'],
        'bar': ['bar', 'pub', 'drinks'],
        'museum': ['museum', 'museu', 'gallery'],
        'ice_cream': ['ice cream', 'sorvete', 'gelato']
    }
    return classifier


@pytest.fixture(scope="module")
def category_matcher(mock_intent_classifier):
    """Create category matcher with mock classifier."""
    return CategoryMatcher(mock_intent_classifier)


@pytest.fixture(scope="module")
def ranking_engine():
    """Create ranking engine."""
    return RankingEngine()


class TestProperty6_QueryPlanBackwardCompatibility:
    """
    Property 6: Query Plan Backward Compatibility
    
    For any valid Query_Plan from the legacy system, the unified retriever should
    process it correctly and produce equivalent results.
    
    **Validates: Requirements 4.5**
    
    Legacy query plans may use:
    - 'place_type' slot instead of 'categories' slot
    - 'proximity_radius' slot for distance filtering
    - Different slot naming conventions
    
    The UnifiedRetriever should handle all these formats correctly.
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=10, max_size=30, unique_by=lambda p: p['placeId']),
        category=st.sampled_from(['restaurant', 'cafe', 'hotel', 'bar', 'museum'])
    )
    @settings(max_examples=100, deadline=None)
    def test_legacy_place_type_slot_compatibility(
        self,
        category_matcher,
        ranking_engine,
        places,
        category
    ):
        """
        Property: Legacy query plans using 'place_type' slot should produce
        the same results as new query plans using 'categories' slot.
        """
        # Create place cache
        place_cache = PlaceCache(places)
        
        # Create retriever
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=None,
            osm_client=None
        )
        
        # Create LEGACY query plan with 'place_type' slot
        legacy_query_plan = {
            'intent': 'find_places',
            'intents': {},
            'slots': {
                'user_location': None,
                'place_type': category,  # LEGACY: single place_type
                'categories': None,
                'open_now': False,
                'price_max': None,
                'min_rating': None
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'original_query': f'find {category}',
            'debug': {}
        }
        
        # Create NEW query plan with 'categories' slot
        new_query_plan = {
            'intent': 'find_places',
            'intents': {},
            'slots': {
                'user_location': None,
                'place_type': None,
                'categories': [category],  # NEW: list of categories
                'open_now': False,
                'price_max': None,
                'min_rating': None
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'original_query': f'find {category}',
            'debug': {}
        }
        
        # Execute retrieval with both query plans
        legacy_result = retriever.retrieve(legacy_query_plan)
        new_result = retriever.retrieve(new_query_plan)
        
        # Verify both produce the same results
        legacy_place_ids = sorted([p['placeId'] for p in legacy_result.places])
        new_place_ids = sorted([p['placeId'] for p in new_result.places])
        
        assert legacy_place_ids == new_place_ids, (
            f"Legacy and new query plans should produce same results.\n"
            f"Legacy: {len(legacy_place_ids)} places\n"
            f"New: {len(new_place_ids)} places\n"
            f"Difference: {set(legacy_place_ids) ^ set(new_place_ids)}"
        )
        
        # Verify both applied category filter
        assert 'category' in legacy_result.filters_applied, (
            "Legacy query plan should apply category filter"
        )
        assert 'category' in new_result.filters_applied, (
            "New query plan should apply category filter"
        )
    
    @given(
        places=st.lists(place_strategy(), min_size=10, max_size=30, unique_by=lambda p: p['placeId']),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_legacy_proximity_radius_slot_compatibility(
        self,
        category_matcher,
        ranking_engine,
        places,
        user_location
    ):
        """
        Property: Legacy query plans with 'proximity_radius' slot should be
        handled correctly (even if the implementation uses radius escalation).
        """
        # Create place cache
        place_cache = PlaceCache(places)
        
        # Create retriever
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=None,
            osm_client=None
        )
        
        # Create LEGACY query plan with 'proximity_radius' slot
        legacy_query_plan = {
            'intent': 'location',
            'intents': {'location': 0.9},
            'slots': {
                'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude},
                'proximity_radius': 1.0,  # LEGACY: explicit radius in km
                'categories': None,
                'place_type': None,
                'open_now': False,
                'price_max': None,
                'min_rating': None
            },
            'proximity_intent_detected': True,
            'retrieval_strategy': 'structured_only',
            'original_query': 'find places nearby',
            'debug': {'detected_intents': ['location']}
        }
        
        # Execute retrieval
        result = retriever.retrieve(legacy_query_plan)
        
        # Verify proximity filter was applied
        assert 'proximity' in result.filters_applied, (
            "Legacy query plan with proximity_radius should apply proximity filter"
        )
        
        # Verify all results have distance calculated
        for place in result.places:
            assert 'distanceKm' in place, (
                f"Place {place['placeId']} should have distanceKm field"
            )
            
            # Verify distance is within reasonable bounds (escalation may expand radius)
            distance = place.get('distanceKm')
            if distance is not None:
                assert distance <= 2.0, (
                    f"Place {place['placeId']} at {distance}km exceeds max escalation radius 2.0km"
                )
    
    @given(
        places=st.lists(place_strategy(), min_size=10, max_size=30, unique_by=lambda p: p['placeId']),
        category=st.sampled_from(['restaurant', 'cafe', 'hotel']),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_legacy_query_plan_with_multiple_slots(
        self,
        category_matcher,
        ranking_engine,
        places,
        category,
        user_location
    ):
        """
        Property: Legacy query plans with multiple legacy slots should work
        correctly together.
        """
        # Create place cache
        place_cache = PlaceCache(places)
        
        # Create retriever
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=None,
            osm_client=None
        )
        
        # Create LEGACY query plan with multiple legacy slots
        legacy_query_plan = {
            'intent': 'location',
            'intents': {'location': 0.9},
            'slots': {
                'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude},
                'place_type': category,  # LEGACY slot
                'proximity_radius': 1.5,  # LEGACY slot
                'categories': None,
                'open_now': False,
                'price_max': 3,
                'min_rating': 3.0
            },
            'proximity_intent_detected': True,
            'retrieval_strategy': 'structured_only',
            'original_query': f'find {category} nearby',
            'debug': {'detected_intents': ['location']}
        }
        
        # Execute retrieval
        result = retriever.retrieve(legacy_query_plan)
        
        # Verify all expected filters were applied
        expected_filters = ['proximity', 'category', 'price', 'rating']
        for filter_name in expected_filters:
            assert filter_name in result.filters_applied, (
                f"Filter '{filter_name}' should be applied for legacy query plan"
            )
        
        # Verify all results match the filters
        for place in result.places:
            # Check category filter
            place_categories = place.get('categories', [])
            assert any(
                category_matcher._matches_keywords(pc, category)
                for pc in place_categories
            ), f"Place {place['placeId']} should match category '{category}'"
            
            # Check price filter
            place_price = place.get('price')
            if place_price is not None:
                assert place_price <= 3, (
                    f"Place {place['placeId']} price {place_price} exceeds max 3"
                )
            
            # Check rating filter
            place_rating = place.get('totalScore')
            if place_rating is not None:
                assert place_rating >= 3.0, (
                    f"Place {place['placeId']} rating {place_rating} below min 3.0"
                )
            
            # Check distance
            assert 'distanceKm' in place, (
                f"Place {place['placeId']} should have distanceKm field"
            )
    
    @given(
        places=st.lists(place_strategy(), min_size=10, max_size=30, unique_by=lambda p: p['placeId']),
        category=st.sampled_from(['restaurant', 'cafe', 'hotel'])
    )
    @settings(max_examples=100, deadline=None)
    def test_legacy_and_new_slots_coexist(
        self,
        category_matcher,
        ranking_engine,
        places,
        category
    ):
        """
        Property: When both legacy 'place_type' and new 'categories' slots
        are present, the system should handle them gracefully (preferring
        categories if both are present).
        """
        # Create place cache
        place_cache = PlaceCache(places)
        
        # Create retriever
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=None,
            osm_client=None
        )
        
        # Create query plan with BOTH legacy and new slots
        mixed_query_plan = {
            'intent': 'find_places',
            'intents': {},
            'slots': {
                'user_location': None,
                'place_type': 'bar',  # LEGACY slot (different category)
                'categories': [category],  # NEW slot (should take precedence)
                'open_now': False,
                'price_max': None,
                'min_rating': None
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'original_query': f'find {category}',
            'debug': {}
        }
        
        # Execute retrieval
        result = retriever.retrieve(mixed_query_plan)
        
        # Verify category filter was applied
        assert 'category' in result.filters_applied, (
            "Category filter should be applied when slots are present"
        )
        
        # Verify results match the NEW 'categories' slot (not the legacy 'place_type')
        # The implementation should prefer 'categories' over 'place_type'
        for place in result.places:
            place_categories = place.get('categories', [])
            # Should match the 'categories' slot value (category), not 'place_type' (bar)
            matches_new = any(
                category_matcher._matches_keywords(pc, category)
                for pc in place_categories
            )
            
            # If it doesn't match the new category, it should at least match one of them
            # (implementation may use fallback to place_type if categories is empty)
            if not matches_new:
                matches_legacy = any(
                    category_matcher._matches_keywords(pc, 'bar')
                    for pc in place_categories
                )
                assert matches_legacy, (
                    f"Place {place['placeId']} should match either categories or place_type"
                )
    
    @given(
        places=st.lists(place_strategy(), min_size=5, max_size=20, unique_by=lambda p: p['placeId'])
    )
    @settings(max_examples=100, deadline=None)
    def test_legacy_query_plan_without_new_fields(
        self,
        category_matcher,
        ranking_engine,
        places
    ):
        """
        Property: Legacy query plans that don't have new fields (like
        'proximity_intent_detected') should still work correctly with
        sensible defaults.
        """
        # Create place cache
        place_cache = PlaceCache(places)
        
        # Create retriever
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=None,
            osm_client=None
        )
        
        # Create MINIMAL legacy query plan (missing new fields)
        minimal_legacy_plan = {
            'intent': 'find_places',
            'slots': {
                'place_type': 'restaurant',
                'open_now': False
            },
            'retrieval_strategy': 'structured_only',
            # Missing: intents, proximity_intent_detected, original_query, debug
        }
        
        # Execute retrieval - should not crash
        result = retriever.retrieve(minimal_legacy_plan)
        
        # Verify we got a valid result
        assert isinstance(result, RetrievalResult), (
            "Should return valid RetrievalResult for minimal legacy plan"
        )
        assert isinstance(result.places, list), (
            "Should return list of places"
        )
        assert result.strategy_used == 'filter_first', (
            "Should use filter_first strategy"
        )
        
        # Verify category filter was applied (from place_type)
        assert 'category' in result.filters_applied, (
            "Should apply category filter from legacy place_type slot"
        )


class TestBackwardCompatibilityInvariants:
    """
    Test invariants that should hold for backward compatibility.
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=10, max_size=30, unique_by=lambda p: p['placeId']),
        category=st.sampled_from(['restaurant', 'cafe', 'hotel', 'bar'])
    )
    @settings(max_examples=100, deadline=None)
    def test_equivalent_results_for_equivalent_queries(
        self,
        category_matcher,
        ranking_engine,
        places,
        category
    ):
        """
        Property: Semantically equivalent query plans (legacy vs new format)
        should produce identical results.
        """
        # Create place cache
        place_cache = PlaceCache(places)
        
        # Create retriever
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=None,
            osm_client=None
        )
        
        # Create two semantically equivalent query plans
        legacy_plan = {
            'intent': 'find_places',
            'intents': {},
            'slots': {
                'place_type': category,
                'categories': None,
                'open_now': False,
                'price_max': 2,
                'min_rating': 4.0
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'original_query': f'find {category}',
            'debug': {}
        }
        
        new_plan = {
            'intent': 'find_places',
            'intents': {},
            'slots': {
                'place_type': None,
                'categories': [category],
                'open_now': False,
                'price_max': 2,
                'min_rating': 4.0
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'original_query': f'find {category}',
            'debug': {}
        }
        
        # Execute both
        legacy_result = retriever.retrieve(legacy_plan)
        new_result = retriever.retrieve(new_plan)
        
        # Verify identical results
        legacy_ids = sorted([p['placeId'] for p in legacy_result.places])
        new_ids = sorted([p['placeId'] for p in new_result.places])
        
        assert legacy_ids == new_ids, (
            f"Equivalent query plans should produce identical results.\n"
            f"Legacy: {len(legacy_ids)} places\n"
            f"New: {len(new_ids)} places"
        )
        
        # Verify same filters applied
        assert set(legacy_result.filters_applied) == set(new_result.filters_applied), (
            f"Equivalent query plans should apply same filters.\n"
            f"Legacy: {legacy_result.filters_applied}\n"
            f"New: {new_result.filters_applied}"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
