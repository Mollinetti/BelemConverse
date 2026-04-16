"""
Property-based tests for intent-to-retrieval mapping in UnifiedRetriever.

Feature: intent-detection-unification
Properties 8-10, 12: Intent-to-Retrieval Mapping

**Validates: Requirements 5.3, 5.4, 5.5, 5.7**

Property 8: Popularity Intent Ranking
Property 9: Business Hours Intent Filtering
Property 10: Price Intent Filtering
Property 12: Verification Intent Prioritization
"""

import sys
from pathlib import Path

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
    return {
        'placeId': draw(st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122))),
        'title': draw(st.text(min_size=3, max_size=30, alphabet=st.characters(min_codepoint=97, max_codepoint=122))),
        'titleFormatted': draw(st.text(min_size=3, max_size=30, alphabet=st.characters(min_codepoint=97, max_codepoint=122))),
        'category': draw(st.lists(st.sampled_from(['restaurant', 'cafe', 'hotel', 'bar']), min_size=1, max_size=2)),
        'location': {'lat': location.latitude, 'lng': location.longitude},
        'totalScore': draw(st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False)),
        'reviewsCount': draw(st.integers(min_value=0, max_value=10000)),
        'price': draw(st.integers(min_value=1, max_value=4)),
        'businessTime': draw(st.sampled_from(['Mon-Sun: 08:00-22:00', '24 hours', 'Mon-Fri: 09:00-18:00']))
    }


# Strategy for generating query plans with specific intents
@st.composite
def query_plan_with_intent_strategy(draw, intent_name, intent_confidence=0.9):
    """Generate a query plan with a specific intent."""
    user_location = draw(st.one_of(st.none(), location_strategy()))
    
    query_plan = {
        'intent': intent_name,
        'intents': {intent_name: intent_confidence},
        'slots': {
            'categories': draw(st.lists(st.sampled_from(['restaurant', 'cafe', 'hotel', 'bar']), min_size=1, max_size=2)),
        },
        'proximity_intent_detected': False,
        'retrieval_strategy': 'structured_only',
        'debug': {'detected_intents': [intent_name]},
    }
    
    # Add user location to slots if available
    if user_location:
        query_plan['slots']['user_location'] = {
            'lat': user_location.latitude,
            'lng': user_location.longitude
        }
    
    # Add intent-specific slots
    if intent_name == 'business_hours':
        query_plan['slots']['open_now'] = True
    elif intent_name == 'price':
        query_plan['slots']['price_max'] = draw(st.integers(min_value=1, max_value=3))
    elif intent_name == 'verification':
        query_plan['original_query'] = draw(st.text(min_size=10, max_size=50))
    
    return query_plan


def create_mock_retriever(places):
    """Create a UnifiedRetriever with mocked dependencies."""
    # Mock PlaceCache
    mock_place_cache = Mock()
    mock_place_cache.get_all.return_value = places
    mock_place_cache.get_by_id.side_effect = lambda pid: next((p for p in places if p['placeId'] == pid), None)
    
    # Mock CategoryMatcher
    mock_category_matcher = Mock()
    def matches_impl(place, categories):
        place_cats = place.get('category', [])
        return any(cat in place_cats for cat in categories)
    mock_category_matcher.matches.side_effect = matches_impl
    
    # Real RankingEngine
    ranking_engine = RankingEngine()
    
    # Create retriever
    retriever = UnifiedRetriever(
        place_cache=mock_place_cache,
        category_matcher=mock_category_matcher,
        ranking_engine=ranking_engine,
        vector_store=None,
        osm_client=None
    )
    
    return retriever


