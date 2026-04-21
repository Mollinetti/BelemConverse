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

from belem_converse.core.query_planner import QueryPlanner


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

        Uses a colloquial PT-BR query ("ta servindo neste exato instante") which
        intentionally bypasses the Strategy-1 phrase list so that the classifier
        path is genuinely exercised. Real users phrase business-hours questions
        in many forms beyond the canonical "open now" / "aberto agora".
        """
        mock_classifier = Mock()
        mock_classifier.predict_intent.side_effect = Exception("Network error")

        planner = QueryPlanner(intent_classifier=mock_classifier)

        with caplog.at_level(logging.WARNING):
            result = planner.extract_open_now(
                "qual restaurante ta servindo neste exato instante?", "pt-BR"
            )

        # Verify error was logged with context
        assert any("Intent_Classifier failed" in record.message for record in caplog.records)
        assert any("FALLBACK MODE" in record.message for record in caplog.records)

        # Verify fallback returns a valid result
        assert result is None or isinstance(result, bool)
    
    def test_fallback_on_classifier_exception_in_proximity_intent(self, caplog):
        """
        Test that extract_proximity_intent falls back gracefully when Intent_Classifier raises exception.

        Uses a colloquial PT-BR query ("ir andando do hotel") which expresses
        proximity intent without using any keyword from the Strategy-1 phrase
        or word lists, so the classifier path is the only path that could
        possibly catch the intent — and therefore the only path whose failure
        we can observe.
        """
        mock_classifier = Mock()
        mock_classifier.predict_intent.side_effect = RuntimeError("Model loading failed")

        planner = QueryPlanner(intent_classifier=mock_classifier)

        with caplog.at_level(logging.WARNING):
            result = planner.extract_proximity_intent(
                "me indica um lugar bacana q da pra ir andando do hotel", "pt-BR"
            )

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

        Requirement: Log errors with full context (query, exception details).

        Uses a PT-BR query with a deliberate typo ("bairo" instead of "bairro")
        — real users misspell, and the classifier path must remain the
        observable one regardless of typos. The query has no Strategy-1
        keyword match, so the classifier is the only thing that can fire.
        """
        mock_classifier = Mock()
        test_exception = ValueError("Test error with details")
        mock_classifier.predict_intent.side_effect = test_exception

        planner = QueryPlanner(intent_classifier=mock_classifier)

        test_query = "tem boteco bom no meu bairo pra ir agora?"
        with caplog.at_level(logging.ERROR):
            planner.extract_proximity_intent(test_query, "pt-BR")

        # Verify error log includes exception info
        error_records = [r for r in caplog.records if r.levelname == 'ERROR']
        assert len(error_records) > 0

        # Check that exception details are propagated into the log message
        assert any("Test error with details" in str(record.message) for record in error_records)

        # Check that the structured `extra` payload carries the original
        # query and the stringified exception. We assert against the
        # LogRecord attributes set by `extra={"query": ..., "error": ...}`
        # rather than the formatted message string, so the contract is on
        # what callers can programmatically extract from the log.
        classifier_failure_records = [
            r for r in error_records
            if 'Intent_Classifier failed' in r.message
        ]
        assert classifier_failure_records, "Expected an 'Intent_Classifier failed' error log"

        for record in classifier_failure_records:
            assert getattr(record, 'query', None) == test_query, (
                f"Log record should carry original query in extra; "
                f"got {getattr(record, 'query', None)!r}"
            )
            assert "Test error with details" in getattr(record, 'error', ''), (
                "Log record should carry stringified exception in extra"
            )
    
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


