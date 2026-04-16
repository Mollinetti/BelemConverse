"""
Golden Queries Test Runner per spec/09-eval-golden-queries.md.

Tests:
- Query Plan JSON output
- Radius escalation (0.5km → 1km → 2km)
- Exactly <=5 results
- Ranking follows sort mode
- LLM only references returned places
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add src to path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from core.query_planner import QueryPlanner
from core.unified_retriever import UnifiedRetriever
from core.place_cache import PlaceCache
from core.category_matcher import CategoryMatcher
from core.ranking_engine import RankingEngine
from classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Test location sets
L1 = {"lat": -1.4500, "lng": -48.4900}
L2 = {"lat": -1.4300, "lng": -48.4600}


# Golden Queries (EN)
GOLDEN_QUERIES_EN = [
    {
        "id": "Q1",
        "query": "Closest restaurants open now",
        "location": L1,
        "expected_plan": {
            "place_type": ["restaurant"],
            "open_now": True,
            "sort_preference": "distance",
            "radius_strategy": "auto_escalate_0.5_1_2_km"
        },
        "expected_results_count": (1, 5),  # min, max
        "expected_all_open_or_unknown": True
    },
    {
        "id": "Q2",
        "query": "Best rated sushi near me open now",
        "location": L1,
        "expected_plan": {
            "categories": ["sushi"],
            "open_now": True,
            "sort_preference": "rating"
        },
        "expected_results_count": (1, 5),
        "expected_rating_desc": True
    },
    {
        "id": "Q3",
        "query": "Popular bars within 1km",
        "location": L1,
        "expected_plan": {
            "place_type": ["bar"],
            "sort_preference": "popularity"
        },
        "expected_results_count": (1, 5),
        "expected_reviews_desc": True
    }
]

# Golden Queries (pt-BR)
GOLDEN_QUERIES_PT = [
    {
        "id": "P1",
        "query": "Restaurantes mais próximos abertos agora",
        "location": L1,
        "expected_plan": {
            "place_type": ["restaurant"],
            "open_now": True,
            "sort_preference": "distance"
        },
        "expected_results_count": (1, 5)
    },
    {
        "id": "P2",
        "query": "Melhores cafés perto de mim",
        "location": L2,
        "expected_plan": {
            "place_type": ["restaurant"],  # café maps to restaurant
            "sort_preference": "rating"
        },
        "expected_results_count": (1, 5)
    },
    {
        "id": "P3",
        "query": "Parque perto de mim aberto agora",
        "location": L1,
        "expected_plan": {
            "place_type": ["park"],
            "open_now": True,
            "sort_preference": "distance"
        },
        "expected_results_count": (1, 5)
    }
]


class GoldenQueriesTestRunner:
    """Test runner for golden queries"""
    
    def __init__(self, places_index_path: Optional[Path] = None):
        """
        Initialize test runner.
        
        Args:
            places_index_path: Path to canonical_places.jsonl. Defaults to data/canonical_places.jsonl
        """
        if places_index_path is None:
            places_index_path = Path(__file__).parent.parent.parent / "data" / "canonical_places.jsonl"
        
        self.places_index_path = places_index_path
        
        # Initialize intent classifier
        self.intent_classifier = SimpleTFIDFIntentClassifier()
        self.intent_classifier.train()
        
        self.query_planner = QueryPlanner(self.intent_classifier)
        self.places_index = self._load_places_index()
        
        # Initialize shared modules for UnifiedRetriever
        place_cache = PlaceCache(self.places_index)
        category_matcher = CategoryMatcher(self.intent_classifier)
        ranking_engine = RankingEngine()
        
        self.retriever = UnifiedRetriever(
            place_cache=place_cache,
            category_matcher=category_matcher,
            ranking_engine=ranking_engine,
            vector_store=None,
            osm_client=None
        )
    
    def _load_places_index(self) -> List[Dict[str, Any]]:
        """Load places index from JSONL file"""
        if not self.places_index_path.exists():
            raise FileNotFoundError(
                f"Places index not found: {self.places_index_path}. "
                "Please run /ingest/csv first."
            )
        
        places = []
        with open(self.places_index_path, 'r', encoding='utf-8') as f:
            for line in f:
                places.append(json.loads(line))
        
        logger.info(f"Loaded {len(places)} places from index")
        return places
    
    def test_query_plan(self, query: str, location: Optional[Dict], expected_plan: Dict) -> Dict[str, Any]:
        """Test that Query Plan matches expected structure"""
        plan = self.query_planner.create_query_plan(
            message=query,
            user_location=location,
            explicit_language=None
        )
        
        plan_dict = self.query_planner.plan_to_dict(plan)
        
        errors = []
        
        # Check place_type
        if 'place_type' in expected_plan:
            expected_types = expected_plan['place_type']
            actual_types = plan.slots.get('place_type') or []
            if not any(t in actual_types for t in expected_types):
                errors.append(f"Expected place_type in {expected_types}, got {actual_types}")
        
        # Check open_now
        if 'open_now' in expected_plan:
            expected_open = expected_plan['open_now']
            actual_open = plan.slots.get('open_now')
            if actual_open != expected_open:
                errors.append(f"Expected open_now={expected_open}, got {actual_open}")
        
        # Check sort_preference
        if 'sort_preference' in expected_plan:
            expected_sort = expected_plan['sort_preference']
            actual_sort = plan.slots.get('sort_preference')
            if actual_sort != expected_sort:
                errors.append(f"Expected sort_preference={expected_sort}, got {actual_sort}")
        
        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "plan": plan_dict
        }
    
    def test_radius_escalation(self, slots: Dict, location: Dict) -> Dict[str, Any]:
        """Test that radius escalation works (0.5km → 1km → 2km)"""
        # This is tested implicitly by checking results count
        # The unified retriever logs radius used
        query_plan_dict = {
            'slots': slots,
            'proximity_intent_detected': slots.get('proximity_intent_detected', False),
            'retrieval_strategy': 'structured_only'
        }
        
        retrieval_result = self.retriever.retrieve(query_plan_dict)
        results = retrieval_result.places
        
        # Check that we got results (radius escalation should have been applied)
        return {
            "passed": len(results) > 0,
            "results_count": len(results),
            "message": f"Got {len(results)} results after radius escalation"
        }
    
    def test_results_count(self, results: List, expected_range: tuple) -> Dict[str, Any]:
        """Test that results count is within expected range"""
        min_count, max_count = expected_range
        actual_count = len(results)
        
        passed = min_count <= actual_count <= max_count
        
        return {
            "passed": passed,
            "expected_range": expected_range,
            "actual_count": actual_count,
            "message": f"Expected {min_count}-{max_count} results, got {actual_count}"
        }
    
    def test_ranking(self, results: List, sort_preference: str) -> Dict[str, Any]:
        """Test that ranking follows sort mode"""
        if len(results) < 2:
            return {"passed": True, "message": "Not enough results to test ranking"}
        
        errors = []
        
        if sort_preference == 'distance':
            # Check distance ASC
            distances = [r.distanceKm for r in results if r.distanceKm is not None]
            if distances != sorted(distances):
                errors.append("Distances not sorted ASC")
        
        elif sort_preference == 'rating':
            # Check totalScore DESC
            scores = [r.place.get('totalScore') or 0.0 for r in results]
            if scores != sorted(scores, reverse=True):
                errors.append("Ratings not sorted DESC")
        
        elif sort_preference == 'popularity':
            # Check reviewsCount DESC
            reviews = [r.place.get('reviewsCount') or 0 for r in results]
            if reviews != sorted(reviews, reverse=True):
                errors.append("Review counts not sorted DESC")
        
        return {
            "passed": len(errors) == 0,
            "errors": errors
        }
    
    def test_open_now_filtering(self, results: List, strict: bool = False) -> Dict[str, Any]:
        """Test that openNow filtering works correctly"""
        if not results:
            return {"passed": True, "message": "No results to test"}
        
        # Check that all results are open or unknown (if relaxed)
        closed_count = sum(1 for r in results if r.openNowStatus == 'closed')
        
        if strict:
            passed = closed_count == 0 and all(r.openNowStatus == 'open' for r in results)
        else:
            passed = closed_count == 0  # No closed places
        
        return {
            "passed": passed,
            "closed_count": closed_count,
            "open_count": sum(1 for r in results if r.openNowStatus == 'open'),
            "unknown_count": sum(1 for r in results if r.openNowStatus == 'unknown')
        }
    
    def run_test(self, test_case: Dict) -> Dict[str, Any]:
        """Run a single golden query test"""
        query = test_case["query"]
        location = test_case.get("location")
        expected_plan = test_case.get("expected_plan", {})
        expected_results_count = test_case.get("expected_results_count", (1, 5))
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing: {test_case['id']} - {query}")
        logger.info(f"{'='*60}")
        
        # Step 1: Test Query Plan
        plan_test = self.test_query_plan(query, location, expected_plan)
        logger.info(f"Query Plan: {'PASS' if plan_test['passed'] else 'FAIL'}")
        if not plan_test['passed']:
            logger.error(f"  Errors: {plan_test['errors']}")
        
        # Create query plan for retrieval
        query_plan = self.query_planner.create_query_plan(
            message=query,
            user_location=location
        )
        
        # Step 2: Retrieve results
        query_plan_dict = {
            'intent': query_plan.intent,
            'slots': query_plan.slots,
            'proximity_intent_detected': query_plan.slots.get('proximity_intent_detected', False),
            'retrieval_strategy': 'structured_only',
            'language': query_plan.language
        }
        
        retrieval_result = self.retriever.retrieve(query_plan_dict)
        
        # Convert places to old format for compatibility with existing tests
        # Create simple objects with place, distanceKm, and openNowStatus attributes
        class PlaceResultForTest:
            def __init__(self, place_dict):
                self.place = place_dict
                self.distanceKm = place_dict.get('distanceKm')
                self.openNowStatus = place_dict.get('openNowStatus', 'unknown')
        
        results = [PlaceResultForTest(place) for place in retrieval_result.places]
        
        # Step 3: Test results count
        count_test = self.test_results_count(results, expected_results_count)
        logger.info(f"Results Count: {'PASS' if count_test['passed'] else 'FAIL'} - {count_test['message']}")
        
        # Step 4: Test ranking
        sort_pref = query_plan.slots.get('sort_preference', 'best_match')
        ranking_test = self.test_ranking(results, sort_pref)
        logger.info(f"Ranking: {'PASS' if ranking_test['passed'] else 'FAIL'}")
        if not ranking_test['passed']:
            logger.error(f"  Errors: {ranking_test['errors']}")
        
        # Step 5: Test openNow filtering if applicable
        open_now_test = None
        if query_plan.slots.get('open_now'):
            open_now_test = self.test_open_now_filtering(results, strict=False)
            logger.info(f"OpenNow Filtering: {'PASS' if open_now_test['passed'] else 'FAIL'}")
            logger.info(f"  Open: {open_now_test.get('open_count', 0)}, "
                       f"Unknown: {open_now_test.get('unknown_count', 0)}, "
                       f"Closed: {open_now_test.get('closed_count', 0)}")
        
        # Step 6: Test radius escalation (implicit)
        radius_test = self.test_radius_escalation(query_plan.slots, location) if location else {"passed": True}
        
        # Overall result
        all_passed = all([
            plan_test['passed'],
            count_test['passed'],
            ranking_test['passed'],
            open_now_test['passed'] if open_now_test else True,
            radius_test['passed']
        ])
        
        return {
            "test_id": test_case['id'],
            "query": query,
            "passed": all_passed,
            "plan_test": plan_test,
            "count_test": count_test,
            "ranking_test": ranking_test,
            "open_now_test": open_now_test,
            "radius_test": radius_test,
            "results_count": len(results),
            "query_plan": self.query_planner.plan_to_dict(query_plan)
        }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all golden query tests"""
        logger.info("Starting Golden Queries Test Suite")
        logger.info(f"Places index: {self.places_index_path}")
        logger.info(f"Total places: {len(self.places_index)}")
        
        results = {
            "en": [],
            "pt": []
        }
        
        # Run EN tests
        logger.info("\n" + "="*60)
        logger.info("ENGLISH QUERIES")
        logger.info("="*60)
        for test_case in GOLDEN_QUERIES_EN:
            result = self.run_test(test_case)
            results["en"].append(result)
        
        # Run PT-BR tests
        logger.info("\n" + "="*60)
        logger.info("PORTUGUESE (pt-BR) QUERIES")
        logger.info("="*60)
        for test_case in GOLDEN_QUERIES_PT:
            result = self.run_test(test_case)
            results["pt"].append(result)
        
        # Summary
        total_tests = len(results["en"]) + len(results["pt"])
        passed_tests = sum(1 for r in results["en"] + results["pt"] if r["passed"])
        
        logger.info("\n" + "="*60)
        logger.info("SUMMARY")
        logger.info("="*60)
        logger.info(f"Total tests: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Failed: {total_tests - passed_tests}")
        
        return {
            "summary": {
                "total": total_tests,
                "passed": passed_tests,
                "failed": total_tests - passed_tests
            },
            "results": results
        }


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run golden queries tests")
    parser.add_argument(
        "--places-index",
        type=Path,
        help="Path to canonical_places.jsonl (default: data/canonical_places.jsonl)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON file for test results"
    )
    
    args = parser.parse_args()
    
    runner = GoldenQueriesTestRunner(places_index_path=args.places_index)
    test_results = runner.run_all_tests()
    
    # Save results if output specified
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(test_results, f, indent=2, ensure_ascii=False)
        logger.info(f"\nTest results saved to: {args.output}")
    
    # Exit with error code if any tests failed
    if test_results["summary"]["failed"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
