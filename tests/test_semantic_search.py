"""
Test semantic search fallback implementation.

This test validates that semantic search:
1. Is triggered only when filter-first returns zero results
2. Performs vector similarity search
3. Re-ranks with structured filters
"""

import sys
from pathlib import Path

# Add project root to path

import pytest
from unittest.mock import Mock

from belem_converse.core.unified_retriever import UnifiedRetriever, RetrievalResult
from belem_converse.core.place_cache import PlaceCache
from belem_converse.core.category_matcher import CategoryMatcher
from belem_converse.core.ranking_engine import RankingEngine


@pytest.fixture
def sample_places():
    """Sample places for testing."""
    return [
        {
            'placeId': 'place1',
            'title': 'Italian Restaurant',
            'category': ['restaurant', 'italian'],
            'location': {'lat': -1.4558, 'lng': -48.4902},
            'totalScore': 4.5,
            'reviewsCount': 100,
            'price': 2,
        },
        {
            'placeId': 'place2',
            'title': 'Sushi Bar',
            'category': ['restaurant', 'japanese'],
            'location': {'lat': -1.4560, 'lng': -48.4900},
            'totalScore': 4.8,
            'reviewsCount': 200,
            'price': 3,
        },
        {
            'placeId': 'place3',
            'title': 'Coffee Shop',
            'category': ['cafe'],
            'location': {'lat': -1.4700, 'lng': -48.5000},
            'totalScore': 4.2,
            'reviewsCount': 50,
            'price': 1,
        }
    ]


@pytest.fixture
def place_cache(sample_places):
    """PlaceCache with sample places."""
    return PlaceCache(sample_places)


@pytest.fixture
def category_matcher():
    """CategoryMatcher instance with mock intent classifier."""
    # Create a mock intent classifier that returns proper category keywords
    mock_intent_classifier = Mock()
    
    # Mock category_keywords attribute
    mock_intent_classifier.category_keywords = {
        'restaurant': ['restaurant', 'food', 'dining', 'eatery'],
        'cafe': ['cafe', 'coffee', 'coffeehouse'],
        'hotel': ['hotel', 'accommodation', 'lodging'],
        'japanese': ['japanese', 'sushi', 'ramen'],
        'italian': ['italian', 'pizza', 'pasta'],
    }
    
    return CategoryMatcher(mock_intent_classifier)


@pytest.fixture
def ranking_engine():
    """RankingEngine instance."""
    return RankingEngine()


@pytest.fixture
def mock_vector_store(sample_places):
    """Mock vector store that returns sample documents."""
    vector_store = Mock()
    
    # Create mock documents with metadata
    mock_docs = []
    for place in sample_places:
        doc = Mock()
        doc.metadata = place
        doc.page_content = f"{place['title']} - {', '.join(place['category'])}"
        mock_docs.append(doc)
    
    # similarity_search_with_score returns (doc, distance) tuples
    # Lower distance = more similar
    vector_store.similarity_search_with_score.return_value = [
        (mock_docs[0], 0.2),  # Italian Restaurant - most similar
        (mock_docs[1], 0.5),  # Sushi Bar - medium similarity
        (mock_docs[2], 0.8),  # Coffee Shop - least similar
    ]
    
    return vector_store


