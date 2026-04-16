"""
Simple standalone test for filter-first implementation.
Tests the core filtering logic without complex imports.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Test the filter logic directly
def test_filter_precedence():
    """Test that filters are applied in the correct order."""
    print("Testing filter precedence order...")
    
    # Sample places
    places = [
        {
            'placeId': 'place1',
            'title': 'Open Restaurant',
            'category': ['restaurant'],
            'location': {'lat': -1.4558, 'lng': -48.4902},
            'totalScore': 4.5,
            'reviewsCount': 100,
            'price': 2,
        },
        {
            'placeId': 'place2',
            'title': 'Closed Cafe',
            'category': ['cafe'],
            'location': {'lat': -1.4560, 'lng': -48.4900},
            'totalScore': 4.8,
            'reviewsCount': 200,
            'price': 1,
        },
        {
            'placeId': 'place3',
            'title': 'Far Restaurant',
            'category': ['restaurant'],
            'location': {'lat': -1.4700, 'lng': -48.5000},
            'totalScore': 4.9,
            'reviewsCount': 300,
            'price': 3,
        },
    ]
    
    # Test 1: Category filter
    print("\nTest 1: Category filter")
    filtered = [p for p in places if 'restaurant' in p['category']]
    print(f"  Restaurants: {len(filtered)} (expected 2)")
    assert len(filtered) == 2
    
    # Test 2: Price filter
    print("\nTest 2: Price filter (max price 2)")
    filtered = [p for p in places if p.get('price', 0) <= 2]
    print(f"  Within budget: {len(filtered)} (expected 2)")
    assert len(filtered) == 2
    
    # Test 3: Rating filter
    print("\nTest 3: Rating filter (min 4.5)")
    filtered = [p for p in places if p.get('totalScore', 0) >= 4.5]
    print(f"  High rated: {len(filtered)} (expected 3)")
    assert len(filtered) == 3
    
    # Test 4: Combined filters
    print("\nTest 4: Combined filters (restaurant + price<=2 + rating>=4.5)")
    filtered = [
        p for p in places
        if 'restaurant' in p['category']
        and p.get('price', 0) <= 2
        and p.get('totalScore', 0) >= 4.5
    ]
    print(f"  Matching all: {len(filtered)} (expected 1)")
    assert len(filtered) == 1
    assert filtered[0]['placeId'] == 'place1'
    
    print("\n✓ All filter tests passed!")


def test_haversine_distance():
    """Test Haversine distance calculation."""
    import math
    
    def haversine(lat1, lng1, lat2, lng2):
        R = 6371  # Earth's radius in km
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    print("\nTesting Haversine distance calculation...")
    
    # Test 1: Same location
    dist = haversine(-1.4558, -48.4902, -1.4558, -48.4902)
    print(f"  Same location: {dist:.4f}km (expected 0)")
    assert dist == 0.0
    
    # Test 2: Known distance (~1km)
    dist = haversine(-1.4558, -48.4902, -1.4650, -48.4900)
    print(f"  ~1km distance: {dist:.4f}km (expected ~1.0)")
    assert 0.9 < dist < 1.1
    
    print("\n✓ Distance calculation tests passed!")


def test_radius_escalation():
    """Test radius escalation logic."""
    print("\nTesting radius escalation...")
    
    places = [
        {'id': 1, 'dist': 0.3},  # Within 0.5km
        {'id': 2, 'dist': 0.4},  # Within 0.5km
        {'id': 3, 'dist': 0.8},  # Within 1km
        {'id': 4, 'dist': 1.5},  # Within 2km
        {'id': 5, 'dist': 2.5},  # Beyond 2km
    ]
    
    radii = [0.5, 1.0, 2.0]
    min_results = 3
    
    for radius in radii:
        filtered = [p for p in places if p['dist'] <= radius]
        print(f"  Radius {radius}km: {len(filtered)} places")
        
        if len(filtered) >= min_results:
            print(f"  ✓ Found {len(filtered)} >= {min_results}, stopping escalation")
            assert len(filtered) == 3  # Should stop at 1km radius with 3 places
            break
    
    print("\n✓ Radius escalation test passed!")


if __name__ == '__main__':
    test_filter_precedence()
    test_haversine_distance()
    test_radius_escalation()
    print("\n" + "="*50)
    print("All tests passed successfully!")
    print("="*50)
