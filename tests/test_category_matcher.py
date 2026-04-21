"""
Unit tests for CategoryMatcher module.

Tests category matching logic including:
- Exact matching
- Special case handling (açaí vs cafe, hotel vs motel)
- Fuzzy matching
- Scoring
"""

import pytest

from belem_converse.classifiers.intent_classifier_TFIDF_simple import (
    SimpleTFIDFIntentClassifier,
)
from belem_converse.core.category_matcher import CategoryMatcher


@pytest.fixture
def intent_classifier():
    """Create and train intent classifier."""
    classifier = SimpleTFIDFIntentClassifier()
    classifier.train()
    return classifier


@pytest.fixture
def category_matcher(intent_classifier):
    """Create category matcher with trained classifier."""
    return CategoryMatcher(intent_classifier)


class TestCategoryMatcherBasics:
    """Test basic category matching functionality."""
    
    def test_exact_match(self, category_matcher):
        """Test exact category matching."""
        place = {'categories': ['restaurant']}
        assert category_matcher.matches(place, ['restaurant']) is True
    
    def test_no_match(self, category_matcher):
        """Test non-matching categories."""
        place = {'categories': ['restaurant']}
        assert category_matcher.matches(place, ['hotel']) is False
    
    def test_empty_query_categories(self, category_matcher):
        """Test that empty query categories match all places."""
        place = {'categories': ['restaurant']}
        assert category_matcher.matches(place, []) is True
    
    def test_empty_place_categories(self, category_matcher):
        """Test that places with no categories are included."""
        place = {'categories': []}
        assert category_matcher.matches(place, ['restaurant']) is True
    
    def test_multiple_place_categories(self, category_matcher):
        """Test matching with multiple place categories."""
        place = {'categories': ['restaurant', 'bar']}
        assert category_matcher.matches(place, ['bar']) is True
    
    def test_multiple_query_categories(self, category_matcher):
        """Test matching with multiple query categories."""
        place = {'categories': ['cafe']}
        assert category_matcher.matches(place, ['restaurant', 'cafe']) is True


class TestSpecialCases:
    """Test special case category matching."""
    
    def test_acai_matches_cafe(self, category_matcher):
        """Test that açaí places match cafe queries."""
        place = {'categories': ['acai']}
        assert category_matcher.matches(place, ['cafe']) is True
    
    def test_acai_with_accent_matches_cafe(self, category_matcher):
        """Test that açaí with accent matches cafe queries."""
        place = {'categories': ['açaí']}
        assert category_matcher.matches(place, ['cafe']) is True
    
    def test_hotel_matches_motel(self, category_matcher):
        """Test that hotel matches motel queries."""
        place = {'categories': ['hotel']}
        assert category_matcher.matches(place, ['motel']) is True
    
    def test_motel_matches_hotel(self, category_matcher):
        """Test that motel matches hotel queries."""
        place = {'categories': ['motel']}
        assert category_matcher.matches(place, ['hotel']) is True
    
    def test_ice_cream_matches_cafe(self, category_matcher):
        """Test that ice cream places match cafe queries."""
        place = {'categories': ['ice_cream']}
        assert category_matcher.matches(place, ['cafe']) is True


class TestFuzzyMatching:
    """Test fuzzy matching for unknown categories."""
    
    def test_fuzzy_match_close_spelling(self, category_matcher):
        """Test fuzzy matching with close spelling."""
        place = {'categories': ['restaurante']}
        assert category_matcher.matches(place, ['restaurant']) is True
    
    def test_fuzzy_match_with_typo(self, category_matcher):
        """Test fuzzy matching with minor typo."""
        place = {'categories': ['resturant']}  # Common typo
        assert category_matcher.matches(place, ['restaurant']) is True
    
    def test_fuzzy_match_threshold(self, category_matcher):
        """Test that fuzzy matching respects threshold."""
        place = {'categories': ['xyz']}
        # Should not match - too different
        assert category_matcher.matches(place, ['restaurant'], fuzzy_threshold=0.8) is False


