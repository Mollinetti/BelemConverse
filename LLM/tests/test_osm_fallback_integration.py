"""
Integration tests for OSM fallback logic in UnifiedRetriever.

Tests the OSM fallback trigger conditions and result merging.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

import pytest
from unittest.mock import Mock, MagicMock
from core.unified_retriever import UnifiedRetriever
from core.place_cache import PlaceCache
from core.category_matcher import CategoryMatcher
from core.ranking_engine import RankingEngine, Location


@pytest.fixture
def mock_osm_client():
    """Mock OSM client that returns sample results."""
    client = Mock()
    
    # Mock search method to return OSM documents
    def mock_search(query, user_coordinates, radius=None, categories=None):
        from langchain_core.documents import Document
        
        # Return a sample OSM result
        return [
            Document(
                page_content="title: OSM Restaurant\ncategoryName: Restaurant",
                metadata={
                    'title': 'OSM Restaurant',
                    'categoryName': 'Restaurant',
                    'location/lat': -1.4560,
                    'location/lng': -48.4900,
                    'address': '123 OSM Street',
                    'phone': '+55 91 1234-5678',
                    'website': 'https://osm-restaurant.com',
                    'businessTime': 'Mon-Sun: 11:00-22:00',
                    'distance_km': 0.5,
                    'data_source': 'osm_realtime',
                    'osm_id': 'node/123456',
                    'osm_type': 'node',
                    'totalScore': None,
                    'reviewsCount': 0,
                }
            )
        ]
    
    client.search = Mock(side_effect=mock_search)
    return client


@pytest.fixture
def retriever_with_osm(mock_osm_client):
    """Create a UnifiedRetriever with mocked OSM client."""
    place_cache = PlaceCache([])
    
    # Mock intent classifier for CategoryMatcher
    mock_intent_classifier = Mock()
    category_matcher = CategoryMatcher(mock_intent_classifier)
    
    ranking_engine = RankingEngine()
    
    retriever = UnifiedRetriever(
        place_cache=place_cache,
        category_matcher=category_matcher,
        ranking_engine=ranking_engine,
        vector_store=None,
        osm_client=mock_osm_client
    )
    
    return retriever


class TestOSMFallbackTriggers:
    """Test OSM fallback trigger conditions."""
    
    def test_trigger_on_empty_results(self, retriever_with_osm):
        """OSM should trigger when database results are empty."""
        query_plan = {
            'original_query': 'find restaurants',
            'intents': {},
            'slots': {
                'user_location': {'lat': -1.4558, 'lng': -48.4902}
            },
            'proximity_intent_detected': False
        }
        
        # Empty database results
        db_results = []
        
        should_trigger = retriever_with_osm._should_trigger_osm(db_results, query_plan)
        assert should_trigger is True
    
    def test_trigger_on_low_quality_scores(self, retriever_with_osm):
        """OSM should trigger when all scores are below 0.3."""
        query_plan = {
            'original_query': 'find restaurants',
            'intents': {},
            'slots': {
                'user_location': {'lat': -1.4558, 'lng': -48.4902}
            },
            'proximity_intent_detected': False
        }
        
        # Low quality results
        db_results = [
            {'title': 'Place 1', 'totalScore': 0.2},
            {'title': 'Place 2', 'totalScore': 0.1},
        ]
        
        should_trigger = retriever_with_osm._should_trigger_osm(db_results, query_plan)
        assert should_trigger is True
    
    def test_trigger_on_distant_results_with_proximity_intent(self, retriever_with_osm):
        """OSM should trigger when nearest result is >5km with proximity intent."""
        query_plan = {
            'original_query': 'find restaurants nearby',
            'intents': {},
            'slots': {
                'user_location': {'lat': -1.4558, 'lng': -48.4902}
            },
            'proximity_intent_detected': True
        }
        
        # Distant results
        db_results = [
            {'title': 'Far Place', 'totalScore': 4.5, 'distance_km': 6.0},
        ]
        
        should_trigger = retriever_with_osm._should_trigger_osm(db_results, query_plan)
        assert should_trigger is True
    
    def test_no_trigger_on_distant_results_without_proximity_intent(self, retriever_with_osm):
        """OSM should NOT trigger when results are distant but no proximity intent."""
        query_plan = {
            'original_query': 'find restaurants',
            'intents': {},
            'slots': {
                'user_location': {'lat': -1.4558, 'lng': -48.4902}
            },
            'proximity_intent_detected': False
        }
        
        # Distant results but no proximity intent
        db_results = [
            {'title': 'Far Place', 'totalScore': 4.5, 'distance_km': 6.0},
        ]
        
        should_trigger = retriever_with_osm._should_trigger_osm(db_results, query_plan)
        assert should_trigger is False
    
    def test_trigger_on_verification_intent_name_not_found(self, retriever_with_osm):
        """OSM should trigger when verification intent and place name not found."""
        query_plan = {
            'original_query': 'is "Specific Restaurant" still open?',
            'intents': {'verification': 0.8},
            'slots': {
                'user_location': {'lat': -1.4558, 'lng': -48.4902}
            },
            'proximity_intent_detected': False
        }
        
        # Results without the specific place
        db_results = [
            {'title': 'Other Restaurant', 'titleFormatted': 'Other Restaurant', 'totalScore': 4.5},
        ]
        
        should_trigger = retriever_with_osm._should_trigger_osm(db_results, query_plan)
        assert should_trigger is True
    
    def test_no_trigger_without_user_location(self, retriever_with_osm):
        """OSM should NOT trigger without user location."""
        query_plan = {
            'original_query': 'find restaurants',
            'intents': {},
            'slots': {},
            'proximity_intent_detected': False
        }
        
        db_results = []
        
        should_trigger = retriever_with_osm._should_trigger_osm(db_results, query_plan)
        assert should_trigger is False
    
    def test_no_trigger_on_good_results(self, retriever_with_osm):
        """OSM should NOT trigger when results are satisfactory."""
        query_plan = {
            'original_query': 'find restaurants',
            'intents': {},
            'slots': {
                'user_location': {'lat': -1.4558, 'lng': -48.4902}
            },
            'proximity_intent_detected': False
        }
        
        # Good quality, nearby results
        db_results = [
            {'title': 'Good Place', 'totalScore': 4.5, 'distance_km': 0.5},
            {'title': 'Another Place', 'totalScore': 4.2, 'distance_km': 1.0},
        ]
        
        should_trigger = retriever_with_osm._should_trigger_osm(db_results, query_plan)
        assert should_trigger is False


class TestOSMFallbackExecution:
    """Test OSM fallback execution and result merging."""
    
    def test_osm_fallback_returns_results(self, retriever_with_osm):
        """OSM fallback should return converted results."""
        query_plan = {
            'original_query': 'find restaurants',
            'intents': {},
            'slots': {
                'user_location': {'lat': -1.4558, 'lng': -48.4902},
                'categories': ['restaurant']
            },
            'proximity_intent_detected': False
        }
        
        db_results = []
        
        osm_results = retriever_with_osm._osm_fallback(query_plan, db_results)
        
        assert len(osm_results) > 0
        assert osm_results[0]['title'] == 'OSM Restaurant'
        assert osm_results[0]['data_source'] == 'osm_realtime'
    
    def test_osm_fallback_without_client(self):
        """OSM fallback should return empty list without client."""
        place_cache = PlaceCache([])
        
        # Mock intent classifier for CategoryMatcher
        mock_intent_classifier = Mock()
        category_matcher = CategoryMatcher(mock_intent_classifier)
        
        ranking_engine = RankingEngine()
        
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=None,
            osm_client=None
        )
        
        query_plan = {
            'original_query': 'find restaurants',
            'intents': {},
            'slots': {
                'user_location': {'lat': -1.4558, 'lng': -48.4902}
            }
        }
        
        osm_results = retriever._osm_fallback(query_plan, [])
        assert osm_results == []
    
    def test_osm_fallback_without_location(self, retriever_with_osm):
        """OSM fallback should return empty list without user location."""
        query_plan = {
            'original_query': 'find restaurants',
            'intents': {},
            'slots': {}
        }
        
        osm_results = retriever_with_osm._osm_fallback(query_plan, [])
        assert osm_results == []


class TestOSMDeduplication:
    """Test OSM result deduplication."""
    
    def test_deduplicate_by_exact_title(self, retriever_with_osm):
        """Should remove OSM results with exact title match."""
        db_results = [
            {'title': 'Restaurant A', 'titleFormatted': 'Restaurant A', 'location': {'lat': -1.4558, 'lng': -48.4902}}
        ]
        
        osm_results = [
            {'title': 'Restaurant A', 'location': {'lat': -1.4559, 'lng': -48.4903}},
            # Restaurant B is far enough away (>50m) to not be filtered by proximity
            {'title': 'Restaurant B', 'location': {'lat': -1.4565, 'lng': -48.4910}}
        ]
        
        unique = retriever_with_osm._deduplicate_osm_results(db_results, osm_results)
        
        assert len(unique) == 1
        assert unique[0]['title'] == 'Restaurant B'
    
    def test_deduplicate_by_proximity(self, retriever_with_osm):
        """Should remove OSM results within 50m of database results."""
        db_results = [
            {'title': 'Restaurant A', 'titleFormatted': 'Restaurant A', 'location': {'lat': -1.4558, 'lng': -48.4902}}
        ]
        
        osm_results = [
            # Very close (within 50m) - should be removed
            {'title': 'Different Name', 'location': {'lat': -1.45581, 'lng': -48.49021}},
            # Far enough (>50m) - should be kept (about 100m away)
            {'title': 'Restaurant B', 'location': {'lat': -1.4567, 'lng': -48.4902}}
        ]
        
        unique = retriever_with_osm._deduplicate_osm_results(db_results, osm_results)
        
        assert len(unique) == 1
        assert unique[0]['title'] == 'Restaurant B'
    
    def test_no_deduplication_with_empty_db(self, retriever_with_osm):
        """Should return all OSM results when database is empty."""
        db_results = []
        
        osm_results = [
            {'title': 'Restaurant A', 'location': {'lat': -1.4558, 'lng': -48.4902}},
            {'title': 'Restaurant B', 'location': {'lat': -1.4560, 'lng': -48.4900}}
        ]
        
        unique = retriever_with_osm._deduplicate_osm_results(db_results, osm_results)
        
        assert len(unique) == 2


class TestPlaceNameExtraction:
    """Test place name extraction from queries."""
    
    def test_extract_quoted_name(self, retriever_with_osm):
        """Should extract place name from quotes."""
        query = 'is "Restaurant ABC" still open?'
        name = retriever_with_osm._extract_place_name_from_query(query)
        assert name == 'Restaurant ABC'
    
    def test_extract_name_after_find(self, retriever_with_osm):
        """Should extract place name after 'where is' keyword."""
        query = 'where is the Belém Tower'
        name = retriever_with_osm._extract_place_name_from_query(query)
        assert name == 'Belém Tower'
    
    def test_extract_name_after_called(self, retriever_with_osm):
        """Should extract place name after 'called' keyword."""
        query = 'restaurant called Pizza Palace is it open'
        name = retriever_with_osm._extract_place_name_from_query(query)
        assert name == 'Pizza Palace'
    
    def test_no_extraction_for_generic_query(self, retriever_with_osm):
        """Should return None for generic queries."""
        query = 'find restaurants nearby'
        name = retriever_with_osm._extract_place_name_from_query(query)
        assert name is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
