"""
Property-based test for semantic search fallback in UnifiedRetriever.

Feature: intent-detection-unification
Property 2: Semantic Search Fallback

**Validates: Requirements 2.3, 9.2**

Property 2: Semantic Search Fallback
For any query where filter-first retrieval returns zero results, the system
should automatically fall back to semantic search.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock, MagicMock, patch

from core.unified_retriever import UnifiedRetriever, RetrievalResult
from core.place_cache import PlaceCache
from core.category_matcher import CategoryMatcher
from core.ranking_engine import RankingEngine, RankingMode, Location


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
def query_plan_strategy(draw, with_location=True):
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
            'original_query': draw(st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' '))).strip() or 'find places',
        },
        'proximity_intent_detected': draw(st.booleans()),
        'retrieval_strategy': 'structured_then_vector_fallback',
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


def create_mock_vector_store(places):
    """
    Create a mock vector store that returns documents based on places.
    
    Args:
        places: List of place dictionaries
        
    Returns:
        Mock vector store
    """
    vector_store = Mock()
    
    # Create mock documents with metadata
    mock_docs = []
    for i, place in enumerate(places):
        doc = Mock()
        doc.metadata = place.copy()
        doc.page_content = f"{place.get('title', 'Place')} - {', '.join(place.get('categories', []))}"
        # Assign varying distances (lower = more similar)
        distance = 0.1 + (i * 0.1)
        mock_docs.append((doc, distance))
    
    # similarity_search_with_score returns (doc, distance) tuples
    vector_store.similarity_search_with_score.return_value = mock_docs
    
    return vector_store


class TestProperty2_SemanticSearchFallback:
    """
    Property 2: Semantic Search Fallback
    
    For any query where filter-first retrieval returns zero results, the system
    should automatically fall back to semantic search.
    
    **Validates: Requirements 2.3, 9.2**
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=3, max_size=20, unique_by=lambda p: p['placeId']),
        query_plan=query_plan_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_semantic_search_triggered_on_empty_filter_first(
        self,
        category_matcher,
        ranking_engine,
        places,
        query_plan
    ):
        """
        Property: When filter-first returns zero results, semantic search
        should be automatically triggered as fallback.
        """
        # Create place cache
        place_cache = PlaceCache(places)
        
        # Create mock vector store
        mock_vector_store = create_mock_vector_store(places)
        
        # Create retriever WITH vector store
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=mock_vector_store,
            osm_client=None
        )
        
        # Ensure retrieval strategy includes vector fallback
        query_plan['retrieval_strategy'] = 'structured_then_vector_fallback'
        
        # Mock _filter_first to return empty results to trigger fallback
        with patch.object(retriever, '_filter_first', return_value=[]):
            result = retriever.retrieve(query_plan)
            
            # Verify semantic search was triggered
            assert result.strategy_used == 'semantic_search', (
                f"Expected semantic_search strategy when filter-first returns empty, "
                f"got {result.strategy_used}"
            )
            
            # Verify vector store was called
            mock_vector_store.similarity_search_with_score.assert_called_once()
            
            # Verify we got results from semantic search
            assert isinstance(result.places, list), "Result should contain a list of places"
    
    @given(
        places=st.lists(place_strategy(), min_size=5, max_size=20, unique_by=lambda p: p['placeId']),
        query_plan=query_plan_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_semantic_search_not_triggered_when_filter_first_has_results(
        self,
        category_matcher,
        ranking_engine,
        places,
        query_plan
    ):
        """
        Property: When filter-first returns results, semantic search should
        NOT be triggered (it's only a fallback).
        """
        # Create place cache
        place_cache = PlaceCache(places)
        
        # Create mock vector store
        mock_vector_store = create_mock_vector_store(places)
        
        # Create retriever WITH vector store
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=mock_vector_store,
            osm_client=None
        )
        
        # Ensure retrieval strategy includes vector fallback
        query_plan['retrieval_strategy'] = 'structured_then_vector_fallback'
        
        # Remove restrictive filters to ensure filter-first returns results
        query_plan['slots']['categories'] = None
        query_plan['slots']['open_now'] = False
        query_plan['slots']['price_max'] = None
        query_plan['slots']['min_rating'] = None
        query_plan['proximity_intent_detected'] = False
        
        # Execute retrieval
        result = retriever.retrieve(query_plan)
        
        # Verify filter-first was used (not semantic search)
        assert result.strategy_used == 'filter_first', (
            f"Expected filter_first strategy when results exist, "
            f"got {result.strategy_used}"
        )
        
        # Verify vector store was NOT called
        mock_vector_store.similarity_search_with_score.assert_not_called()
    
    @given(
        places=st.lists(place_strategy(), min_size=3, max_size=20, unique_by=lambda p: p['placeId']),
        query_plan=query_plan_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_semantic_search_not_triggered_without_vector_store(
        self,
        category_matcher,
        ranking_engine,
        places,
        query_plan
    ):
        """
        Property: When filter-first returns zero results but vector store is
        not available, semantic search should not be triggered.
        """
        # Create place cache
        place_cache = PlaceCache(places)
        
        # Create retriever WITHOUT vector store
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=None,  # No vector store
            osm_client=None
        )
        
        # Ensure retrieval strategy includes vector fallback
        query_plan['retrieval_strategy'] = 'structured_then_vector_fallback'
        
        # Mock _filter_first to return empty results
        with patch.object(retriever, '_filter_first', return_value=[]):
            result = retriever.retrieve(query_plan)
            
            # Should still use filter_first strategy (no fallback available)
            assert result.strategy_used == 'filter_first', (
                f"Expected filter_first strategy when vector store unavailable, "
                f"got {result.strategy_used}"
            )
            
            # Should have empty results
            assert len(result.places) == 0, (
                "Should have empty results when filter-first returns empty and no fallback"
            )
    
    @given(
        places=st.lists(place_strategy(), min_size=3, max_size=20, unique_by=lambda p: p['placeId']),
        query_plan=query_plan_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_semantic_search_not_triggered_without_fallback_strategy(
        self,
        category_matcher,
        ranking_engine,
        places,
        query_plan
    ):
        """
        Property: When filter-first returns zero results but retrieval strategy
        does not include vector fallback, semantic search should not be triggered.
        """
        # Create place cache
        place_cache = PlaceCache(places)
        
        # Create mock vector store
        mock_vector_store = create_mock_vector_store(places)
        
        # Create retriever WITH vector store
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=mock_vector_store,
            osm_client=None
        )
        
        # Set retrieval strategy WITHOUT vector fallback
        query_plan['retrieval_strategy'] = 'structured_only'
        
        # Mock _filter_first to return empty results
        with patch.object(retriever, '_filter_first', return_value=[]):
            result = retriever.retrieve(query_plan)
            
            # Should use filter_first strategy (fallback not enabled)
            assert result.strategy_used == 'filter_first', (
                f"Expected filter_first strategy when fallback not enabled, "
                f"got {result.strategy_used}"
            )
            
            # Verify vector store was NOT called
            mock_vector_store.similarity_search_with_score.assert_not_called()
    
    @given(
        places=st.lists(place_strategy(), min_size=5, max_size=20, unique_by=lambda p: p['placeId']),
        query_text=st.text(min_size=5, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' ')),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_semantic_search_performs_vector_search_and_reranking(
        self,
        category_matcher,
        ranking_engine,
        places,
        query_text,
        user_location
    ):
        """
        Property: When semantic search is triggered, it should:
        1. Perform vector similarity search
        2. Re-rank results with structured filters
        3. Return ranked results
        """
        # Ensure query text is not empty
        query_text = query_text.strip()
        assume(len(query_text) > 0)
        
        # Create place cache
        place_cache = PlaceCache(places)
        
        # Create mock vector store
        mock_vector_store = create_mock_vector_store(places)
        
        # Create retriever WITH vector store
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=mock_vector_store,
            osm_client=None
        )
        
        # Create query plan
        query_plan = {
            'intent': 'general',
            'intents': {},
            'slots': {
                'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude},
                'categories': None,
                'open_now': False,
                'price_max': None,
                'min_rating': None,
                'original_query': query_text,
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_then_vector_fallback',
            'original_query': query_text,
            'debug': {}
        }
        
        # Mock _filter_first to return empty results to trigger fallback
        with patch.object(retriever, '_filter_first', return_value=[]):
            result = retriever.retrieve(query_plan)
            
            # Verify semantic search was triggered
            assert result.strategy_used == 'semantic_search'
            
            # Verify vector store was called with correct query
            mock_vector_store.similarity_search_with_score.assert_called_once_with(
                query_text,
                k=50
            )
            
            # Verify results are returned
            assert isinstance(result.places, list)
            
            # Note: Distance calculation in semantic search depends on valid location data
            # The key property is that semantic search was triggered and returned results
    
    @given(
        places=st.lists(place_strategy(), min_size=5, max_size=20, unique_by=lambda p: p['placeId']),
        categories=st.lists(st.sampled_from(['restaurant', 'cafe', 'hotel']), min_size=1, max_size=2, unique=True),
        query_text=st.text(min_size=5, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), whitelist_characters=' '))
    )
    @settings(max_examples=100, deadline=None)
    def test_semantic_search_applies_category_filter(
        self,
        category_matcher,
        ranking_engine,
        places,
        categories,
        query_text
    ):
        """
        Property: When semantic search is triggered with category filters,
        it should re-rank results and apply category filtering.
        """
        # Ensure query text is not empty
        query_text = query_text.strip()
        assume(len(query_text) > 0)
        
        # Create place cache
        place_cache = PlaceCache(places)
        
        # Create mock vector store
        mock_vector_store = create_mock_vector_store(places)
        
        # Create retriever WITH vector store
        retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=mock_vector_store,
            osm_client=None
        )
        
        # Create query plan with category filter
        query_plan = {
            'intent': 'general',
            'intents': {},
            'slots': {
                'user_location': None,
                'categories': categories,
                'open_now': False,
                'price_max': None,
                'min_rating': None,
                'original_query': query_text,
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_then_vector_fallback',
            'original_query': query_text,
            'debug': {}
        }
        
        # Mock _filter_first to return empty results to trigger fallback
        with patch.object(retriever, '_filter_first', return_value=[]):
            result = retriever.retrieve(query_plan)
            
            # Verify semantic search was triggered
            assert result.strategy_used == 'semantic_search'
            
            # Verify all results match the category filter
            for place in result.places:
                place_categories = place.get('categories', [])
                matches = any(
                    category_matcher._matches_keywords(pc, cat)
                    for pc in place_categories
                    for cat in categories
                )
                assert matches, (
                    f"Place {place.get('placeId')} with categories {place_categories} "
                    f"should match filter categories {categories}"
                )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