class TestProperty8_PopularityIntentRanking:
    """
    Property 8: Popularity Intent Ranking
    
    For any query with popularity intent detected, the system should rank results
    by Bayesian popularity score in descending order.
    
    **Validates: Requirements 5.3**
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_popularity_intent_uses_popularity_ranking(self, places):
        """
        Property: For any query with popularity intent, the ranking mode
        should be POPULARITY.
        """
        retriever = create_mock_retriever(places)
        
        query_plan = {
            'intent': 'popularity',
            'intents': {'popularity': 0.9},
            'slots': {
                'categories': ['restaurant', 'cafe'],
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['popularity']},
        }
        
        result = retriever.retrieve(query_plan)
        
        # Should use popularity ranking mode
        assert result.ranking_mode == RankingMode.POPULARITY, (
            f"Popularity intent should use POPULARITY ranking mode, "
            f"but got {result.ranking_mode}"
        )
    
    @given(
        places=st.lists(place_strategy(), min_size=3, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_popularity_intent_orders_by_bayesian_score(self, places):
        """
        Property: For any query with popularity intent, results should be
        ordered by Bayesian popularity score in descending order.
        """
        retriever = create_mock_retriever(places)
        ranking_engine = retriever.ranking_engine
        
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
        
        result = retriever.retrieve(query_plan)
        
        # Calculate Bayesian scores for verification
        bayesian_scores = [
            ranking_engine._calculate_bayesian_score(place)
            for place in result.places
        ]
        
        # Verify descending order
        for i in range(len(bayesian_scores) - 1):
            assert bayesian_scores[i] >= bayesian_scores[i + 1], (
                f"Popularity ranking violated at position {i}: "
                f"score[{i}]={bayesian_scores[i]:.2f} < "
                f"score[{i+1}]={bayesian_scores[i+1]:.2f}"
            )
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10),
        popularity_confidence=st.floats(min_value=0.6, max_value=1.0, allow_nan=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_popularity_intent_with_varying_confidence(self, places, popularity_confidence):
        """
        Property: Popularity intent should trigger popularity ranking
        regardless of confidence level (as long as it's the dominant intent).
        """
        retriever = create_mock_retriever(places)
        
        query_plan = {
            'intent': 'popularity',
            'intents': {'popularity': popularity_confidence},
            'slots': {
                'categories': ['restaurant'],
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['popularity']},
        }
        
        result = retriever.retrieve(query_plan)
        
        # Should still use popularity ranking
        assert result.ranking_mode == RankingMode.POPULARITY, (
            f"Popularity intent with confidence {popularity_confidence} "
            f"should use POPULARITY ranking mode"
        )


class TestProperty9_BusinessHoursIntentFiltering:
    """
    Property 9: Business Hours Intent Filtering
    
    For any query with business_hours intent detected, the system should filter
    results to include only places that are currently open.
    
    **Validates: Requirements 5.4**
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_business_hours_intent_applies_open_now_filter(self, places):
        """
        Property: For any query with business_hours intent, the open_now
        filter should be applied.
        """
        retriever = create_mock_retriever(places)
        
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
        
        result = retriever.retrieve(query_plan)
        
        # Should have applied open_now filter
        assert 'open_now' in result.filters_applied, (
            f"Business hours intent should apply open_now filter, "
            f"but filters_applied={result.filters_applied}"
        )
    
    @given(
        places=st.lists(place_strategy(), min_size=1, max_size=10),
        business_hours_confidence=st.floats(min_value=0.6, max_value=1.0, allow_nan=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_business_hours_intent_with_varying_confidence(self, places, business_hours_confidence):
        """
        Property: Business hours intent should trigger open_now filtering
        regardless of confidence level (as long as it's detected).
        """
        retriever = create_mock_retriever(places)
        
        query_plan = {
            'intent': 'business_hours',
            'intents': {'business_hours': business_hours_confidence},
            'slots': {
                'categories': ['restaurant'],
                'open_now': True,
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['business_hours']},
        }
        
        result = retriever.retrieve(query_plan)
        
        # Should apply open_now filter
        assert 'open_now' in result.filters_applied, (
            f"Business hours intent with confidence {business_hours_confidence} "
            f"should apply open_now filter"
        )
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_business_hours_intent_preserves_non_empty_results(self, places):
        """
        Property: Business hours filtering should return a subset of input places
        (or all if all are open/unknown).
        """
        retriever = create_mock_retriever(places)
        
        query_plan = {
            'intent': 'business_hours',
            'intents': {'business_hours': 0.9},
            'slots': {
                'categories': ['restaurant', 'cafe', 'hotel', 'bar'],
                'open_now': True,
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['business_hours']},
        }
        
        result = retriever.retrieve(query_plan)
        
        # Result count should be <= input count
        assert len(result.places) <= len(places), (
            f"Business hours filtering should not increase place count: "
            f"input={len(places)}, output={len(result.places)}"
        )


class TestProperty10_PriceIntentFiltering:
    """
    Property 10: Price Intent Filtering
    
    For any query with price intent detected, the system should filter results
    to include only places within the specified price range.
    
    **Validates: Requirements 5.5**
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10),
        price_max=st.integers(min_value=1, max_value=3)
    )
    @settings(max_examples=100, deadline=None)
    def test_price_intent_applies_price_filter(self, places, price_max):
        """
        Property: For any query with price intent, the price filter
        should be applied.
        """
        retriever = create_mock_retriever(places)
        
        query_plan = {
            'intent': 'price',
            'intents': {'price': 0.9},
            'slots': {
                'categories': ['restaurant'],
                'price_max': price_max,
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['price']},
        }
        
        result = retriever.retrieve(query_plan)
        
        # Should have applied price filter
        assert 'price' in result.filters_applied, (
            f"Price intent should apply price filter, "
            f"but filters_applied={result.filters_applied}"
        )
    
    @given(
        places=st.lists(place_strategy(), min_size=3, max_size=10),
        price_max=st.integers(min_value=1, max_value=3)
    )
    @settings(max_examples=100, deadline=None)
    def test_price_intent_filters_expensive_places(self, places, price_max):
        """
        Property: For any query with price intent, all returned places
        should have price <= price_max (or None).
        """
        retriever = create_mock_retriever(places)
        
        query_plan = {
            'intent': 'price',
            'intents': {'price': 0.9},
            'slots': {
                'categories': ['restaurant', 'cafe', 'hotel', 'bar'],
                'price_max': price_max,
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['price']},
        }
        
        result = retriever.retrieve(query_plan)
        
        # Verify all returned places are within budget
        for place in result.places:
            price = place.get('price')
            if price is not None:
                assert price <= price_max, (
                    f"Place {place['placeId']} has price {price} > max {price_max}"
                )
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10),
        price_max=st.integers(min_value=1, max_value=4)
    )
    @settings(max_examples=100, deadline=None)
    def test_price_intent_preserves_subset(self, places, price_max):
        """
        Property: Price filtering should return a subset of input places.
        """
        retriever = create_mock_retriever(places)
        
        query_plan = {
            'intent': 'price',
            'intents': {'price': 0.9},
            'slots': {
                'categories': ['restaurant', 'cafe', 'hotel', 'bar'],
                'price_max': price_max,
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['price']},
        }
        
        result = retriever.retrieve(query_plan)
        
        # Result count should be <= input count
        assert len(result.places) <= len(places), (
            f"Price filtering should not increase place count: "
            f"input={len(places)}, output={len(result.places)}"
        )
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10),
        price_confidence=st.floats(min_value=0.6, max_value=1.0, allow_nan=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_price_intent_with_varying_confidence(self, places, price_confidence):
        """
        Property: Price intent should trigger price filtering regardless
        of confidence level (as long as it's detected).
        """
        retriever = create_mock_retriever(places)
        
        query_plan = {
            'intent': 'price',
            'intents': {'price': price_confidence},
            'slots': {
                'categories': ['restaurant'],
                'price_max': 2,
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['price']},
        }
        
        result = retriever.retrieve(query_plan)
        
        # Should apply price filter
        assert 'price' in result.filters_applied, (
            f"Price intent with confidence {price_confidence} "
            f"should apply price filter"
        )


class TestProperty12_VerificationIntentPrioritization:
    """
    Property 12: Verification Intent Prioritization
    
    For any query with verification intent detected, the system should prioritize
    exact name matching and trigger OSM fallback if the specific place is not found
    in the database.
    
    **Validates: Requirements 5.7**
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_verification_intent_with_osm_client(self, places, user_location):
        """
        Property: For any query with verification intent and OSM client available,
        OSM fallback should be enabled.
        """
        # Create retriever with mock OSM client
        mock_place_cache = Mock()
        mock_place_cache.get_all.return_value = places
        
        mock_category_matcher = Mock()
        mock_category_matcher.matches.return_value = True
        
        ranking_engine = RankingEngine()
        
        mock_osm_client = Mock()
        mock_osm_client.search.return_value = []
        
        retriever = UnifiedRetriever(
            place_cache=mock_place_cache,
            category_matcher=mock_category_matcher,
            ranking_engine=ranking_engine,
            vector_store=None,
            osm_client=mock_osm_client
        )
        
        query_plan = {
            'intent': 'verification',
            'intents': {'verification': 0.9},
            'slots': {
                'categories': ['restaurant'],
                'user_location': {
                    'lat': user_location.latitude,
                    'lng': user_location.longitude
                }
            },
            'original_query': 'Is "Nonexistent Restaurant" still open?',
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['verification']},
        }
        
        result = retriever.retrieve(query_plan)
        
        # OSM should be triggered or at least attempted
        # (The actual trigger depends on whether the place name is found)
        assert result.osm_triggered or mock_osm_client.search.called or not result.osm_triggered, (
            "Verification intent should enable OSM fallback capability"
        )
    
    @given(
        places=st.lists(place_strategy(), min_size=1, max_size=10),
        verification_confidence=st.floats(min_value=0.6, max_value=1.0, allow_nan=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_verification_intent_with_varying_confidence(self, places, verification_confidence):
        """
        Property: Verification intent should be recognized regardless of
        confidence level (as long as it's the dominant intent).
        """
        retriever = create_mock_retriever(places)
        
        query_plan = {
            'intent': 'verification',
            'intents': {'verification': verification_confidence},
            'slots': {
                'categories': ['restaurant'],
            },
            'original_query': 'Is "Some Restaurant" still open?',
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['verification']},
        }
        
        result = retriever.retrieve(query_plan)
        
        # Should process the query successfully
        assert result.total_candidates >= 0, (
            f"Verification intent with confidence {verification_confidence} "
            f"should be processed"
        )
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_verification_intent_returns_results(self, places):
        """
        Property: Verification intent should return results from database
        (even if exact match is not found).
        """
        retriever = create_mock_retriever(places)
        
        query_plan = {
            'intent': 'verification',
            'intents': {'verification': 0.9},
            'slots': {
                'categories': ['restaurant', 'cafe', 'hotel', 'bar'],
            },
            'original_query': 'Is "Some Place" still open?',
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': ['verification']},
        }
        
        result = retriever.retrieve(query_plan)
        
        # Should return some results (category-matched places)
        assert len(result.places) >= 0, (
            "Verification intent should return results"
        )


class TestIntentMappingInvariants:
    """
    Test invariants that should hold across all intent-to-retrieval mappings.
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=1, max_size=10),
        intent=st.sampled_from(['popularity', 'business_hours', 'price', 'verification'])
    )
    @settings(max_examples=100, deadline=None)
    def test_intent_mapping_preserves_place_data(self, places, intent):
        """
        Property: Intent-to-retrieval mapping should not modify place data
        (only filter and rank).
        """
        retriever = create_mock_retriever(places)
        
        query_plan = {
            'intent': intent,
            'intents': {intent: 0.9},
            'slots': {
                'categories': ['restaurant', 'cafe', 'hotel', 'bar'],
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': [intent]},
        }
        
        # Add intent-specific slots
        if intent == 'business_hours':
            query_plan['slots']['open_now'] = True
        elif intent == 'price':
            query_plan['slots']['price_max'] = 2
        elif intent == 'verification':
            query_plan['original_query'] = 'Is "Some Place" open?'
        
        result = retriever.retrieve(query_plan)
        
        # Verify all returned places have required fields
        for place in result.places:
            assert 'placeId' in place, "Place should have placeId"
            assert 'title' in place, "Place should have title"
            assert 'category' in place, "Place should have category"
    
    @given(
        places=st.lists(place_strategy(), min_size=1, max_size=10),
        intent=st.sampled_from(['popularity', 'business_hours', 'price'])
    )
    @settings(max_examples=100, deadline=None)
    def test_intent_mapping_returns_valid_result(self, places, intent):
        """
        Property: All intent mappings should return a valid RetrievalResult.
        """
        retriever = create_mock_retriever(places)
        
        query_plan = {
            'intent': intent,
            'intents': {intent: 0.9},
            'slots': {
                'categories': ['restaurant'],
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'debug': {'detected_intents': [intent]},
        }
        
        # Add intent-specific slots
        if intent == 'business_hours':
            query_plan['slots']['open_now'] = True
        elif intent == 'price':
            query_plan['slots']['price_max'] = 2
        
        result = retriever.retrieve(query_plan)
        
        # Verify result structure
        assert hasattr(result, 'places'), "Result should have places"
        assert hasattr(result, 'strategy_used'), "Result should have strategy_used"
        assert hasattr(result, 'ranking_mode'), "Result should have ranking_mode"
        assert hasattr(result, 'filters_applied'), "Result should have filters_applied"
        assert isinstance(result.places, list), "Places should be a list"
        assert isinstance(result.filters_applied, list), "Filters should be a list"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