class TestProximityInstrumentation:
    """Locks in the contract introduced alongside the rebase intent-detection
    validation work: ``extract_proximity_intent`` always runs both Strategy 1
    (keywords) AND Strategy 2 (classifier), even when Strategy 1 already gives
    a definitive boolean answer.

    This costs one extra inference per query but gives us continuous
    observability about how often the keyword list and the classifier agree
    — i.e. the data needed to decide whether the keyword list can eventually
    be retired in favour of the classifier alone.
    """

    def test_classifier_is_invoked_even_when_strategy1_hits(self):
        """When Strategy 1 matches, Strategy 2 is still invoked for instrumentation."""
        mock_classifier = Mock()
        mock_classifier.predict_intent.return_value = {
            'primary_intent': 'location',
            'primary_confidence': 0.9,
            'intents': [{'intent': 'location', 'confidence': 0.9}],
        }

        planner = QueryPlanner(intent_classifier=mock_classifier)
        result = planner.extract_proximity_intent("near me", "en")

        assert result is True
        mock_classifier.predict_intent.assert_called_once_with("near me")

    def test_strategy1_wins_even_if_classifier_raises(self, caplog):
        """Resilience: a classifier failure must NOT regress proximity detection
        for queries that Strategy 1 would have caught. The boolean still
        reflects Strategy 1, the classifier failure is logged, and the
        instrumentation event still fires.

        Note: we deliberately do NOT assert ``strategy2_hit`` here — when the
        classifier raises, the helper falls back to a minimal keyword list
        that may or may not also catch the query. What matters for this test
        is the resilience and observability contract, not the exact fallback
        keyword coverage (that is the subject of other tests).
        """
        mock_classifier = Mock()
        mock_classifier.predict_intent.side_effect = RuntimeError("model unavailable")

        planner = QueryPlanner(intent_classifier=mock_classifier)

        with caplog.at_level(logging.INFO):
            result = planner.extract_proximity_intent("near me", "en")

        assert result is True, "Strategy 1 hit must win even when classifier raises"
        mock_classifier.predict_intent.assert_called_once_with("near me")

        assert any(
            "Intent_Classifier failed" in r.message for r in caplog.records
        ), "Classifier failure must still be logged"

        instrumentation_records = [
            r for r in caplog.records
            if r.message == "proximity_intent_detection"
        ]
        assert instrumentation_records, "Instrumentation event must be emitted"
        event = instrumentation_records[-1]
        assert getattr(event, 'strategy1_hit') is True
        assert getattr(event, 'result') is True
        assert getattr(event, 'strategy1_signal', '').startswith('phrase:near me')

    def test_instrumentation_event_records_agreement_when_both_strategies_hit(self, caplog):
        """When both strategies independently detect proximity intent, the
        instrumentation event records ``agree=True``. Mining this signal over
        real traffic is what tells us whether Strategy 1 is still pulling its
        weight or can be retired.
        """
        mock_classifier = Mock()
        mock_classifier.predict_intent.return_value = {
            'primary_intent': 'location',
            'primary_confidence': 0.85,
            'intents': [{'intent': 'location', 'confidence': 0.85}],
        }

        planner = QueryPlanner(intent_classifier=mock_classifier)

        with caplog.at_level(logging.INFO):
            result = planner.extract_proximity_intent("perto de mim", "pt-BR")

        assert result is True

        events = [r for r in caplog.records if r.message == "proximity_intent_detection"]
        assert events, "Instrumentation event must be emitted"
        event = events[-1]
        assert getattr(event, 'strategy1_hit') is True
        assert getattr(event, 'strategy2_hit') is True
        assert getattr(event, 'agree') is True
        assert getattr(event, 'language') == 'pt-BR'
        assert getattr(event, 'query') == 'perto de mim'

    def test_instrumentation_event_records_disagreement_when_only_classifier_hits(self, caplog):
        """When Strategy 1 misses but the classifier catches the intent, the
        instrumentation event records ``agree=False`` with ``strategy1_hit=False,
        strategy2_hit=True``. This is the signal that the keyword list has a
        coverage gap worth investigating.
        """
        mock_classifier = Mock()
        mock_classifier.predict_intent.return_value = {
            'primary_intent': 'location',
            'primary_confidence': 0.7,
            'intents': [{'intent': 'location', 'confidence': 0.7}],
        }

        planner = QueryPlanner(intent_classifier=mock_classifier)

        # PT-BR query expressing proximity ("ir andando" = walking distance)
        # that the keyword list does not catch.
        msg = "me indica um lugar bacana q da pra ir andando do hotel"
        with caplog.at_level(logging.INFO):
            result = planner.extract_proximity_intent(msg, "pt-BR")

        assert result is True

        events = [r for r in caplog.records if r.message == "proximity_intent_detection"]
        assert events
        event = events[-1]
        assert getattr(event, 'strategy1_hit') is False
        assert getattr(event, 'strategy2_hit') is True
        assert getattr(event, 'agree') is False
        assert getattr(event, 'strategy1_signal') is None


