"""
Property-based tests for UnifiedRetriever multi-ranking support.

Feature: intent-detection-unification
Property 5: Multi-Ranking Support

**Validates: Requirements 4.3**

Property 5: Multi-Ranking Support
For any ranking mode (distance, rating, popularity, best_match), the unified retriever
should correctly order results according to that mode's algorithm.
"""

import sys
from pathlib import Path
from typing import Optional

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import pytest
from hypothesis import given, strategies as st, settings, assume

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
        'title': draw(st.text(min_size=1, max_size=50, alphabet=st.characters(min_codepoint=97, max_codepoint=122))),
        'category': [draw(st.sampled_from(['restaurant', 'cafe', 'hotel', 'bar']))],
        'location': {'lat': location.latitude, 'lng': location.longitude},
        'totalScore': draw(st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False)),
        'reviewsCount': draw(st.integers(min_value=0, max_value=10000))
    }


# Strategy for generating query plans with different ranking modes
@st.composite
def query_plan_strategy(draw, ranking_mode: str, user_location: Optional[Location] = None):
    """Generate a query plan with specified ranking mode."""
    # Map ranking modes to sort preferences
    sort_preference_map = {
        RankingMode.DISTANCE: 'distance',
        RankingMode.RATING: 'rating',
        RankingMode.POPULARITY: 'popularity',
        RankingMode.BEST_MATCH: 'best_match'
    }
    
    return {
        'slots': {
            'sort_preference': sort_preference_map.get(ranking_mode, 'best_match'),
            'user_location': {
                'lat': user_location.latitude,
                'lng': user_location.longitude
            } if user_location else None
        },
        'proximity_intent_detected': False,
        'retrieval_strategy': 'structured_only',
        'intents': {},
        'debug': {}
    }