class TestSemanticSearch:
    """Test semantic search fallback."""
    
    def test_semantic_search_without_vector_store(self, place_cache, category_matcher, ranking_engine):
        """Test that semantic search returns empty when vector store not available."""
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=None  # No vector store
        )
        
        query_plan = {
            'slots': {
                'original_query': 'find italian food'
            }
        }
        
        results = retriever._semantic_search(query_plan)
        
        assert results == []
    
    def test_semantic_search_without_query_text(self, place_cache, category_matcher, ranking_engine, mock_vector_store):
        """Test that semantic search returns empty when no query text available."""
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=mock_vector_store
        )
        
        query_plan = {
            'slots': {}  # No original_query
        }
        
        results = retriever._semantic_search(query_plan)
        
        assert results == []
    
    def test_semantic_search_basic(self, place_cache, category_matcher, ranking_engine, mock_vector_store):
        """Test basic semantic search functionality."""
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=mock_vector_store
        )
        
        query_plan = {
            'slots': {
                'original_query': 'find italian food'
            }
        }
        
        results = retriever._semantic_search(query_plan)
        
        # Should return results
        assert len(results) > 0
        
        # Should call vector store
        mock_vector_store.similarity_search_with_score.assert_called_once_with(
            'find italian food',
            k=50
        )
        
        # Results should be sorted by composite score
        # Italian Restaurant should be first (highest semantic similarity)
        assert results[0]['placeId'] == 'place1'
    
    def test_semantic_search_with_category_filter(self, place_cache, category_matcher, ranking_engine, mock_vector_store):
        """Test semantic search with category filtering."""
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=mock_vector_store
        )
        
        query_plan = {
            'slots': {
                'original_query': 'find good places',
                'categories': ['restaurant']
            }
        }
        
        results = retriever._semantic_search(query_plan)
        
        # Should filter to only restaurants
        assert len(results) == 2
        for place in results:
            assert 'restaurant' in place['category']
    
    def test_semantic_search_with_location(self, place_cache, category_matcher, ranking_engine, mock_vector_store):
        """Test semantic search with user location for proximity scoring."""
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=mock_vector_store
        )
        
        query_plan = {
            'slots': {
                'original_query': 'find restaurants',
                'user_location': {'lat': -1.4558, 'lng': -48.4902}
            }
        }
        
        results = retriever._semantic_search(query_plan)
        
        # Should calculate distances
        for place in results:
            assert 'distanceKm' in place
            assert place['distanceKm'] is not None
    
    def test_semantic_search_composite_scoring(self, place_cache, category_matcher, ranking_engine, mock_vector_store):
        """Test that semantic search uses composite scoring (semantic + rating + popularity + proximity)."""
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=mock_vector_store
        )
        
        query_plan = {
            'slots': {
                'original_query': 'best restaurants',
                'user_location': {'lat': -1.4558, 'lng': -48.4902}
            }
        }
        
        results = retriever._semantic_search(query_plan)
        
        # Should return results sorted by composite score
        # Sushi Bar (place2) has highest rating (4.8) and most reviews (200)
        # But Italian Restaurant (place1) has better semantic match and proximity
        # The exact order depends on the composite weights
        assert len(results) > 0
        
        # All results should have required fields
        for place in results:
            assert 'placeId' in place
            assert 'totalScore' in place
            assert 'reviewsCount' in place
    
    def test_semantic_search_error_handling(self, place_cache, category_matcher, ranking_engine):
        """Test that semantic search handles errors gracefully."""
        # Create vector store that raises exception
        error_vector_store = Mock()
        error_vector_store.similarity_search_with_score.side_effect = Exception("Vector store error")
        
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=error_vector_store
        )
        
        query_plan = {
            'slots': {
                'original_query': 'find restaurants'
            }
        }
        
        # Should not raise exception, just return empty
        results = retriever._semantic_search(query_plan)
        
        assert results == []


class TestSemanticSearchFallback:
    """Test that semantic search is used as fallback when filter-first returns zero results."""
    
    def test_fallback_triggered_on_empty_filter_first(self, place_cache, category_matcher, ranking_engine, mock_vector_store):
        """Test that semantic search is triggered when filter-first returns zero results."""
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=mock_vector_store
        )
        
        # Query that will return zero results from filter-first
        # Use a query without category filter so semantic search can return results
        query_plan = {
            'slots': {
                'original_query': 'find amazing places with great atmosphere',
                # No categories specified - filter-first will return all places
                # But we'll mock filter-first to return empty
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_then_vector_fallback'
        }
        
        # Mock _filter_first to return empty results to trigger fallback
        original_filter_first = retriever._filter_first
        retriever._filter_first = lambda qp: []
        
        result = retriever.retrieve(query_plan)
        
        # Restore original method
        retriever._filter_first = original_filter_first
        
        # Should fall back to semantic search
        assert result.strategy_used == 'semantic_search'
        
        # Should have results from semantic search
        assert len(result.places) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