class TestScoring:
    """Test category match scoring."""
    
    def test_exact_match_score(self, category_matcher):
        """Test that exact matches get perfect score."""
        place = {'categories': ['restaurant']}
        score = category_matcher.get_match_score(place, ['restaurant'])
        assert score == 1.0
    
    def test_special_case_score(self, category_matcher):
        """Test that special cases get high score."""
        place = {'categories': ['acai']}
        score = category_matcher.get_match_score(place, ['cafe'])
        assert score >= 0.9
    
    def test_no_match_score(self, category_matcher):
        """Test that non-matches get zero score."""
        place = {'categories': ['restaurant']}
        score = category_matcher.get_match_score(place, ['hotel'])
        assert score == 0.0
    
    def test_empty_query_score(self, category_matcher):
        """Test that empty query gets perfect score."""
        place = {'categories': ['restaurant']}
        score = category_matcher.get_match_score(place, [])
        assert score == 1.0
    
    def test_empty_place_categories_score(self, category_matcher):
        """Test that places with no categories get neutral score."""
        place = {'categories': []}
        score = category_matcher.get_match_score(place, ['restaurant'])
        assert score == 0.5


class TestDataFormats:
    """Test different place data formats."""
    
    def test_dict_with_categories(self, category_matcher):
        """Test dictionary format with 'categories' field."""
        place = {'categories': ['restaurant']}
        assert category_matcher.matches(place, ['restaurant']) is True
    
    def test_dict_with_category_string(self, category_matcher):
        """Test dictionary format with 'category' as string."""
        place = {'category': 'restaurant'}
        assert category_matcher.matches(place, ['restaurant']) is True
    
    def test_dict_with_category_list(self, category_matcher):
        """Test dictionary format with 'category' as list."""
        place = {'category': ['restaurant', 'bar']}
        assert category_matcher.matches(place, ['bar']) is True
    
    def test_dict_with_category_name(self, category_matcher):
        """Test dictionary format with 'categoryName' field."""
        place = {'categoryName': 'restaurant'}
        assert category_matcher.matches(place, ['restaurant']) is True
    
    def test_object_with_categories(self, category_matcher):
        """Test object format with categories attribute."""
        class MockPlace:
            def __init__(self):
                self.categories = ['restaurant']
        
        place = MockPlace()
        assert category_matcher.matches(place, ['restaurant']) is True


class TestKeywordMatching:
    """Test matching using Intent_Classifier keywords."""
    
    def test_keyword_match_restaurant(self, category_matcher):
        """Test that restaurant keywords match restaurant category."""
        # 'pizza' is a keyword for restaurant in Intent_Classifier
        place = {'categories': ['pizza']}
        assert category_matcher.matches(place, ['restaurant']) is True
    
    def test_keyword_match_cafe(self, category_matcher):
        """Test that cafe keywords match cafe category."""
        # 'coffee' is a keyword for cafe in Intent_Classifier
        place = {'categories': ['coffee']}
        assert category_matcher.matches(place, ['cafe']) is True
    
    def test_keyword_match_hotel(self, category_matcher):
        """Test that hotel keywords match hotel category."""
        # 'pousada' is a keyword for hotel in Intent_Classifier
        place = {'categories': ['pousada']}
        assert category_matcher.matches(place, ['hotel']) is True


class TestNormalization:
    """Test text normalization."""
    
    def test_case_insensitive(self, category_matcher):
        """Test that matching is case insensitive."""
        place = {'categories': ['RESTAURANT']}
        assert category_matcher.matches(place, ['restaurant']) is True
    
    def test_accent_normalization(self, category_matcher):
        """Test that accents are normalized."""
        place = {'categories': ['café']}
        assert category_matcher.matches(place, ['cafe']) is True
    
    def test_whitespace_normalization(self, category_matcher):
        """Test that whitespace is normalized."""
        place = {'categories': ['  restaurant  ']}
        assert category_matcher.matches(place, ['restaurant']) is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
