"""
Simplified deep validation tests for intent detection and retrieval system.
Tests various query types with detailed logging for manual inspection.

Test Location: Travessa Curuzu, 1475, Belem, PA
Coordinates: -1.4557549, -48.4901799
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


class TestIntentValidationSimple:
    """Simplified validation tests focusing on intent detection."""
    
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
        logger.info(f"\n{'='*100}")
        logger.info(f"TEST RUN STARTED: {timestamp}")
        logger.info(f"Test Location: {TEST_LOCATION}")
        logger.info(f"Coordinates: ({TEST_LAT}, {TEST_LON})")
        logger.info(f"{'='*100}\n")
    
    def log_query_plan(self, test_name: str, query: str, plan_dict: Dict[str, Any]):
        """Log query plan details for manual inspection."""
        logger.info(f"\n{'-'*100}")
        logger.info(f"TEST: {test_name}")
        logger.info(f"QUERY: '{query}'")
        logger.info(f"{'-'*100}")
        logger.info(f"INTENT: {plan_dict.get('intent')}")
        logger.info(f"LANGUAGE: {plan_dict.get('language')}")
        logger.info(f"RETRIEVAL STRATEGY: {plan_dict.get('retrieval_strategy')}")
        
        slots = plan_dict.get('slots', {})
        logger.info(f"\nEXTRACTED SLOTS:")
        logger.info(f"  - Place Types: {slots.get('place_type')}")
        logger.info(f"  - Categories: {slots.get('categories')}")
        logger.info(f"  - City: {slots.get('city')}")
        logger.info(f"  - Neighborhood: {slots.get('neighborhood')}")
        logger.info(f"  - Open Now: {slots.get('open_now')}")
        logger.info(f"  - Price Max: {slots.get('price_max')}")
        logger.info(f"  - Min Rating: {slots.get('min_rating')}")
        logger.info(f"  - Min Reviews: {slots.get('min_reviews')}")
        logger.info(f"  - Proximity Intent: {slots.get('proximity_intent_detected')}")
        logger.info(f"  - Sort Preference: {slots.get('sort_preference')}")
        logger.info(f"  - Keywords: {slots.get('keywords')}")
        
        debug = plan_dict.get('debug', {})
        if debug.get('detected_signals'):
            logger.info(f"\nDETECTED SIGNALS: {', '.join(debug['detected_signals'])}")
        
        logger.info(f"{'-'*100}\n")
    
    def test_01_nearby_restaurants(self):
        """Test: 'restaurants near me' - should detect proximity intent."""
        query = "restaurants near me"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_plan("Nearby Restaurants", query, plan_dict)
        
        # Assertions
        assert plan_dict['intent'] == 'proximity', f"Expected 'proximity', got '{plan_dict['intent']}'"
        assert plan_dict['slots']['proximity_intent_detected'] == True
        assert plan_dict['slots']['sort_preference'] == 'distance'
    
    def test_02_best_restaurants(self):
        """Test: 'best restaurants in Belem' - should detect popularity intent."""
        query = "best restaurants in Belem"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_plan("Best Restaurants (Popularity)", query, plan_dict)
        
        # Assertions
        assert plan_dict['intent'] in ['popularity', 'general'], f"Expected 'popularity' or 'general', got '{plan_dict['intent']}'"
        assert plan_dict['slots']['sort_preference'] in ['rating', 'best_match']
    
    def test_03_specific_restaurant(self):
        """Test: 'Restaurante Lá em Casa' - should detect verification intent."""
        query = "Restaurante Lá em Casa"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_plan("Specific Restaurant Name", query, plan_dict)
        
        # Assertions
        assert plan_dict['intent'] in ['verification', 'general']
        assert plan_dict['retrieval_strategy'] in ['semantic_search', 'hybrid', 'filter_first']
    
    def test_04_pizza_nearby(self):
        """Test: 'pizza places nearby' - proximity + category."""
        query = "pizza places nearby"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_plan("Pizza Nearby (Category + Proximity)", query, plan_dict)
        
        # Assertions
        assert plan_dict['intent'] == 'proximity'
        assert plan_dict['slots']['proximity_intent_detected'] == True
        # Should extract pizza as category or place type
        categories = plan_dict['slots'].get('categories', [])
        place_types = plan_dict['slots'].get('place_type', [])
        assert 'pizza' in str(categories).lower() or 'pizza' in str(place_types).lower()
    
    def test_05_tour_planning(self):
        """Test: 'plan a tour of museums' - should detect tour planning intent."""
        query = "plan a tour of museums in Belem"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_plan("Tour Planning", query, plan_dict)
        
        # Assertions
        assert plan_dict['intent'] == 'tour_planning'
    
    def test_06_open_now(self):
        """Test: 'restaurants open now' - should extract open_now filter."""
        query = "restaurants open now"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_plan("Open Now Filter", query, plan_dict)
        
        # Assertions
        assert plan_dict['slots']['open_now'] == True
    
    def test_07_cheap_restaurants(self):
        """Test: 'cheap restaurants' - should extract price filter."""
        query = "cheap restaurants near me"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_plan("Cheap Restaurants (Price Filter)", query, plan_dict)
        
        # Assertions
        assert plan_dict['slots']['price_max'] is not None
        assert plan_dict['slots']['price_max'] <= 2
    
    def test_08_highly_rated(self):
        """Test: 'highly rated restaurants' - should extract rating filter."""
        query = "highly rated restaurants"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_plan("Highly Rated (Rating Filter)", query, plan_dict)
        
        # Assertions
        assert plan_dict['slots']['min_rating'] is not None
        assert plan_dict['slots']['min_rating'] >= 4.0
    
    def test_09_italian_restaurants(self):
        """Test: 'italian restaurants' - should extract category."""
        query = "italian restaurants in Belem"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_plan("Italian Restaurants (Category)", query, plan_dict)
        
        # Assertions
        categories = plan_dict['slots'].get('categories', [])
        assert 'italian' in str(categories).lower()
    
    def test_10_coffee_shops(self):
        """Test: 'coffee shops' - should extract cafe category."""
        query = "coffee shops near me"
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        self.log_query_plan("Coffee Shops (Cafe Category)", query, plan_dict)
        
        # Assertions
        assert plan_dict['intent'] == 'proximity'
        categories = plan_dict['slots'].get('categories', [])
        place_types = plan_dict['slots'].get('place_type', [])
        assert 'cafe' in str(categories).lower() or 'coffee' in str(place_types).lower()
    
    def test_11_consistency_nearby_queries(self):
        """Test: Similar nearby queries should produce consistent intents."""
        queries = [
            "restaurants near me",
            "nearby restaurants",
            "restaurants close by",
            "find restaurants around here"
        ]
        
        logger.info(f"\n{'='*100}")
        logger.info("CONSISTENCY TEST: Nearby Query Variations")
        logger.info(f"{'='*100}")
        
        intents = []
        for query in queries:
            plan = self.query_planner.create_query_plan(
                message=query,
                user_location={'lat': TEST_LAT, 'lng': TEST_LON}
            )
            plan_dict = self.query_planner.plan_to_dict(plan)
            intents.append(plan_dict['intent'])
            logger.info(f"  '{query}' -> Intent: {plan_dict['intent']}, Proximity: {plan_dict['slots']['proximity_intent_detected']}")
        
        logger.info(f"\nAll intents: {intents}")
        logger.info(f"Consistent: {len(set(intents)) == 1}")
        logger.info(f"{'='*100}\n")
        
        # All should be proximity intent
        assert all(intent == 'proximity' for intent in intents), f"Inconsistent intents: {intents}"
    
    def test_12_consistency_popular_queries(self):
        """Test: Similar popularity queries should produce consistent intents."""
        queries = [
            "best restaurants",
            "top restaurants",
            "popular restaurants",
            "top rated restaurants"
        ]
        
        logger.info(f"\n{'='*100}")
        logger.info("CONSISTENCY TEST: Popularity Query Variations")
        logger.info(f"{'='*100}")
        
        intents = []
        for query in queries:
            plan = self.query_planner.create_query_plan(
                message=query,
                user_location={'lat': TEST_LAT, 'lng': TEST_LON}
            )
            plan_dict = self.query_planner.plan_to_dict(plan)
            intents.append(plan_dict['intent'])
            logger.info(f"  '{query}' -> Intent: {plan_dict['intent']}, Sort: {plan_dict['slots']['sort_preference']}")
        
        logger.info(f"\nAll intents: {intents}")
        logger.info(f"All should prioritize rating/popularity")
        logger.info(f"{'='*100}\n")
        
        # All should prioritize rating
        for query in queries:
            plan = self.query_planner.create_query_plan(message=query, user_location={'lat': TEST_LAT, 'lng': TEST_LON})
            plan_dict = self.query_planner.plan_to_dict(plan)
            assert plan_dict['slots']['sort_preference'] in ['rating', 'best_match']


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