class TestProperty5_MultiRankingSupport:
    """
    Property 5: Multi-Ranking Support
    
    For any ranking mode (distance, rating, popularity, best_match), the unified retriever
    should correctly order results according to that mode's algorithm.
    
    **Validates: Requirements 4.3**
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_distance_ranking_mode_applied(self, places, user_location):
        """
        Property: When distance ranking mode is requested, UnifiedRetriever
        should return results sorted by distance ascending.
        """
        # Setup
        place_cache = PlaceCache(places)
        
        # Mock category matcher
        class MockIntentClassifier:
            category_keywords = {'restaurant': ['restaurant'], 'cafe': ['cafe'], 'hotel': ['hotel'], 'bar': ['bar']}
        category_matcher = CategoryMatcher(MockIntentClassifier())
        
        ranking_engine = RankingEngine()
        retriever = UnifiedRetriever(place_cache, category_matcher, ranking_engine)
        
        # Create query plan requesting distance ranking
        query_plan = {
            'slots': {
                'sort_preference': 'distance',
                'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude}
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'intents': {},
            'debug': {}
        }
        
        # Execute
        result = retriever.retrieve(query_plan)
        
        # Verify
        assert isinstance(result, RetrievalResult)
        assert result.ranking_mode == RankingMode.DISTANCE
        
        # Verify results are sorted by distance ascending
        if len(result.places) >= 2:
            for i in range(len(result.places) - 1):
                place1 = result.places[i]
                place2 = result.places[i + 1]
                
                # Calculate distances
                loc1 = Location(place1['location']['lat'], place1['location']['lng'])
                loc2 = Location(place2['location']['lat'], place2['location']['lng'])
                
                dist1 = user_location.distance_to(loc1)
                dist2 = user_location.distance_to(loc2)
                
                assert dist1 <= dist2, (
                    f"Distance ranking violated: place[{i}] distance={dist1:.2f}km > "
                    f"place[{i+1}] distance={dist2:.2f}km"
                )
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_rating_ranking_mode_applied(self, places):
        """
        Property: When rating ranking mode is requested, UnifiedRetriever
        should return results sorted by rating descending.
        """
        # Setup
        place_cache = PlaceCache(places)
        
        class MockIntentClassifier:
            category_keywords = {'restaurant': ['restaurant'], 'cafe': ['cafe'], 'hotel': ['hotel'], 'bar': ['bar']}
        category_matcher = CategoryMatcher(MockIntentClassifier())
        
        ranking_engine = RankingEngine()
        retriever = UnifiedRetriever(place_cache, category_matcher, ranking_engine)
        
        # Create query plan requesting rating ranking
        query_plan = {
            'slots': {
                'sort_preference': 'rating'
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'intents': {},
            'debug': {}
        }
        
        # Execute
        result = retriever.retrieve(query_plan)
        
        # Verify
        assert isinstance(result, RetrievalResult)
        assert result.ranking_mode == RankingMode.RATING
        
        # Verify results are sorted by rating descending
        if len(result.places) >= 2:
            for i in range(len(result.places) - 1):
                rating1 = result.places[i]['totalScore']
                rating2 = result.places[i + 1]['totalScore']
                
                assert rating1 >= rating2, (
                    f"Rating ranking violated: place[{i}] rating={rating1:.2f} < "
                    f"place[{i+1}] rating={rating2:.2f}"
                )
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_popularity_ranking_mode_applied(self, places):
        """
        Property: When popularity ranking mode is requested, UnifiedRetriever
        should return results sorted by Bayesian popularity score descending.
        """
        # Setup
        place_cache = PlaceCache(places)
        
        class MockIntentClassifier:
            category_keywords = {'restaurant': ['restaurant'], 'cafe': ['cafe'], 'hotel': ['hotel'], 'bar': ['bar']}
        category_matcher = CategoryMatcher(MockIntentClassifier())
        
        ranking_engine = RankingEngine()
        retriever = UnifiedRetriever(place_cache, category_matcher, ranking_engine)
        
        # Create query plan requesting popularity ranking
        query_plan = {
            'slots': {
                'sort_preference': 'popularity'
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'intents': {},
            'debug': {}
        }
        
        # Execute
        result = retriever.retrieve(query_plan)
        
        # Verify
        assert isinstance(result, RetrievalResult)
        assert result.ranking_mode == RankingMode.POPULARITY
        
        # Verify results are sorted by Bayesian score descending
        if len(result.places) >= 2:
            for i in range(len(result.places) - 1):
                place1 = result.places[i]
                place2 = result.places[i + 1]
                
                # Calculate Bayesian scores
                score1 = ranking_engine._calculate_bayesian_score(place1)
                score2 = ranking_engine._calculate_bayesian_score(place2)
                
                assert score1 >= score2, (
                    f"Popularity ranking violated: place[{i}] score={score1:.2f} < "
                    f"place[{i+1}] score={score2:.2f}"
                )
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_best_match_ranking_mode_applied(self, places, user_location):
        """
        Property: When best_match ranking mode is requested, UnifiedRetriever
        should return results sorted by composite score (45% rating, 35% popularity, 20% proximity).
        """
        # Setup
        place_cache = PlaceCache(places)
        
        class MockIntentClassifier:
            category_keywords = {'restaurant': ['restaurant'], 'cafe': ['cafe'], 'hotel': ['hotel'], 'bar': ['bar']}
        category_matcher = CategoryMatcher(MockIntentClassifier())
        
        ranking_engine = RankingEngine()
        retriever = UnifiedRetriever(place_cache, category_matcher, ranking_engine)
        
        # Create query plan requesting best_match ranking
        query_plan = {
            'slots': {
                'sort_preference': 'best_match',
                'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude}
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'intents': {},
            'debug': {}
        }
        
        # Execute
        result = retriever.retrieve(query_plan)
        
        # Verify
        assert isinstance(result, RetrievalResult)
        assert result.ranking_mode == RankingMode.BEST_MATCH
        
        # Verify results are sorted by composite score descending
        if len(result.places) >= 2:
            # Calculate max distance for normalization
            max_distance = 0.0
            for place in result.places:
                place_loc = Location(place['location']['lat'], place['location']['lng'])
                distance = user_location.distance_to(place_loc)
                max_distance = max(max_distance, distance)
            
            if max_distance == 0.0:
                max_distance = 1.0
            
            for i in range(len(result.places) - 1):
                place1 = result.places[i]
                place2 = result.places[i + 1]
                
                # Calculate composite scores manually
                # Rating component (45%)
                rating_score1 = (place1['totalScore'] / 5.0) * 0.45
                rating_score2 = (place2['totalScore'] / 5.0) * 0.45
                
                # Popularity component (35%)
                bayesian_score1 = ranking_engine._calculate_bayesian_score(place1)
                bayesian_score2 = ranking_engine._calculate_bayesian_score(place2)
                popularity_score1 = (bayesian_score1 / 5.0) * 0.35
                popularity_score2 = (bayesian_score2 / 5.0) * 0.35
                
                # Proximity component (20%)
                place_loc1 = Location(place1['location']['lat'], place1['location']['lng'])
                place_loc2 = Location(place2['location']['lat'], place2['location']['lng'])
                distance1 = user_location.distance_to(place_loc1)
                distance2 = user_location.distance_to(place_loc2)
                proximity_score1 = (1.0 - (distance1 / max_distance)) * 0.20
                proximity_score2 = (1.0 - (distance2 / max_distance)) * 0.20
                
                composite_score1 = rating_score1 + popularity_score1 + proximity_score1
                composite_score2 = rating_score2 + popularity_score2 + proximity_score2
                
                # Allow small tolerance for floating point comparison
                assert composite_score1 >= composite_score2 - 1e-9, (
                    f"Best match ranking violated: place[{i}] score={composite_score1:.4f} < "
                    f"place[{i+1}] score={composite_score2:.4f}"
                )
    
    @given(
        places=st.lists(place_strategy(), min_size=1, max_size=10),
        ranking_mode=st.sampled_from([
            RankingMode.DISTANCE,
            RankingMode.RATING,
            RankingMode.POPULARITY,
            RankingMode.BEST_MATCH
        ]),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_all_ranking_modes_preserve_places(self, places, ranking_mode, user_location):
        """
        Property: All ranking modes should preserve all input places (no loss or duplication).
        """
        # Setup
        place_cache = PlaceCache(places)
        
        class MockIntentClassifier:
            category_keywords = {'restaurant': ['restaurant'], 'cafe': ['cafe'], 'hotel': ['hotel'], 'bar': ['bar']}
        category_matcher = CategoryMatcher(MockIntentClassifier())
        
        ranking_engine = RankingEngine()
        retriever = UnifiedRetriever(place_cache, category_matcher, ranking_engine)
        
        # Map ranking mode to sort preference
        sort_preference_map = {
            RankingMode.DISTANCE: 'distance',
            RankingMode.RATING: 'rating',
            RankingMode.POPULARITY: 'popularity',
            RankingMode.BEST_MATCH: 'best_match'
        }
        
        # Create query plan
        query_plan = {
            'slots': {
                'sort_preference': sort_preference_map[ranking_mode],
                'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude}
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'intents': {},
            'debug': {}
        }
        
        # Execute
        result = retriever.retrieve(query_plan)
        
        # Verify
        assert len(result.places) == len(places), (
            f"Ranking mode {ranking_mode} should preserve all places: "
            f"expected {len(places)}, got {len(result.places)}"
        )
        
        # All original places present
        original_ids = {p['placeId'] for p in places}
        ranked_ids = {p['placeId'] for p in result.places}
        assert original_ids == ranked_ids, (
            f"Ranking mode {ranking_mode} should not lose or duplicate places"
        )
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_ranking_mode_deterministic(self, places, user_location):
        """
        Property: Ranking should be deterministic (same input produces same output).
        """
        # Setup
        place_cache = PlaceCache(places)
        
        class MockIntentClassifier:
            category_keywords = {'restaurant': ['restaurant'], 'cafe': ['cafe'], 'hotel': ['hotel'], 'bar': ['bar']}
        category_matcher = CategoryMatcher(MockIntentClassifier())
        
        ranking_engine = RankingEngine()
        retriever = UnifiedRetriever(place_cache, category_matcher, ranking_engine)
        
        # Create query plan
        query_plan = {
            'slots': {
                'sort_preference': 'rating',
                'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude}
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'intents': {},
            'debug': {}
        }
        
        # Execute twice
        result1 = retriever.retrieve(query_plan)
        result2 = retriever.retrieve(query_plan)
        
        # Verify
        ids1 = [p['placeId'] for p in result1.places]
        ids2 = [p['placeId'] for p in result2.places]
        
        assert ids1 == ids2, "Ranking should be deterministic"
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_intent_based_ranking_selection(self, places, user_location):
        """
        Property: UnifiedRetriever should select appropriate ranking mode based on detected intents.
        """
        # Setup
        place_cache = PlaceCache(places)
        
        class MockIntentClassifier:
            category_keywords = {'restaurant': ['restaurant'], 'cafe': ['cafe'], 'hotel': ['hotel'], 'bar': ['bar']}
        category_matcher = CategoryMatcher(MockIntentClassifier())
        
        ranking_engine = RankingEngine()
        retriever = UnifiedRetriever(place_cache, category_matcher, ranking_engine)
        
        # Test 1: Location intent should trigger distance ranking
        query_plan_location = {
            'slots': {
                'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude}
            },
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'intents': {},
            'debug': {'detected_intents': ['location']}
        }
        
        result_location = retriever.retrieve(query_plan_location)
        assert result_location.ranking_mode == RankingMode.DISTANCE, (
            "Location intent should trigger distance ranking"
        )
        
        # Test 2: Popularity intent should trigger popularity ranking
        query_plan_popularity = {
            'slots': {},
            'proximity_intent_detected': False,
            'retrieval_strategy': 'structured_only',
            'intents': {},
            'debug': {'detected_intents': ['popularity']}
        }
        
        result_popularity = retriever.retrieve(query_plan_popularity)
        assert result_popularity.ranking_mode == RankingMode.POPULARITY, (
            "Popularity intent should trigger popularity ranking"
        )


class TestRankingModeEdgeCases:
    """Test edge cases for ranking mode support."""
    
    def test_empty_places_all_modes(self):
        """
        Property: All ranking modes should handle empty place lists gracefully.
        """
        # Setup
        place_cache = PlaceCache([])
        
        class MockIntentClassifier:
            category_keywords = {'restaurant': ['restaurant']}
        category_matcher = CategoryMatcher(MockIntentClassifier())
        
        ranking_engine = RankingEngine()
        retriever = UnifiedRetriever(place_cache, category_matcher, ranking_engine)
        
        user_location = Location(latitude=0.0, longitude=0.0)
        
        # Test all ranking modes
        for mode in [RankingMode.DISTANCE, RankingMode.RATING, RankingMode.POPULARITY, RankingMode.BEST_MATCH]:
            sort_preference_map = {
                RankingMode.DISTANCE: 'distance',
                RankingMode.RATING: 'rating',
                RankingMode.POPULARITY: 'popularity',
                RankingMode.BEST_MATCH: 'best_match'
            }
            
            query_plan = {
                'slots': {
                    'sort_preference': sort_preference_map[mode],
                    'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude}
                },
                'proximity_intent_detected': False,
                'retrieval_strategy': 'structured_only',
                'intents': {},
                'debug': {}
            }
            
            result = retriever.retrieve(query_plan)
            
            assert result.places == [], f"Ranking mode {mode} should return empty list for empty input"
            assert result.ranking_mode == mode
    
    def test_single_place_all_modes(self):
        """
        Property: All ranking modes should handle single place gracefully.
        """
        # Setup
        single_place = [{
            'placeId': 'test1',
            'title': 'Test Place',
            'category': ['restaurant'],
            'location': {'lat': 1.0, 'lng': 1.0},
            'totalScore': 4.5,
            'reviewsCount': 100
        }]
        
        place_cache = PlaceCache(single_place)
        
        class MockIntentClassifier:
            category_keywords = {'restaurant': ['restaurant']}
        category_matcher = CategoryMatcher(MockIntentClassifier())
        
        ranking_engine = RankingEngine()
        retriever = UnifiedRetriever(place_cache, category_matcher, ranking_engine)
        
        user_location = Location(latitude=0.0, longitude=0.0)
        
        # Test all ranking modes
        for mode in [RankingMode.DISTANCE, RankingMode.RATING, RankingMode.POPULARITY, RankingMode.BEST_MATCH]:
            sort_preference_map = {
                RankingMode.DISTANCE: 'distance',
                RankingMode.RATING: 'rating',
                RankingMode.POPULARITY: 'popularity',
                RankingMode.BEST_MATCH: 'best_match'
            }
            
            query_plan = {
                'slots': {
                    'sort_preference': sort_preference_map[mode],
                    'user_location': {'lat': user_location.latitude, 'lng': user_location.longitude}
                },
                'proximity_intent_detected': False,
                'retrieval_strategy': 'structured_only',
                'intents': {},
                'debug': {}
            }
            
            result = retriever.retrieve(query_plan)
            
            assert len(result.places) == 1, f"Ranking mode {mode} should return single place"
            assert result.places[0]['placeId'] == 'test1'
            assert result.ranking_mode == mode


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
