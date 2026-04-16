"""
Property-based test for distance calculation in UnifiedRetriever.

Feature: intent-detection-unification
Property 13: Distance Calculation Invariant

**Validates: Requirements 6.5**

Property 13: Distance Calculation Invariant
For any query result with user location available, distance should be calculated
and included in the response regardless of whether proximity filtering was applied.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock

# Import modules
from core.unified_retriever import UnifiedRetriever, RetrievalResult
from core.place_cache import PlaceCache
from core.category_matcher import CategoryMatcher
from core.ranking_engine import RankingEngine, Location


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


class TestProperty13_DistanceCalculationInvariant:
    """
    Property 13: Distance Calculation Invariant
    
    For any query result with user location available, distance should be calculated
    and included in the response regardless of whether proximity filtering was applied.
    
    **Validates: Requirements 6.5**
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=5, max_size=30, unique_by=lambda p: p['placeId']),
        user_location=location_strategy(),
        proximity_intent_detected=st.booleans()
    )
    @settings(max_examples=100, deadline=None)
    def test_distance_calculated_regardless_of_proximity_intent(
        self,
        category_matcher,
        ranking_engine,
        places,
        user_location,
        proximity_intent_detected
    ):
        """
        Property: For any query with user location available, distance should be
        calculated for all results regardless of whether proximity intent was detected.
        
        This is the core property test for Requirement 6.5.
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
        
        # Create query plan with user location but varying proximity intent
        query_plan = {
            'intent': 'general',
            'intents': {},
            'slots': {
                'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude},
                'categories': None,
                'open_now': False,
                'price_max': None,
                'min_rating': None
            },
            'proximity_intent_detected': proximity_intent_detected,
            'retrieval_strategy': 'structured_only',
            'original_query': 'find places',
            'debug': {}
        }
        
        # Execute retrieval
        result = retriever.retrieve(query_plan)
        
        # CRITICAL ASSERTION: Distance should be calculated for ALL results
        # regardless of proximity_intent_detected value
        for place in result.places:
            assert 'distanceKm' in place, (
                f"Place {place['placeId']} missing distanceKm field "
                f"(proximity_intent={proximity_intent_detected})"
            )
            
            # Distance should be a valid number (not None) when location is valid
            distance = place.get('distanceKm')
            place_loc = place.get('location', {})
            place_lat = place_loc.get('lat')
            place_lng = place_loc.get('lng')
            
            if place_lat is not None and place_lng is not None:
                assert distance is not None, (
                    f"Place {place['placeId']} has valid location but distanceKm is None "
                    f"(proximity_intent={proximity_intent_detected})"
                )
                assert isinstance(distance, (int, float)), (
                    f"Place {place['placeId']} distanceKm should be numeric, got {type(distance)}"
                )
                assert distance >= 0, (
                    f"Place {place['placeId']} has negative distance: {distance}"
                )
            else:
                # If place has invalid location, distance should be None
                assert distance is None, (
                    f"Place {place['placeId']} has invalid location but distanceKm is not None"
                )
    
    @given(
        places=st.lists(place_strategy(), min_size=5, max_size=30, unique_by=lambda p: p['placeId']),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_distance_calculated_without_proximity_filtering(
        self,
        category_matcher,
        ranking_engine,
        places,
        user_location
    ):
        """
        Property: When proximity intent is NOT detected, proximity filtering should
        NOT be applied, but distances should still be calculated for all results.
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
        
        # Create query plan WITHOUT proximity intent
        query_plan = {
            'intent': 'general',
            'intents': {},
            'slots': {
                'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude},
                'categories': None,
                'open_now': False
            },
            'proximity_intent_detected': False,  # KEY: No proximity intent
            'retrieval_strategy': 'structured_only',
            'original_query': 'find places',
            'debug': {}
        }
        
        # Execute retrieval
        result = retriever.retrieve(query_plan)
        
        # Verify proximity filter was NOT applied
        assert 'proximity' not in result.filters_applied, (
            "Proximity filter should NOT be applied when proximity intent not detected"
        )
        
        # Verify distances are still calculated for all results
        assert len(result.places) > 0, "Should have results"
        
        for place in result.places:
            assert 'distanceKm' in place, (
                f"Place {place['placeId']} should have distanceKm even without proximity filter"
            )
            
            # Verify distance is valid for places with valid locations
            place_loc = place.get('location', {})
            if place_loc.get('lat') is not None and place_loc.get('lng') is not None:
                distance = place.get('distanceKm')
                assert distance is not None, (
                    f"Place {place['placeId']} should have calculated distance"
                )
                assert isinstance(distance, (int, float)), (
                    f"Distance should be numeric, got {type(distance)}"
                )
                assert distance >= 0, f"Distance should be non-negative, got {distance}"
    
    @given(
        places=st.lists(place_strategy(), min_size=5, max_size=30, unique_by=lambda p: p['placeId']),
        user_location=location_strategy(),
        categories=st.lists(st.sampled_from(['restaurant', 'cafe', 'hotel']), min_size=1, max_size=2, unique=True)
    )
    @settings(max_examples=100, deadline=None)
    def test_distance_calculated_with_other_filters(
        self,
        category_matcher,
        ranking_engine,
        places,
        user_location,
        categories
    ):
        """
        Property: Distance should be calculated even when other filters (category,
        price, rating) are applied but proximity filtering is not.
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
        
        # Create query plan with category filter but NO proximity intent
        query_plan = {
            'intent': 'general',
            'intents': {},
            'slots': {
                'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude},
                'categories': categories,
                'open_now': False,
                'price_max': 3,
                'min_rating': 3.0
            },
            'proximity_intent_detected': False,  # No proximity intent
            'retrieval_strategy': 'structured_only',
            'original_query': 'find places',
            'debug': {}
        }
        
        # Execute retrieval
        result = retriever.retrieve(query_plan)
        
        # Verify other filters were applied but not proximity
        assert 'category' in result.filters_applied, "Category filter should be applied"
        assert 'proximity' not in result.filters_applied, "Proximity filter should NOT be applied"
        
        # Verify distances are calculated for all results
        for place in result.places:
            assert 'distanceKm' in place, (
                f"Place {place['placeId']} should have distanceKm with other filters"
            )
            
            # Verify distance is valid
            place_loc = place.get('location', {})
            if place_loc.get('lat') is not None and place_loc.get('lng') is not None:
                distance = place.get('distanceKm')
                assert distance is not None, (
                    f"Place {place['placeId']} should have calculated distance"
                )
                assert isinstance(distance, (int, float)), "Distance should be numeric"
                assert distance >= 0, "Distance should be non-negative"
    
    @given(
        places=st.lists(place_strategy(), min_size=5, max_size=30, unique_by=lambda p: p['placeId'])
    )
    @settings(max_examples=100, deadline=None)
    def test_no_distance_without_user_location(
        self,
        category_matcher,
        ranking_engine,
        places
    ):
        """
        Property: When user location is NOT available, distances should NOT be
        calculated (distanceKm should be None or absent).
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
        
        # Create query plan WITHOUT user location
        query_plan = {
            'intent': 'general',
            'intents': {},
            'slots': {
                'user_location': None,  # KEY: No user location
                'categories': None,
                'open_now': False
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'original_query': 'find places',
            'debug': {}
        }
        
        # Execute retrieval
        result = retriever.retrieve(query_plan)
        
        # Verify results exist
        assert len(result.places) > 0, "Should have results"
        
        # Verify distances are NOT calculated (None or absent)
        for place in result.places:
            if 'distanceKm' in place:
                assert place['distanceKm'] is None, (
                    f"Place {place['placeId']} should have None distanceKm without user location"
                )
    
    @given(
        places=st.lists(place_strategy(), min_size=5, max_size=30, unique_by=lambda p: p['placeId']),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_distance_accuracy_haversine(
        self,
        category_matcher,
        ranking_engine,
        places,
        user_location
    ):
        """
        Property: Calculated distances should be accurate using Haversine formula.
        
        This verifies that the distance calculation is mathematically correct.
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
        
        # Create query plan with user location
        query_plan = {
            'intent': 'general',
            'intents': {},
            'slots': {
                'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude},
                'categories': None,
                'open_now': False
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'original_query': 'find places',
            'debug': {}
        }
        
        # Execute retrieval
        result = retriever.retrieve(query_plan)
        
        # Verify distance calculations are reasonable
        for place in result.places:
            distance = place.get('distanceKm')
            
            if distance is not None:
                # Distance should be within Earth's circumference (40,075 km)
                assert 0 <= distance <= 20100, (
                    f"Place {place['placeId']} has unreasonable distance: {distance}km"
                )
                
                # Verify distance matches manual Haversine calculation
                place_loc = place.get('location', {})
                place_lat = place_loc.get('lat')
                place_lng = place_loc.get('lng')
                
                if place_lat is not None and place_lng is not None:
                    # Calculate expected distance using Haversine
                    expected_distance = retriever._haversine_distance(
                        user_location.latitude, user_location.longitude,
                        place_lat, place_lng
                    )
                    
                    # Allow small floating point tolerance (0.001 km = 1 meter)
                    assert abs(distance - expected_distance) < 0.001, (
                        f"Place {place['placeId']} distance mismatch: "
                        f"got {distance}km, expected {expected_distance}km"
                    )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
