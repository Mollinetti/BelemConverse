"""
Property-based test for tour planning intent routing.

Feature: intent-detection-unification
Property 11: Tour Planning Intent Routing

**Validates: Requirements 5.6**

Property 11: Tour Planning Intent Routing
For any query with tour_planning intent detected, the system should route
the request to the tour planner component rather than the standard retrieval pipeline.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock, MagicMock

# Import modules
from core.query_planner import QueryPlanner, QueryPlan


# Tour planning keywords for generating test queries
# Using keywords that match the fallback list in query_planner.py
# Avoiding multi-word phrases that might not match substring checks
tour_keywords_en = [
    'plan', 'itinerary', 'tour', 'schedule', 'route'
]

tour_keywords_pt = [
    'roteiro', 'passeio', 'planejar', 'itinerario', 'viagem', 
    'programar', 'programacao', 'rota'
]

all_tour_keywords = tour_keywords_en + tour_keywords_pt


def create_mock_intent_classifier_with_tour_planning():
    """Create a mock intent classifier that detects tour_planning intent."""
    mock_classifier = Mock()
    
    # Mock predict_intent to return tour_planning intent for tour keywords
    def mock_predict_intent(message):
        message_lower = message.lower()
        
        # Check for tour planning keywords
        if any(kw in message_lower for kw in all_tour_keywords):
            return {
                'primary_intent': 'tour_planning',
                'primary_confidence': 0.9,
                'intents': [{'intent': 'tour_planning', 'confidence': 0.9}]
            }
        
        # Default
        return {
            'primary_intent': 'unknown',
            'primary_confidence': 0.5,
            'intents': []
        }
    
    mock_classifier.predict_intent.side_effect = mock_predict_intent
    
    # Mock predict_category
    def mock_predict_category(message):
        return {
            'primary_category': 'restaurant',
            'primary_category_confidence': 0.8,
            'categories': [{'category': 'restaurant', 'confidence': 0.8}]
        }
    
    mock_classifier.predict_category.side_effect = mock_predict_category
    
    # Mock category_keywords
    mock_classifier.category_keywords = {
        'restaurant': ['restaurant', 'restaurante', 'food'],
        'cafe': ['cafe', 'café', 'coffee'],
        'bar': ['bar', 'pub'],
        'hotel': ['hotel', 'motel']
    }
    
    return mock_classifier


class TestProperty11_TourPlanningIntentRouting:
    """
    Property 11: Tour Planning Intent Routing
    
    For any query with tour_planning intent detected, the system should route
    the request to the tour planner component rather than the standard retrieval pipeline.
    
    **Validates: Requirements 5.6**
    """
    
    @given(
        base_query=st.text(min_size=3, max_size=50, alphabet=st.characters(min_codepoint=97, max_codepoint=122)),
        tour_keyword=st.sampled_from(all_tour_keywords)
    )
    @settings(max_examples=100, deadline=None)
    def test_tour_planning_intent_detected_in_query_plan(self, base_query, tour_keyword):
        """
        Property: For any query containing tour planning keywords, the Query_Planner
        should detect tour_planning intent and set it in the query plan.
        """
        assume(base_query.strip())
        
        planner = QueryPlanner(intent_classifier=create_mock_intent_classifier_with_tour_planning())
        
        # Create query with tour planning keyword
        query = f"{base_query} {tour_keyword}"
        
        # Classify intent
        intent = planner.classify_intent(query)
        
        # Intent should be tour_planning
        assert intent == 'tour_planning', (
            f"Intent should be 'tour_planning' for query with keyword '{tour_keyword}': {query}, got '{intent}'"
        )
    
    @given(
        tour_keyword=st.sampled_from(all_tour_keywords),
        place_type=st.sampled_from(['restaurant', 'cafe', 'museum', 'park', 'hotel'])
    )
    @settings(max_examples=100, deadline=None)
    def test_tour_planning_with_place_types(self, tour_keyword, place_type):
        """
        Property: Tour planning intent should be detected even when combined
        with place type queries (e.g., "plan a tour of restaurants").
        """
        planner = QueryPlanner(intent_classifier=create_mock_intent_classifier_with_tour_planning())
        
        query = f"{tour_keyword} {place_type}"
        
        # Classify intent
        intent = planner.classify_intent(query)
        
        # Intent should be tour_planning
        assert intent == 'tour_planning', (
            f"Tour planning intent should be detected for: {query}, got '{intent}'"
        )
    
    @given(
        tour_keyword=st.sampled_from(all_tour_keywords)
    )
    @settings(max_examples=100, deadline=None)
    def test_tour_planning_query_plan_has_correct_intent(self, tour_keyword):
        """
        Property: Query plans created for tour planning queries should have
        intent='tour_planning'.
        """
        planner = QueryPlanner(intent_classifier=create_mock_intent_classifier_with_tour_planning())
        
        query = f"I want to {tour_keyword} for tomorrow"
        
        # Create query plan
        query_plan = planner.create_query_plan(query)
        
        # Query plan intent should be tour_planning
        assert query_plan.intent == 'tour_planning', (
            f"Query plan intent should be 'tour_planning' for query: {query}, got '{query_plan.intent}'"
        )
    
    @given(
        tour_keyword=st.sampled_from(all_tour_keywords),
        user_location=st.one_of(
            st.none(),
            st.fixed_dictionaries({
                'lat': st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False),
                'lng': st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False)
            })
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_tour_planning_routing_with_location(self, tour_keyword, user_location):
        """
        Property: Tour planning intent should be detected regardless of whether
        user location is available (location is useful but not required for tour planning).
        """
        planner = QueryPlanner(intent_classifier=create_mock_intent_classifier_with_tour_planning())
        
        query = f"I want to {tour_keyword}"
        
        # Create query plan with or without location
        query_plan = planner.create_query_plan(query, user_location=user_location)
        
        # Intent should be tour_planning regardless of location
        assert query_plan.intent == 'tour_planning', (
            f"Tour planning intent should be detected with/without location: {query}"
        )
    
    @given(
        base_query=st.text(min_size=3, max_size=50, alphabet=st.characters(min_codepoint=97, max_codepoint=122))
    )
    @settings(max_examples=100, deadline=None)
    def test_non_tour_planning_queries_not_misclassified(self, base_query):
        """
        Property: Queries without tour planning keywords should NOT be
        classified as tour_planning intent.
        """
        assume(base_query.strip())
        # Ensure base_query doesn't contain tour planning keywords
        assume(not any(kw in base_query.lower() for kw in all_tour_keywords))
        
        planner = QueryPlanner(intent_classifier=create_mock_intent_classifier_with_tour_planning())
        
        # Classify intent
        intent = planner.classify_intent(base_query)
        
        # Intent should NOT be tour_planning
        assert intent != 'tour_planning', (
            f"Query without tour keywords should not be classified as tour_planning: {base_query}"
        )
    
    @given(
        tour_keyword_en=st.sampled_from(tour_keywords_en)
    )
    @settings(max_examples=50, deadline=None)
    def test_english_tour_planning_keywords(self, tour_keyword_en):
        """
        Property: All English tour planning keywords should trigger tour_planning intent.
        """
        planner = QueryPlanner(intent_classifier=create_mock_intent_classifier_with_tour_planning())
        
        query = f"can you {tour_keyword_en} for me"
        
        intent = planner.classify_intent(query)
        
        assert intent == 'tour_planning', (
            f"English tour keyword '{tour_keyword_en}' should trigger tour_planning intent"
        )
    
    @given(
        tour_keyword_pt=st.sampled_from(tour_keywords_pt)
    )
    @settings(max_examples=50, deadline=None)
    def test_portuguese_tour_planning_keywords(self, tour_keyword_pt):
        """
        Property: All Portuguese tour planning keywords should trigger tour_planning intent.
        """
        planner = QueryPlanner(intent_classifier=create_mock_intent_classifier_with_tour_planning())
        
        query = f"você pode {tour_keyword_pt} para mim"
        
        intent = planner.classify_intent(query)
        
        assert intent == 'tour_planning', (
            f"Portuguese tour keyword '{tour_keyword_pt}' should trigger tour_planning intent"
        )
    
    @given(
        tour_keyword=st.sampled_from(all_tour_keywords),
        language=st.sampled_from(['en', 'pt-BR'])
    )
    @settings(max_examples=100, deadline=None)
    def test_tour_planning_language_detection(self, tour_keyword, language):
        """
        Property: Tour planning queries should have correct language detection
        in the query plan.
        """
        planner = QueryPlanner(intent_classifier=create_mock_intent_classifier_with_tour_planning())
        
        query = f"I want to {tour_keyword}"
        
        # Create query plan with explicit language
        query_plan = planner.create_query_plan(query, explicit_language=language)
        
        # Language should match explicit language
        assert query_plan.language == language, (
            f"Query plan language should be '{language}' when explicitly set"
        )
        
        # Intent should still be tour_planning
        assert query_plan.intent == 'tour_planning', (
            f"Tour planning intent should be detected regardless of language"
        )
    
    @given(
        tour_keyword=st.sampled_from(all_tour_keywords)
    )
    @settings(max_examples=100, deadline=None)
    def test_tour_planning_does_not_use_standard_retrieval_strategy(self, tour_keyword):
        """
        Property: Tour planning queries should be routed differently from standard
        retrieval queries. The query plan should indicate tour_planning intent,
        which signals to the system to use the tour planner component instead of
        standard retrieval.
        
        This test verifies that the intent is correctly set, which is the mechanism
        for routing to the tour planner (as seen in EnhancedRAGAgent._is_tour_planning_query).
        """
        planner = QueryPlanner(intent_classifier=create_mock_intent_classifier_with_tour_planning())
        
        query = f"I need to {tour_keyword}"
        
        # Create query plan
        query_plan = planner.create_query_plan(query)
        
        # The key routing mechanism is the intent field
        assert query_plan.intent == 'tour_planning', (
            f"Tour planning queries should have intent='tour_planning' for routing: {query}"
        )
        
        # The query plan should still have a retrieval strategy (for fallback),
        # but the intent field is what triggers tour planner routing
        assert query_plan.retrieval_strategy is not None, (
            "Query plan should have a retrieval strategy (for fallback)"
        )
    
    @given(
        tour_keyword=st.sampled_from(all_tour_keywords),
        additional_filters=st.fixed_dictionaries({
            'openNow': st.one_of(st.none(), st.booleans()),
            'priceMax': st.one_of(st.none(), st.floats(min_value=1.0, max_value=4.0))
        })
    )
    @settings(max_examples=100, deadline=None)
    def test_tour_planning_with_filters(self, tour_keyword, additional_filters):
        """
        Property: Tour planning queries can include additional filters
        (like open_now, price_max) which should be preserved in the query plan
        for the tour planner to use.
        """
        planner = QueryPlanner(intent_classifier=create_mock_intent_classifier_with_tour_planning())
        
        query = f"I want to {tour_keyword}"
        
        # Create query plan with filters
        query_plan = planner.create_query_plan(query, filters=additional_filters)
        
        # Intent should be tour_planning
        assert query_plan.intent == 'tour_planning', (
            f"Tour planning intent should be detected even with filters"
        )
        
        # Filters should be preserved in slots
        if additional_filters.get('openNow') is not None:
            assert query_plan.slots.get('open_now') == additional_filters['openNow'], (
                "open_now filter should be preserved in query plan"
            )
        
        if additional_filters.get('priceMax') is not None:
            assert query_plan.slots.get('price_max') == additional_filters['priceMax'], (
                "price_max filter should be preserved in query plan"
            )


class TestTourPlanningRoutingInvariants:
    """
    Test invariants specific to tour planning routing.
    """
    
    @given(
        tour_keyword=st.sampled_from(all_tour_keywords)
    )
    @settings(max_examples=100, deadline=None)
    def test_tour_planning_intent_is_consistent(self, tour_keyword):
        """
        Property: Tour planning intent detection should be consistent across
        multiple calls with the same query.
        """
        planner = QueryPlanner(intent_classifier=create_mock_intent_classifier_with_tour_planning())
        
        query = f"please {tour_keyword} for me"
        
        # Call multiple times
        intent1 = planner.classify_intent(query)
        intent2 = planner.classify_intent(query)
        intent3 = planner.classify_intent(query)
        
        # All should return tour_planning
        assert intent1 == intent2 == intent3 == 'tour_planning', (
            f"Tour planning intent detection should be consistent: {query}"
        )
    
    @given(
        tour_keyword=st.sampled_from(all_tour_keywords)
    )
    @settings(max_examples=100, deadline=None)
    def test_tour_planning_query_plan_is_serializable(self, tour_keyword):
        """
        Property: Query plans with tour_planning intent should be JSON-serializable
        (for API communication).
        """
        import json
        
        planner = QueryPlanner(intent_classifier=create_mock_intent_classifier_with_tour_planning())
        
        query = f"I want to {tour_keyword}"
        
        # Create query plan
        query_plan = planner.create_query_plan(query)
        
        # Convert to dict
        plan_dict = planner.plan_to_dict(query_plan)
        
        # Should be JSON-serializable
        try:
            json_str = json.dumps(plan_dict)
            assert json_str is not None
            
            # Deserialize and verify intent is preserved
            deserialized = json.loads(json_str)
            assert deserialized['intent'] == 'tour_planning', (
                "Tour planning intent should be preserved in serialization"
            )
        except (TypeError, ValueError) as e:
            pytest.fail(f"Query plan should be JSON-serializable: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
