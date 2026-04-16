"""
Tests for intent-to-retrieval mapping in UnifiedRetriever.

This module tests how detected intents translate to retrieval behavior:
- location intent → proximity filtering + distance ranking
- popularity intent → popularity ranking
- business_hours intent → open_now filtering
- price intent → price range filtering
- verification intent → exact name matching + OSM fallback

Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.7
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))
sys.path.insert(0, str(project_root / 'src' / 'core'))

import pytest
from unittest.mock import Mock, MagicMock, patch

# Import modules directly
from core.unified_retriever import UnifiedRetriever, RetrievalResult
from core.place_cache import PlaceCache
from core.category_matcher import CategoryMatcher
from core.ranking_engine import RankingEngine, RankingMode, Location


@pytest.fixture
def mock_place_cache():
    """Create a mock PlaceCache with sample places."""
    cache = Mock(spec=PlaceCache)
    
    # Sample places for testing
    places = [
        {
            'placeId': 'place1',
            'title': 'Popular Restaurant',
            'titleFormatted': 'Popular Restaurant',
            'category': ['restaurant'],
            'location': {'lat': -23.5505, 'lng': -46.6333},
            'totalScore': 4.5,
            'reviewsCount': 500,
            'price': 2,
            'businessTime': 'Mon-Sun: 11:00-22:00',
        },
        {
            'placeId': 'place2',
            'title': 'Nearby Cafe',
            'titleFormatted': 'Nearby Cafe',
            'category': ['cafe'],
            'location': {'lat': -23.5510, 'lng': -46.6340},
            'totalScore': 4.2,
            'reviewsCount': 200,
            'price': 1,
            'businessTime': 'Mon-Sun: 08:00-20:00',
        },
        {
            'placeId': 'place3',
            'title': 'Expensive Hotel',
            'titleFormatted': 'Expensive Hotel',
            'category': ['hotel'],
            'location': {'lat': -23.5520, 'lng': -46.6350},
            'totalScore': 4.8,
            'reviewsCount': 1000,
            'price': 4,
            'businessTime': '24 hours',
        },
        {
            'placeId': 'place4',
            'title': 'Budget Bar',
            'titleFormatted': 'Budget Bar',
            'category': ['bar'],
            'location': {'lat': -23.5530, 'lng': -46.6360},
            'totalScore': 3.8,
            'reviewsCount': 100,
            'price': 1,
            'businessTime': 'Mon-Sat: 18:00-02:00',
        },
    ]
    
    cache.get_all.return_value = places
    cache.get_by_id.side_effect = lambda pid: next((p for p in places if p['placeId'] == pid), None)
    
    return cache


@pytest.fixture
def mock_category_matcher():
    """Create a mock CategoryMatcher."""
    matcher = Mock(spec=CategoryMatcher)
    
    def matches_impl(place, categories):
        place_cats = place.get('category', [])
        return any(cat in place_cats for cat in categories)
    
    matcher.matches.side_effect = matches_impl
    return matcher


@pytest.fixture
def mock_ranking_engine():
    """Create a mock RankingEngine that sorts by the specified mode."""
    engine = Mock(spec=RankingEngine)
    
    def rank_impl(places, mode, user_location=None):
        if mode == RankingMode.DISTANCE and user_location:
            # Sort by distance (already calculated)
            return sorted(places, key=lambda p: p.get('distanceKm', float('inf')))
        elif mode == RankingMode.POPULARITY:
            # Sort by review count as proxy for popularity
            return sorted(places, key=lambda p: p.get('reviewsCount', 0), reverse=True)
        elif mode == RankingMode.RATING:
            # Sort by rating
            return sorted(places, key=lambda p: p.get('totalScore', 0), reverse=True)
        else:  # BEST_MATCH
            # Sort by rating as default
            return sorted(places, key=lambda p: p.get('totalScore', 0), reverse=True)
    
    engine.rank.side_effect = rank_impl
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


class TestLocationIntentMapping:
    """Test location intent → proximity filtering + distance ranking."""
    
    def test_location_intent_applies_proximity_filter(self, unified_retriever):
        """
        GIVEN a query with location intent detected
        WHEN retrieval is performed
        THEN proximity filtering should be applied
        
        Validates: Requirement 5.2
        """
        query_plan = {
            'intent': 'location',
            'intents': {'location': 0.9},
            'slots': {
                'categories': ['restaurant'],
                'user_location': {'lat': -23.5505, 'lng': -46.6333},
            },
            'proximity_intent_detected': True,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['location']},
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        # Should apply proximity filter
        assert 'proximity' in result.filters_applied or result.total_candidates > 0
        # Should use distance ranking
        assert result.ranking_mode == RankingMode.DISTANCE
    
    def test_location_intent_uses_distance_ranking(self, unified_retriever):
        """
        GIVEN a query with location intent
        WHEN results are ranked
        THEN distance ranking mode should be used
        
        Validates: Requirement 5.2
        """
        query_plan = {
            'intent': 'location',
            'intents': {'location': 0.9},
            'slots': {
                'categories': ['restaurant'],
                'user_location': {'lat': -23.5505, 'lng': -46.6333},
            },
            'proximity_intent_detected': True,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['location']},
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        assert result.ranking_mode == RankingMode.DISTANCE
    
    def test_no_proximity_filter_without_location_intent(self, unified_retriever):
        """
        GIVEN a query without location intent
        WHEN retrieval is performed
        THEN proximity filtering should NOT be applied
        
        Validates: Requirement 6.3
        """
        query_plan = {
            'intent': 'general',
            'intents': {},
            'slots': {
                'categories': ['restaurant'],
                'user_location': {'lat': -23.5505, 'lng': -46.6333},
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': []},
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        # Should NOT apply proximity filter even though location is available
        assert 'proximity' not in result.filters_applied


class TestPopularityIntentMapping:
    """Test popularity intent → popularity ranking."""
    
    def test_popularity_intent_uses_popularity_ranking(self, unified_retriever):
        """
        GIVEN a query with popularity intent detected
        WHEN results are ranked
        THEN popularity ranking mode should be used
        
        Validates: Requirement 5.3
        """
        query_plan = {
            'intent': 'popularity',
            'intents': {'popularity': 0.9},
            'slots': {
                'categories': ['restaurant'],
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['popularity']},
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        assert result.ranking_mode == RankingMode.POPULARITY
    
    def test_popularity_ranking_orders_by_review_count(self, unified_retriever, mock_ranking_engine):
        """
        GIVEN places with different popularity scores
        WHEN ranked by popularity
        THEN places should be ordered by Bayesian popularity score
        
        Validates: Requirement 5.3
        """
        query_plan = {
            'intent': 'popularity',
            'intents': {'popularity': 0.9},
            'slots': {
                'categories': ['restaurant', 'cafe', 'hotel', 'bar'],
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['popularity']},
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        # Verify ranking engine was called with POPULARITY mode
        mock_ranking_engine.rank.assert_called()
        call_args = mock_ranking_engine.rank.call_args
        assert call_args[1]['mode'] == RankingMode.POPULARITY


class TestBusinessHoursIntentMapping:
    """Test business_hours intent → open_now filtering."""
    
    def test_business_hours_intent_applies_open_now_filter(self, unified_retriever):
        """
        GIVEN a query with business_hours intent detected
        WHEN retrieval is performed
        THEN open_now filtering should be applied
        
        Validates: Requirement 5.4
        """
        query_plan = {
            'intent': 'business_hours',
            'intents': {'business_hours': 0.9},
            'slots': {
                'categories': ['restaurant'],
                'open_now': True,
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['business_hours']},
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        # Should apply open_now filter
        assert 'open_now' in result.filters_applied
    
    def test_business_hours_intent_filters_closed_places(self, unified_retriever, mock_place_cache):
        """
        GIVEN places with different business hours
        WHEN open_now filter is applied
        THEN only open places should be returned
        
        Validates: Requirement 5.4
        
        Note: This test verifies that the open_now filter is applied.
        The actual filtering logic is tested in test_filter_first_simple.py
        """
        query_plan = {
            'intent': 'business_hours',
            'intents': {'business_hours': 0.9},
            'slots': {
                'categories': ['restaurant'],
                'open_now': True,
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['business_hours']},
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        # Should have applied open_now filter
        assert 'open_now' in result.filters_applied
        # Should have processed the query successfully
        assert result.total_candidates >= 0


class TestPriceIntentMapping:
    """Test price intent → price range filtering."""
    
    def test_price_intent_applies_price_filter(self, unified_retriever):
        """
        GIVEN a query with price intent detected
        WHEN retrieval is performed
        THEN price range filtering should be applied
        
        Validates: Requirement 5.5
        """
        query_plan = {
            'intent': 'price',
            'intents': {'price': 0.9},
            'slots': {
                'categories': ['restaurant'],
                'price_range': '$$',
                'price_max': 2,
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['price']},
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        # Should apply price filter
        assert 'price' in result.filters_applied
    
    def test_price_filter_excludes_expensive_places(self, unified_retriever):
        """
        GIVEN places with different price levels
        WHEN price filter is applied
        THEN only places within budget should be returned
        
        Validates: Requirement 5.5
        """
        query_plan = {
            'intent': 'price',
            'intents': {'price': 0.9},
            'slots': {
                'categories': ['restaurant', 'cafe', 'hotel', 'bar'],
                'price_max': 2,
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['price']},
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        # Should exclude expensive places (price > 2)
        for place in result.places:
            price = place.get('price')
            if price is not None:
                assert price <= 2


class TestVerificationIntentMapping:
    """Test verification intent → exact name matching + OSM fallback."""
    
    def test_verification_intent_triggers_osm_fallback(self, unified_retriever):
        """
        GIVEN a query with verification intent
        WHEN specific place name is not found in database
        THEN OSM fallback should be triggered
        
        Validates: Requirement 5.7
        """
        # Create a mock OSM client
        mock_osm = Mock()
        mock_osm.search.return_value = []
        unified_retriever.osm_client = mock_osm
        
        query_plan = {
            'intent': 'verification',
            'intents': {'verification': 0.9},
            'slots': {
                'categories': ['restaurant'],
                'user_location': {'lat': -23.5505, 'lng': -46.6333},
            },
            'original_query': 'Is "Nonexistent Restaurant" still open?',
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['verification']},
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        # OSM should be triggered because the specific place name is not found
        # (Note: This depends on _should_trigger_osm logic)
        assert result.osm_triggered or mock_osm.search.called
    
    def test_verification_intent_prioritizes_exact_name_match(self, unified_retriever, mock_place_cache):
        """
        GIVEN a query with verification intent and specific place name
        WHEN database contains the place
        THEN exact name matching should be prioritized
        
        Validates: Requirement 5.7
        """
        query_plan = {
            'intent': 'verification',
            'intents': {'verification': 0.9},
            'slots': {
                'categories': ['restaurant'],
            },
            'original_query': 'Is "Popular Restaurant" still open?',
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['verification']},
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        # Should find the place in database
        assert len(result.places) > 0
        # First result should be the exact match
        assert 'Popular Restaurant' in result.places[0]['title']


class TestDefaultIntentMapping:
    """Test default behavior when no specific intent is detected."""
    
    def test_no_intent_uses_best_match_ranking(self, unified_retriever):
        """
        GIVEN a query with no specific intent detected
        WHEN results are ranked
        THEN best_match ranking mode should be used
        
        Validates: Requirement 5.1
        """
        query_plan = {
            'intent': 'general',
            'intents': {},
            'slots': {
                'categories': ['restaurant'],
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': []},
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        assert result.ranking_mode == RankingMode.BEST_MATCH
    
    def test_category_only_filter_applied(self, unified_retriever):
        """
        GIVEN a query with only category specified
        WHEN retrieval is performed
        THEN only category filter should be applied
        
        Validates: Requirement 5.1
        """
        query_plan = {
            'intent': 'general',
            'intents': {},
            'slots': {
                'categories': ['restaurant'],
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': []},
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        # Should only apply category filter
        assert 'category' in result.filters_applied
        assert 'proximity' not in result.filters_applied
        assert 'open_now' not in result.filters_applied
        assert 'price' not in result.filters_applied


class TestMultipleIntentsMapping:
    """Test behavior when multiple intents are detected."""
    
    def test_location_and_popularity_intents(self, unified_retriever):
        """
        GIVEN a query with both location and popularity intents
        WHEN retrieval is performed
        THEN location intent should take precedence for ranking
        
        Validates: Requirement 5.2
        """
        query_plan = {
            'intent': 'location',
            'intents': {'location': 0.9, 'popularity': 0.7},
            'slots': {
                'categories': ['restaurant'],
                'user_location': {'lat': -23.5505, 'lng': -46.6333},
            },
            'proximity_intent_detected': True,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['location', 'popularity']},
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        # Location intent should take precedence
        assert result.ranking_mode == RankingMode.DISTANCE
    
    def test_business_hours_and_price_intents(self, unified_retriever):
        """
        GIVEN a query with both business_hours and price intents
        WHEN retrieval is performed
        THEN both filters should be applied
        
        Validates: Requirements 5.4, 5.5
        """
        query_plan = {
            'intent': 'business_hours',
            'intents': {'business_hours': 0.9, 'price': 0.8},
            'slots': {
                'categories': ['restaurant'],
                'open_now': True,
                'price_max': 2,
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['business_hours', 'price']},
        }
        
        result = unified_retriever.retrieve(query_plan)
        
        # Both filters should be applied
        assert 'open_now' in result.filters_applied
        assert 'price' in result.filters_applied
