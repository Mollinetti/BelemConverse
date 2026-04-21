"""
Unit tests for RankingEngine module.

Tests ranking logic including:
- Distance ranking (ascending with rating tiebreaker)
- Rating ranking (descending with review count tiebreaker)
- Popularity ranking (Bayesian score descending)
- Best match ranking (composite scoring)
"""

import pytest

from belem_converse.core.ranking_engine import Location, RankingEngine, RankingMode


@pytest.fixture
def ranking_engine():
    """Create ranking engine instance."""
    return RankingEngine()


@pytest.fixture
def user_location():
    """Create a user location for testing."""
    # São Paulo coordinates
    return Location(latitude=-23.5505, longitude=-46.6333)


@pytest.fixture
def sample_places():
    """Create sample places for testing."""
    return [
        {
            'placeId': 'place1',
            'title': 'Close High Rated',
            'location': {'lat': -23.5510, 'lng': -46.6340},  # ~0.8km away
            'totalScore': 4.5,
            'reviewsCount': 100
        },
        {
            'placeId': 'place2',
            'title': 'Far High Rated',
            'location': {'lat': -23.5600, 'lng': -46.6500},  # ~2km away
            'totalScore': 4.8,
            'reviewsCount': 200
        },
        {
            'placeId': 'place3',
            'title': 'Close Low Rated',
            'location': {'lat': -23.5508, 'lng': -46.6335},  # ~0.5km away
            'totalScore': 3.5,
            'reviewsCount': 50
        },
        {
            'placeId': 'place4',
            'title': 'Popular Many Reviews',
            'location': {'lat': -23.5520, 'lng': -46.6350},  # ~1.5km away
            'totalScore': 4.2,
            'reviewsCount': 500
        },
        {
            'placeId': 'place5',
            'title': 'High Rating Few Reviews',
            'location': {'lat': -23.5515, 'lng': -46.6345},  # ~1km away
            'totalScore': 5.0,
            'reviewsCount': 5
        }
    ]


class TestLocation:
    """Test Location class and distance calculation."""
    
    def test_distance_calculation(self):
        """Test Haversine distance calculation."""
        # São Paulo to Rio de Janeiro (approximately 360km)
        sao_paulo = Location(latitude=-23.5505, longitude=-46.6333)
        rio = Location(latitude=-22.9068, longitude=-43.1729)
        
        distance = sao_paulo.distance_to(rio)
        
        # Should be approximately 360km (allow 10% margin)
        assert 320 < distance < 400
    
    def test_distance_same_location(self):
        """Test distance to same location is zero."""
        location = Location(latitude=-23.5505, longitude=-46.6333)
        distance = location.distance_to(location)
        
        assert distance == 0.0
    
    def test_distance_nearby(self):
        """Test distance calculation for nearby locations."""
        loc1 = Location(latitude=-23.5505, longitude=-46.6333)
        loc2 = Location(latitude=-23.5510, longitude=-46.6340)
        
        distance = loc1.distance_to(loc2)
        
        # Should be less than 1km
        assert distance < 1.0


class TestDistanceRanking:
    """Test distance ranking mode."""
    
    def test_rank_by_distance_ascending(self, ranking_engine, sample_places, user_location):
        """Test that places are sorted by distance ascending."""
        ranked = ranking_engine.rank(sample_places, RankingMode.DISTANCE, user_location)
        
        # Extract distances
        distances = []
        for place in ranked:
            place_loc = Location(
                latitude=place['location']['lat'],
                longitude=place['location']['lng']
            )
            distances.append(user_location.distance_to(place_loc))
        
        # Verify ascending order
        assert distances == sorted(distances)
    
    def test_rank_by_distance_rating_tiebreaker(self, ranking_engine, user_location):
        """Test that rating is used as tiebreaker for equal distances."""
        places = [
            {
                'placeId': 'place1',
                'location': {'lat': -23.5510, 'lng': -46.6340},
                'totalScore': 3.0,
                'reviewsCount': 50
            },
            {
                'placeId': 'place2',
                'location': {'lat': -23.5510, 'lng': -46.6340},  # Same location
                'totalScore': 4.5,
                'reviewsCount': 100
            }
        ]
        
        ranked = ranking_engine.rank(places, RankingMode.DISTANCE, user_location)
        
        # Higher rated place should come first when distances are equal
        assert ranked[0]['placeId'] == 'place2'
        assert ranked[1]['placeId'] == 'place1'
    
    def test_rank_by_distance_requires_location(self, ranking_engine, sample_places):
        """Test that distance ranking requires user location."""
        with pytest.raises(ValueError, match="user_location is required"):
            ranking_engine.rank(sample_places, RankingMode.DISTANCE, None)
    
    def test_rank_by_distance_missing_place_location(self, ranking_engine, user_location):
        """Test that places without location go to the end."""
        places = [
            {
                'placeId': 'place1',
                'location': {'lat': -23.5510, 'lng': -46.6340},
                'totalScore': 4.0,
                'reviewsCount': 50
            },
            {
                'placeId': 'place2',
                'location': None,  # No location
                'totalScore': 5.0,
                'reviewsCount': 100
            }
        ]
        
        ranked = ranking_engine.rank(places, RankingMode.DISTANCE, user_location)
        
        # Place with location should come first
        assert ranked[0]['placeId'] == 'place1'
        assert ranked[1]['placeId'] == 'place2'


