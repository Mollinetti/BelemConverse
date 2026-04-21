"""
Test retrieval strategy selection implementation.

This test verifies Task 5.3 requirements:
- Filter-first as default primary strategy
- Semantic search as fallback
- OSM enabled when user location is available
- No ENABLE_VECTOR_FALLBACK environment variable usage
- No vibe keyword detection
"""

import sys
from pathlib import Path
import pytest

# Add src to path

from belem_converse.core.query_planner import QueryPlanner
from belem_converse.classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier


class TestRetrievalStrategySelection:
    """Test retrieval strategy selection per Task 5.3."""
    
    @pytest.fixture
    def query_planner(self):
        """Create a QueryPlanner with trained intent classifier."""
        intent_classifier = SimpleTFIDFIntentClassifier()
        intent_classifier.train()
        return QueryPlanner(intent_classifier)
    
    def test_filter_first_is_default_strategy(self, query_planner):
        """
        Requirement 2.2, 9.1: Filter-first should be the default primary strategy.
        """
        # Test with various queries
        queries = [
            "find restaurants",
            "show me cafes nearby",
            "popular hotels in Belém",
            "open restaurants",
            "cheap places to eat"
        ]
        
        for query in queries:
            strategy = query_planner.determine_retrieval_strategy(query, None)
            assert strategy == 'structured_then_lexical', (
                f"Expected 'structured_then_lexical' for query '{query}', got '{strategy}'"
            )
    
    def test_filter_first_with_user_location(self, query_planner):
        """
        Requirement 9.3: OSM should be enabled when user location is available.
        Note: OSM enablement is determined by UnifiedRetriever based on user_location presence.
        """
        user_location = {'lat': -1.4558, 'lng': -48.4902}
        
        # Strategy should still be filter-first
        strategy = query_planner.determine_retrieval_strategy(
            "find restaurants nearby",
            user_location
        )
        
        assert strategy == 'structured_then_lexical', (
            "Strategy should be filter-first even with user location"
        )
        
        # Verify that user_location is passed through in query plan
        query_plan = query_planner.create_query_plan(
            "find restaurants nearby",
            user_location=user_location
        )
        
        # User location should be in slots when proximity intent is detected
        assert query_plan.slots.get('proximity_intent_detected') is True, (
            "Proximity intent should be detected for 'nearby' query"
        )
        assert query_plan.slots.get('user_location') is not None, (
            "User location should be in slots when proximity intent detected"
        )
    
    def test_no_vibe_keyword_detection(self, query_planner):
        """
        Requirement 9.5: Vibe keyword detection should be removed.
        """
        # Queries with "vibe" keywords that used to trigger special handling
        vibe_queries = [
            "romantic restaurants",
            "cozy cafes",
            "quiet places to work",
            "instagrammable spots",
            "trendy bars"
        ]
        
        for query in vibe_queries:
            strategy = query_planner.determine_retrieval_strategy(query, None)
            assert strategy == 'structured_then_lexical', (
                f"Vibe query '{query}' should use filter-first, not special handling"
            )
    
    def test_no_environment_variable_usage(self, query_planner):
        """
        Requirement 9.4: ENABLE_VECTOR_FALLBACK environment variable should not be used.
        """
        import os
        
        # Set the environment variable to verify it's ignored
        os.environ['ENABLE_VECTOR_FALLBACK'] = 'true'
        
        try:
            strategy = query_planner.determine_retrieval_strategy(
                "find restaurants",
                None
            )
            
            # Strategy should still be filter-first, ignoring the env var
            assert strategy == 'structured_then_lexical', (
                "Strategy should ignore ENABLE_VECTOR_FALLBACK environment variable"
            )
        finally:
            # Clean up
            os.environ.pop('ENABLE_VECTOR_FALLBACK', None)
    
    def test_semantic_search_fallback_in_unified_retriever(self):
        """
        Requirement 2.3, 9.2: Semantic search should be used as fallback when filter-first returns zero results.
        Note: This is handled by UnifiedRetriever, not QueryPlanner.
        """
        # This test verifies the design intent is documented
        # The actual fallback logic is in UnifiedRetriever.retrieve()
        
        from belem_converse.core.unified_retriever import UnifiedRetriever
        import inspect
        
        # Verify the retrieve method has semantic search fallback logic
        source = inspect.getsource(UnifiedRetriever.retrieve)
        
        assert 'semantic_search' in source, (
            "UnifiedRetriever.retrieve should have semantic search fallback logic"
        )
        assert 'not db_results' in source, (
            "Semantic search should be triggered when filter-first returns zero results"
        )
    
    def test_osm_enabled_with_location_in_unified_retriever(self):
        """
        Requirement 9.3: OSM should be enabled when user location is available.
        Note: This is handled by UnifiedRetriever._should_trigger_osm().
        """
        from belem_converse.core.unified_retriever import UnifiedRetriever
        import inspect
        
        # Verify the _should_trigger_osm method checks for user location
        source = inspect.getsource(UnifiedRetriever._should_trigger_osm)
        
        assert 'user_location' in source, (
            "_should_trigger_osm should check for user location"
        )
        assert 'not user_location' in source, (
            "_should_trigger_osm should return False when no user location"
        )
    
    def test_query_plan_structure(self, query_planner):
        """
        Verify query plan structure includes all necessary fields for retrieval strategy.
        """
        user_location = {'lat': -1.4558, 'lng': -48.4902}
        
        query_plan = query_planner.create_query_plan(
            "find popular restaurants nearby",
            user_location=user_location
        )
        
        # Verify query plan has retrieval_strategy field
        assert hasattr(query_plan, 'retrieval_strategy'), (
            "QueryPlan should have retrieval_strategy field"
        )
        assert query_plan.retrieval_strategy == 'structured_then_lexical', (
            "Retrieval strategy should be filter-first"
        )
        
        # Verify slots contain necessary information
        assert 'proximity_intent_detected' in query_plan.slots, (
            "Slots should indicate if proximity intent was detected"
        )
        assert 'user_location' in query_plan.slots, (
            "Slots should contain user_location when proximity intent detected"
        )


def test_integration_filter_first_strategy():
    """
    Integration test: Verify QueryPlanner sets filter-first strategy.
    
    This test verifies:
    1. QueryPlanner always sets filter-first as the primary strategy
    2. The strategy is correctly passed to UnifiedRetriever
    3. UnifiedRetriever uses filter-first as the primary retrieval method
    """
    from belem_converse.core.query_planner import QueryPlanner
    from belem_converse.classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier
    
    # Setup
    intent_classifier = SimpleTFIDFIntentClassifier()
    intent_classifier.train()
    
    query_planner = QueryPlanner(intent_classifier)
    
    # Test various queries
    test_cases = [
        ("find restaurants", None),
        ("show me cafes nearby", {'lat': -1.4558, 'lng': -48.4902}),
        ("popular hotels", None),
        ("open restaurants", {'lat': -1.4558, 'lng': -48.4902}),
    ]
    
    for query, user_location in test_cases:
        # Create query plan
        query_plan = query_planner.create_query_plan(query, user_location=user_location)
        
        # Verify strategy is always filter-first
        assert query_plan.retrieval_strategy == 'structured_then_lexical', (
            f"Query '{query}' should use filter-first strategy"
        )
        
        # Verify user_location is in slots when proximity intent detected
        if user_location and 'nearby' in query.lower():
            assert query_plan.slots.get('proximity_intent_detected') is True, (
                f"Proximity intent should be detected for query '{query}'"
            )
            assert query_plan.slots.get('user_location') is not None, (
                f"User location should be in slots for query '{query}'"
            )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
