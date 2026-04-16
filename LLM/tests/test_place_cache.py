"""
Unit tests for PlaceCache shared module.

Tests:
- Lookup by placeId
- Lookup by title
- Lookup by titleFormatted
- Filter with predicate functions
- Cache invalidation and reload
- Edge cases (empty data, missing fields, case sensitivity)
"""

import sys
from pathlib import Path
import importlib.util

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest

# Import modules directly without triggering __init__.py
def import_module_from_file(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# Import place cache
place_cache_path = project_root / "src" / "core" / "place_cache.py"
place_cache_module = import_module_from_file("place_cache", place_cache_path)
PlaceCache = place_cache_module.PlaceCache


class TestPlaceCache:
    """Test suite for PlaceCache module."""
    
    @pytest.fixture
    def sample_places(self):
        """Sample place data for testing."""
        return [
            {
                'placeId': 'place1',
                'title': 'Restaurant A',
                'titleFormatted': 'Restaurant A - Downtown',
                'categoryName': 'restaurant',
                'location/lat': -23.5505,
                'location/lng': -46.6333,
                'totalScore': 4.5,
                'reviewsCount': 100
            },
            {
                'placeId': 'place2',
                'title': 'Cafe B',
                'titleFormatted': 'Café B',
                'categoryName': 'cafe',
                'location/lat': -23.5515,
                'location/lng': -46.6343,
                'totalScore': 4.2,
                'reviewsCount': 50
            },
            {
                'placeId': 'place3',
                'title': 'Hotel C',
                'titleFormatted': 'Hotel C Luxury',
                'categoryName': 'hotel',
                'location/lat': -23.5525,
                'location/lng': -46.6353,
                'totalScore': 4.8,
                'reviewsCount': 200
            },
            {
                'cid': 'place4',  # Using cid instead of placeId
                'title': 'Bar D',
                'titleFormatted': 'Bar D Lounge',
                'categoryName': 'bar',
                'location/lat': -23.5535,
                'location/lng': -46.6363,
                'totalScore': 4.0,
                'reviewsCount': 75
            }
        ]
    
    @pytest.fixture
    def place_cache(self, sample_places):
        """PlaceCache instance with sample data."""
        return PlaceCache(sample_places)
    
    def test_initialization(self, place_cache, sample_places):
        """Test PlaceCache initialization."""
        assert place_cache.get_count() == len(sample_places)
        assert len(place_cache.get_all()) == len(sample_places)
    
    def test_get_by_id_with_place_id(self, place_cache):
        """Test lookup by placeId."""
        place = place_cache.get_by_id('place1')
        assert place is not None
        assert place['title'] == 'Restaurant A'
        assert place['placeId'] == 'place1'
    
    def test_get_by_id_with_cid(self, place_cache):
        """Test lookup by cid (alternative ID field)."""
        place = place_cache.get_by_id('place4')
        assert place is not None
        assert place['title'] == 'Bar D'
        assert place['cid'] == 'place4'
    
    def test_get_by_id_not_found(self, place_cache):
        """Test lookup by non-existent ID."""
        place = place_cache.get_by_id('nonexistent')
        assert place is None
    
    def test_get_by_title_exact_match(self, place_cache):
        """Test lookup by exact title."""
        place = place_cache.get_by_title('Restaurant A')
        assert place is not None
        assert place['placeId'] == 'place1'
    
    def test_get_by_title_case_insensitive(self, place_cache):
        """Test lookup by title is case-insensitive."""
        place = place_cache.get_by_title('restaurant a')
        assert place is not None
        assert place['placeId'] == 'place1'
        
        place = place_cache.get_by_title('RESTAURANT A')
        assert place is not None
        assert place['placeId'] == 'place1'
    
    def test_get_by_title_formatted(self, place_cache):
        """Test lookup by titleFormatted."""
        place = place_cache.get_by_title('Restaurant A - Downtown')
        assert place is not None
        assert place['placeId'] == 'place1'
    
    def test_get_by_title_formatted_case_insensitive(self, place_cache):
        """Test lookup by titleFormatted is case-insensitive."""
        place = place_cache.get_by_title('café b')
        assert place is not None
        assert place['placeId'] == 'place2'
    
    def test_get_by_title_not_found(self, place_cache):
        """Test lookup by non-existent title."""
        place = place_cache.get_by_title('Nonexistent Place')
        assert place is None
    
    def test_get_all(self, place_cache, sample_places):
        """Test get_all returns all places."""
        all_places = place_cache.get_all()
        assert len(all_places) == len(sample_places)
        assert all_places == sample_places
    
    def test_filter_by_category(self, place_cache):
        """Test filter with category predicate."""
        restaurants = place_cache.filter(
            lambda p: p.get('categoryName') == 'restaurant'
        )
        assert len(restaurants) == 1
        assert restaurants[0]['title'] == 'Restaurant A'
    
    def test_filter_by_rating(self, place_cache):
        """Test filter with rating predicate."""
        high_rated = place_cache.filter(
            lambda p: p.get('totalScore', 0) >= 4.5
        )
        assert len(high_rated) == 2
        titles = [p['title'] for p in high_rated]
        assert 'Restaurant A' in titles
        assert 'Hotel C' in titles
    
    def test_filter_by_review_count(self, place_cache):
        """Test filter with review count predicate."""
        popular = place_cache.filter(
            lambda p: p.get('reviewsCount', 0) >= 100
        )
        assert len(popular) == 2
        titles = [p['title'] for p in popular]
        assert 'Restaurant A' in titles
        assert 'Hotel C' in titles
    
    def test_filter_multiple_conditions(self, place_cache):
        """Test filter with multiple conditions."""
        filtered = place_cache.filter(
            lambda p: (
                p.get('totalScore', 0) >= 4.0 and
                p.get('reviewsCount', 0) >= 50 and
                p.get('categoryName') in ['cafe', 'restaurant']
            )
        )
        assert len(filtered) == 2
        titles = [p['title'] for p in filtered]
        assert 'Restaurant A' in titles
        assert 'Cafe B' in titles
    
    def test_filter_returns_empty_list(self, place_cache):
        """Test filter returns empty list when no matches."""
        filtered = place_cache.filter(
            lambda p: p.get('totalScore', 0) > 5.0
        )
        assert filtered == []
    
    def test_invalidate(self, place_cache):
        """Test cache invalidation."""
        assert place_cache.get_count() == 4
        
        place_cache.invalidate()
        
        assert place_cache.get_count() == 0
        assert place_cache.get_all() == []
        assert place_cache.get_by_id('place1') is None
        assert place_cache.get_by_title('Restaurant A') is None
    
    def test_reload(self, place_cache):
        """Test cache reload with new data."""
        new_places = [
            {
                'placeId': 'new1',
                'title': 'New Place',
                'titleFormatted': 'New Place',
                'categoryName': 'restaurant'
            }
        ]
        
        place_cache.reload(new_places)
        
        assert place_cache.get_count() == 1
        assert place_cache.get_by_id('new1') is not None
        assert place_cache.get_by_id('place1') is None
        assert place_cache.get_by_title('New Place') is not None
    
    def test_empty_initialization(self):
        """Test PlaceCache with empty data."""
        cache = PlaceCache([])
        assert cache.get_count() == 0
        assert cache.get_all() == []
        assert cache.get_by_id('any') is None
        assert cache.get_by_title('any') is None
    
    def test_places_with_missing_fields(self):
        """Test PlaceCache handles places with missing fields."""
        places = [
            {'placeId': 'p1'},  # Missing title
            {'title': 'Place 2'},  # Missing placeId
            {}  # Empty place
        ]
        
        cache = PlaceCache(places)
        assert cache.get_count() == 3
        
        # Can lookup by ID
        place = cache.get_by_id('p1')
        assert place is not None
        
        # Can lookup by title
        place = cache.get_by_title('Place 2')
        assert place is not None
    
    def test_duplicate_titles(self):
        """Test PlaceCache handles duplicate titles (first occurrence wins)."""
        places = [
            {'placeId': 'p1', 'title': 'Duplicate'},
            {'placeId': 'p2', 'title': 'Duplicate'}
        ]
        
        cache = PlaceCache(places)
        
        # Should return first occurrence
        place = cache.get_by_title('Duplicate')
        assert place is not None
        assert place['placeId'] == 'p1'
    
    def test_whitespace_handling(self, place_cache):
        """Test PlaceCache handles whitespace in titles."""
        # Should find place even with extra whitespace
        place = place_cache.get_by_title('  Restaurant A  ')
        assert place is not None
        assert place['placeId'] == 'place1'
    
    def test_filter_with_complex_predicate(self, place_cache):
        """Test filter with complex predicate function."""
        def complex_predicate(place):
            # Places with high rating OR many reviews
            rating = place.get('totalScore', 0)
            reviews = place.get('reviewsCount', 0)
            return rating >= 4.5 or reviews >= 100
        
        filtered = place_cache.filter(complex_predicate)
        assert len(filtered) == 2
        titles = [p['title'] for p in filtered]
        assert 'Restaurant A' in titles
        assert 'Hotel C' in titles
    
    def test_get_count(self, place_cache):
        """Test get_count returns correct count."""
        assert place_cache.get_count() == 4
        
        place_cache.invalidate()
        assert place_cache.get_count() == 0
        
        place_cache.reload([{'placeId': 'p1'}])
        assert place_cache.get_count() == 1
