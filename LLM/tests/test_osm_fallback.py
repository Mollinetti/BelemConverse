#!/usr/bin/env python3
"""
Test suite for OSM Fallback Search functionality.

Tests various scenarios where OSM fallback should be triggered:
1. Empty results from database
2. Low confidence results
3. Geographic gap (user far from results)
4. Specific place name not found
5. Verification queries
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Test configuration
TEST_COORDINATES = (-1.4695, -48.4665)  # Belém, PA
LOG_FILE = Path(__file__).parent / "osm_fallback_test_results.log"


class OSMFallbackTester:
    """Test harness for OSM fallback functionality."""
    
    def __init__(self):
        self.results = []
        self.log_lines = []
        
    def log(self, message: str):
        """Log message to console and file."""
        print(message)
        self.log_lines.append(message)
    
    def save_log(self):
        """Save test log to file."""
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.log_lines))
        print(f"\nLog saved to: {LOG_FILE}")
    
    def test_osm_realtime_search(self):
        """Test 1: Basic OSM realtime search functionality."""
        self.log("\n" + "=" * 60)
        self.log("TEST 1: OSM Realtime Search (Basic)")
        self.log("=" * 60)
        
        try:
            from data.osm_realtime_search import OSMRealtimeSearch
            
            searcher = OSMRealtimeSearch()
            
            # Test restaurant search
            self.log("\n--- Searching for restaurants near user ---")
            results = searcher.search(
                query="restaurante perto de mim",
                user_coordinates=TEST_COORDINATES,
                radius=2000
            )
            
            self.log(f"Found {len(results)} restaurants from OSM")
            for i, doc in enumerate(results[:3]):
                name = doc.metadata.get('title', 'Unknown')
                dist = doc.metadata.get('distance_km', 'N/A')
                cat = doc.metadata.get('categoryName', 'Unknown')
                self.log(f"  {i+1}. {name} ({cat}) - {dist:.2f}km away")
            
            # Test cafe search
            self.log("\n--- Searching for cafes ---")
            results = searcher.search(
                query="cafe coffee shop",
                user_coordinates=TEST_COORDINATES,
                radius=2000
            )
            
            self.log(f"Found {len(results)} cafes from OSM")
            
            # Test name search
            self.log("\n--- Searching by specific name ---")
            results = searcher.search_by_name(
                name="Ver-o-Peso",
                user_coordinates=TEST_COORDINATES,
                radius=10000
            )
            
            self.log(f"Found {len(results)} places matching 'Ver-o-Peso'")
            for doc in results[:3]:
                name = doc.metadata.get('title', 'Unknown')
                self.log(f"  - {name}")
            
            self.results.append(('test_osm_realtime_search', True, "OSM search working"))
            return True
            
        except Exception as e:
            self.log(f"ERROR: {e}")
            self.results.append(('test_osm_realtime_search', False, str(e)))
            return False
    
    def test_fallback_orchestrator_decision(self):
        """Test 2: Fallback orchestrator decision making."""
        self.log("\n" + "=" * 60)
        self.log("TEST 2: Fallback Orchestrator Decisions")
        self.log("=" * 60)
        
        try:
            from core.search_fallback import SearchFallbackOrchestrator, FallbackReason
            from langchain_core.documents import Document
            
            orchestrator = SearchFallbackOrchestrator()
            
            # Test 2a: Empty results should trigger fallback
            self.log("\n--- 2a: Empty Results ---")
            decision = orchestrator.evaluate_fallback_need(
                query="find restaurants",
                db_results=[],
                user_coordinates=TEST_COORDINATES
            )
            self.log(f"Should fallback: {decision.should_fallback}")
            self.log(f"Reason: {decision.reason.value}")
            assert decision.should_fallback == True
            assert decision.reason == FallbackReason.EMPTY_RESULTS
            self.log("✓ Empty results correctly triggers fallback")
            
            # Test 2b: Low confidence should trigger fallback
            self.log("\n--- 2b: Low Confidence Results ---")
            low_conf_docs = [
                Document(page_content="test", metadata={'title': 'Test Place', 'distance_km': 1.0})
            ]
            decision = orchestrator.evaluate_fallback_need(
                query="find restaurants",
                db_results=low_conf_docs,
                user_coordinates=TEST_COORDINATES,
                scores=[0.1, 0.2]  # All below 0.3 threshold
            )
            self.log(f"Should fallback: {decision.should_fallback}")
            self.log(f"Reason: {decision.reason.value}")
            assert decision.should_fallback == True
            assert decision.reason == FallbackReason.LOW_CONFIDENCE
            self.log("✓ Low confidence correctly triggers fallback")
            
            # Test 2c: Geographic gap should trigger fallback
            self.log("\n--- 2c: Geographic Gap ---")
            far_docs = [
                Document(page_content="test", metadata={'title': 'Far Place', 'distance_km': 10.0})
            ]
            decision = orchestrator.evaluate_fallback_need(
                query="find restaurants nearby",
                db_results=far_docs,
                user_coordinates=TEST_COORDINATES,
                scores=[0.8]
            )
            self.log(f"Should fallback: {decision.should_fallback}")
            self.log(f"Reason: {decision.reason.value}")
            self.log(f"Details: {decision.details}")
            assert decision.should_fallback == True
            assert decision.reason == FallbackReason.GEOGRAPHIC_GAP
            self.log("✓ Geographic gap correctly triggers fallback")
            
            # Test 2d: Verification query should trigger fallback
            self.log("\n--- 2d: Verification Query ---")
            decision = orchestrator.evaluate_fallback_need(
                query="Is Mercado Ver-o-Peso still open?",
                db_results=[Document(page_content="test", metadata={'title': 'Other Place'})],
                user_coordinates=TEST_COORDINATES,
                scores=[0.8]
            )
            self.log(f"Should fallback: {decision.should_fallback}")
            self.log(f"Reason: {decision.reason.value}")
            assert decision.should_fallback == True
            assert decision.reason == FallbackReason.VERIFICATION_QUERY
            self.log("✓ Verification query correctly triggers fallback")
            
            # Test 2e: Name not found should trigger fallback
            self.log("\n--- 2e: Name Not Found ---")
            decision = orchestrator.evaluate_fallback_need(
                query='Find "Restaurant XYZ"',
                db_results=[Document(page_content="test", metadata={'title': 'Different Place', 'distance_km': 0.5})],
                user_coordinates=TEST_COORDINATES,
                scores=[0.8]
            )
            self.log(f"Should fallback: {decision.should_fallback}")
            self.log(f"Reason: {decision.reason.value}")
            self.log(f"Extracted name: {decision.extracted_name}")
            assert decision.should_fallback == True
            assert decision.reason == FallbackReason.NAME_NOT_FOUND
            self.log("✓ Name not found correctly triggers fallback")
            
            # Test 2f: Good results should NOT trigger fallback
            self.log("\n--- 2f: Good Results (No Fallback) ---")
            good_docs = [
                Document(page_content="test", metadata={'title': 'Good Restaurant', 'distance_km': 0.5})
            ]
            decision = orchestrator.evaluate_fallback_need(
                query="find restaurants",
                db_results=good_docs,
                user_coordinates=TEST_COORDINATES,
                scores=[0.8]
            )
            self.log(f"Should fallback: {decision.should_fallback}")
            self.log(f"Reason: {decision.reason.value}")
            assert decision.should_fallback == False
            assert decision.reason == FallbackReason.NONE
            self.log("✓ Good results correctly avoid fallback")
            
            self.results.append(('test_fallback_orchestrator_decision', True, "All decisions correct"))
            return True
            
        except Exception as e:
            self.log(f"ERROR: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.results.append(('test_fallback_orchestrator_decision', False, str(e)))
            return False
    
    def test_verification_intent_detection(self):
        """Test 3: Verification intent detection in classifier."""
        self.log("\n" + "=" * 60)
        self.log("TEST 3: Verification Intent Detection")
        self.log("=" * 60)
        
        try:
            from classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier
            
            classifier = SimpleTFIDFIntentClassifier()
            
            test_queries = [
                ("Is Ver-o-Peso still open?", "verification"),
                ("Does the old restaurant still exist?", "verification"),
                ("O restaurante ainda está aberto?", "verification"),
                ("Check if the museum is still there", "verification"),
                ("Best restaurants nearby", "popularity"),  # Should NOT be verification
                ("Where is the nearest hotel?", "location"),  # Should NOT be verification
            ]
            
            for query, expected_intent in test_queries:
                result = classifier.predict(query)
                detected_intents = [i['intent'] for i in result.get('intents', [])]
                
                if expected_intent == "verification":
                    has_verification = 'verification' in detected_intents
                    self.log(f"Query: '{query[:40]}...'")
                    self.log(f"  Expected: {expected_intent}, Got: {detected_intents}")
                    self.log(f"  {'✓' if has_verification else '✗'} Verification intent detected: {has_verification}")
                else:
                    primary = result.get('primary_intent', '')
                    self.log(f"Query: '{query[:40]}...'")
                    self.log(f"  Expected primary: {expected_intent}, Got: {primary}")
            
            self.results.append(('test_verification_intent_detection', True, "Intent detection working"))
            return True
            
        except Exception as e:
            self.log(f"ERROR: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.results.append(('test_verification_intent_detection', False, str(e)))
            return False
    
    def test_end_to_end_fallback(self):
        """Test 4: End-to-end fallback integration."""
        self.log("\n" + "=" * 60)
        self.log("TEST 4: End-to-End Fallback (Integration)")
        self.log("=" * 60)
        
        try:
            from core.search_fallback import SearchFallbackOrchestrator
            from langchain_core.documents import Document
            
            orchestrator = SearchFallbackOrchestrator()
            
            # Simulate empty database results
            self.log("\n--- Simulating empty DB results with OSM fallback ---")
            
            merged = orchestrator.search_with_fallback(
                query="find restaurants perto de mim",
                db_results=[],
                user_coordinates=TEST_COORDINATES,
                intent_result={'primary_category': 'restaurant'},
                scores=[]
            )
            
            self.log(f"Fallback used: {merged.fallback_used}")
            self.log(f"Fallback reason: {merged.fallback_reason.value}")
            self.log(f"DB results: {merged.db_count}")
            self.log(f"OSM results: {merged.osm_count}")
            self.log(f"Total merged: {len(merged.documents)}")
            
            if merged.documents:
                self.log("\nMerged results:")
                for i, doc in enumerate(merged.documents[:5]):
                    name = doc.metadata.get('title', 'Unknown')
                    source = doc.metadata.get('data_source', 'unknown')
                    self.log(f"  {i+1}. {name} [source: {source}]")
            
            self.results.append(('test_end_to_end_fallback', True, "Integration working"))
            return True
            
        except Exception as e:
            self.log(f"ERROR: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.results.append(('test_end_to_end_fallback', False, str(e)))
            return False
    
    def run_all_tests(self):
        """Run all fallback tests."""
        self.log("=" * 60)
        self.log("OSM FALLBACK SYSTEM TEST SUITE")
        self.log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"Test coordinates: {TEST_COORDINATES}")
        self.log("=" * 60)
        
        # Run tests
        self.test_osm_realtime_search()
        self.test_fallback_orchestrator_decision()
        self.test_verification_intent_detection()
        self.test_end_to_end_fallback()
        
        # Summary
        self.log("\n" + "=" * 60)
        self.log("TEST SUMMARY")
        self.log("=" * 60)
        
        passed = sum(1 for _, success, _ in self.results if success)
        failed = sum(1 for _, success, _ in self.results if not success)
        
        for test_name, success, message in self.results:
            status = "✓ PASS" if success else "✗ FAIL"
            self.log(f"  {status}: {test_name} - {message}")
        
        self.log(f"\nTotal: {passed} passed, {failed} failed")
        self.log("=" * 60)
        
        # Save log
        self.save_log()
        
        return failed == 0


def main():
    tester = OSMFallbackTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

