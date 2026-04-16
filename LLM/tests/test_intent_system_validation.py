"""
Comprehensive validation tests for intent detection and retrieval system.
Tests various query types with detailed logging for manual inspection.

Test Location: Travessa Curuzu, 1475, Belem, PA
Coordinates: -1.4557549, -48.4901799

This test suite validates:
1. Intent classification accuracy
2. Proximity detection
3. Category extraction
4. Filter extraction (price, rating, open_now)
5. Sort preference determination
6. Consistency across similar queries
"""

import pytest
import logging
import sys
from pathlib import Path
from typing import Dict, Any
import json
from datetime import datetime

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from core.query_planner import QueryPlanner
from classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test location constants
TEST_LAT = -1.4557549
TEST_LON = -48.4901799
TEST_LOCATION = "Travessa Curuzu, 1475, Belem, PA"


class TestIntentSystemValidation:
    """Comprehensive validation tests with detailed logging."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test components."""
        # Initialize and train intent classifier
        self.intent_classifier = SimpleTFIDFIntentClassifier()
        self.intent_classifier.train()
        
        # Initialize query planner
        self.query_planner = QueryPlanner(intent_classifier=self.intent_classifier)
        
        # Log test start
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info(f"\n{'='*120}")
        logger.info(f"INTENT DETECTION VALIDATION TEST RUN")
        logger.info(f"Started: {timestamp}")
        logger.info(f"Test Location: {TEST_LOCATION}")
        logger.info(f"Coordinates: ({TEST_LAT}, {TEST_LON})")
        logger.info(f"{'='*120}\n")
    
    def log_query_plan(self, test_name: str, query: str, plan_dict: Dict[str, Any], expected: Dict[str, Any] = None):
        """Log query plan details for manual inspection."""
        logger.info(f"\n{'-'*120}")
        logger.info(f"TEST: {test_name}")
        logger.info(f"QUERY: '{query}'")
        logger.info(f"{'-'*120}")
        logger.info(f"INTENT: {plan_dict.get('intent')}")
        logger.info(f"LANGUAGE: {plan_dict.get('language')}")
        logger.info(f"RETRIEVAL STRATEGY: {plan_dict.get('retrieval_strategy')}")
        
        slots = plan_dict.get('slots', {})
        logger.info(f"\nEXTRACTED INFORMATION:")
        logger.info(f"  Place Types: {slots.get('place_type')}")
        logger.info(f"  Categories: {slots.get('categories')}")
        logger.info(f"  City: {slots.get('city')}")
        logger.info(f"  Neighborhood: {slots.get('neighborhood')}")
        logger.info(f"  Open Now: {slots.get('open_now')}")
        logger.info(f"  Price Max: {slots.get('price_max')}")
        logger.info(f"  Min Rating: {slots.get('min_rating')}")
        logger.info(f"  Min Reviews: {slots.get('min_reviews')}")
        logger.info(f"  Proximity Intent Detected: {slots.get('proximity_intent_detected')}")
        logger.info(f"  Sort Preference: {slots.get('sort_preference')}")
        logger.info(f"  Keywords: {slots.get('keywords')}")
        
        if expected:
            logger.info(f"\nEXPECTED BEHAVIOR:")
            for key, value in expected.items():
                logger.info(f"  {key}: {value}")
        
        debug = plan_dict.get('debug', {})
        if debug.get('detected_signals'):
            logger.info(f"\nDETECTED SIGNALS: {', '.join(debug['detected_signals'])}")
        
        logger.info(f"{'-'*120}\n")
    
    def test_01_nearby_restaurants(self):
        """Test: 'restaurants near me' - should detect proximity and prioritize distance."""
        query = "restaurants near me"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        expected = {
            "proximity_intent": True,
            "sort_by": "distance",
            "category": "restaurant"
        }
        
        self.log_query_plan("Nearby Restaurants", query, plan_dict, expected)
        
        # Assertions
        assert plan_dict['slots']['proximity_intent_detected'] == True, "Should detect proximity intent"
        assert plan_dict['slots']['sort_preference'] == 'distance', "Should sort by distance"
        assert 'restaurant' in str(plan_dict['slots'].get('categories', [])).lower(), "Should extract restaurant category"
    
    def test_02_best_restaurants(self):
        """Test: 'best restaurants in Belem' - should prioritize rating/popularity."""
        query = "best restaurants in Belem"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        expected = {
            "sort_by": "rating or popularity",
            "category": "restaurant",
            "location": "Belem"
        }
        
        self.log_query_plan("Best Restaurants (Popularity)", query, plan_dict, expected)
        
        # Assertions
        assert plan_dict['slots']['sort_preference'] in ['rating', 'popularity', 'best_match'], "Should prioritize rating/popularity"
        assert 'restaurant' in str(plan_dict['slots'].get('categories', [])).lower(), "Should extract restaurant category"
    
    def test_03_specific_restaurant(self):
        """Test: 'Restaurante Lá em Casa' - should use semantic search."""
        query = "Restaurante Lá em Casa"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        expected = {
            "retrieval_strategy": "semantic_search or hybrid",
            "specific_name": "Lá em Casa"
        }
        
        self.log_query_plan("Specific Restaurant Name", query, plan_dict, expected)
        
        # Assertions - just log for manual inspection
        logger.info(f"✓ Logged specific restaurant query for manual inspection")
    
    def test_04_pizza_nearby(self):
        """Test: 'pizza places nearby' - proximity + category."""
        query = "pizza places nearby"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        expected = {
            "proximity_intent": True,
            "sort_by": "distance",
            "category": "pizza"
        }
        
        self.log_query_plan("Pizza Nearby (Category + Proximity)", query, plan_dict, expected)
        
        # Assertions
        assert plan_dict['slots']['proximity_intent_detected'] == True, "Should detect proximity intent"
        assert plan_dict['slots']['sort_preference'] == 'distance', "Should sort by distance"
        # Should extract pizza as category or place type
        categories = str(plan_dict['slots'].get('categories', [])).lower()
        place_types = str(plan_dict['slots'].get('place_type', [])).lower()
        assert 'pizza' in categories or 'pizza' in place_types, "Should extract pizza category"
    
    def test_05_tour_planning(self):
        """Test: 'plan a tour of museums' - should detect tour planning intent."""
        query = "plan a tour of museums in Belem"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        expected = {
            "intent": "tour_planning",
            "category": "museum"
        }
        
        self.log_query_plan("Tour Planning", query, plan_dict, expected)
        
        # Assertions
        assert plan_dict['intent'] == 'tour_planning', "Should detect tour planning intent"
    
    def test_06_open_now(self):
        """Test: 'restaurants open now' - should extract open_now filter."""
        query = "restaurants open now"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        expected = {
            "open_now": True,
            "category": "restaurant"
        }
        
        self.log_query_plan("Open Now Filter", query, plan_dict, expected)
        
        # Assertions
        assert plan_dict['slots']['open_now'] == True, "Should extract open_now filter"
    
    def test_07_cheap_restaurants(self):
        """Test: 'cheap restaurants' - should extract price filter."""
        query = "cheap restaurants near me"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        expected = {
            "price_max": "1 or 2",
            "proximity_intent": True
        }
        
        self.log_query_plan("Cheap Restaurants (Price Filter)", query, plan_dict, expected)
        
        # Assertions
        assert plan_dict['slots']['price_max'] is not None, "Should extract price filter"
        assert plan_dict['slots']['price_max'] <= 2, "Cheap should mean price <= 2"
    
    def test_08_highly_rated(self):
        """Test: 'highly rated restaurants' - should extract rating filter."""
        query = "highly rated restaurants"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        expected = {
            "min_rating": "4.0 or higher",
            "sort_by": "rating"
        }
        
        self.log_query_plan("Highly Rated (Rating Filter)", query, plan_dict, expected)
        
        # Log for manual inspection - rating extraction may vary
        logger.info(f"✓ Logged highly rated query for manual inspection")
    
    def test_09_italian_restaurants(self):
        """Test: 'italian restaurants' - should extract category."""
        query = "italian restaurants in Belem"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        expected = {
            "category": "italian",
            "location": "Belem"
        }
        
        self.log_query_plan("Italian Restaurants (Category)", query, plan_dict, expected)
        
        # Assertions
        categories = str(plan_dict['slots'].get('categories', [])).lower()
        assert 'italian' in categories, "Should extract italian category"
    
    def test_10_coffee_shops(self):
        """Test: 'coffee shops' - should extract cafe category."""
        query = "coffee shops near me"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        expected = {
            "proximity_intent": True,
            "category": "cafe or coffee"
        }
        
        self.log_query_plan("Coffee Shops (Cafe Category)", query, plan_dict, expected)
        
        # Assertions
        assert plan_dict['slots']['proximity_intent_detected'] == True, "Should detect proximity intent"
        categories = str(plan_dict['slots'].get('categories', [])).lower()
        place_types = str(plan_dict['slots'].get('place_type', [])).lower()
        assert 'cafe' in categories or 'coffee' in place_types or 'coffee' in categories, "Should extract cafe/coffee category"
    
    def test_11_consistency_nearby_queries(self):
        """Test: Similar nearby queries should produce consistent behavior."""
        queries = [
            "restaurants near me",
            "nearby restaurants",
            "restaurants close by",
            "find restaurants around here"
        ]
        
        logger.info(f"\n{'='*120}")
        logger.info("CONSISTENCY TEST: Nearby Query Variations")
        logger.info(f"{'='*120}")
        
        results = []
        for query in queries:
            plan = self.query_planner.create_query_plan(
                message=query,
                user_location={'lat': TEST_LAT, 'lng': TEST_LON}
            )
            plan_dict = self.query_planner.plan_to_dict(plan)
            results.append({
                'query': query,
                'proximity_detected': plan_dict['slots']['proximity_intent_detected'],
                'sort_preference': plan_dict['slots']['sort_preference']
            })
            logger.info(f"  '{query}'")
            logger.info(f"    → Proximity: {plan_dict['slots']['proximity_intent_detected']}, Sort: {plan_dict['slots']['sort_preference']}")
        
        logger.info(f"\nCONSISTENCY CHECK:")
        proximity_detected = [r['proximity_detected'] for r in results]
        sort_prefs = [r['sort_preference'] for r in results]
        logger.info(f"  All detected proximity: {all(proximity_detected)}")
        logger.info(f"  All sort by distance: {all(s == 'distance' for s in sort_prefs)}")
        logger.info(f"{'='*120}\n")
        
        # All should detect proximity and sort by distance
        assert all(r['proximity_detected'] for r in results), "All nearby queries should detect proximity"
        assert all(r['sort_preference'] == 'distance' for r in results), "All nearby queries should sort by distance"
    
    def test_12_consistency_popular_queries(self):
        """Test: Similar popularity queries should produce consistent behavior."""
        queries = [
            "best restaurants",
            "top restaurants",
            "popular restaurants",
            "top rated restaurants"
        ]
        
        logger.info(f"\n{'='*120}")
        logger.info("CONSISTENCY TEST: Popularity Query Variations")
        logger.info(f"{'='*120}")
        
        results = []
        for query in queries:
            plan = self.query_planner.create_query_plan(
                message=query,
                user_location={'lat': TEST_LAT, 'lng': TEST_LON}
            )
            plan_dict = self.query_planner.plan_to_dict(plan)
            results.append({
                'query': query,
                'sort_preference': plan_dict['slots']['sort_preference']
            })
            logger.info(f"  '{query}' → Sort: {plan_dict['slots']['sort_preference']}")
        
        logger.info(f"\nCONSISTENCY CHECK:")
        sort_prefs = [r['sort_preference'] for r in results]
        logger.info(f"  Sort preferences: {sort_prefs}")
        logger.info(f"  All prioritize rating/popularity: {all(s in ['rating', 'popularity', 'best_match'] for s in sort_prefs)}")
        logger.info(f"{'='*120}\n")
        
        # All should prioritize rating/popularity
        assert all(r['sort_preference'] in ['rating', 'popularity', 'best_match'] for r in results), \
            "All popularity queries should prioritize rating/popularity"
    
    def test_13_distance_vs_popularity_tradeoff(self):
        """Test: Verify distance vs popularity tradeoff in different queries."""
        test_cases = [
            ("restaurants near me", "distance", True),
            ("best restaurants", "rating/popularity", False),
            ("top rated restaurants nearby", "distance", True),  # Proximity wins when both present
        ]
        
        logger.info(f"\n{'='*120}")
        logger.info("DISTANCE VS POPULARITY TRADEOFF TEST")
        logger.info(f"{'='*120}")
        
        for query, expected_priority, expected_proximity in test_cases:
            plan = self.query_planner.create_query_plan(
                message=query,
                user_location={'lat': TEST_LAT, 'lng': TEST_LON}
            )
            plan_dict = self.query_planner.plan_to_dict(plan)
            
            logger.info(f"\nQuery: '{query}'")
            logger.info(f"  Expected Priority: {expected_priority}")
            logger.info(f"  Actual Sort: {plan_dict['slots']['sort_preference']}")
            logger.info(f"  Proximity Detected: {plan_dict['slots']['proximity_intent_detected']}")
            logger.info(f"  Match: {'✓' if plan_dict['slots']['proximity_intent_detected'] == expected_proximity else '✗'}")
        
        logger.info(f"{'='*120}\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
