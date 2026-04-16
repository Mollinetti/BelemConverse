"""
Test Query_Planner refactoring to ensure it delegates to Intent_Classifier.

This test verifies that Query_Planner correctly delegates all intent detection
to Intent_Classifier and removes duplicate keyword-based logic.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from core.query_planner import QueryPlanner
from classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier


def test_query_planner_uses_intent_classifier():
    """Test that Query_Planner uses Intent_Classifier for intent detection."""
    # Initialize with intent classifier
    intent_classifier = SimpleTFIDFIntentClassifier()
    intent_classifier.train()
    
    query_planner = QueryPlanner(intent_classifier=intent_classifier)
    
    # Test proximity intent detection
    query = "find restaurants near me"
    user_location = {"lat": -1.4558, "lng": -48.4902}
    
    plan = query_planner.create_query_plan(query, user_location=user_location)
    
    # Verify proximity intent was detected
    assert plan.slots['proximity_intent_detected'] == True, "Proximity intent should be detected"
    assert plan.slots['sort_preference'] == 'distance', "Sort preference should be distance"
    
    print("✓ Query_Planner correctly delegates proximity intent detection to Intent_Classifier")


def test_query_planner_detects_popularity_intent():
    """Test that Query_Planner detects popularity intent via Intent_Classifier."""
    intent_classifier = SimpleTFIDFIntentClassifier()
    intent_classifier.train()
    
    query_planner = QueryPlanner(intent_classifier=intent_classifier)
    
    # Test popularity intent detection
    query = "show me the most popular restaurants"
    
    plan = query_planner.create_query_plan(query)
    
    # Verify popularity intent affects sort preference
    assert plan.slots['sort_preference'] == 'popularity', "Sort preference should be popularity"
    
    print("✓ Query_Planner correctly delegates popularity intent detection to Intent_Classifier")


def test_query_planner_detects_business_hours_intent():
    """Test that Query_Planner detects business hours intent via Intent_Classifier."""
    intent_classifier = SimpleTFIDFIntentClassifier()
    intent_classifier.train()
    
    query_planner = QueryPlanner(intent_classifier=intent_classifier)
    
    # Test business hours intent detection
    query = "find restaurants that are open now"
    
    plan = query_planner.create_query_plan(query)
    
    # Verify open_now was detected
    assert plan.slots['open_now'] == True, "open_now should be True"
    
    print("✓ Query_Planner correctly delegates business hours intent detection to Intent_Classifier")


def test_query_planner_fallback_without_classifier():
    """Test that Query_Planner uses fallback when Intent_Classifier is unavailable."""
    # Initialize without intent classifier
    query_planner = QueryPlanner(intent_classifier=None)
    
    # Test that it still works with fallback
    query = "find restaurants near me"
    user_location = {"lat": -1.4558, "lng": -48.4902}
    
    plan = query_planner.create_query_plan(query, user_location=user_location)
    
    # Verify it returns a valid plan (even if less accurate)
    assert plan is not None, "Should return a valid plan"
    assert plan.language in ['en', 'pt-BR'], "Should detect language"
    
    print("✓ Query_Planner correctly uses fallback when Intent_Classifier is unavailable")


def test_query_planner_extracts_categories():
    """Test that Query_Planner extracts categories via Intent_Classifier."""
    intent_classifier = SimpleTFIDFIntentClassifier()
    intent_classifier.train()
    
    query_planner = QueryPlanner(intent_classifier=intent_classifier)
    
    # Test category extraction
    query = "find pizza restaurants"
    
    plan = query_planner.create_query_plan(query)
    
    # Verify categories were extracted
    assert plan.slots['categories'] is not None, "Categories should be extracted"
    assert len(plan.slots['categories']) > 0, "Should have at least one category"
    
    print("✓ Query_Planner correctly extracts categories via Intent_Classifier")


def test_retrieval_strategy_is_filter_first():
    """Test that retrieval strategy is always filter-first (no vibe keywords)."""
    intent_classifier = SimpleTFIDFIntentClassifier()
    intent_classifier.train()
    
    query_planner = QueryPlanner(intent_classifier=intent_classifier)
    
    # Test that retrieval strategy is always structured_then_lexical
    query = "find romantic restaurants"
    
    plan = query_planner.create_query_plan(query)
    
    # Verify retrieval strategy is filter-first
    assert plan.retrieval_strategy == 'structured_then_lexical', \
        "Retrieval strategy should always be structured_then_lexical (filter-first)"
    
    print("✓ Query_Planner uses filter-first retrieval strategy (no vibe keywords)")


if __name__ == "__main__":
    test_query_planner_uses_intent_classifier()
    test_query_planner_detects_popularity_intent()
    test_query_planner_detects_business_hours_intent()
    test_query_planner_fallback_without_classifier()
    test_query_planner_extracts_categories()
    test_retrieval_strategy_is_filter_first()
    
    print("\n✅ All Query_Planner refactoring tests passed!")
