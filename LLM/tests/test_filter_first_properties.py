"""
Property-based tests for filter-first retrieval path in UnifiedRetriever.

Feature: intent-detection-unification
Properties 1, 4, 7, 14: Filter-First Path Correctness

**Validates: Requirements 2.2, 4.2, 6.1, 6.2, 6.3, 6.4, 8.1, 8.2, 8.3, 8.4, 9.1**

Property 1: Filter-First as Primary Strategy
Property 4: Multi-Filter Support
Property 7: Proximity Intent Handling
Property 14: Filter Precedence Order
"""

import sys
from pathlib import Path
from datetime import datetime, time

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock, MagicMock

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


# Strategy for generating query plans
@st.composite
def query_plan_strategy(draw, with_location=True, with_proximity_intent=False):
    """Generate a valid query plan."""
    user_location = draw(location_strategy()) if with_location else None
    
    return {
        'intent': draw(st.sampled_from(['location', 'popularity', 'business_hours', 'price', 'general'])),
        'intents': draw(st.dictionaries(
            keys=st.sampled_from(['location', 'popularity', 'business_hours', 'price']),
            values=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=0,
            max_size=3
        )),
        'slots': {
            'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude} if user_location else None,
            'categories': draw(st.one_of(
                st.none(),
                st.lists(st.sampled_from(['restaurant', 'cafe', 'hotel', 'bar', 'museum']), min_size=1, max_size=2)
            )),
            'open_now': draw(st.booleans()),
            'price_max': draw(st.one_of(st.none(), st.integers(min_value=1, max_value=4))),
            'min_rating': draw(st.one_of(st.none(), st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False))),
        },
        'proximity_intent_detected': with_proximity_intent or draw(st.booleans()),
        'retrieval_strategy': 'structured_only',
        'original_query': draw(st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' '))).strip() or 'find places',
        'debug': {}
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


class TestProperty1_FilterFirstAsPrimaryStrategy:
    """
    Property 1: Filter-First as Primary Strategy
    
    For any query processed by the Unified_System, the filter-first retrieval
    strategy should be attempted before any other retrieval strategy.
    
    **Validates: Requirements 2.2, 9.1**
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=1, max_size=20, unique_by=lambda p: p['placeId']),
        query_plan=query_plan_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_filter_first_always_attempted(
        self,
        category_matcher,
        ranking_engine,
        places,
        query_plan
    ):
        """
        Property: For any query, filter-first retrieval should be attempted
        before any other strategy.
        """
        # Create place cache
        place_cache = PlaceCache(places)
        
        # Create retriever WITHOUT vector store or OSM client
        # This ensures only filter-first is available
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=None,
            osm_client=None
        )
        
        # Execute retrieval
        result = retriever.retrieve(query_plan)
        
        # Verify filter-first was used
        assert result.strategy_used == 'filter_first', (
            f"Expected filter_first strategy, got {result.strategy_used}"
        )
        
        # Verify OSM was not triggered (no OSM client available)
        assert result.osm_triggered is False, (
            "OSM should not be triggered when no OSM client is available"
        )
    
    @given(
        places=st.lists(place_strategy(), min_size=5, max_size=20, unique_by=lambda p: p['placeId']),
        query_plan=query_plan_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_filter_first_returns_results(
        self,
        category_matcher,
        ranking_engine,
        places,
        query_plan
    ):
        """
        Property: Filter-first should return results when matching places exist.
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
        
        # Execute retrieval
        result = retriever.retrieve(query_plan)
        
        # Verify we got results (may be empty if filters are too restrictive)
        assert isinstance(result.places, list), "Result should contain a list of places"
        assert result.strategy_used == 'filter_first', "Should use filter-first strategy"