class TestRatingRanking:
    """Test rating ranking mode."""
    
    def test_rank_by_rating_descending(self, ranking_engine, sample_places):
        """Test that places are sorted by rating descending."""
        ranked = ranking_engine.rank(sample_places, RankingMode.RATING, None)
        
        # Extract ratings
        ratings = [place['totalScore'] for place in ranked]
        
        # Verify descending order
        assert ratings == sorted(ratings, reverse=True)
    
    def test_rank_by_rating_review_count_tiebreaker(self, ranking_engine):
        """Test that review count is used as tiebreaker for equal ratings."""
        places = [
            {
                'placeId': 'place1',
                'totalScore': 4.5,
                'reviewsCount': 50
            },
            {
                'placeId': 'place2',
                'totalScore': 4.5,
                'reviewsCount': 200
            }
        ]
        
        ranked = ranking_engine.rank(places, RankingMode.RATING, None)
        
        # Place with more reviews should come first when ratings are equal
        assert ranked[0]['placeId'] == 'place2'
        assert ranked[1]['placeId'] == 'place1'
    
    def test_rank_by_rating_missing_values(self, ranking_engine):
        """Test that places with missing ratings are handled."""
        places = [
            {
                'placeId': 'place1',
                'totalScore': 4.5,
                'reviewsCount': 100
            },
            {
                'placeId': 'place2',
                'totalScore': None,  # Missing rating
                'reviewsCount': 50
            }
        ]
        
        ranked = ranking_engine.rank(places, RankingMode.RATING, None)
        
        # Place with rating should come first
        assert ranked[0]['placeId'] == 'place1'


class TestPopularityRanking:
    """Test popularity ranking mode."""
    
    def test_rank_by_popularity_bayesian(self, ranking_engine, sample_places):
        """Test that places are sorted by Bayesian score."""
        ranked = ranking_engine.rank(sample_places, RankingMode.POPULARITY, None)
        
        # Calculate Bayesian scores
        scores = [ranking_engine._calculate_bayesian_score(place) for place in ranked]
        
        # Verify descending order
        assert scores == sorted(scores, reverse=True)
    
    def test_bayesian_score_many_reviews(self, ranking_engine):
        """Test that Bayesian score approaches actual rating with many reviews."""
        place = {
            'totalScore': 4.5,
            'reviewsCount': 1000  # Many reviews
        }
        
        score = ranking_engine._calculate_bayesian_score(place)
        
        # With many reviews, Bayesian score should be close to actual rating
        assert abs(score - 4.5) < 0.1
    
    def test_bayesian_score_few_reviews(self, ranking_engine):
        """Test that Bayesian score pulls toward prior with few reviews."""
        place = {
            'totalScore': 5.0,
            'reviewsCount': 1  # Very few reviews
        }
        
        score = ranking_engine._calculate_bayesian_score(place)
        
        # With few reviews, score should be pulled toward prior (3.5)
        assert score < 5.0
        assert score > 3.5
    
    def test_bayesian_score_no_reviews(self, ranking_engine):
        """Test that Bayesian score equals prior with no reviews."""
        place = {
            'totalScore': 5.0,
            'reviewsCount': 0
        }
        
        score = ranking_engine._calculate_bayesian_score(place)
        
        # With no reviews, score should equal prior mean
        assert score == ranking_engine.prior_mean
    
    def test_popularity_balances_rating_and_reviews(self, ranking_engine):
        """Test that popularity ranking balances high rating vs many reviews."""
        places = [
            {
                'placeId': 'high_rating_few_reviews',
                'totalScore': 5.0,
                'reviewsCount': 10
            },
            {
                'placeId': 'good_rating_many_reviews',
                'totalScore': 4.3,
                'reviewsCount': 500
            }
        ]
        
        ranked = ranking_engine.rank(places, RankingMode.POPULARITY, None)
        
        # Place with many reviews should rank higher due to Bayesian adjustment
        assert ranked[0]['placeId'] == 'good_rating_many_reviews'


