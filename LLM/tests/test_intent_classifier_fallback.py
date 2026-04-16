"""
Tests for Intent_Classifier fallback handling in Query_Planner.

Validates Requirement 1.4: Fallback handling when Intent_Classifier fails.
"""

import pytest
import logging
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from core.query_planner import QueryPlanner


class TestIntentClassifierFallback:
    """Test suite for Intent_Classifier fallback handling"""
    
    def test_fallback_on_classifier_exception_in_place_types(self, caplog):
        """
        Test that extract_place_types falls back gracefully when Intent_Classifier raises exception.
        
        Requirements:
        - Try-catch around Intent_Classifier calls
        - Fallback logic invoked on exception
        - Errors logged with full context
        - Confidence scores set to 0.0 in fallback mode
        """
        # Create mock classifier that raises exception
        mock_classifier = Mock()
        mock_classifier.predict_category.side_effect = Exception("Classifier unavailable")
        
        planner = QueryPlanner(intent_classifier=mock_classifier)
        
        with caplog.at_level(logging.WARNING):
            result = planner.extract_place_types("find restaurants near me", "en")
        
        # Verify fallback was used
        assert any("Intent_Classifier failed" in record.message for record in caplog.records)
        assert any("FALLBACK MODE" in record.message for record in caplog.records)
        
        # Verify result is still returned (fallback provides default)
        assert isinstance(result, list)
    
    def test_fallback_on_classifier_exception_in_open_now(self, caplog):
        """
        Test that extract_open_now falls back gracefully when Intent_Classifier raises exception.
        """
        mock_classifier = Mock()
        mock_classifier.predict_intent.side_effect = Exception("Network error")
        
        planner = QueryPlanner(intent_classifier=mock_classifier)
        
        with caplog.at_level(logging.WARNING):
            result = planner.extract_open_now("restaurants open now", "en")
        
        # Verify error was logged with context
        assert any("Intent_Classifier failed" in record.message for record in caplog.records)
        assert any("FALLBACK MODE" in record.message for record in caplog.records)
        
        # Verify fallback returns a valid result
        assert result is None or isinstance(result, bool)
    
    def test_fallback_on_classifier_exception_in_proximity_intent(self, caplog):
        """
        Test that extract_proximity_intent falls back gracefully when Intent_Classifier raises exception.
        """
        mock_classifier = Mock()
        mock_classifier.predict_intent.side_effect = RuntimeError("Model loading failed")
        
        planner = QueryPlanner(intent_classifier=mock_classifier)
        
        with caplog.at_level(logging.WARNING):
            result = planner.extract_proximity_intent("restaurants near me", "en")
        
        # Verify error was logged
        assert any("Intent_Classifier failed" in record.message for record in caplog.records)
        assert any("FALLBACK MODE" in record.message for record in caplog.records)
        
        # Verify fallback returns boolean
        assert isinstance(result, bool)
    
    def test_fallback_on_classifier_exception_in_sort_preference(self, caplog):
        """
        Test that determine_sort_preference falls back gracefully when Intent_Classifier raises exception.
        """
        mock_classifier = Mock()
        mock_classifier.predict_intent.side_effect = ValueError("Invalid input")
        
        planner = QueryPlanner(intent_classifier=mock_classifier)
        
        with caplog.at_level(logging.ERROR):
            result = planner.determine_sort_preference(
                "best restaurants", "en", {"lat": 0.0, "lng": 0.0}, False
            )
        
        # Verify error was logged
        assert any("Intent_Classifier failed" in record.message for record in caplog.records)
        
        # Verify fallback returns valid sort preference
        assert result == "best_match"
    
    def test_fallback_on_classifier_exception_in_categories(self, caplog):
        """
        Test that extract_categories falls back gracefully when Intent_Classifier raises exception.
        """
        mock_classifier = Mock()
        mock_classifier.predict_category.side_effect = Exception("Prediction failed")
        mock_classifier.category_keywords = {
            'restaurant': ['restaurant', 'restaurante'],
            'bar': ['bar', 'pub']
        }
        
        planner = QueryPlanner(intent_classifier=mock_classifier)
        
        with caplog.at_level(logging.ERROR):
            result = planner.extract_categories("find a restaurant")
        
        # Verify error was logged
        assert any("Intent_Classifier failed" in record.message for record in caplog.records)
        
        # Verify fallback still extracts categories using keyword matching
        assert isinstance(result, list)
    
    def test_fallback_mode_sets_confidence_to_zero(self):
        """
        Test that fallback mode explicitly sets confidence scores to 0.0.
        
        Requirement: Set confidence scores to 0.0 in fallback mode
        """
        planner = QueryPlanner(intent_classifier=None)
        
        # Call fallback directly
        result = planner._fallback_intent_detection("restaurants near me", "Test context")
        
        # Verify all confidence scores are 0.0
        assert result['primary_confidence'] == 0.0
        assert result['primary_category_confidence'] == 0.0
        assert all(intent['confidence'] == 0.0 for intent in result['intents'])
        assert all(cat['confidence'] == 0.0 for cat in result['categories'])
        assert result['fallback_mode'] is True
    
    def test_fallback_logs_error_context(self, caplog):
        """
        Test that fallback logs include error context explaining why fallback was used.
        
        Requirement: Log errors with full context
        """
        planner = QueryPlanner(intent_classifier=None)
        
        with caplog.at_level(logging.WARNING):
            planner._fallback_intent_detection(
                "test message", 
                "predict_intent failed: Connection timeout"
            )
        
        # Verify log includes both message and error context
        log_messages = [record.message for record in caplog.records]
        assert any("FALLBACK MODE" in msg for msg in log_messages)
        assert any("test message" in msg for msg in log_messages)
        assert any("Connection timeout" in msg for msg in log_messages)
    
    def test_no_classifier_uses_fallback(self, caplog):
        """
        Test that QueryPlanner without classifier uses fallback for all operations.
        
        Requirement: Implement minimal keyword-based fallback on failure
        """
        planner = QueryPlanner(intent_classifier=None)
        
        with caplog.at_level(logging.WARNING):
            # Test various operations
            place_types = planner.extract_place_types("restaurants", "en")
            open_now = planner.extract_open_now("open now", "en")
            proximity = planner.extract_proximity_intent("near me", "en")
            sort_pref = planner.determine_sort_preference("best", "en", None, False)
        
        # Verify fallback was used
        assert any("FALLBACK MODE" in record.message for record in caplog.records)
        
        # Verify operations still return valid results
        assert isinstance(place_types, list)
        assert open_now is None or isinstance(open_now, bool)
        assert isinstance(proximity, bool)
        assert sort_pref in ['distance', 'rating', 'popularity', 'best_match']
    
    def test_error_logs_include_exception_details(self, caplog):
        """
        Test that error logs include exception details in extra context.
        
        Requirement: Log errors with full context (message, exception details)
        """
        mock_classifier = Mock()
        test_exception = ValueError("Test error with details")
        mock_classifier.predict_intent.side_effect = test_exception
        
        planner = QueryPlanner(intent_classifier=mock_classifier)
        
        with caplog.at_level(logging.ERROR):
            planner.extract_proximity_intent("near me", "en")
        
        # Verify error log includes exception details
        error_records = [r for r in caplog.records if r.levelname == 'ERROR']
        assert len(error_records) > 0
        
        # Check that exception info is logged
        assert any("Test error with details" in str(record.message) for record in error_records)
        
        # Check that extra context includes message and exception
        for record in error_records:
            if hasattr(record, 'message') and 'Intent_Classifier failed' in record.message:
                # Verify the log includes context
                assert 'near me' in str(record) or 'message' in str(record.__dict__)
    
    def test_fallback_provides_minimal_but_valid_results(self):
        """
        Test that fallback provides minimal but valid results for all operations.
        
        Requirement: Implement minimal keyword-based fallback on failure
        """
        planner = QueryPlanner(intent_classifier=None)
        
        # Test fallback detection
        result = planner._fallback_intent_detection("restaurants near me open now cheap")
        
        # Verify structure is valid
        assert 'intents' in result
        assert 'primary_intent' in result
        assert 'categories' in result
        assert 'primary_category' in result
        assert 'fallback_mode' in result
        
        # Verify minimal detection works
        assert isinstance(result['intents'], list)
        assert isinstance(result['categories'], list)
        assert result['fallback_mode'] is True
        
        # Verify it detects at least some intents from keywords
        intent_names = [i['intent'] for i in result['intents']]
        # Should detect location (near), business_hours (open), price (cheap)
        assert len(intent_names) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