class TestOpenNowInstrumentation:
    """Mirrors :class:`TestProximityInstrumentation` for ``extract_open_now``.

    Same architectural contract: Strategy 1 (phrase matching with closed-phrase
    override) and Strategy 2 (classifier ``business_hours`` intent) are
    **both** always evaluated, and a structured ``open_now_detection`` event
    is emitted on every call. Boolean output preserves the legacy tri-valued
    contract: ``True`` if either strategy hits, else ``None`` (never False).
    """

    def test_classifier_is_invoked_even_when_strategy1_hits(self):
        """When Strategy 1 matches an open phrase, the classifier is still invoked."""
        mock_classifier = Mock()
        mock_classifier.predict_intent.return_value = {
            'primary_intent': 'business_hours',
            'primary_confidence': 0.9,
            'intents': [{'intent': 'business_hours', 'confidence': 0.9}],
        }

        planner = QueryPlanner(intent_classifier=mock_classifier)
        result = planner.extract_open_now("places open now", "en")

        assert result is True
        mock_classifier.predict_intent.assert_called_once_with("places open now")

    def test_strategy1_resilience_when_classifier_raises(self, caplog):
        """A classifier failure must NOT regress open_now detection for queries
        that Strategy 1 already caught. The boolean still reflects Strategy 1,
        the classifier failure is logged, and the instrumentation event fires.
        """
        mock_classifier = Mock()
        mock_classifier.predict_intent.side_effect = RuntimeError("model unavailable")

        planner = QueryPlanner(intent_classifier=mock_classifier)

        with caplog.at_level(logging.INFO):
            result = planner.extract_open_now("aberto agora", "pt-BR")

        assert result is True, "Strategy 1 hit must win even when classifier raises"
        mock_classifier.predict_intent.assert_called_once_with("aberto agora")

        assert any(
            "Intent_Classifier failed" in r.message for r in caplog.records
        )

        events = [r for r in caplog.records if r.message == "open_now_detection"]
        assert events, "Instrumentation event must be emitted"
        event = events[-1]
        assert getattr(event, 'strategy1_hit') is True
        assert getattr(event, 'result') is True
        assert getattr(event, 'strategy1_signal', '').startswith('phrase:aberto agora')

    def test_closed_phrase_overrides_open_phrase_in_strategy1(self, caplog):
        """If both an open phrase and a closed phrase appear, the closed phrase
        wins for Strategy 1 — the user is probably asking about a transition,
        not about currently-open places. Final result must be ``None`` (unknown)
        unless Strategy 2 independently confirms business_hours intent.
        """
        # Classifier returns nothing relevant — only Strategy 1 is in play.
        mock_classifier = Mock()
        mock_classifier.predict_intent.return_value = {
            'primary_intent': 'popularity',
            'primary_confidence': 0.6,
            'intents': [{'intent': 'popularity', 'confidence': 0.6}],
        }

        planner = QueryPlanner(intent_classifier=mock_classifier)

        with caplog.at_level(logging.INFO):
            result = planner.extract_open_now(
                "qual abre depois que esse fechado agora reabrir?", "pt-BR"
            )

        assert result is None, "Closed-phrase override must suppress Strategy 1 True"

        events = [r for r in caplog.records if r.message == "open_now_detection"]
        assert events
        event = events[-1]
        assert getattr(event, 'strategy1_hit') is False
        assert getattr(event, 'strategy1_signal', '').startswith('closed_override:')
        assert getattr(event, 'result') is None

    def test_instrumentation_records_disagreement_when_only_classifier_hits(self, caplog):
        """A colloquial PT-BR query like "ta servindo agora?" expresses
        business_hours intent without using any keyword from the Strategy-1
        phrase list. The classifier should catch it; the keyword list won't.
        Record this as ``strategy1_hit=False, strategy2_hit=True, agree=False``
        — that signal is exactly the data we want to mine to know whether
        the keyword list has coverage gaps worth filling.
        """
        mock_classifier = Mock()
        mock_classifier.predict_intent.return_value = {
            'primary_intent': 'business_hours',
            'primary_confidence': 0.7,
            'intents': [{'intent': 'business_hours', 'confidence': 0.7}],
        }

        planner = QueryPlanner(intent_classifier=mock_classifier)

        msg = "qual restaurante ta aberto neste exato instante?"
        with caplog.at_level(logging.INFO):
            result = planner.extract_open_now(msg, "pt-BR")

        # Strategy 1 doesn't match the canonical phrases, but the classifier
        # confirms business_hours and "aberto" is present, so result is True.
        assert result is True

        events = [r for r in caplog.records if r.message == "open_now_detection"]
        assert events
        event = events[-1]
        assert getattr(event, 'strategy1_hit') is False
        assert getattr(event, 'strategy2_hit') is True
        assert getattr(event, 'agree') is False
        assert getattr(event, 'language') == 'pt-BR'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
