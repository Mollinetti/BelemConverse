"""
Test cases for Two-Stage Retrieval and LLM Response Quality.

Tests:
1. Basic category query (restaurant search)
2. Location-based query (nearby places)
3. Popularity query (best rated)
4. Combined query (best nearby)
5. Portuguese language query

Run with: python -m tests.test_two_stage_retrieval
"""

import sys
import os
import time
import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

# #region agent log - Hypothesis A/B/D: Check Python environment
_debug_log_path = "/Users/marcomollinetti/Documents/Projects/BelemConverse/.cursor/debug.log"
def _debug_log(hyp_id, location, message, data=None):
    try:
        with open(_debug_log_path, "a") as f:
            f.write(json.dumps({"hypothesisId": hyp_id, "location": location, "message": message, "data": data or {}, "timestamp": time.time(), "sessionId": "debug-session"}) + "\n")
    except: pass
# #endregion

# #region agent log - Log Python interpreter and sys.path
_debug_log("A", "test_two_stage_retrieval.py:startup", "Python environment info", {
    "python_executable": sys.executable,
    "python_version": sys.version,
    "sys_path_first_5": sys.path[:5],
    "cwd": os.getcwd()
})
# #endregion

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# #region agent log - Check if langchain_community can be imported
try:
    import langchain_community
    _debug_log("A", "test_two_stage_retrieval.py:import_check", "langchain_community import SUCCESS", {"version": getattr(langchain_community, "__version__", "unknown")})
except ImportError as e:
    _debug_log("A", "test_two_stage_retrieval.py:import_check", "langchain_community import FAILED", {"error": str(e)})
    
# Check for other key dependencies
for pkg_name in ["langchain", "chromadb", "sentence_transformers"]:
    try:
        __import__(pkg_name)
        _debug_log("A", "test_two_stage_retrieval.py:import_check", f"{pkg_name} import SUCCESS", {})
    except ImportError as e:
        _debug_log("A", "test_two_stage_retrieval.py:import_check", f"{pkg_name} import FAILED", {"error": str(e)})

# Check langchain_core (required for new import paths)
try:
    from langchain_core.documents import Document
    _debug_log("B", "test_two_stage_retrieval.py:import_check", "langchain_core.documents.Document import SUCCESS", {})
except ImportError as e:
    _debug_log("B", "test_two_stage_retrieval.py:import_check", "langchain_core.documents.Document import FAILED", {"error": str(e)})

try:
    from langchain_core.retrievers import BaseRetriever
    _debug_log("B", "test_two_stage_retrieval.py:import_check", "langchain_core.retrievers.BaseRetriever import SUCCESS", {})
except ImportError as e:
    _debug_log("B", "test_two_stage_retrieval.py:import_check", "langchain_core.retrievers.BaseRetriever import FAILED", {"error": str(e)})
# #endregion

# Configure logging to both console and file
LOG_FILE_PATH = Path(__file__).parent / "test_results.log"

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
logger.info(f"Test log file will be saved to: {LOG_FILE_PATH}")


# User's home coordinates for location testing
USER_HOME_COORDS = (-1.4695, -48.4665)  # Marco's location in Belém

# Test cases: (query, user_coordinates, expected_intent, expected_category, description)
TEST_CASES: List[Tuple[str, Tuple[float, float], str, str, str]] = [
    # Test 1: Basic category query (no location)
    (
        "I'm looking for a good restaurant for dinner",
        None,
        "popularity",
        "restaurant",
        "Basic restaurant search - should find restaurants and prioritize by Bayesian rating"
    ),
    
    # Test 2: Location-based query - cafes nearby
    (
        "What cafes are nearby?",
        USER_HOME_COORDS,
        "location",
        "cafe",
        "Location query - should filter by distance and return closest cafes to user"
    ),
    
    # Test 3: Popularity query - best hotels
    (
        "What are the best rated hotels in Belém?",
        None,
        "popularity",
        "hotel",
        "Popularity query - should use Bayesian ranking for hotels"
    ),
    
    # Test 4: Combined location + popularity - best restaurants nearby
    (
        "Find the best restaurants close to me",
        USER_HOME_COORDS,
        "location",
        "restaurant",
        "Combined query - should balance distance and Bayesian rating"
    ),
    
    # Test 5: Portuguese language query - açaí nearby
    (
        "Onde posso encontrar açaí por aqui?",
        USER_HOME_COORDS,
        "location",
        "cafe",
        "Portuguese query - should detect language and find açaí places near user"
    ),
]


