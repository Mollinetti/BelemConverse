"""
Tests for distance calculation in UnifiedRetriever.

This module tests that distance is calculated and included in results
for display purposes, regardless of whether proximity filtering is applied.

Feature: intent-detection-unification
Property 13: Distance Calculation Invariant
Validates: Requirements 6.5
"""

import sys
from pathlib import Path

# Add project root and src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

import pytest
from unittest.mock import Mock, MagicMock
from typing import List, Dict, Any

# Import using standard imports since we added src to path
from core.unified_retriever import UnifiedRetriever, RetrievalResult
from core.place_cache import PlaceCache
from core.category_matcher import CategoryMatcher
from core.ranking_engine import RankingEngine, Location


@pytest.fixture
def mock_place_cache():
    """Create a mock PlaceCache with test data."""
    cache = Mock(spec=PlaceCache)
    
    # Create test places at different distances from user
    test_places = [
        {
            'placeId': 'place1',
            'title': 'Restaurant A',
            'titleFormatted': 'Restaurant A',
            'category': ['restaurant'],
            'location': {'lat': -23.5505, 'lng': -46.6333},  # ~0km from user
            'totalScore': 4.5,
            'reviewsCount': 100,
            'priceRange': '$$'
        },
        {
            'placeId': 'place2',
            'title': 'Cafe B',
            'titleFormatted': 'Cafe B',
            'category': ['cafe'],
            'location': {'lat': -23.5605, 'lng': -46.6433},  # ~1.5km from user
            'totalScore': 4.2,
            'reviewsCount': 50,
            'priceRange': '$'
        },
        {
            'placeId': 'place3',
            'title': 'Hotel C',
            'titleFormatted': 'Hotel C',
            'category': ['hotel'],
            'location': {'lat': -23.5805, 'lng': -46.6633},  # ~4km from user
            'totalScore': 4.8,
            'reviewsCount': 200,
            'priceRange': '$$$'
        }
    ]
    
    cache.get_all.return_value = test_places
    cache.get_by_id.side_effect = lambda pid: next(
        (p for p in test_places if p['placeId'] == pid), None
    )
    
    return cache


@pytest.fixture
def mock_category_matcher():
    """Create a mock CategoryMatcher."""
    matcher = Mock(spec=CategoryMatcher)
    # Default: all places match all categories
    matcher.matches.return_value = True
    return matcher


@pytest.fixture
def mock_ranking_engine():
    """Create a mock RankingEngine."""
    engine = Mock(spec=RankingEngine)
    # Default: return places as-is, accepting all keyword arguments
    engine.rank.side_effect = lambda places, **kwargs: places
    return engine


@pytest.fixture
def unified_retriever(mock_place_cache, mock_category_matcher, mock_ranking_engine):
    """Create a UnifiedRetriever with mocked dependencies."""
    return UnifiedRetriever(
        place_cache=mock_place_cache,
        category_matcher=mock_category_matcher,
        ranking_engine=mock_ranking_engine,
        vector_store=None,
        osm_client=None
    )