class TestBestMatchRanking:
    """Test best match ranking mode."""
    
    def test_rank_by_best_match_composite(self, ranking_engine, sample_places, user_location):
        """Test that best match uses composite scoring."""
        ranked = ranking_engine.rank(sample_places, RankingMode.BEST_MATCH, user_location)
        
        # Should return a valid ranking
        assert len(ranked) == len(sample_places)
        assert all(place in ranked for place in sample_places)
    
    def test_best_match_without_location(self, ranking_engine, sample_places):
        """Test that best match works without user location."""
        # Should work but proximity component will be 0
        ranked = ranking_engine.rank(sample_places, RankingMode.BEST_MATCH, None)
        
        assert len(ranked) == len(sample_places)
    
    def test_best_match_balances_factors(self, ranking_engine, user_location):
        """Test that best match balances rating, popularity, and proximity."""
        places = [
            {
                'placeId': 'close_low_rated',
                'location': {'lat': -23.5506, 'lng': -46.6334},  # Very close
                'totalScore': 3.0,
                'reviewsCount': 10
            },
            {
                'placeId': 'far_high_rated',
                'location': {'lat': -23.5700, 'lng': -46.6600},  # Far
                'totalScore': 5.0,
                'reviewsCount': 500
            },
            {
                'placeId': 'balanced',
                'location': {'lat': -23.5520, 'lng': -46.6350},  # Medium distance
                'totalScore': 4.3,
                'reviewsCount': 200
            }
        ]
        
        ranked = ranking_engine.rank(places, RankingMode.BEST_MATCH, user_location)
        
        # Balanced place should rank well (likely first or second)
        balanced_index = next(i for i, p in enumerate(ranked) if p['placeId'] == 'balanced')
        assert balanced_index <= 1


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_places_list(self, ranking_engine, user_location):
        """Test ranking empty list."""
        ranked = ranking_engine.rank([], RankingMode.DISTANCE, user_location)
        assert ranked == []
    
    def test_single_place(self, ranking_engine, user_location):
        """Test ranking single place."""
        places = [
            {
                'placeId': 'place1',
                'location': {'lat': -23.5510, 'lng': -46.6340},
                'totalScore': 4.5,
                'reviewsCount': 100
            }
        ]
        
        ranked = ranking_engine.rank(places, RankingMode.DISTANCE, user_location)
        assert len(ranked) == 1
        assert ranked[0]['placeId'] == 'place1'
    
    def test_invalid_ranking_mode(self, ranking_engine, sample_places, user_location):
        """Test that invalid ranking mode raises error."""
        with pytest.raises(ValueError, match="Unknown ranking mode"):
            ranking_engine.rank(sample_places, "invalid_mode", user_location)
    
    def test_places_with_missing_fields(self, ranking_engine, user_location):
        """Test ranking places with missing fields."""
        places = [
            {
                'placeId': 'place1',
                'location': {'lat': -23.5510, 'lng': -46.6340}
                # Missing totalScore and reviewsCount
            },
            {
                'placeId': 'place2',
                'location': {'lat': -23.5520, 'lng': -46.6350},
                'totalScore': 4.5,
                'reviewsCount': 100
            }
        ]
        
        # Should not crash
        ranked = ranking_engine.rank(places, RankingMode.DISTANCE, user_location)
        assert len(ranked) == 2


class TestDataFormats:
    """Test different place data formats."""
    
    def test_pydantic_model_format(self, ranking_engine, user_location):
        """Test ranking with Pydantic model objects."""
        class MockPlace:
            def __init__(self, place_id, lat, lng, score, reviews):
                self.placeId = place_id
                self.location = type('obj', (object,), {'lat': lat, 'lng': lng})()
                self.totalScore = score
                self.reviewsCount = reviews
        
        places = [
            MockPlace('place1', -23.5510, -46.6340, 4.5, 100),
            MockPlace('place2', -23.5520, -46.6350, 4.8, 200)
        ]
        
        ranked = ranking_engine.rank(places, RankingMode.DISTANCE, user_location)
        
        assert len(ranked) == 2
        # Closer place should be first
        assert ranked[0].placeId == 'place1'
    
    def test_dict_format(self, ranking_engine, user_location):
        """Test ranking with dictionary format."""
        places = [
            {
                'placeId': 'place1',
                'location': {'lat': -23.5510, 'lng': -46.6340},
                'totalScore': 4.5,
                'reviewsCount': 100
            }
        ]
        
        ranked = ranking_engine.rank(places, RankingMode.DISTANCE, user_location)
        
        assert len(ranked) == 1
        assert ranked[0]['placeId'] == 'place1'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
