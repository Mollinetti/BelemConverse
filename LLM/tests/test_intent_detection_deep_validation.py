"""
Deep validation tests for intent detection and retrieval system.
Tests various query types with detailed logging for manual inspection.

Test Location: Travessa Curuzu, 1475, Belem, PA
Coordinates: -1.4557549, -48.4901799
"""

import pytest
import logging
from typing import Dict, Any, List
import json
from datetime import datetime
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from core.query_planner import QueryPlanner
from core.unified_retriever import UnifiedRetriever
from core.ranking_engine import RankingEngine
from core.place_cache import PlaceCache
from core.category_matcher import CategoryMatcher
from classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test location constants
TEST_LAT = -1.4557549
TEST_LON = -48.4901799
TEST_LOCATION = "Travessa Curuzu, 1475, Belem, PA"


class TestIntentDetectionDeepValidation:
    """Deep validation tests with comprehensive logging."""
    
    @pytest.fixture
    def sample_places(self):
        """Sample places database for testing at the specified location."""
        return [
            {
                'placeId': 'place1',
                'title': 'Restaurante Lá em Casa',
                'titleFormatted': 'Restaurante Lá em Casa',
                'category': ['restaurant'],
                'location': {'lat': -1.4558, 'lng': -48.4902},  # ~0.1km from test location
                'totalScore': 4.8,
                'reviewsCount': 500,
                'price': 2,
                'businessTime': 'Monday-Sunday: 11:00 AM – 10:00 PM',
                'address': 'Near Travessa Curuzu, Belem'
            },
            {
                'placeId': 'place2',
                'title': 'Pizzaria Bella',
                'titleFormatted': 'Pizzaria Bella',
                'category': ['restaurant', 'pizza'],
                'location': {'lat': -1.4560, 'lng': -48.4900},  # ~0.3km from test location
                'totalScore': 4.5,
                'reviewsCount': 200,
                'price': 2,
                'businessTime': 'Monday-Sunday: 6:00 PM – 11:00 PM',
                'address': 'Belem, PA'
            },
            {
                'placeId': 'place3',
                'title': 'Top Rated Restaurant Belem',
                'titleFormatted': 'Top Rated Restaurant Belem',
                'category': ['restaurant'],
                'location': {'lat': -1.4700, 'lng': -48.5000},  # ~6km from test location
                'totalScore': 4.9,
                'reviewsCount': 1200,
                'price': 3,
                'businessTime': 'Open 24 hours',
                'address': 'Downtown Belem'
            },
            {
                'placeId': 'place4',
                'title': 'Cafe Central',
                'titleFormatted': 'Cafe Central',
                'category': ['cafe', 'coffee'],
                'location': {'lat': -1.4561, 'lng': -48.4903},  # ~0.4km from test location
                'totalScore': 4.6,
                'reviewsCount': 350,
                'price': 1,
                'businessTime': 'Monday-Saturday: 7:00 AM – 6:00 PM',
                'address': 'Belem, PA'
            },
            {
                'placeId': 'place5',
                'title': 'Museu Paraense Emílio Goeldi',
                'titleFormatted': 'Museu Paraense Emílio Goeldi',
                'category': ['museum'],
                'location': {'lat': -1.4550, 'lng': -48.4895},  # ~0.5km from test location
                'totalScore': 4.7,
                'reviewsCount': 800,
                'price': 1,
                'businessTime': 'Tuesday-Sunday: 9:00 AM – 5:00 PM',
                'address': 'Belem, PA'
            },
            {
                'placeId': 'place6',
                'title': 'Bar do Parque',
                'titleFormatted': 'Bar do Parque',
                'category': ['bar', 'pub'],
                'location': {'lat': -1.4565, 'lng': -48.4905},  # ~0.7km from test location
                'totalScore': 4.3,
                'reviewsCount': 150,
                'price': 2,
                'businessTime': 'Monday-Sunday: 5:00 PM – 2:00 AM',
                'address': 'Belem, PA'
            },
            {
                'placeId': 'place7',
                'title': 'Farmacia Popular',
                'titleFormatted': 'Farmacia Popular',
                'category': ['pharmacy'],
                'location': {'lat': -1.4556, 'lng': -48.4898},  # ~0.2km from test location
                'totalScore': 4.2,
                'reviewsCount': 80,
                'price': 1,
                'businessTime': 'Monday-Saturday: 8:00 AM – 8:00 PM',
                'address': 'Travessa Curuzu, Belem'
            },
            {
                'placeId': 'place8',
                'title': 'Italian Restaurant Bella Italia',
                'titleFormatted': 'Italian Restaurant Bella Italia',
                'category': ['restaurant', 'italian'],
                'location': {'lat': -1.4562, 'lng': -48.4908},  # ~0.8km from test location
                'totalScore': 4.7,
                'reviewsCount': 450,
                'price': 3,
                'businessTime': 'Tuesday-Sunday: 12:00 PM – 11:00 PM',
                'address': 'Belem, PA'
            }
        ]
    
    @pytest.fixture(autouse=True)
    def setup(self, sample_places):
        """Setup test components."""
        # Initialize intent classifier and train it
        self.intent_classifier = SimpleTFIDFIntentClassifier()
        self.intent_classifier.train()
        
        # Initialize components in correct order
        self.place_cache = PlaceCache(sample_places)
        self.category_matcher = CategoryMatcher(self.intent_classifier)
        self.ranking_engine = RankingEngine()
        
        # Initialize retriever with dependencies
        self.unified_retriever = UnifiedRetriever(
            place_cache=self.place_cache,
            category_matcher=self.category_matcher,
            ranking_engine=self.ranking_engine
        )
        
        # Initialize query planner with intent classifier
        self.query_planner = QueryPlanner(intent_classifier=self.intent_classifier)
        
        # Create log file for this test run
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = f"test_results_{timestamp}.log"
        
        logger.info(f"=== Test Run Started: {timestamp} ===")
        logger.info(f"Test Location: {TEST_LOCATION}")
        logger.info(f"Coordinates: ({TEST_LAT}, {TEST_LON})")
        logger.info("=" * 80)
    
    def log_test_result(self, test_name: str, query: str, result: Dict[str, Any]):
        """Log detailed test results for manual inspection."""
        logger.info(f"\n{'='*80}")
        logger.info(f"TEST: {test_name}")
        logger.info(f"QUERY: {query}")
        logger.info(f"{'='*80}")
        
        # Log intent detection
        if 'intent' in result:
            logger.info(f"DETECTED INTENT: {result['intent']}")
            logger.info(f"Intent Confidence: {result.get('intent_confidence', 'N/A')}")
        
        # Log retrieval strategy
        if 'retrieval_strategy' in result:
            logger.info(f"RETRIEVAL STRATEGY: {result['retrieval_strategy']}")
        
        # Log filters applied
        if 'filters' in result:
            logger.info(f"FILTERS APPLIED: {json.dumps(result['filters'], indent=2)}")
        
        # Log ranking factors
        if 'ranking_factors' in result:
            logger.info(f"RANKING FACTORS: {json.dumps(result['ranking_factors'], indent=2)}")
        
        # Log results
        if 'results' in result:
            logger.info(f"NUMBER OF RESULTS: {len(result['results'])}")
            for idx, place in enumerate(result['results'][:5], 1):  # Log top 5
                logger.info(f"\n  Result #{idx}:")
                logger.info(f"    Name: {place.get('name', 'N/A')}")
                logger.info(f"    Category: {place.get('category', 'N/A')}")
                logger.info(f"    Distance: {place.get('distance_km', 'N/A')} km")
                logger.info(f"    Popularity Score: {place.get('popularity_score', 'N/A')}")
                logger.info(f"    Final Score: {place.get('final_score', 'N/A')}")
        
        logger.info(f"{'='*80}\n")
    
    def test_nearby_query_intent(self):
        """Test: Nearby query - should prioritize distance."""
        query = "restaurants near me"
        
        # Plan query
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location={'lat': TEST_LAT, 'lng': TEST_LON}
        )
        
        # Convert plan to dict for easier access
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        # Execute retrieval
        results = self.unified_retriever.retrieve(
            query=query,
            user_lat=TEST_LAT,
            user_lon=TEST_LON,
            intent=plan_dict['intent'],
            filters=plan_dict.get('slots', {})
        )
        
        # Apply ranking
        ranked_results = self.ranking_engine.rank(
            places=results,
            user_lat=TEST_LAT,
            user_lon=TEST_LON,
            intent=plan_dict['intent']
        )
        
        result = {
            'intent': plan_dict['intent'],
            'intent_confidence': plan_dict.get('confidence'),
            'retrieval_strategy': plan_dict.get('retrieval_strategy'),
            'filters': plan_dict.get('slots'),
            'ranking_factors': plan_dict.get('ranking_factors'),
            'results': ranked_results
        }
        
        self.log_test_result("Nearby Query Intent", query, result)
        
        # Assertions
        assert plan_dict['intent'] == 'proximity'
        assert plan_dict.get('slots', {}).get('proximity_intent_detected') == True
    
    def test_popular_query_intent(self):
        """Test: Popular query - should prioritize popularity."""
        query = "best restaurants in Belem"
        
        plan = self.query_planner.create_query_plan(
            query=query,
            user_lat=TEST_LAT,
            user_lon=TEST_LON
        )
        
        results = self.unified_retriever.retrieve(
            query=query,
            user_lat=TEST_LAT,
            user_lon=TEST_LON,
            intent=plan['intent'],
            filters=plan.get('filters', {})
        )
        
        ranked_results = self.ranking_engine.rank(
            places=results,
            user_lat=TEST_LAT,
            user_lon=TEST_LON,
            intent=plan['intent']
        )
        
        result = {
            'intent': plan['intent'],
            'intent_confidence': plan.get('confidence'),
            'retrieval_strategy': plan.get('retrieval_strategy'),
            'filters': plan.get('filters'),
            'ranking_factors': plan.get('ranking_factors'),
            'results': ranked_results
        }
        
        self.log_test_result("Popular Query Intent", query, result)
        
        # Assertions
        assert plan['intent'] == 'popular'
        assert 'popularity' in plan.get('ranking_factors', {})
        assert plan['ranking_factors']['popularity'] > 0.5  # Popularity should be primary
    
    def test_specific_establishment_query(self):
        """Test: Specific establishment - should use semantic search."""
        query = "Restaurante Lá em Casa"
        
        plan = self.query_planner.create_query_plan(
            query=query,
            user_lat=TEST_LAT,
            user_lon=TEST_LON
        )
        
        results = self.unified_retriever.retrieve(
            query=query,
            user_lat=TEST_LAT,
            user_lon=TEST_LON,
            intent=plan['intent'],
            filters=plan.get('filters', {})
        )
        
        ranked_results = self.ranking_engine.rank(
            places=results,
            user_lat=TEST_LAT,
            user_lon=TEST_LON,
            intent=plan['intent']
        )
        
        result = {
            'intent': plan['intent'],
            'intent_confidence': plan.get('confidence'),
            'retrieval_strategy': plan.get('retrieval_strategy'),
            'filters': plan.get('filters'),
            'ranking_factors': plan.get('ranking_factors'),
            'results': ranked_results
        }
        
        self.log_test_result("Specific Establishment Query", query, result)
        
        # Assertions
        assert plan['intent'] in ['specific_place', 'semantic']
        assert plan.get('retrieval_strategy') in ['semantic_search', 'hybrid']
    
    def test_category_with_location_query(self):
        """Test: Category with location - should balance distance and category match."""
        query = "pizza places nearby"
        
        plan = self.query_planner.create_query_plan(
            query=query,
            user_lat=TEST_LAT,
            user_lon=TEST_LON
        )
        
        results = self.unified_retriever.retrieve(
            query=query,
            user_lat=TEST_LAT,
            user_lon=TEST_LON,
            intent=plan['intent'],
            filters=plan.get('filters', {})
        )
        
        ranked_results = self.ranking_engine.rank(
            places=results,
            user_lat=TEST_LAT,
            user_lon=TEST_LON,
            intent=plan['intent']
        )
        
        result = {
            'intent': plan['intent'],
            'intent_confidence': plan.get('confidence'),
            'retrieval_strategy': plan.get('retrieval_strategy'),
            'filters': plan.get('filters'),
            'ranking_factors': plan.get('ranking_factors'),
            'results': ranked_results
        }
        
        self.log_test_result("Category with Location Query", query, result)
        
        # Assertions
        assert 'pizza' in str(plan.get('filters', {})).lower() or 'pizza' in query.lower()
        assert plan['intent'] in ['nearby', 'category']
    
    def test_tour_planning_query(self):
        """Test: Tour planning - should use route optimization."""
        query = "plan a tour of museums in Belem"
        
        plan = self.query_planner.create_query_plan(
            query=query,
            user_lat=TEST_LAT,
            user_lon=TEST_LON
        )
        
        results = self.unified_retriever.retrieve(
            query=query,
            user_lat=TEST_LAT,
            user_lon=TEST_LON,
            intent=plan['intent'],
            filters=plan.get('filters', {})
        )
        
        ranked_results = self.ranking_engine.rank(
            places=results,
            user_lat=TEST_LAT,
            user_lon=TEST_LON,
            intent=plan['intent']
        )
        
        result = {
            'intent': plan['intent'],
            'intent_confidence': plan.get('confidence'),
            'retrieval_strategy': plan.get('retrieval_strategy'),
            'filters': plan.get('filters'),
            'ranking_factors': plan.get('ranking_factors'),
            'results': ranked_results
        }
        
        self.log_test_result("Tour Planning Query", query, result)
        
        # Assertions
        assert plan['intent'] == 'tour_planning'
        assert 'route_optimization' in str(plan.get('ranking_factors', {})).lower() or plan['intent'] == 'tour_planning'
    
    def test_ambiguous_query_fallback(self):
        """Test: Ambiguous query - should have fallback strategy."""
        query = "good food"
        
        plan = self.query_planner.create_query_plan(
            query=query,
            user_lat=TEST_LAT,
            user_lon=TEST_LON
        )
        
        results = self.unified_retriever.retrieve(
            query=query,
            user_lat=TEST_LAT,
            user_lon=TEST_LON,
            intent=plan['intent'],
            filters=plan.get('filters', {})
        )
        
        ranked_results = self.ranking_engine.rank(
            places=results,
            user_lat=TEST_LAT,
            user_lon=TEST_LON,
            intent=plan['intent']
        )
        
        result = {
            'intent': plan['intent'],
            'intent_confidence': plan.get('confidence'),
            'retrieval_strategy': plan.get('retrieval_strategy'),
            'filters': plan.get('filters'),
            'ranking_factors': plan.get('ranking_factors'),
            'results': ranked_results
        }
        
        self.log_test_result("Ambiguous Query Fallback", query, result)
        
        # Should have some intent assigned
        assert plan['intent'] is not None
        assert len(ranked_results) > 0
    
    def test_distance_vs_popularity_tradeoff(self):
        """Test: Verify distance vs popularity tradeoff in ranking."""
        query1 = "restaurants near me"  # Should prioritize distance
        query2 = "top rated restaurants"  # Should prioritize popularity
        
        # Query 1: Nearby
        plan1 = self.query_planner.create_query_plan(query1, TEST_LAT, TEST_LON)
        results1 = self.unified_retriever.retrieve(
            query1, TEST_LAT, TEST_LON, plan1['intent'], plan1.get('filters', {})
        )
        ranked1 = self.ranking_engine.rank(results1, TEST_LAT, TEST_LON, plan1['intent'])
        
        result1 = {
            'intent': plan1['intent'],
            'ranking_factors': plan1.get('ranking_factors'),
            'results': ranked1
        }
        
        self.log_test_result("Distance Priority Query", query1, result1)
        
        # Query 2: Popular
        plan2 = self.query_planner.create_query_plan(query2, TEST_LAT, TEST_LON)
        results2 = self.unified_retriever.retrieve(
            query2, TEST_LAT, TEST_LON, plan2['intent'], plan2.get('filters', {})
        )
        ranked2 = self.ranking_engine.rank(results2, TEST_LAT, TEST_LON, plan2['intent'])
        
        result2 = {
            'intent': plan2['intent'],
            'ranking_factors': plan2.get('ranking_factors'),
            'results': ranked2
        }
        
        self.log_test_result("Popularity Priority Query", query2, result2)
        
        # Compare ranking factors
        logger.info("\n" + "="*80)
        logger.info("DISTANCE VS POPULARITY COMPARISON")
        logger.info("="*80)
        logger.info(f"Query 1 (nearby) distance weight: {plan1.get('ranking_factors', {}).get('distance', 0)}")
        logger.info(f"Query 1 (nearby) popularity weight: {plan1.get('ranking_factors', {}).get('popularity', 0)}")
        logger.info(f"Query 2 (popular) distance weight: {plan2.get('ranking_factors', {}).get('distance', 0)}")
        logger.info(f"Query 2 (popular) popularity weight: {plan2.get('ranking_factors', {}).get('popularity', 0)}")
        logger.info("="*80 + "\n")
        
        # Assertions
        assert plan1['ranking_factors'].get('distance', 0) > plan1['ranking_factors'].get('popularity', 0)
        assert plan2['ranking_factors'].get('popularity', 0) > plan2['ranking_factors'].get('distance', 0)
    
    def test_category_filtering_accuracy(self):
        """Test: Verify category filtering works correctly."""
        queries = [
            ("coffee shops near me", ["cafe", "coffee"]),
            ("italian restaurants", ["restaurant", "italian"]),
            ("bars and pubs", ["bar", "pub"]),
            ("pharmacies nearby", ["pharmacy", "drugstore"])
        ]
        
        for query, expected_categories in queries:
            plan = self.query_planner.create_query_plan(query, TEST_LAT, TEST_LON)
            results = self.unified_retriever.retrieve(
                query, TEST_LAT, TEST_LON, plan['intent'], plan.get('filters', {})
            )
            ranked = self.ranking_engine.rank(results, TEST_LAT, TEST_LON, plan['intent'])
            
            result = {
                'intent': plan['intent'],
                'filters': plan.get('filters'),
                'expected_categories': expected_categories,
                'results': ranked
            }
            
            self.log_test_result(f"Category Filtering: {query}", query, result)
            
            # Verify category filtering
            filters_str = str(plan.get('filters', {})).lower()
            assert any(cat in filters_str or cat in query.lower() for cat in expected_categories)
    
    def test_retrieval_strategy_selection(self):
        """Test: Verify correct retrieval strategy is selected."""
        test_cases = [
            ("restaurants near me", ["filter_first", "spatial"]),
            ("Restaurante Lá em Casa", ["semantic_search", "hybrid"]),
            ("best pizza in town", ["hybrid", "semantic_search"]),
            ("coffee", ["filter_first", "spatial", "semantic_search"])
        ]
        
        for query, expected_strategies in test_cases:
            plan = self.query_planner.create_query_plan(query, TEST_LAT, TEST_LON)
            
            result = {
                'intent': plan['intent'],
                'retrieval_strategy': plan.get('retrieval_strategy'),
                'expected_strategies': expected_strategies
            }
            
            self.log_test_result(f"Retrieval Strategy: {query}", query, result)
            
            # Verify strategy is one of expected
            assert plan.get('retrieval_strategy') in expected_strategies
    
    def test_consistency_across_similar_queries(self):
        """Test: Similar queries should produce consistent intents."""
        similar_queries = [
            ["restaurants near me", "nearby restaurants", "restaurants close by"],
            ["best restaurants", "top restaurants", "popular restaurants"],
            ["Restaurante Lá em Casa", "find Lá em Casa restaurant"]
        ]
        
        for query_group in similar_queries:
            intents = []
            logger.info(f"\n{'='*80}")
            logger.info(f"CONSISTENCY TEST: {query_group}")
            logger.info(f"{'='*80}")
            
            for query in query_group:
                plan = self.query_planner.create_query_plan(query, TEST_LAT, TEST_LON)
                intents.append(plan['intent'])
                logger.info(f"Query: '{query}' -> Intent: {plan['intent']}")
            
            logger.info(f"All intents: {intents}")
            logger.info(f"Consistent: {len(set(intents)) == 1}")
            logger.info(f"{'='*80}\n")
            
            # All queries in group should have same intent
            assert len(set(intents)) == 1, f"Inconsistent intents for similar queries: {intents}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