class TestDistanceCalculationWithProximityIntent:
    """Test distance calculation when proximity intent is detected."""
    
    def test_distance_calculated_with_proximity_intent(self, unified_retriever):
        """
        When proximity intent is detected AND user location is available,
        distances should be calculated for all results.
        """
        query_plan = {
            'slots': {
                'user_location': {
                    'latitude': -23.5505,
                    'longitude': -46.6333
                },
                'original_query': 'restaurants near me'
            },
            'proximity_intent_detected': True,
            'intents': {'location': 0.9}
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        # Verify distances were calculated
        assert len(result.places) > 0, "Should have results"
        
        for place in result.places:
            assert 'distanceKm' in place, f"Place {place['title']} missing distanceKm"
            assert place['distanceKm'] is not None, f"Place {place['title']} has None distanceKm"
            assert isinstance(place['distanceKm'], (int, float)), \
                f"Place {place['title']} distanceKm is not numeric"
            assert place['distanceKm'] >= 0, \
                f"Place {place['title']} has negative distance"


class TestDistanceCalculationWithoutProximityIntent:
    """Test distance calculation when proximity intent is NOT detected."""
    
    def test_distance_calculated_without_proximity_intent(self, unified_retriever):
        """
        When proximity intent is NOT detected BUT user location is available,
        distances should still be calculated for display purposes.
        
        This is the key test for Requirement 6.5: distance should be calculated
        regardless of proximity filtering.
        """
        query_plan = {
            'slots': {
                'user_location': {
                    'latitude': -23.5505,
                    'longitude': -46.6333
                },
                'original_query': 'best restaurants'  # No proximity keywords
            },
            'proximity_intent_detected': False,  # KEY: No proximity intent
            'intents': {'popularity': 0.8}
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        # Verify distances were calculated even without proximity intent
        assert len(result.places) > 0, "Should have results"
        
        for place in result.places:
            assert 'distanceKm' in place, \
                f"Place {place['title']} missing distanceKm (proximity_intent=False)"
            assert place['distanceKm'] is not None, \
                f"Place {place['title']} has None distanceKm (proximity_intent=False)"
            assert isinstance(place['distanceKm'], (int, float)), \
                f"Place {place['title']} distanceKm is not numeric (proximity_intent=False)"
            assert place['distanceKm'] >= 0, \
                f"Place {place['title']} has negative distance (proximity_intent=False)"
    
    def test_no_proximity_filtering_without_intent(self, unified_retriever, mock_place_cache):
        """
        When proximity intent is NOT detected, proximity filtering should NOT be applied,
        but distances should still be calculated.
        """
        # All test places are at different distances
        all_places = mock_place_cache.get_all()
        
        query_plan = {
            'slots': {
                'user_location': {
                    'latitude': -23.5505,
                    'longitude': -46.6333
                },
                'original_query': 'restaurants'
            },
            'proximity_intent_detected': False,
            'intents': {}
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        # Should return all places (no proximity filtering)
        assert len(result.places) == len(all_places), \
            "Should return all places when proximity intent not detected"
        
        # But all should have distances calculated
        for place in result.places:
            assert 'distanceKm' in place, "Distance should be calculated"
            assert place['distanceKm'] is not None, "Distance should not be None"


class TestDistanceCalculationWithoutUserLocation:
    """Test distance calculation when user location is unavailable."""
    
    def test_no_distance_without_user_location(self, unified_retriever):
        """
        When user location is NOT available, distances should NOT be calculated
        (set to None).
        """
        query_plan = {
            'slots': {
                'original_query': 'restaurants'
                # No user_location
            },
            'proximity_intent_detected': False,
            'intents': {}
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        # Should have results but no distances
        assert len(result.places) > 0, "Should have results"
        
        for place in result.places:
            # Distance field may or may not be present, but if present should be None
            if 'distanceKm' in place:
                assert place['distanceKm'] is None, \
                    f"Place {place['title']} should have None distanceKm without user location"
    
    def test_proximity_intent_ignored_without_location(self, unified_retriever, mock_place_cache):
        """
        When proximity intent is detected BUT user location is unavailable,
        proximity filtering should NOT be applied and distances should NOT be calculated.
        """
        all_places = mock_place_cache.get_all()
        
        query_plan = {
            'slots': {
                'original_query': 'restaurants near me'
                # No user_location
            },
            'proximity_intent_detected': True,  # Intent detected but no location
            'intents': {'location': 0.9}
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        # Should return all places (no proximity filtering possible)
        assert len(result.places) == len(all_places), \
            "Should return all places when user location unavailable"
        
        # Distances should not be calculated
        for place in result.places:
            if 'distanceKm' in place:
                assert place['distanceKm'] is None, \
                    "Distance should be None without user location"


class TestDistanceCalculationAccuracy:
    """Test that distance calculations are accurate."""
    
    def test_distance_calculation_haversine(self, unified_retriever):
        """
        Test that distance calculation uses Haversine formula correctly.
        """
        # São Paulo coordinates
        user_location = Location(latitude=-23.5505, longitude=-46.6333)
        
        # Place at known distance (approximately 1.5km away)
        places = [{
            'placeId': 'test1',
            'title': 'Test Place',
            'location': {'lat': -23.5605, 'lng': -46.6433}
        }]
        
        # Calculate distance
        result = unified_retriever._add_distances(places, user_location)
        
        # Verify distance is approximately correct (within 0.5km tolerance)
        assert len(result) == 1
        distance = result[0]['distanceKm']
        assert distance is not None
        assert 1.0 <= distance <= 2.0, \
            f"Expected distance ~1.5km, got {distance}km"
    
    def test_distance_zero_for_same_location(self, unified_retriever):
        """
        Test that distance is zero (or very close) for same location.
        """
        user_location = Location(latitude=-23.5505, longitude=-46.6333)
        
        places = [{
            'placeId': 'test1',
            'title': 'Test Place',
            'location': {'lat': -23.5505, 'lng': -46.6333}  # Same location
        }]
        
        result = unified_retriever._add_distances(places, user_location)
        
        assert len(result) == 1
        distance = result[0]['distanceKm']
        assert distance is not None
        assert distance < 0.01, \
            f"Expected distance ~0km for same location, got {distance}km"
    
    def test_distance_none_for_missing_coordinates(self, unified_retriever):
        """
        Test that distance is None when place has missing coordinates.
        """
        user_location = Location(latitude=-23.5505, longitude=-46.6333)
        
        places = [
            {
                'placeId': 'test1',
                'title': 'Place with no location',
                'location': {}  # Missing lat/lng
            },
            {
                'placeId': 'test2',
                'title': 'Place with partial location',
                'location': {'lat': -23.5505}  # Missing lng
            }
        ]
        
        result = unified_retriever._add_distances(places, user_location)
        
        assert len(result) == 2
        for place in result:
            assert place['distanceKm'] is None, \
                f"Place {place['title']} should have None distance with missing coordinates"


class TestDistanceCalculationInSemanticSearch:
    """Test distance calculation in semantic search fallback."""
    
    def test_distance_calculated_in_semantic_search(self, unified_retriever, mock_place_cache):
        """
        When semantic search is used as fallback, distances should still be calculated
        when user location is available.
        """
        # Mock vector store to return results
        mock_vector_store = Mock()
        mock_doc = Mock()
        mock_doc.metadata = {'placeId': 'place1'}
        mock_vector_store.similarity_search_with_score.return_value = [
            (mock_doc, 0.5)
        ]
        unified_retriever.vector_store = mock_vector_store
        
        query_plan = {
            'slots': {
                'user_location': {
                    'latitude': -23.5505,
                    'longitude': -46.6333
                },
                'original_query': 'cozy atmosphere'
            },
            'proximity_intent_detected': False,
            'intents': {}
        }
        
        # Call semantic search directly
        results = unified_retriever._semantic_search(query_plan)
        
        # Verify distances were calculated
        assert len(results) > 0, "Should have semantic search results"
        
        for place in results:
            assert 'distanceKm' in place, \
                f"Place {place.get('title', 'Unknown')} missing distanceKm in semantic search"
            # Distance should be calculated (not None) since we have user location
            assert place['distanceKm'] is not None, \
                f"Place {place.get('title', 'Unknown')} has None distanceKm in semantic search"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
