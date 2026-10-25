"""
PlaceCache - Shared module for unified place data access and caching.

Implements:
- Unified caching for place data
- Lookup by placeId
- Filter method with predicate functions
- Consistent data access for all retrievers

Requirements: 11.1, 11.2, 11.3
"""

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class PlaceCache:
    """
    Unified place data access and caching module.
    
    Provides consistent place data access patterns for all retrievers,
    supporting lookup by id and filtering with predicate functions.
    """
    
    def __init__(self, places_data: list[dict[str, Any]]):
        """
        Initialize PlaceCache with place data.
        
        Args:
            places_data: List of place dictionaries from database/data loader
        """
        self.places_data = places_data
        self._cache_by_id: dict[str, dict[str, Any]] = {}
        self._build_caches()
    
    def _build_caches(self) -> None:
        """Build the placeId lookup."""
        logger.info(f"Building PlaceCache indexes for {len(self.places_data)} places")
        
        for place in self.places_data:
            # Index by placeId
            place_id = place.get('placeId') or place.get('cid')
            if place_id:
                self._cache_by_id[str(place_id)] = place
        
        logger.info(f"PlaceCache built: {len(self._cache_by_id)} by ID")
    
    def get_by_id(self, place_id: str) -> dict[str, Any] | None:
        """
        Get place by placeId.
        
        Args:
            place_id: Place ID to lookup
            
        Returns:
            Place dictionary if found, None otherwise
        """
        return self._cache_by_id.get(str(place_id))
    
    def get_all(self) -> list[dict[str, Any]]:
        """
        Get all places from cache.
        
        Returns:
            List of all place dictionaries
        """
        return self.places_data
    
    def filter(self, predicate: Callable[[dict[str, Any]], bool]) -> list[dict[str, Any]]:
        """
        Filter places by predicate function.
        
        Args:
            predicate: Function that takes a place dict and returns True to include it
            
        Returns:
            List of places that match the predicate
        """
        return [place for place in self.places_data if predicate(place)]
    