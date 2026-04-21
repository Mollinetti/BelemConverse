"""
RankingEngine: Shared module for consistent ranking logic.

This module provides unified ranking across all retrieval components,
supporting four ranking modes: distance, rating, popularity, and best_match.

Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
"""

from typing import List, Optional, Any, Dict
from dataclasses import dataclass
import math


@dataclass
class Location:
    """Location with latitude and longitude coordinates."""
    latitude: float
    longitude: float
    
    def distance_to(self, other: 'Location') -> float:
        """
        Calculate distance in kilometers using Haversine formula.
        
        Args:
            other: Target location
            
        Returns:
            Distance in kilometers
        """
        # Haversine formula
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(self.latitude)
        lat2_rad = math.radians(other.latitude)
        delta_lat = math.radians(other.latitude - self.latitude)
        delta_lng = math.radians(other.longitude - self.longitude)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c


class RankingMode:
    """Ranking mode constants."""
    DISTANCE = "distance"
    RATING = "rating"
    POPULARITY = "popularity"
    BEST_MATCH = "best_match"


class RankingEngine:
    """
    Provides consistent ranking logic for all retrievers.
    
    Features:
    - Distance ranking: Sort by distance ascending with rating tiebreaker
    - Rating ranking: Sort by totalScore descending with reviewsCount tiebreaker
    - Popularity ranking: Sort by Bayesian popularity score descending
    - Best match ranking: Composite scoring (45% rating, 35% popularity, 20% proximity)
    """
    
    def __init__(self):
        """Initialize RankingEngine."""
        # Bayesian prior parameters (can be tuned based on dataset)
        self.prior_mean = 3.5  # Average rating across all places
        self.prior_weight = 10  # Confidence in prior (equivalent to 10 reviews)
    
    def rank(
        self,
        places: List[Any],
        mode: str,
        user_location: Optional[Location] = None
    ) -> List[Any]:
        """
        Rank places according to specified mode.
        
        Args:
            places: List of places to rank (dict or Pydantic model)
            mode: Ranking mode (distance, rating, popularity, best_match)
            user_location: User location for distance calculations (required for distance and best_match modes)
            
        Returns:
            Sorted list of places
        """
        if not places:
            return []
        
        if mode == RankingMode.DISTANCE:
            if user_location is None:
                raise ValueError("user_location is required for distance ranking")
            return self._rank_by_distance(places, user_location)
        
        elif mode == RankingMode.RATING:
            return self._rank_by_rating(places)
        
        elif mode == RankingMode.POPULARITY:
            return self._rank_by_popularity(places)
        
        elif mode == RankingMode.BEST_MATCH:
            return self._rank_by_best_match(places, user_location)
        
        else:
            raise ValueError(f"Unknown ranking mode: {mode}")
    
    def _get_location(self, place: Any) -> Optional[Location]:
        """
        Extract location from place object or dictionary.
        
        Args:
            place: Place object or dictionary
            
        Returns:
            Location object or None if not available
        """
        if isinstance(place, dict):
            if 'location' in place and place['location']:
                loc = place['location']
                if isinstance(loc, dict):
                    return Location(
                        latitude=loc.get('lat', 0.0),
                        longitude=loc.get('lng', 0.0)
                    )
                elif hasattr(loc, 'lat') and hasattr(loc, 'lng'):
                    return Location(latitude=loc.lat, longitude=loc.lng)
        else:
            if hasattr(place, 'location') and place.location:
                loc = place.location
                if hasattr(loc, 'lat') and hasattr(loc, 'lng'):
                    return Location(latitude=loc.lat, longitude=loc.lng)
        
        return None
    
    def _get_rating(self, place: Any) -> float:
        """
        Extract rating from place object or dictionary.
        
        Args:
            place: Place object or dictionary
            
        Returns:
            Rating value (default 0.0 if not available)
        """
        if isinstance(place, dict):
            return place.get('totalScore', 0.0) or 0.0
        else:
            return getattr(place, 'totalScore', 0.0) or 0.0
    
    def _get_review_count(self, place: Any) -> int:
        """
        Extract review count from place object or dictionary.
        
        Args:
            place: Place object or dictionary
            
        Returns:
            Review count (default 0 if not available)
        """
        if isinstance(place, dict):
            return place.get('reviewsCount', 0) or 0
        else:
            return getattr(place, 'reviewsCount', 0) or 0
    
    def _rank_by_distance(
        self,
        places: List[Any],
        user_location: Location
    ) -> List[Any]:
        """
        Sort by distance ascending, rating as tiebreaker.
        
        Args:
            places: List of places to rank
            user_location: User location for distance calculation
            
        Returns:
            Sorted list of places
        """
        def sort_key(place):
            place_location = self._get_location(place)
            
            if place_location is None:
                # Places without location go to the end
                return (float('inf'), 0.0)
            
            distance = user_location.distance_to(place_location)
            rating = self._get_rating(place)
            
            # Sort by distance ascending, then by rating descending (negative for descending)
            return (distance, -rating)
        
        return sorted(places, key=sort_key)
    
    def _rank_by_rating(self, places: List[Any]) -> List[Any]:
        """
        Sort by totalScore descending, reviewsCount as tiebreaker.
        
        Args:
            places: List of places to rank
            
        Returns:
            Sorted list of places
        """
        def sort_key(place):
            rating = self._get_rating(place)
            review_count = self._get_review_count(place)
            
            # Sort by rating descending, then by review count descending
            # Use negative values for descending order
            return (-rating, -review_count)
        
        return sorted(places, key=sort_key)
    
    def _rank_by_popularity(self, places: List[Any]) -> List[Any]:
        """
        Sort by Bayesian popularity score descending.
        
        The Bayesian score adjusts ratings based on the number of reviews,
        preventing places with few high ratings from dominating over places
        with many slightly lower ratings.
        
        Args:
            places: List of places to rank
            
        Returns:
            Sorted list of places
        """
        def sort_key(place):
            bayesian_score = self._calculate_bayesian_score(place)
            # Negative for descending order
            return -bayesian_score
        
        return sorted(places, key=sort_key)
    
    def _rank_by_best_match(
        self,
        places: List[Any],
        user_location: Optional[Location]
    ) -> List[Any]:
        """
        Composite scoring: 45% rating, 35% popularity, 20% proximity.
        
        This mode balances multiple factors to find the best overall match:
        - Rating (45%): Quality of the place
        - Popularity (35%): How well-known/reviewed the place is
        - Proximity (20%): How close the place is to the user
        
        Args:
            places: List of places to rank
            user_location: User location for distance calculation (optional)
            
        Returns:
            Sorted list of places
        """
        # Calculate max distance for normalization (if user location available)
        max_distance = 0.0
        if user_location:
            for place in places:
                place_location = self._get_location(place)
                if place_location:
                    distance = user_location.distance_to(place_location)
                    max_distance = max(max_distance, distance)
        
        # Avoid division by zero
        if max_distance == 0.0:
            max_distance = 1.0
        
        def sort_key(place):
            # Rating component (45%) - normalized to 0-1 scale (rating is 0-5)
            rating = self._get_rating(place)
            rating_score = (rating / 5.0) * 0.45
            
            # Popularity component (35%) - Bayesian score normalized to 0-1 scale
            bayesian_score = self._calculate_bayesian_score(place)
            popularity_score = (bayesian_score / 5.0) * 0.35
            
            # Proximity component (20%) - inverse distance normalized
            proximity_score = 0.0
            if user_location:
                place_location = self._get_location(place)
                if place_location:
                    distance = user_location.distance_to(place_location)
                    # Inverse distance: closer = higher score
                    # Normalize by max_distance so score is 0-1
                    proximity_score = (1.0 - (distance / max_distance)) * 0.20
            
            # Total composite score
            composite_score = rating_score + popularity_score + proximity_score
            
            # Negative for descending order
            return -composite_score
        
        return sorted(places, key=sort_key)
    
    def _calculate_bayesian_score(self, place: Any) -> float:
        """
        Calculate Bayesian popularity score.
        
        The Bayesian average adjusts a place's rating based on the number of reviews:
        - Places with few reviews are pulled toward the prior mean
        - Places with many reviews are closer to their actual rating
        
        Formula: (prior_weight * prior_mean + review_count * rating) / (prior_weight + review_count)
        
        Args:
            place: Place object or dictionary
            
        Returns:
            Bayesian popularity score (0.0 to 5.0)
        """
        rating = self._get_rating(place)
        review_count = self._get_review_count(place)
        
        # Bayesian average formula
        numerator = (self.prior_weight * self.prior_mean) + (review_count * rating)
        denominator = self.prior_weight + review_count
        
        return numerator / denominator if denominator > 0 else self.prior_mean