class RetrievalTester:
    """Test harness for two-stage retrieval system."""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.agent = None
        self.initialized = False
    
    def initialize(self) -> bool:
        """Initialize the RAG agent."""
        try:
            logger.info("Initializing RAG agent...")
            
            # #region agent log - Hypothesis C/D: Track internal module imports
            try:
                from data.vector_store import VectorStoreManager
                _debug_log("C", "RetrievalTester.initialize", "vector_store import SUCCESS", {})
            except ImportError as e:
                _debug_log("C", "RetrievalTester.initialize", "vector_store import FAILED", {"error": str(e)})
                raise
            
            try:
                from utils.models import ModelManager
                _debug_log("C", "RetrievalTester.initialize", "models import SUCCESS", {})
            except ImportError as e:
                _debug_log("C", "RetrievalTester.initialize", "models import FAILED", {"error": str(e)})
                raise
            
            try:
                from core.enhanced_rag_agent import EnhancedRAGAgent
                _debug_log("C", "RetrievalTester.initialize", "enhanced_rag_agent import SUCCESS", {})
            except ImportError as e:
                _debug_log("C", "RetrievalTester.initialize", "enhanced_rag_agent import FAILED", {"error": str(e)})
                raise
            # #endregion
            
            # #region agent log - Hypothesis E: Track vector store and embedding initialization
            # Initialize vector store
            logger.info("Loading vector store...")
            _debug_log("E", "RetrievalTester.initialize", "Starting vector_store initialization", {})
            try:
                vector_store_manager = VectorStoreManager()
                _debug_log("F", "RetrievalTester.initialize", "Calling vector_store_manager.initialize()", {})
                vector_store_manager.initialize()
                _debug_log("E", "RetrievalTester.initialize", "vector_store initialization SUCCESS", {})
            except Exception as e:
                _debug_log("E", "RetrievalTester.initialize", "vector_store initialization FAILED", {"error": str(e), "error_type": type(e).__name__})
                raise
            
            # Initialize LLM
            logger.info("Loading LLM model...")
            try:
                llm_model = ModelManager.get_llm()
                _debug_log("E", "RetrievalTester.initialize", "LLM initialization SUCCESS", {})
            except Exception as e:
                _debug_log("E", "RetrievalTester.initialize", "LLM initialization FAILED", {"error": str(e)})
                raise
            # #endregion
            
            # Initialize RAG Agent
            logger.info("Setting up Enhanced RAG Agent...")
            self.agent = EnhancedRAGAgent(
                vector_store_manager=vector_store_manager,
                llm_model=llm_model
            )
            
            self.initialized = True
            logger.info("Initialization complete!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            return False
    
    def run_test(
        self,
        query: str,
        user_coordinates: Tuple[float, float],
        expected_intent: str,
        expected_category: str,
        description: str,
        test_num: int
    ) -> Dict[str, Any]:
        """Run a single test case."""
        result = {
            "test_num": test_num,
            "query": query,
            "description": description,
            "expected_intent": expected_intent,
            "expected_category": expected_category,
            "passed": False,
            "response": None,
            "response_time": 0.0,
            "intent_detected": None,
            "category_detected": None,
            "documents_retrieved": 0,
            "error": None
        }
        
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"TEST {test_num}: {description}")
            logger.info(f"Query: '{query}'")
            if user_coordinates:
                logger.info(f"Coordinates: {user_coordinates}")
            logger.info("="*60)
            
            # Run query
            start_time = time.time()
            response = self.agent.query(
                question=query,
                user_coordinates=user_coordinates,
                top_k=3
            )
            result["response_time"] = time.time() - start_time
            result["response"] = response
            
            # Get metrics
            metrics = self.agent.get_performance_metrics()
            
            # Check intent detection
            intent_result = self.agent.tfidf_classifier.predict(query)
            result["intent_detected"] = intent_result.get("primary_intent", "unknown")
            result["category_detected"] = intent_result.get("primary_category", "unknown")
            
            logger.info(f"\nDetected intent: {result['intent_detected']}")
            logger.info(f"Detected category: {result['category_detected']}")
            logger.info(f"Response time: {result['response_time']:.2f}s")
            
            # Evaluate response
            passed, reasons = self._evaluate_response(result, response)
            result["passed"] = passed
            result["evaluation_reasons"] = reasons
            
            # #region agent log - Log FULL response for debugging
            # Print FULL response (not truncated) for debugging
            logger.info(f"\n{'='*60}")
            logger.info(f"FULL LLM RESPONSE FOR TEST {test_num}:")
            logger.info("="*60)
            logger.info(response)
            logger.info("="*60)
            
            # Log to debug file for easy review
            _debug_log("RESPONSE", f"test_{test_num}", "Full LLM response", {
                "query": query,
                "coordinates": user_coordinates,
                "intent_detected": result["intent_detected"],
                "category_detected": result["category_detected"],
                "response_time": result["response_time"],
                "full_response": response
            })
            # #endregion
            
            if passed:
                logger.info("✓ TEST PASSED")
            else:
                logger.info(f"✗ TEST FAILED: {reasons}")
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Test error: {e}")
        
        return result
    
    def _evaluate_response(
        self, 
        result: Dict[str, Any], 
        response: str
    ) -> Tuple[bool, List[str]]:
        """Evaluate if the response meets expectations."""
        reasons = []
        passed = True
        
        # Check 1: Response is not empty
        if not response or len(response.strip()) < 20:
            passed = False
            reasons.append("Response too short or empty")
        
        # Check 2: Response doesn't contain error messages
        error_phrases = [
            "I don't know",
            "could not find",
            "no information",
            "não encontrei",
            "não tenho"
        ]
        
        has_error_phrase = any(phrase.lower() in response.lower() for phrase in error_phrases)
        if has_error_phrase:
            # This might be acceptable in some cases, but flag it
            reasons.append("Response indicates no results found")
        
        # Check 3: Response is coherent (has complete sentences)
        if response and not any(c in response for c in ['.', '!', '?']):
            passed = False
            reasons.append("Response lacks sentence structure")
        
        # Check 4: Intent detection matches expected (flexible)
        detected_intent = result.get("intent_detected", "")
        expected_intent = result.get("expected_intent", "")
        
        # Allow some flexibility - location and popularity can co-occur
        valid_intents = [expected_intent]
        if expected_intent == "location":
            valid_intents.extend(["popularity"])
        elif expected_intent == "popularity":
            valid_intents.extend(["location"])
        
        if detected_intent not in valid_intents and detected_intent != "unknown":
            reasons.append(f"Intent mismatch: got '{detected_intent}', expected '{expected_intent}'")
        
        # Check 5: Category detection (flexible matching)
        detected_category = result.get("category_detected", "").lower()
        expected_category = result.get("expected_category", "").lower()
        
        # Some categories are related
        related_categories = {
            "cafe": ["cafe", "restaurant", "coffee"],
            "restaurant": ["restaurant", "cafe"],
            "hotel": ["hotel", "accommodation"],
        }
        
        valid_categories = [expected_category]
        valid_categories.extend(related_categories.get(expected_category, []))
        
        if detected_category not in valid_categories:
            reasons.append(f"Category mismatch: got '{detected_category}', expected '{expected_category}'")
        
        # Check 6: Response time is reasonable (< 60 seconds for full LLM inference)
        if result.get("response_time", 0) > 60:
            reasons.append(f"Response too slow: {result['response_time']:.2f}s")
        
        # Determine overall pass/fail
        critical_failures = [r for r in reasons if "too short" in r or "lacks sentence" in r]
        if critical_failures:
            passed = False
        
        return passed, reasons
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all test cases."""
        if not self.initialized:
            if not self.initialize():
                return {"error": "Failed to initialize", "tests_run": 0}
        
        logger.info("\n" + "="*70)
        logger.info("STARTING TWO-STAGE RETRIEVAL TESTS")
        logger.info("="*70)
        
        for i, (query, coords, expected_intent, expected_category, description) in enumerate(TEST_CASES, 1):
            result = self.run_test(
                query=query,
                user_coordinates=coords,
                expected_intent=expected_intent,
                expected_category=expected_category,
                description=description,
                test_num=i
            )
            self.results.append(result)
            
            # Small delay between tests to avoid overwhelming the system
            time.sleep(1)
        
        return self._generate_summary()
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate test summary."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.get("passed", False))
        failed = total - passed
        
        avg_time = sum(r.get("response_time", 0) for r in self.results) / total if total > 0 else 0
        
        summary = {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{(passed/total)*100:.1f}%" if total > 0 else "N/A",
            "avg_response_time": f"{avg_time:.2f}s",
            "results": self.results
        }
        
        logger.info("\n" + "="*70)
        logger.info("TEST SUMMARY")
        logger.info("="*70)
        logger.info(f"Total tests: {total}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Pass rate: {summary['pass_rate']}")
        logger.info(f"Average response time: {summary['avg_response_time']}")
        
        if failed > 0:
            logger.info("\nFailed tests:")
            for r in self.results:
                if not r.get("passed", False):
                    logger.info(f"  - Test {r['test_num']}: {r['description']}")
                    for reason in r.get("evaluation_reasons", []):
                        logger.info(f"      Reason: {reason}")
        
        # #region agent log - Log all results to debug file
        logger.info("\n" + "="*70)
        logger.info("ALL TEST RESPONSES SUMMARY")
        logger.info("="*70)
        for r in self.results:
            logger.info(f"\nTest {r['test_num']}: {r['description']}")
            logger.info(f"  Query: {r['query']}")
            logger.info(f"  Intent: {r['intent_detected']} | Category: {r['category_detected']}")
            logger.info(f"  Time: {r['response_time']:.2f}s | Passed: {r['passed']}")
        
        _debug_log("SUMMARY", "all_tests", "Test run complete", {
            "total": total,
            "passed": passed,
            "failed": failed,
            "avg_time": avg_time,
            "user_coordinates": USER_HOME_COORDS
        })
        # #endregion
        
        return summary


def run_quick_test():
    """Run a quick single test to verify system is working."""
    logger.info("Running quick system check...")
    
    tester = RetrievalTester()
    if not tester.initialize():
        logger.error("Failed to initialize. Check your model and data paths.")
        return False
    
    # Run just the first test
    query, coords, intent, category, desc = TEST_CASES[0]
    result = tester.run_test(
        query=query,
        user_coordinates=coords,
        expected_intent=intent,
        expected_category=category,
        description=desc,
        test_num=1
    )
    
    return result.get("passed", False)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test two-stage retrieval and LLM responses"
    )
    parser.add_argument(
        "--quick", 
        action="store_true", 
        help="Run quick single test only"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.quick:
        success = run_quick_test()
        sys.exit(0 if success else 1)
    else:
        tester = RetrievalTester()
        summary = tester.run_all_tests()
        
        # Exit with error code if any tests failed
        if summary.get("failed", 0) > 0:
            sys.exit(1)
        sys.exit(0)


if __name__ == "__main__":
    main()

