"""
Test cases for Tour Planning Functionality.

Tests:
1. Açaí Morning Tour (EN) - Multiple açaí shops
2. Traditional Food Tour (PT) - Regional Amazonian cuisine
3. Tourist Attractions Tour (EN) - Parks, museums, monuments
4. Mixed Day Tour (EN) - Food + attractions combined
5. Evening Food & Bar Tour (PT) - Dinner and bar hopping
6. Vague Tour Request (EN) - Generic "plan a tour for me"
7. Vague Tour Request (PT) - Generic "planeje um passeio"
8. Beach/Waterfront Tour (PT) - Praia e orla
9. Historical/Cultural Tour (PT) - Museus e história
10. Family Tour (PT) - Passeio com crianças

Run with: python -m tests.test_tour_planning
"""

import sys
import os
import time
import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Configure logging to both console and file
LOG_FILE_PATH = Path(__file__).parent / "tour_planning_test_results.log"

# Create file handler
file_handler = logging.FileHandler(LOG_FILE_PATH, mode='w', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Configure root logger
logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
logger = logging.getLogger(__name__)


# User's home coordinates for location testing
USER_HOME_COORDS = (-1.4695, -48.4665)  # Marco's location in Belém

# Alternative tourist area coordinates
TOURIST_CENTER_COORDS = (-1.4558, -48.4902)  # Near Ver-o-Peso / Old Town


# Test case structure: (query, coordinates, categories, num_stops, duration_hours, description)
TOUR_TEST_CASES: List[Dict[str, Any]] = [
    # Test 1: Açaí Tour (English)
    {
        "query": "I want to spend my morning trying the best açaí places in Belém. Plan a route for me!",
        "coordinates": USER_HOME_COORDS,
        "categories": ["açaí", "acai", "ice cream", "sorveteria"],
        "num_stops": 4,
        "duration_hours": 4,
        "start_time": "08:00",
        "description": "Açaí Morning Tour (EN) - Visit 4 açaí shops in the morning"
    },
    
    # Test 2: Traditional Amazonian Food Tour (Portuguese)
    {
        "query": "Quero experimentar a comida tradicional paraense. Monte um roteiro de almoço com restaurantes típicos.",
        "coordinates": TOURIST_CENTER_COORDS,
        "categories": ["restaurant", "restaurante", "regional", "traditional"],
        "num_stops": 3,
        "duration_hours": 5,
        "start_time": "11:00",
        "description": "Traditional Food Lunch Tour (PT) - Restaurantes típicos amazônicos"
    },
    
    # Test 3: Tourist Attractions Tour (English)
    {
        "query": "I'm a tourist visiting Belém for one day. I want to see the main attractions like parks, museums, and monuments. Create an itinerary!",
        "coordinates": TOURIST_CENTER_COORDS,
        "categories": ["tourist_attraction", "museum", "park", "monument", "church", "teatro"],
        "num_stops": 5,
        "duration_hours": 8,
        "start_time": "09:00",
        "description": "Full Day Tourist Attractions (EN) - Parks, museums, monuments, churches"
    },
    
    # Test 4: Mixed Day Tour (English)
    {
        "query": "Plan a day for me: start with açaí for breakfast, visit some tourist spots, then have traditional lunch at a good restaurant, and end with a nice café.",
        "coordinates": USER_HOME_COORDS,
        "categories": ["açaí", "tourist_attraction", "restaurant", "cafe", "museum", "park"],
        "num_stops": 6,
        "duration_hours": 10,
        "start_time": "07:30",
        "description": "Mixed Day Tour (EN) - Açaí breakfast, attractions, traditional lunch, café"
    },
    
    # Test 5: Evening Food & Bar Tour (Portuguese)
    {
        "query": "Quero um roteiro para a noite: jantar em um bom restaurante e depois ir a alguns bares em Belém.",
        "coordinates": TOURIST_CENTER_COORDS,
        "categories": ["restaurant", "bar", "pub", "drinks"],
        "num_stops": 4,
        "duration_hours": 5,
        "start_time": "19:00",
        "description": "Evening Food & Bar Tour (PT) - Jantar e bares"
    },
    
    # Test 6: VAGUE TOUR REQUEST (English)
    {
        "query": "Plan a tour for me in Belém. I have one day.",
        "coordinates": USER_HOME_COORDS,
        "categories": None,  # Should default to tourist + restaurants
        "num_stops": 6,
        "duration_hours": 8,
        "start_time": "09:00",
        "description": "Vague Tour Request (EN) - Should mix tourist attractions + restaurants"
    },
    
    # Test 7: VAGUE TOUR REQUEST (Portuguese)
    {
        "query": "Planeje um passeio para mim em Belém. O que devo visitar?",
        "coordinates": TOURIST_CENTER_COORDS,
        "categories": None,  # Should default to tourist + restaurants
        "num_stops": 6,
        "duration_hours": 8,
        "start_time": "09:00",
        "description": "Vague Tour Request (PT) - Deveria misturar pontos turísticos + restaurantes"
    },
    
    # Test 8: Generic "What to do" request (Portuguese)
    {
        "query": "O que fazer em Belém em um dia? Quero conhecer a cidade!",
        "coordinates": TOURIST_CENTER_COORDS,
        "categories": None,  # Should default to tourist + restaurants
        "num_stops": 5,
        "duration_hours": 8,
        "start_time": "10:00",
        "description": "What To Do Request (PT) - Conhecer a cidade"
    },
    
    # Test 9: Historical/Cultural Tour (Portuguese)
    {
        "query": "Quero conhecer a história de Belém. Me leve aos museus, igrejas antigas e lugares históricos.",
        "coordinates": TOURIST_CENTER_COORDS,
        "categories": ["museum", "church", "historical", "monument", "memorial"],
        "num_stops": 5,
        "duration_hours": 6,
        "start_time": "09:00",
        "description": "Historical/Cultural Tour (PT) - Museus, igrejas e história"
    },
    
    # Test 10: Family Tour with Parks (Portuguese)
    {
        "query": "Estou em Belém com minha família e crianças. Planeje um passeio com parques, lugares divertidos e um almoço.",
        "coordinates": USER_HOME_COORDS,
        "categories": ["park", "parque", "ecological", "zoo", "restaurant"],
        "num_stops": 4,
        "duration_hours": 6,
        "start_time": "09:30",
        "description": "Family Tour (PT) - Parques e lugares para crianças"
    }
]


class TourPlanningTester:
    """Test runner for tour planning functionality."""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.agent = None
        self.tour_planner = None
    
    def initialize(self):
        """Initialize the RAG agent and tour planner."""
        logger.info("Initializing RAG agent and Tour Planner...")
        
        try:
            from data.vector_store import VectorStoreManager
            from utils.models import ModelManager
            from core.enhanced_rag_agent import EnhancedRAGAgent
            from data.data_loader import DataLoader
            
            # Initialize vector store
            logger.info("Loading vector store...")
            vector_store_manager = VectorStoreManager()
            
            # Initialize LLM model
            logger.info("Loading LLM model...")
            llm_model = ModelManager.get_llm()
            
            # Initialize RAG Agent
            logger.info("Setting up Enhanced RAG Agent...")
            self.agent = EnhancedRAGAgent(
                vector_store_manager=vector_store_manager,
                llm_model=llm_model
            )
            
            # Get the tour planner from the agent
            if hasattr(self.agent, 'tour_planner'):
                self.tour_planner = self.agent.tour_planner
                logger.info("Tour planner initialized from agent")
            else:
                # Initialize tour planner separately
                from core.tour_planner import TourPlanner
                data_loader = DataLoader()
                self.tour_planner = TourPlanner(data_loader)
                logger.info("Tour planner initialized separately")
            
            logger.info("Initialization complete!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def run_tour_test(
        self,
        test_num: int,
        query: str,
        coordinates: Tuple[float, float],
        categories: List[str],
        num_stops: int,
        duration_hours: int,
        start_time: str,
        description: str
    ) -> Dict[str, Any]:
        """Run a single tour planning test."""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST {test_num}: {description}")
        logger.info(f"Query: '{query}'")
        logger.info(f"Coordinates: {coordinates}")
        logger.info(f"Categories: {categories}")
        logger.info(f"Stops: {num_stops}, Duration: {duration_hours}h, Start: {start_time}")
        logger.info(f"{'='*60}")
        
        result = {
            "test_num": test_num,
            "description": description,
            "query": query,
            "coordinates": coordinates,
            "categories": categories,
            "num_stops": num_stops,
            "duration_hours": duration_hours,
            "start_time": start_time,
            "passed": False,
            "itinerary": None,
            "llm_response": None,
            "error": None,
            "response_time": 0
        }
        
        start = time.time()
        itinerary = None  # Initialize for vague requests
        
        try:
            # Test 1: Direct tour planner test (only if categories specified)
            if categories is not None:
                logger.info("\n--- Testing Tour Planner Directly ---")
                
                itinerary = self.tour_planner.plan_tour(
                    user_coordinates=coordinates,
                    duration_hours=duration_hours,
                    start_time=start_time,
                    categories=categories,
                    num_stops=num_stops,
                    day_of_week=datetime.now().strftime('%A')
                )
                
                result["itinerary"] = {
                    "num_stops": len(itinerary.stops),
                    "total_distance_km": itinerary.total_distance_km,
                    "total_duration_minutes": itinerary.total_duration_minutes,
                    "stops": [s.to_dict() for s in itinerary.stops]
                }
                
                logger.info(f"\nItinerary created with {len(itinerary.stops)} stops:")
                logger.info(f"Total Distance: {itinerary.total_distance_km:.2f} km")
                logger.info(f"Total Duration: {itinerary.total_duration_minutes} minutes")
                
                for i, stop in enumerate(itinerary.stops, 1):
                    logger.info(f"\n  Stop {i}: {stop.name}")
                    logger.info(f"    Category: {stop.category}")
                    logger.info(f"    Address: {stop.address}")
                    logger.info(f"    Rating: {stop.rating}★ ({stop.review_count} reviews)")
                    if stop.arrival_time:
                        logger.info(f"    Arrival: {stop.arrival_time.strftime('%I:%M %p')}")
                    if stop.departure_time:
                        logger.info(f"    Departure: {stop.departure_time.strftime('%I:%M %p')}")
                    logger.info(f"    Duration: {stop.duration_minutes} min")
                    if stop.distance_to_next > 0:
                        logger.info(f"    Travel to next: {stop.distance_to_next:.2f} km (~{stop.travel_time_to_next} min)")
            else:
                logger.info("\n--- Vague Request: Skipping direct tour planner test ---")
                logger.info("Testing full agent response for default category handling...")
            
            # Test 2: Full LLM response test (always run)
            logger.info("\n--- Testing Full LLM Response ---")
            
            response = self.agent.query(
                question=query,
                user_coordinates=coordinates
            )
            
            result["llm_response"] = response
            
            logger.info(f"\n{'='*60}")
            logger.info(f"FULL LLM RESPONSE FOR TEST {test_num}:")
            logger.info(f"{'='*60}")
            logger.info(response)
            logger.info(f"{'='*60}")
            
            # Evaluate results
            result["passed"] = self._evaluate_tour_result(result, itinerary)
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Test {test_num} failed with error: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        result["response_time"] = time.time() - start
        logger.info(f"\nTest {test_num} completed in {result['response_time']:.2f}s")
        logger.info(f"Result: {'✓ PASSED' if result['passed'] else '✗ FAILED'}")
        
        return result
    
    def _evaluate_tour_result(
        self,
        result: Dict[str, Any],
        itinerary
    ) -> bool:
        """Evaluate if the tour planning test passed."""
        checks = []
        is_vague_request = result.get("categories") is None
        
        # For vague requests, check LLM response; for specific, check itinerary
        if itinerary is not None:
            # Check 1: Itinerary has stops
            has_stops = len(itinerary.stops) > 0
            checks.append(("has_stops", has_stops))
            
            # Check 2: Reasonable number of stops
            expected_stops = result["num_stops"]
            actual_stops = len(itinerary.stops)
            reasonable_stops = actual_stops >= 1 and actual_stops <= expected_stops + 2
            checks.append(("reasonable_stops", reasonable_stops))
            
            # Check 3: Total distance is reasonable (not > 20km for a walking tour)
            reasonable_distance = itinerary.total_distance_km < 20
            checks.append(("reasonable_distance", reasonable_distance))
        
        # Check 4: LLM response exists
        has_llm_response = result.get("llm_response") is not None
        checks.append(("has_llm_response", has_llm_response))
        
        # Check 5: LLM response is not an error message
        if result.get("llm_response"):
            response_lower = result["llm_response"].lower()
            not_error = "unfortunately" not in response_lower[:100]
            checks.append(("not_error_response", not_error))
            
            # Check 6: For vague requests, verify we have a mix of attractions and restaurants
            if is_vague_request:
                # Look for tourist attraction keywords in response
                tourist_keywords = ['museum', 'museu', 'theater', 'teatro', 'park', 'parque', 
                                   'fort', 'forte', 'church', 'igreja', 'mercado', 'market',
                                   'mangal', 'palacete', 'ecological']
                restaurant_keywords = ['restaurant', 'restaurante', 'lunch', 'almoço',
                                       'dinner', 'jantar', 'pizza', 'buffet', 'seafood']
                
                has_tourist = any(kw in response_lower for kw in tourist_keywords)
                has_restaurant = any(kw in response_lower for kw in restaurant_keywords)
                
                checks.append(("has_tourist_attractions", has_tourist))
                checks.append(("has_restaurants", has_restaurant))
                
                if has_tourist and has_restaurant:
                    checks.append(("is_mixed_tour", True))
                    logger.info("  ✓ Vague request correctly returned mixed tour!")
                else:
                    checks.append(("is_mixed_tour", False))
                    logger.info(f"  ✗ Vague request should have mixed results (tourist: {has_tourist}, restaurant: {has_restaurant})")
        
        # Log check results
        for check_name, check_result in checks:
            status = "✓" if check_result else "✗"
            logger.info(f"  {status} {check_name}")
        
        # Pass if most checks pass
        passed_checks = sum(1 for _, passed in checks if passed)
        return passed_checks >= len(checks) * 0.6  # 60% threshold
    
    def run_all_tests(self):
        """Run all tour planning tests."""
        logger.info("\n" + "="*70)
        logger.info("STARTING TOUR PLANNING TESTS")
        logger.info("="*70)
        
        for i, test_case in enumerate(TOUR_TEST_CASES, 1):
            result = self.run_tour_test(
                test_num=i,
                query=test_case["query"],
                coordinates=test_case["coordinates"],
                categories=test_case["categories"],
                num_stops=test_case["num_stops"],
                duration_hours=test_case["duration_hours"],
                start_time=test_case["start_time"],
                description=test_case["description"]
            )
            self.results.append(result)
            
            # Small delay between tests
            if i < len(TOUR_TEST_CASES):
                time.sleep(1)
        
        self._generate_summary()
    
    def _generate_summary(self):
        """Generate test summary."""
        logger.info("\n" + "="*70)
        logger.info("TOUR PLANNING TEST SUMMARY")
        logger.info("="*70)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed
        
        logger.info(f"Total tests: {total}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Pass rate: {passed/total*100:.1f}%")
        
        avg_time = sum(r["response_time"] for r in self.results) / total if total > 0 else 0
        logger.info(f"Average response time: {avg_time:.2f}s")
        
        logger.info("\n" + "="*70)
        logger.info("DETAILED RESULTS")
        logger.info("="*70)
        
        for r in self.results:
            status = "✓ PASSED" if r["passed"] else "✗ FAILED"
            logger.info(f"\nTest {r['test_num']}: {r['description']}")
            logger.info(f"  Status: {status}")
            logger.info(f"  Query: {r['query'][:50]}...")
            logger.info(f"  Time: {r['response_time']:.2f}s")
            
            if r.get("itinerary"):
                itin = r["itinerary"]
                logger.info(f"  Stops: {itin['num_stops']}")
                logger.info(f"  Distance: {itin['total_distance_km']:.2f} km")
                logger.info(f"  Duration: {itin['total_duration_minutes']} min")
                
                if itin.get("stops"):
                    logger.info("  Stop names:")
                    for stop in itin["stops"]:
                        logger.info(f"    - {stop['name']} ({stop['category']})")
            
            if r.get("error"):
                logger.info(f"  Error: {r['error']}")
        
        # Write summary to separate file
        summary_path = Path(__file__).parent / "tour_planning_summary.txt"
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("TOUR PLANNING TEST SUMMARY\n")
            f.write("="*50 + "\n\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total tests: {total}\n")
            f.write(f"Passed: {passed}\n")
            f.write(f"Failed: {failed}\n")
            f.write(f"Pass rate: {passed/total*100:.1f}%\n")
            f.write(f"Average time: {avg_time:.2f}s\n\n")
            
            for r in self.results:
                f.write(f"\nTest {r['test_num']}: {r['description']}\n")
                f.write(f"  Status: {'PASSED' if r['passed'] else 'FAILED'}\n")
                f.write(f"  Query: {r['query']}\n")
                
                if r.get("llm_response"):
                    f.write(f"\n  LLM Response:\n")
                    f.write("-"*40 + "\n")
                    f.write(r["llm_response"])
                    f.write("\n" + "-"*40 + "\n")
        
        logger.info(f"\nSummary saved to: {summary_path}")
        logger.info(f"Full logs saved to: {LOG_FILE_PATH}")


def main():
    """Main entry point."""
    tester = TourPlanningTester()
    
    if not tester.initialize():
        logger.error("Failed to initialize. Exiting.")
        sys.exit(1)
    
    tester.run_all_tests()


if __name__ == "__main__":
    main()