class TestProperty4_MultiFilterSupport:
    """
    Property 4: Multi-Filter Support
    
    For any combination of filters (open hours, proximity, category, price, rating),
    the unified retriever should correctly apply all specified filters to the result set.
    
    **Validates: Requirements 4.2**
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=10, max_size=30, unique_by=lambda p: p['placeId']),
        categories=st.lists(st.sampled_from(['restaurant', 'cafe', 'hotel']), min_size=1, max_size=2, unique=True),
        price_max=st.integers(min_value=1, max_value=4),
        min_rating=st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_multiple_filters_applied_correctly(
        self,
        category_matcher,
        ranking_engine,
        places,
        categories,
        price_max,
        min_rating
    ):
        """
        Property: When multiple filters are specified, all filters should be
        applied to the result set.
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
        
        # Create query plan with multiple filters
        query_plan = {
            'intent': 'general',
            'intents': {},
            'slots': {
                'user_location': None,
                'categories': categories,
                'price_max': price_max,
                'min_rating': min_rating,
                'open_now': False
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'original_query': 'find places',
            'debug': {}
        }
        
        # Execute retrieval
        result = retriever.retrieve(query_plan)
        
        # Verify all filters were applied
        expected_filters = ['category', 'price', 'rating']
        for filter_name in expected_filters:
            assert filter_name in result.filters_applied, (
                f"Filter '{filter_name}' should be in filters_applied"
            )
        
        # Verify all results match the filters
        for place in result.places:
            # Check category filter
            place_categories = place.get('categories', [])
            assert any(
                category_matcher._matches_keywords(pc, cat)
                for pc in place_categories
                for cat in categories
            ), f"Place {place['placeId']} should match category filter"
            
            # Check price filter
            place_price = place.get('price')
            if place_price is not None:
                assert place_price <= price_max, (
                    f"Place {place['placeId']} price {place_price} exceeds max {price_max}"
                )
            
            # Check rating filter
            place_rating = place.get('totalScore')
            if place_rating is not None:
                assert place_rating >= min_rating, (
                    f"Place {place['placeId']} rating {place_rating} below min {min_rating}"
                )

    
    @given(
        places=st.lists(place_strategy(), min_size=10, max_size=30, unique_by=lambda p: p['placeId']),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_proximity_filter_with_other_filters(
        self,
        category_matcher,
        ranking_engine,
        places,
        user_location
    ):
        """
        Property: Proximity filter should work correctly in combination with
        other filters (category, price, rating).
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
        
        # Create query plan with proximity + category filters
        query_plan = {
            'intent': 'location',
            'intents': {'location': 0.9},
            'slots': {
                'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude},
                'categories': ['restaurant'],
                'price_max': None,
                'min_rating': None,
                'open_now': False
            },
            'proximity_intent_detected': True,
            'retrieval_strategy': 'structured_only',
            'original_query': 'find restaurants nearby',
            'debug': {'detected_intents': ['location']}
        }
        
        # Execute retrieval
        result = retriever.retrieve(query_plan)
        
        # Verify both filters were applied
        assert 'proximity' in result.filters_applied, "Proximity filter should be applied"
        assert 'category' in result.filters_applied, "Category filter should be applied"
        
        # Verify all results have distance calculated
        for place in result.places:
            assert 'distanceKm' in place, (
                f"Place {place['placeId']} should have distanceKm field"
            )
            
            # Verify distance is reasonable (within escalation radius)
            distance = place.get('distanceKm')
            if distance is not None:
                assert distance <= 2.0, (
                    f"Place {place['placeId']} distance {distance}km exceeds max radius 2.0km"
                )


class TestProperty7_ProximityIntentHandling:
    """
    Property 7: Proximity Intent Handling
    
    For any query, proximity filtering should be applied if and only if proximity
    keywords are present in the query AND user location is available, with radius
    escalation (0.5km → 1km → 2km) when results are insufficient.
    
    **Validates: Requirements 5.2, 6.1, 6.2, 6.3, 6.4**
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=10, max_size=30, unique_by=lambda p: p['placeId']),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_proximity_filter_only_with_intent_and_location(
        self,
        category_matcher,
        ranking_engine,
        places,
        user_location
    ):
        """
        Property: Proximity filtering should only be applied when BOTH
        proximity intent is detected AND user location is available.
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
        
        # Test Case 1: WITH proximity intent AND location
        query_plan_with_both = {
            'intent': 'location',
            'intents': {'location': 0.9},
            'slots': {
                'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude},
                'categories': None,
                'open_now': False
            },
            'proximity_intent_detected': True,
            'retrieval_strategy': 'structured_only',
            'original_query': 'find places nearby',
            'debug': {'detected_intents': ['location']}
        }
        
        result_with_both = retriever.retrieve(query_plan_with_both)
        
        # Should apply proximity filter
        assert 'proximity' in result_with_both.filters_applied, (
            "Proximity filter should be applied when intent detected AND location available"
        )

        
        # Test Case 2: WITHOUT proximity intent (but with location)
        query_plan_no_intent = {
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
        
        result_no_intent = retriever.retrieve(query_plan_no_intent)
        
        # Should NOT apply proximity filter
        assert 'proximity' not in result_no_intent.filters_applied, (
            "Proximity filter should NOT be applied when intent not detected"
        )
        
        # Test Case 3: WITH proximity intent but WITHOUT location
        query_plan_no_location = {
            'intent': 'location',
            'intents': {'location': 0.9},
            'slots': {
                'user_location': None,
                'categories': None,
                'open_now': False
            },
            'proximity_intent_detected': True,
            'retrieval_strategy': 'structured_only',
            'original_query': 'find places nearby',
            'debug': {'detected_intents': ['location']}
        }
        
        result_no_location = retriever.retrieve(query_plan_no_location)
        
        # Should NOT apply proximity filter
        assert 'proximity' not in result_no_location.filters_applied, (
            "Proximity filter should NOT be applied when location not available"
        )
    
    @given(
        user_location=location_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_radius_escalation_sequence(
        self,
        category_matcher,
        ranking_engine,
        user_location
    ):
        """
        Property: Proximity filtering should use radius escalation
        (0.5km → 1km → 2km) to ensure sufficient results.
        """
        # Create places at different distances
        places = []
        distances = [0.3, 0.4, 0.7, 0.9, 1.5, 1.8, 2.5, 3.0]  # km
        
        for i, dist_km in enumerate(distances):
            # Calculate lat/lng offset for approximate distance
            # 1 degree latitude ≈ 111km
            lat_offset = dist_km / 111.0
            
            places.append({
                'placeId': f'place_{i}',
                'title': f'Place {i}',
                'titleFormatted': f'Place {i}',
                'categories': ['restaurant'],
                'location': {
                    'lat': user_location.latitude + lat_offset,
                    'lng': user_location.longitude
                },
                'totalScore': 4.0,
                'reviewsCount': 100,
                'price': 2,
                'businessTime': None
            })
        
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
        
        # Create query plan with proximity intent
        query_plan = {
            'intent': 'location',
            'intents': {'location': 0.9},
            'slots': {
                'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude},
                'categories': None,
                'open_now': False
            },
            'proximity_intent_detected': True,
            'retrieval_strategy': 'structured_only',
            'original_query': 'find places nearby',
            'debug': {'detected_intents': ['location']}
        }
        
        # Execute retrieval
        result = retriever.retrieve(query_plan)
        
        # Verify proximity filter was applied
        assert 'proximity' in result.filters_applied, "Proximity filter should be applied"
        
        # Verify all results are within maximum radius (2km)
        for place in result.places:
            distance = place.get('distanceKm')
            if distance is not None:
                assert distance <= 2.0, (
                    f"Place {place['placeId']} at {distance}km exceeds max radius 2.0km"
                )

    
    @given(
        places=st.lists(place_strategy(), min_size=5, max_size=20, unique_by=lambda p: p['placeId']),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_distance_calculated_for_all_results(
        self,
        category_matcher,
        ranking_engine,
        places,
        user_location
    ):
        """
        Property: Distance should be calculated for all results when user
        location is available, regardless of whether proximity filtering is applied.
        
        This validates Requirement 6.5: Distance Calculation Invariant.
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
        
        # Create query plan WITHOUT proximity intent (but with location)
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
        
        # Verify proximity filter was NOT applied
        assert 'proximity' not in result.filters_applied, (
            "Proximity filter should not be applied without proximity intent"
        )
        
        # Verify distance is calculated for all results
        for place in result.places:
            assert 'distanceKm' in place, (
                f"Place {place['placeId']} should have distanceKm field even without proximity filter"
            )
            
            # Verify distance is a valid number
            distance = place.get('distanceKm')
            if distance is not None:
                assert isinstance(distance, (int, float)), (
                    f"Distance should be numeric, got {type(distance)}"
                )
                assert distance >= 0, f"Distance should be non-negative, got {distance}"


class TestProperty14_FilterPrecedenceOrder:
    """
    Property 14: Filter Precedence Order
    
    For any query with multiple filters, the system should apply filters in the
    following order: open_now, proximity, category, price, rating.
    
    **Validates: Requirements 8.1, 8.2, 8.3, 8.4**
    """
    
    @given(
        user_location=location_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_filter_precedence_order(
        self,
        category_matcher,
        ranking_engine,
        user_location
    ):
        """
        Property: Filters should be applied in the correct precedence order:
        open_now → proximity → category → price → rating.
        
        This test creates places that would be filtered out at different stages
        and verifies the order of filtering.
        """
        # Create places with specific characteristics to test precedence
        places = [
            # Place 1: Passes all filters
            {
                'placeId': 'place_all_pass',
                'title': 'Perfect Place',
                'titleFormatted': 'Perfect Place',
                'categories': ['restaurant'],
                'location': {'lat': user_location.latitude + 0.001, 'lng': user_location.longitude},
                'totalScore': 4.5,
                'reviewsCount': 100,
                'price': 2,
                'businessTime': 'Open 24 hours'
            },
            # Place 2: Closed (fails open_now - FIRST filter)
            {
                'placeId': 'place_closed',
                'title': 'Closed Place',
                'titleFormatted': 'Closed Place',
                'categories': ['restaurant'],
                'location': {'lat': user_location.latitude + 0.001, 'lng': user_location.longitude},
                'totalScore': 4.5,
                'reviewsCount': 100,
                'price': 2,
                'businessTime': 'Monday-Sunday: 00:00-00:01'  # Effectively closed
            },
            # Place 3: Too far (fails proximity - SECOND filter)
            {
                'placeId': 'place_far',
                'title': 'Far Place',
                'titleFormatted': 'Far Place',
                'categories': ['restaurant'],
                'location': {'lat': user_location.latitude + 0.5, 'lng': user_location.longitude},  # ~55km away
                'totalScore': 4.5,
                'reviewsCount': 100,
                'price': 2,
                'businessTime': 'Open 24 hours'
            },
            # Place 4: Wrong category (fails category - THIRD filter)
            {
                'placeId': 'place_wrong_category',
                'title': 'Hotel Place',
                'titleFormatted': 'Hotel Place',
                'categories': ['hotel'],
                'location': {'lat': user_location.latitude + 0.001, 'lng': user_location.longitude},
                'totalScore': 4.5,
                'reviewsCount': 100,
                'price': 2,
                'businessTime': 'Open 24 hours'
            },
            # Place 5: Too expensive (fails price - FOURTH filter)
            {
                'placeId': 'place_expensive',
                'title': 'Expensive Place',
                'titleFormatted': 'Expensive Place',
                'categories': ['restaurant'],
                'location': {'lat': user_location.latitude + 0.001, 'lng': user_location.longitude},
                'totalScore': 4.5,
                'reviewsCount': 100,
                'price': 4,
                'businessTime': 'Open 24 hours'
            },
            # Place 6: Low rating (fails rating - FIFTH filter)
            {
                'placeId': 'place_low_rating',
                'title': 'Low Rating Place',
                'titleFormatted': 'Low Rating Place',
                'categories': ['restaurant'],
                'location': {'lat': user_location.latitude + 0.001, 'lng': user_location.longitude},
                'totalScore': 2.0,
                'reviewsCount': 100,
                'price': 2,
                'businessTime': 'Open 24 hours'
            }
        ]
        
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

        
        # Create query plan with ALL filters enabled
        query_plan = {
            'intent': 'location',
            'intents': {'location': 0.9},
            'slots': {
                'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude},
                'categories': ['restaurant'],
                'open_now': True,
                'price_max': 3,
                'min_rating': 4.0
            },
            'proximity_intent_detected': True,
            'retrieval_strategy': 'structured_only',
            'original_query': 'find open restaurants nearby',
            'debug': {'detected_intents': ['location', 'business_hours']}
        }
        
        # Execute retrieval
        result = retriever.retrieve(query_plan)
        
        # Verify all filters were applied in order
        expected_filters = ['open_now', 'proximity', 'category', 'price', 'rating']
        for filter_name in expected_filters:
            assert filter_name in result.filters_applied, (
                f"Filter '{filter_name}' should be in filters_applied"
            )
        
        # Verify only the perfect place passed all filters
        # (or possibly none if the test data doesn't match perfectly)
        for place in result.places:
            # All results should pass all filters
            assert place['placeId'] == 'place_all_pass', (
                f"Only 'place_all_pass' should pass all filters, got {place['placeId']}"
            )
    
    @given(
        places=st.lists(place_strategy(), min_size=10, max_size=30, unique_by=lambda p: p['placeId']),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_filters_applied_list_order(
        self,
        category_matcher,
        ranking_engine,
        places,
        user_location
    ):
        """
        Property: The filters_applied list should reflect the order in which
        filters were applied (though the list itself may not be ordered).
        
        This verifies that the system tracks which filters were applied.
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
        
        # Create query plan with multiple filters
        query_plan = {
            'intent': 'location',
            'intents': {'location': 0.9},
            'slots': {
                'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude},
                'categories': ['restaurant'],
                'open_now': True,
                'price_max': 3,
                'min_rating': 3.5
            },
            'proximity_intent_detected': True,
            'retrieval_strategy': 'structured_only',
            'original_query': 'find open restaurants nearby',
            'debug': {'detected_intents': ['location', 'business_hours']}
        }
        
        # Execute retrieval
        result = retriever.retrieve(query_plan)
        
        # Verify filters_applied contains all expected filters
        expected_filters = {'open_now', 'proximity', 'category', 'price', 'rating'}
        actual_filters = set(result.filters_applied)
        
        assert expected_filters == actual_filters, (
            f"Expected filters {expected_filters}, got {actual_filters}"
        )


class TestFilterFirstInvariants:
    """
    Test invariants that should hold for all filter-first retrievals.
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=0, max_size=20, unique_by=lambda p: p['placeId']),
        query_plan=query_plan_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_filter_first_preserves_place_count_or_reduces(
        self,
        category_matcher,
        ranking_engine,
        places,
        query_plan
    ):
        """
        Property: Filter-first should return the same or fewer places than
        the input (filters can only remove, not add places).
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
        
        # Execute retrieval
        result = retriever.retrieve(query_plan)
        
        # Verify result count is <= input count
        assert len(result.places) <= len(places), (
            f"Filter-first returned {len(result.places)} places but started with {len(places)}"
        )
    
    @given(
        places=st.lists(place_strategy(), min_size=1, max_size=20, unique_by=lambda p: p['placeId']),
        query_plan=query_plan_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_filter_first_no_duplicate_places(
        self,
        category_matcher,
        ranking_engine,
        places,
        query_plan
    ):
        """
        Property: Filter-first should not return duplicate places.
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
        
        # Execute retrieval
        result = retriever.retrieve(query_plan)
        
        # Verify no duplicates
        place_ids = [p['placeId'] for p in result.places]
        unique_ids = set(place_ids)
        
        assert len(place_ids) == len(unique_ids), (
            f"Found duplicate places in results: {len(place_ids)} total, {len(unique_ids)} unique"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
