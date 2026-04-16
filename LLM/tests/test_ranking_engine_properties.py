"""
Property-based tests for RankingEngine module.

Feature: intent-detection-unification
Properties 16-19: Ranking Correctness

**Validates: Requirements 10.3, 10.4, 10.5, 10.6**

Property 16: Distance Ranking Correctness
Property 17: Rating Ranking Correctness
Property 18: Popularity Ranking Correctness
Property 19: Best Match Ranking Correctness
"""

import sys
from pathlib import Path
import importlib.util

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from hypothesis import given, strategies as st, settings, assume

# Import modules directly without triggering __init__.py
def import_module_from_file(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# Import ranking engine
ranking_engine_path = project_root / "src" / "core" / "ranking_engine.py"
ranking_engine_module = import_module_from_file("ranking_engine", ranking_engine_path)
RankingEngine = ranking_engine_module.RankingEngine
RankingMode = ranking_engine_module.RankingMode
Location = ranking_engine_module.Location


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
        'location': {'lat': location.latitude, 'lng': location.longitude},
        'totalScore': draw(st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False)),
        'reviewsCount': draw(st.integers(min_value=0, max_value=10000))
    }


class TestProperty16_DistanceRankingCorrectness:
    """
    Property 16: Distance Ranking Correctness
    
    For any list of places ranked by distance mode, the results should be sorted
    by distance ascending with rating as tiebreaker for equal distances.
    
    **Validates: Requirements 10.3**
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_distance_ranking_ascending_order(self, places, user_location):
        """
        Property: For any list of places, distance ranking should produce
        results in ascending distance order.
        """
        ranking_engine = RankingEngine()
        
        # Rank places by distance
        ranked = ranking_engine.rank(places, RankingMode.DISTANCE, user_location)
        
        # Calculate distances for verification
        distances = []
        for place in ranked:
            place_loc = Location(
                latitude=place['location']['lat'],
                longitude=place['location']['lng']
            )
            distance = user_location.distance_to(place_loc)
            distances.append(distance)
        
        # Verify ascending order
        for i in range(len(distances) - 1):
            assert distances[i] <= distances[i + 1], (
                f"Distance ranking violated: distance[{i}]={distances[i]:.2f} > "
                f"distance[{i+1}]={distances[i+1]:.2f}"
            )
    
    @given(
        user_location=location_strategy(),
        rating1=st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        rating2=st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        reviews1=st.integers(min_value=0, max_value=1000),
        reviews2=st.integers(min_value=0, max_value=1000)
    )
    @settings(max_examples=100, deadline=None)
    def test_distance_ranking_rating_tiebreaker(
        self, user_location, rating1, rating2, reviews1, reviews2
    ):
        """
        Property: For places at the same distance, higher rated places should
        come first (rating as tiebreaker).
        """
        ranking_engine = RankingEngine()
        
        # Ensure ratings are different for meaningful test
        assume(abs(rating1 - rating2) > 0.1)
        
        # Create two places at the same location (same distance)
        places = [
            {
                'placeId': 'place1',
                'location': {'lat': user_location.latitude + 0.01, 'lng': user_location.longitude + 0.01},
                'totalScore': rating1,
                'reviewsCount': reviews1
            },
            {
                'placeId': 'place2',
                'location': {'lat': user_location.latitude + 0.01, 'lng': user_location.longitude + 0.01},
                'totalScore': rating2,
                'reviewsCount': reviews2
            }
        ]
        
        ranked = ranking_engine.rank(places, RankingMode.DISTANCE, user_location)
        
        # Higher rated place should come first when distances are equal
        if rating1 > rating2:
            assert ranked[0]['placeId'] == 'place1', (
                f"Higher rated place (rating={rating1}) should come before "
                f"lower rated place (rating={rating2}) at same distance"
            )
        else:
            assert ranked[0]['placeId'] == 'place2', (
                f"Higher rated place (rating={rating2}) should come before "
                f"lower rated place (rating={rating1}) at same distance"
            )
    
    @given(
        places=st.lists(place_strategy(), min_size=1, max_size=10),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_distance_ranking_preserves_all_places(self, places, user_location):
        """
        Property: Distance ranking should preserve all input places (no loss or duplication).
        """
        ranking_engine = RankingEngine()
        
        ranked = ranking_engine.rank(places, RankingMode.DISTANCE, user_location)
        
        # Same number of places
        assert len(ranked) == len(places), "Ranking should preserve all places"
        
        # All original places present
        original_ids = {p['placeId'] for p in places}
        ranked_ids = {p['placeId'] for p in ranked}
        assert original_ids == ranked_ids, "Ranking should not lose or duplicate places"


class TestProperty17_RatingRankingCorrectness:
    """
    Property 17: Rating Ranking Correctness
    
    For any list of places ranked by rating mode, the results should be sorted
    by totalScore descending with reviewsCount as tiebreaker for equal ratings.
    
    **Validates: Requirements 10.4**
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_rating_ranking_descending_order(self, places):
        """
        Property: For any list of places, rating ranking should produce
        results in descending rating order.
        """
        ranking_engine = RankingEngine()
        
        # Rank places by rating
        ranked = ranking_engine.rank(places, RankingMode.RATING, None)
        
        # Extract ratings
        ratings = [place['totalScore'] for place in ranked]
        
        # Verify descending order
        for i in range(len(ratings) - 1):
            assert ratings[i] >= ratings[i + 1], (
                f"Rating ranking violated: rating[{i}]={ratings[i]:.2f} < "
                f"rating[{i+1}]={ratings[i+1]:.2f}"
            )
    
    @given(
        rating=st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        reviews1=st.integers(min_value=0, max_value=1000),
        reviews2=st.integers(min_value=0, max_value=1000)
    )
    @settings(max_examples=100, deadline=None)
    def test_rating_ranking_review_count_tiebreaker(
        self, rating, reviews1, reviews2
    ):
        """
        Property: For places with the same rating, places with more reviews
        should come first (review count as tiebreaker).
        """
        ranking_engine = RankingEngine()
        
        # Ensure review counts are different for meaningful test
        assume(abs(reviews1 - reviews2) > 5)
        
        # Create two places with same rating but different review counts
        places = [
            {
                'placeId': 'place1',
                'location': {'lat': 0.0, 'lng': 0.0},
                'totalScore': rating,
                'reviewsCount': reviews1
            },
            {
                'placeId': 'place2',
                'location': {'lat': 0.0, 'lng': 0.0},
                'totalScore': rating,
                'reviewsCount': reviews2
            }
        ]
        
        ranked = ranking_engine.rank(places, RankingMode.RATING, None)
        
        # Place with more reviews should come first when ratings are equal
        if reviews1 > reviews2:
            assert ranked[0]['placeId'] == 'place1', (
                f"Place with more reviews ({reviews1}) should come before "
                f"place with fewer reviews ({reviews2}) at same rating"
            )
        else:
            assert ranked[0]['placeId'] == 'place2', (
                f"Place with more reviews ({reviews2}) should come before "
                f"place with fewer reviews ({reviews1}) at same rating"
            )
    
    @given(
        places=st.lists(place_strategy(), min_size=1, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_rating_ranking_preserves_all_places(self, places):
        """
        Property: Rating ranking should preserve all input places (no loss or duplication).
        """
        ranking_engine = RankingEngine()
        
        ranked = ranking_engine.rank(places, RankingMode.RATING, None)
        
        # Same number of places
        assert len(ranked) == len(places), "Ranking should preserve all places"
        
        # All original places present
        original_ids = {p['placeId'] for p in places}
        ranked_ids = {p['placeId'] for p in ranked}
        assert original_ids == ranked_ids, "Ranking should not lose or duplicate places"


class TestProperty18_PopularityRankingCorrectness:
    """
    Property 18: Popularity Ranking Correctness
    
    For any list of places ranked by popularity mode, the results should be sorted
    by Bayesian popularity score in descending order.
    
    **Validates: Requirements 10.5**
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_popularity_ranking_descending_order(self, places):
        """
        Property: For any list of places, popularity ranking should produce
        results in descending Bayesian score order.
        """
        ranking_engine = RankingEngine()
        
        # Rank places by popularity
        ranked = ranking_engine.rank(places, RankingMode.POPULARITY, None)
        
        # Calculate Bayesian scores
        bayesian_scores = [
            ranking_engine._calculate_bayesian_score(place)
            for place in ranked
        ]
        
        # Verify descending order
        for i in range(len(bayesian_scores) - 1):
            assert bayesian_scores[i] >= bayesian_scores[i + 1], (
                f"Popularity ranking violated: score[{i}]={bayesian_scores[i]:.2f} < "
                f"score[{i+1}]={bayesian_scores[i+1]:.2f}"
            )
    
    @given(
        rating=st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        reviews=st.integers(min_value=0, max_value=10000)
    )
    @settings(max_examples=100, deadline=None)
    def test_bayesian_score_bounded(self, rating, reviews):
        """
        Property: Bayesian scores should always be bounded between 0 and 5
        (same range as ratings).
        """
        ranking_engine = RankingEngine()
        
        place = {
            'totalScore': rating,
            'reviewsCount': reviews
        }
        
        score = ranking_engine._calculate_bayesian_score(place)
        
        assert 0.0 <= score <= 5.0, (
            f"Bayesian score {score} out of valid range [0.0, 5.0] "
            f"for rating={rating}, reviews={reviews}"
        )
    
    @given(
        rating=st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        reviews=st.integers(min_value=100, max_value=10000)
    )
    @settings(max_examples=100, deadline=None)
    def test_bayesian_score_converges_with_many_reviews(self, rating, reviews):
        """
        Property: With many reviews, Bayesian score should converge to actual rating.
        """
        ranking_engine = RankingEngine()
        
        place = {
            'totalScore': rating,
            'reviewsCount': reviews
        }
        
        score = ranking_engine._calculate_bayesian_score(place)
        
        # With many reviews, score should be close to actual rating
        # Allow 10% tolerance
        tolerance = 0.5
        assert abs(score - rating) < tolerance, (
            f"With {reviews} reviews, Bayesian score {score:.2f} should be close "
            f"to actual rating {rating:.2f}"
        )
    
    @given(
        rating=st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_bayesian_score_pulls_toward_prior_with_few_reviews(self, rating):
        """
        Property: With few reviews, Bayesian score should be pulled toward prior mean.
        """
        ranking_engine = RankingEngine()
        
        # Assume rating is significantly different from prior
        assume(abs(rating - ranking_engine.prior_mean) > 0.5)
        
        place = {
            'totalScore': rating,
            'reviewsCount': 1  # Very few reviews
        }
        
        score = ranking_engine._calculate_bayesian_score(place)
        
        # Score should be between rating and prior mean
        if rating > ranking_engine.prior_mean:
            assert ranking_engine.prior_mean < score < rating, (
                f"With few reviews, score {score:.2f} should be between "
                f"prior {ranking_engine.prior_mean:.2f} and rating {rating:.2f}"
            )
        else:
            assert rating < score < ranking_engine.prior_mean, (
                f"With few reviews, score {score:.2f} should be between "
                f"rating {rating:.2f} and prior {ranking_engine.prior_mean:.2f}"
            )
    
    @given(
        places=st.lists(place_strategy(), min_size=1, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_popularity_ranking_preserves_all_places(self, places):
        """
        Property: Popularity ranking should preserve all input places (no loss or duplication).
        """
        ranking_engine = RankingEngine()
        
        ranked = ranking_engine.rank(places, RankingMode.POPULARITY, None)
        
        # Same number of places
        assert len(ranked) == len(places), "Ranking should preserve all places"
        
        # All original places present
        original_ids = {p['placeId'] for p in places}
        ranked_ids = {p['placeId'] for p in ranked}
        assert original_ids == ranked_ids, "Ranking should not lose or duplicate places"


class TestProperty19_BestMatchRankingCorrectness:
    """
    Property 19: Best Match Ranking Correctness
    
    For any list of places ranked by best_match mode, the results should be sorted
    by composite score using weights: 45% rating, 35% popularity, 20% proximity.
    
    **Validates: Requirements 10.6**
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_best_match_ranking_descending_order(self, places, user_location):
        """
        Property: For any list of places, best_match ranking should produce
        results in descending composite score order.
        """
        ranking_engine = RankingEngine()
        
        # Rank places by best_match
        ranked = ranking_engine.rank(places, RankingMode.BEST_MATCH, user_location)
        
        # Calculate composite scores manually
        max_distance = 0.0
        for place in places:
            place_loc = Location(
                latitude=place['location']['lat'],
                longitude=place['location']['lng']
            )
            distance = user_location.distance_to(place_loc)
            max_distance = max(max_distance, distance)
        
        if max_distance == 0.0:
            max_distance = 1.0
        
        composite_scores = []
        for place in ranked:
            # Rating component (45%)
            rating_score = (place['totalScore'] / 5.0) * 0.45
            
            # Popularity component (35%)
            bayesian_score = ranking_engine._calculate_bayesian_score(place)
            popularity_score = (bayesian_score / 5.0) * 0.35
            
            # Proximity component (20%)
            place_loc = Location(
                latitude=place['location']['lat'],
                longitude=place['location']['lng']
            )
            distance = user_location.distance_to(place_loc)
            proximity_score = (1.0 - (distance / max_distance)) * 0.20
            
            composite_score = rating_score + popularity_score + proximity_score
            composite_scores.append(composite_score)
        
        # Verify descending order (with small tolerance for floating point)
        for i in range(len(composite_scores) - 1):
            assert composite_scores[i] >= composite_scores[i + 1] - 1e-9, (
                f"Best match ranking violated: score[{i}]={composite_scores[i]:.4f} < "
                f"score[{i+1}]={composite_scores[i+1]:.4f}"
            )
    
    @given(
        places=st.lists(place_strategy(), min_size=2, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_best_match_works_without_location(self, places):
        """
        Property: Best match ranking should work without user location
        (proximity component becomes 0).
        """
        ranking_engine = RankingEngine()
        
        # Should not raise an error
        ranked = ranking_engine.rank(places, RankingMode.BEST_MATCH, None)
        
        # Should return all places
        assert len(ranked) == len(places), "Ranking should preserve all places"
        
        # All original places present
        original_ids = {p['placeId'] for p in places}
        ranked_ids = {p['placeId'] for p in ranked}
        assert original_ids == ranked_ids, "Ranking should not lose or duplicate places"
    
    @given(
        rating=st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        reviews=st.integers(min_value=0, max_value=1000),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_best_match_composite_score_bounded(self, rating, reviews, user_location):
        """
        Property: Composite scores should be bounded between 0 and 1
        (since all components are normalized to 0-1 and sum to 100%).
        """
        ranking_engine = RankingEngine()
        
        place = {
            'placeId': 'test_place',
            'location': {'lat': user_location.latitude + 0.01, 'lng': user_location.longitude + 0.01},
            'totalScore': rating,
            'reviewsCount': reviews
        }
        
        # Rank single place to get its composite score
        ranked = ranking_engine.rank([place], RankingMode.BEST_MATCH, user_location)
        
        # Calculate composite score manually
        rating_score = (rating / 5.0) * 0.45
        bayesian_score = ranking_engine._calculate_bayesian_score(place)
        popularity_score = (bayesian_score / 5.0) * 0.35
        proximity_score = 0.20  # Max proximity for single place
        
        composite_score = rating_score + popularity_score + proximity_score
        
        assert 0.0 <= composite_score <= 1.0, (
            f"Composite score {composite_score} out of valid range [0.0, 1.0]"
        )
    
    @given(
        places=st.lists(place_strategy(), min_size=1, max_size=10),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_best_match_preserves_all_places(self, places, user_location):
        """
        Property: Best match ranking should preserve all input places (no loss or duplication).
        """
        ranking_engine = RankingEngine()
        
        ranked = ranking_engine.rank(places, RankingMode.BEST_MATCH, user_location)
        
        # Same number of places
        assert len(ranked) == len(places), "Ranking should preserve all places"
        
        # All original places present
        original_ids = {p['placeId'] for p in places}
        ranked_ids = {p['placeId'] for p in ranked}
        assert original_ids == ranked_ids, "Ranking should not lose or duplicate places"


class TestRankingInvariants:
    """
    Test invariants that should hold across all ranking modes.
    """
    
    @given(
        places=st.lists(place_strategy(), min_size=0, max_size=10),
        mode=st.sampled_from([RankingMode.RATING, RankingMode.POPULARITY]),
        user_location=location_strategy()
    )
    @settings(max_examples=100, deadline=None)
    def test_ranking_preserves_count(self, places, mode, user_location):
        """
        Property: All ranking modes should preserve the number of places.
        """
        ranking_engine = RankingEngine()
        
        # For distance and best_match, we need user_location
        if mode in [RankingMode.DISTANCE, RankingMode.BEST_MATCH]:
            ranked = ranking_engine.rank(places, mode, user_location)
        else:
            ranked = ranking_engine.rank(places, mode, None)
        
        assert len(ranked) == len(places), (
            f"Ranking mode {mode} should preserve place count"
        )
    
    @given(
        places=st.lists(place_strategy(), min_size=1, max_size=10),
        mode=st.sampled_from([RankingMode.RATING, RankingMode.POPULARITY])
    )
    @settings(max_examples=100, deadline=None)
    def test_ranking_deterministic(self, places, mode):
        """
        Property: Ranking should be deterministic (same input produces same output).
        """
        ranking_engine = RankingEngine()
        
        # Rank twice
        ranked1 = ranking_engine.rank(places, mode, None)
        ranked2 = ranking_engine.rank(places, mode, None)
        
        # Should produce identical results
        ids1 = [p['placeId'] for p in ranked1]
        ids2 = [p['placeId'] for p in ranked2]
        
        assert ids1 == ids2, (
            f"Ranking mode {mode} should be deterministic"
        )
    
    @given(
        mode=st.sampled_from([RankingMode.RATING, RankingMode.POPULARITY])
    )
    @settings(max_examples=50, deadline=None)
    def test_empty_list_returns_empty(self, mode):
        """
        Property: Ranking an empty list should return an empty list.
        """
        ranking_engine = RankingEngine()
        
        ranked = ranking_engine.rank([], mode, None)
        assert ranked == [], f"Ranking mode {mode} should return empty list for empty input"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
