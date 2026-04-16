"""
CategoryMatcher: Shared module for consistent category matching logic.

This module provides unified category matching across all retrieval components,
using Intent_Classifier as the authoritative source for category keywords.

Validates: Requirements 3.1, 3.2, 3.3, 7.1, 7.3
"""

from typing import List, Dict, Optional, Any
from difflib import SequenceMatcher
import unicodedata


class CategoryMatcher:
    """
    Provides consistent category matching logic using Intent_Classifier keywords.
    
    Features:
    - Uses Intent_Classifier as authoritative source for category keywords
    - Handles special cases (açaí vs cafe, hotel vs motel)
    - Provides fuzzy matching for unknown categories
    - Supports both exact matching and similarity scoring
    """
    
    def __init__(self, intent_classifier):
        """
        Initialize CategoryMatcher with Intent_Classifier.
        
        Args:
            intent_classifier: Instance of SimpleTFIDFIntentClassifier
        """
        self.intent_classifier = intent_classifier
        self._special_cases = self._load_special_cases()
        self._category_keywords_cache = None
    
    def _load_special_cases(self) -> Dict[str, List[str]]:
        """
        Load special case mappings for category matching.
        
        Special cases handle situations where:
        - One category should match another (açaí matches cafe)
        - Synonyms should be treated as equivalent (hotel matches motel)
        
        Returns:
            Dictionary mapping categories to their equivalent categories
        """
        return {
            # Açaí places should match cafe queries
            'acai': ['cafe', 'acai'],
            'açaí': ['cafe', 'acai'],
            
            # Hotel and motel are interchangeable
            'hotel': ['hotel', 'motel'],
            'motel': ['hotel', 'motel'],
            
            # Ice cream can match cafe for dessert queries
            'ice_cream': ['ice_cream', 'cafe'],
            'sorvete': ['ice_cream', 'cafe'],
            
            # Tourist attractions can match various specific types
            'tourist_attraction': [
                'tourist_attraction', 'museum', 'park', 'church',
                'monument', 'historical', 'beach', 'plaza'
            ],
        }
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison (remove accents, lowercase).
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        if not text:
            return ""
        
        # Remove accents
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        
        # Lowercase and strip
        return text.lower().strip()
    
    def _get_category_keywords(self) -> Dict[str, List[str]]:
        """
        Get category keywords from Intent_Classifier.
        
        Returns:
            Dictionary mapping category names to their keywords
        """
        if self._category_keywords_cache is None:
            # Access the category_keywords from the intent classifier
            self._category_keywords_cache = self.intent_classifier.category_keywords
        
        return self._category_keywords_cache
    
    def _expand_with_special_cases(self, category: str) -> List[str]:
        """
        Expand a category with its special case equivalents.
        
        Args:
            category: Category name to expand
            
        Returns:
            List of equivalent category names
        """
        normalized = self._normalize_text(category)
        
        # Check special cases
        if normalized in self._special_cases:
            return self._special_cases[normalized]
        
        # Return original if no special case
        return [normalized]
    
    def _fuzzy_match_score(self, text1: str, text2: str) -> float:
        """
        Calculate fuzzy match score between two strings.
        
        Args:
            text1: First string
            text2: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not text1 or not text2:
            return 0.0
        
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def _matches_keywords(
        self, 
        place_category: str, 
        query_category: str,
        fuzzy_threshold: float = 0.8
    ) -> bool:
        """
        Check if place category matches query category using keywords.
        
        Args:
            place_category: Category from place data
            query_category: Category from query
            fuzzy_threshold: Minimum similarity score for fuzzy matching
            
        Returns:
            True if categories match
        """
        # Normalize both categories
        place_norm = self._normalize_text(place_category)
        query_norm = self._normalize_text(query_category)
        
        # Exact match
        if place_norm == query_norm:
            return True
        
        # Check if query category has special case equivalents
        query_equivalents = self._expand_with_special_cases(query_category)
        if place_norm in [self._normalize_text(eq) for eq in query_equivalents]:
            return True
        
        # Check if place category has special case equivalents
        place_equivalents = self._expand_with_special_cases(place_category)
        if query_norm in [self._normalize_text(eq) for eq in place_equivalents]:
            return True
        
        # Get keywords for the query category
        category_keywords = self._get_category_keywords()
        
        # Check if place category matches any keywords for the query category
        for cat_name, keywords in category_keywords.items():
            cat_norm = self._normalize_text(cat_name)
            
            # If this is the query category, check if place matches any keywords
            if cat_norm == query_norm or cat_norm in query_equivalents:
                for keyword in keywords:
                    keyword_norm = self._normalize_text(keyword)
                    
                    # Exact keyword match
                    if place_norm == keyword_norm:
                        return True
                    
                    # Fuzzy keyword match
                    if self._fuzzy_match_score(place_norm, keyword_norm) >= fuzzy_threshold:
                        return True
        
        # Fuzzy match as last resort
        if self._fuzzy_match_score(place_norm, query_norm) >= fuzzy_threshold:
            return True
        
        return False
    
    def matches(
        self, 
        place: Any, 
        query_categories: List[str],
        fuzzy_threshold: float = 0.8
    ) -> bool:
        """
        Check if place matches any of the query categories.
        
        Args:
            place: Place object or dictionary with 'categories' or 'category' field
            query_categories: List of category names from query
            fuzzy_threshold: Minimum similarity score for fuzzy matching (default 0.8)
            
        Returns:
            True if place matches any query category
        """
        if not query_categories:
            return True  # No category filter means match all
        
        # Extract place categories
        place_categories = []
        
        if isinstance(place, dict):
            # Handle dictionary format
            if 'categories' in place:
                place_categories = place['categories']
            elif 'category' in place:
                cat = place['category']
                place_categories = cat if isinstance(cat, list) else [cat]
            elif 'categoryName' in place:
                place_categories = [place['categoryName']]
        else:
            # Handle object format (Pydantic model or dataclass)
            if hasattr(place, 'categories'):
                place_categories = place.categories
            elif hasattr(place, 'category'):
                cat = place.category
                place_categories = cat if isinstance(cat, list) else [cat]
            elif hasattr(place, 'categoryName'):
                place_categories = [place.categoryName]
        
        # If place has no categories, include it (don't exclude due to missing data)
        if not place_categories:
            return True
        
        # Check if any place category matches any query category
        for place_cat in place_categories:
            if not place_cat:
                continue
            
            for query_cat in query_categories:
                if not query_cat:
                    continue
                
                if self._matches_keywords(place_cat, query_cat, fuzzy_threshold):
                    return True
        
        return False
    
    def get_match_score(
        self, 
        place: Any, 
        query_categories: List[str],
        fuzzy_threshold: float = 0.8
    ) -> float:
        """
        Calculate category match score (0.0 to 1.0).
        
        The score represents how well the place's categories match the query categories:
        - 1.0: Perfect exact match
        - 0.8-0.99: Fuzzy match or special case match
        - 0.0: No match
        
        Args:
            place: Place object or dictionary with 'categories' or 'category' field
            query_categories: List of category names from query
            fuzzy_threshold: Minimum similarity score for fuzzy matching (default 0.8)
            
        Returns:
            Match score between 0.0 and 1.0
        """
        if not query_categories:
            return 1.0  # No category filter means perfect match
        
        # Extract place categories
        place_categories = []
        
        if isinstance(place, dict):
            if 'categories' in place:
                place_categories = place['categories']
            elif 'category' in place:
                cat = place['category']
                place_categories = cat if isinstance(cat, list) else [cat]
            elif 'categoryName' in place:
                place_categories = [place['categoryName']]
        else:
            if hasattr(place, 'categories'):
                place_categories = place.categories
            elif hasattr(place, 'category'):
                cat = place.category
                place_categories = cat if isinstance(cat, list) else [cat]
            elif hasattr(place, 'categoryName'):
                place_categories = [place.categoryName]
        
        # If place has no categories, return neutral score
        if not place_categories:
            return 0.5
        
        # Calculate best match score
        best_score = 0.0
        
        for place_cat in place_categories:
            if not place_cat:
                continue
            
            for query_cat in query_categories:
                if not query_cat:
                    continue
                
                place_norm = self._normalize_text(place_cat)
                query_norm = self._normalize_text(query_cat)
                
                # Exact match - perfect score
                if place_norm == query_norm:
                    return 1.0
                
                # Special case match - high score
                query_equivalents = self._expand_with_special_cases(query_cat)
                if place_norm in [self._normalize_text(eq) for eq in query_equivalents]:
                    best_score = max(best_score, 0.95)
                    continue
                
                place_equivalents = self._expand_with_special_cases(place_cat)
                if query_norm in [self._normalize_text(eq) for eq in place_equivalents]:
                    best_score = max(best_score, 0.95)
                    continue
                
                # Keyword match
                category_keywords = self._get_category_keywords()
                for cat_name, keywords in category_keywords.items():
                    cat_norm = self._normalize_text(cat_name)
                    
                    if cat_norm == query_norm or cat_norm in query_equivalents:
                        for keyword in keywords:
                            keyword_norm = self._normalize_text(keyword)
                            
                            # Exact keyword match
                            if place_norm == keyword_norm:
                                best_score = max(best_score, 0.9)
                                break
                            
                            # Fuzzy keyword match
                            fuzzy_score = self._fuzzy_match_score(place_norm, keyword_norm)
                            if fuzzy_score >= fuzzy_threshold:
                                best_score = max(best_score, fuzzy_score * 0.9)
                
                # Direct fuzzy match
                fuzzy_score = self._fuzzy_match_score(place_norm, query_norm)
                if fuzzy_score >= fuzzy_threshold:
                    best_score = max(best_score, fuzzy_score)
        
        return best_score
