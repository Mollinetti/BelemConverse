"""
PlaceCache - Shared module for unified place data access and caching.

Implements:
- Unified caching for place data
- Lookup by placeId, title, and titleFormatted
- Filter method with predicate functions
- Consistent data access for all retrievers

Requirements: 11.1, 11.2, 11.3
"""

import logging
from typing import List, Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)


class PlaceCache:
    """
    Unified place data access and caching module.
    
    Provides consistent place data access patterns for all retrievers,
    supporting lookup by multiple keys and filtering with predicate functions.
    """
    
    def __init__(self, places_data: List[Dict[str, Any]]):
        """
        Initialize PlaceCache with place data.
        
        Args:
            places_data: List of place dictionaries from database/data loader
        """
        self.places_data = places_data
        self._cache_by_id: Dict[str, Dict[str, Any]] = {}
        self._cache_by_title: Dict[str, Dict[str, Any]] = {}
        self._cache_by_title_formatted: Dict[str, Dict[str, Any]] = {}
        self._build_caches()
    
    def _build_caches(self) -> None:
        """Build lookup caches for fast access by different keys."""
        logger.info(f"Building PlaceCache indexes for {len(self.places_data)} places")
        
        for place in self.places_data:
            # Index by placeId
            place_id = place.get('placeId') or place.get('cid')
            if place_id:
                self._cache_by_id[str(place_id)] = place
            
            # Index by title (case-insensitive)
            title = place.get('title', '').strip()
            if title:
                title_lower = title.lower()
                # Store first occurrence only to avoid conflicts
                if title_lower not in self._cache_by_title:
                    self._cache_by_title[title_lower] = place
            
            # Index by titleFormatted (case-insensitive)
            title_formatted = place.get('titleFormatted', '').strip()
            if title_formatted:
                title_formatted_lower = title_formatted.lower()
                # Store first occurrence only to avoid conflicts
                if title_formatted_lower not in self._cache_by_title_formatted:
                    self._cache_by_title_formatted[title_formatted_lower] = place
        
        logger.info(
            f"PlaceCache built: {len(self._cache_by_id)} by ID, "
            f"{len(self._cache_by_title)} by title, "
            f"{len(self._cache_by_title_formatted)} by titleFormatted"
        )
    
    def get_by_id(self, place_id: str) -> Optional[Dict[str, Any]]:
        """
        Get place by placeId.
        
        Args:
            place_id: Place ID to lookup
            
        Returns:
            Place dictionary if found, None otherwise
        """
        return self._cache_by_id.get(str(place_id))
    
    def get_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        """
        Get place by title or titleFormatted.
        
        Searches both title and titleFormatted fields (case-insensitive).
        
        Args:
            title: Title to lookup
            
        Returns:
            Place dictionary if found, None otherwise
        """
        title_lower = title.lower().strip()
        
        # Try title first
        place = self._cache_by_title.get(title_lower)
        if place:
            return place
        
        # Try titleFormatted
        place = self._cache_by_title_formatted.get(title_lower)
        if place:
            return place
        
        return None
    
    def get_all(self) -> List[Dict[str, Any]]:
        """
        Get all places from cache.
        
        Returns:
            List of all place dictionaries
        """
        return self.places_data
    
    def filter(self, predicate: Callable[[Dict[str, Any]], bool]) -> List[Dict[str, Any]]:
        """
        Filter places by predicate function.
        
        Args:
            predicate: Function that takes a place dict and returns True to include it
            
        Returns:
            List of places that match the predicate
        """
        return [place for place in self.places_data if predicate(place)]
    
    def invalidate(self) -> None:
        """
        Clear all caches.
        
        Call this when place data needs to be reloaded.
        """
        logger.info("Invalidating PlaceCache")
        self._cache_by_id.clear()
        self._cache_by_title.clear()
        self._cache_by_title_formatted.clear()
        self.places_data = []
    
    def reload(self, places_data: List[Dict[str, Any]]) -> None:
        """
        Reload cache with new place data.
        
        Args:
            places_data: New list of place dictionaries
        """
        logger.info(f"Reloading PlaceCache with {len(places_data)} places")
        self.places_data = places_data
        self._cache_by_id.clear()
        self._cache_by_title.clear()
        self._cache_by_title_formatted.clear()
        self._build_caches()
    
    def get_count(self) -> int:
        """
        Get total number of places in cache.
        
        Returns:
            Number of places
        """
        return len(self.places_data)
