"""
Test tour planning intent detection in Query_Planner.

This test verifies that Query_Planner correctly detects tour_planning intent
when users request itinerary planning, tours, or day trips.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from core.query_planner import QueryPlanner


def test_tour_planning_intent_english():
    """Test that tour planning intent is detected for English keywords."""
    query_planner = QueryPlanner()
    
    # Test various English tour planning keywords
    test_cases = [
        "plan a day trip to the city",
        "create an itinerary for tomorrow",
        "I want to plan a tour",
        "help me schedule my day",
        "what's a good route to visit museums",
    ]
    
    for query in test_cases:
        intent = query_planner.classify_intent(query)
        assert intent == 'tour_planning', f"Expected 'tour_planning' for query: '{query}', got '{intent}'"
    
    print("✓ Tour planning intent correctly detected for English keywords")


def test_tour_planning_intent_portuguese():
    """Test that tour planning intent is detected for Portuguese keywords."""
    query_planner = QueryPlanner()
    
    # Test various Portuguese tour planning keywords
    test_cases = [
        "planejar um passeio pela cidade",
        "criar um roteiro para amanhã",
        "quero fazer um passeio",
        "me ajude a programar meu dia",
        "qual a melhor rota para visitar museus",
    ]
    
    for query in test_cases:
        intent = query_planner.classify_intent(query)
        assert intent == 'tour_planning', f"Expected 'tour_planning' for query: '{query}', got '{intent}'"
    
    print("✓ Tour planning intent correctly detected for Portuguese keywords")


def test_tour_planning_query_plan():
    """Test that tour planning intent is included in Query Plan."""
    query_planner = QueryPlanner()
    
    query = "plan a day trip to visit restaurants and museums"
    plan = query_planner.create_query_plan(query)
    
    # Verify the intent is set correctly in the query plan
    assert plan.intent == 'tour_planning', f"Expected intent 'tour_planning', got '{plan.intent}'"
    
    print("✓ Tour planning intent correctly included in Query Plan")


def test_non_tour_planning_queries():
    """Test that non-tour planning queries are not misclassified."""
    query_planner = QueryPlanner()
    
    # Test queries that should NOT be classified as tour_planning
    test_cases = [
        ("find restaurants near me", "find_places"),
        ("what is the best cafe", "place_details"),
        ("compare two hotels", "compare_places"),
        ("hello", "smalltalk"),
        ("how do I use this", "help"),
    ]
    
    for query, expected_intent in test_cases:
        intent = query_planner.classify_intent(query)
        assert intent == expected_intent, f"Query '{query}' should be '{expected_intent}', got '{intent}'"
    
    print("✓ Non-tour planning queries correctly classified")


if __name__ == "__main__":
    test_tour_planning_intent_english()
    test_tour_planning_intent_portuguese()
    test_tour_planning_query_plan()
    test_non_tour_planning_queries()
    print("\n✅ All tour planning intent tests passed!")
