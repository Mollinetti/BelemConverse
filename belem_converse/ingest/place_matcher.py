"""
Place Matcher - Fuzzy matching between OSM and CSV data.

Uses a combination of geographic distance (Haversine) and fuzzy string
matching to identify matches between OSM places and existing database entries.
"""

import logging
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False
    logging.warning("rapidfuzz not installed. Install with: pip install rapidfuzz")

from .osm_fetcher import OSMPlace

logger = logging.getLogger(__name__)


class MatchStatus(Enum):
    """Status of a place match."""
    MATCHED = "matched"          # OSM place matches existing CSV place
    NEW = "new"                  # OSM place is new (not in CSV)
    POSSIBLY_CLOSED = "possibly_closed"  # CSV place not found in OSM


@dataclass
class MatchResult:
    """Result of matching an OSM place to CSV data."""
    osm_place: Optional[OSMPlace]
    csv_place: Optional[Dict[str, Any]]
    status: MatchStatus
    distance_meters: Optional[float] = None
    name_similarity: Optional[float] = None
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for reporting."""
        return {
            'status': self.status.value,
            'osm_name': self.osm_place.name if self.osm_place else None,
            'csv_name': self.csv_place.get('title') if self.csv_place else None,
            'distance_meters': round(self.distance_meters, 1) if self.distance_meters else None,
            'name_similarity': round(self.name_similarity, 2) if self.name_similarity else None,
            'confidence': round(self.confidence, 2),
        }


class PlaceMatcher:
    """
    Matches places between OSM data and existing CSV database.
    
    Uses a two-stage matching approach:
    1. Geographic proximity (Haversine distance)
    2. Fuzzy name matching (rapidfuzz ratio)
    """
    
    def __init__(
        self,
        distance_threshold_meters: float = 50.0,
        name_similarity_threshold: float = 0.80,
        distance_weight: float = 0.4,
        name_weight: float = 0.6
    ):
        """
        Initialize the matcher.
        
        Args:
            distance_threshold_meters: Maximum distance to consider a match (default 50m)
            name_similarity_threshold: Minimum name similarity ratio (0-1)
            distance_weight: Weight for distance in confidence score
            name_weight: Weight for name similarity in confidence score
        """
        self.distance_threshold = distance_threshold_meters
        self.name_threshold = name_similarity_threshold
        self.distance_weight = distance_weight
        self.name_weight = name_weight
        
        if not RAPIDFUZZ_AVAILABLE:
            raise ImportError("rapidfuzz is required. Install with: pip install rapidfuzz")
    
    @staticmethod
    def haversine_distance(
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """
        Calculate the Haversine distance between two points in meters.
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
            
        Returns:
            Distance in meters
        """
        R = 6371000  # Earth's radius in meters
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_phi / 2) ** 2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """
        Normalize a place name for comparison.
        
        Handles common variations in Brazilian business names.
        """
        if not name or (isinstance(name, float) and str(name) == 'nan'):
            return ""
        
        # Ensure string type
        name = str(name)
        
        # Convert to lowercase
        normalized = name.lower().strip()
        
        # Common abbreviations and variations
        replacements = [
            ('restaurante', 'rest'),
            ('lanchonete', 'lanch'),
            ('padaria', 'pad'),
            ('supermercado', 'sup'),
            ('açaí', 'acai'),
            ('são', 'sao'),
            ('nossa senhora', 'n s'),
            ('nª sª', 'n s'),
            ('av.', 'avenida'),
            ('r.', 'rua'),
            ('tv.', 'travessa'),
        ]
        
        for old, new in replacements:
            normalized = normalized.replace(old, new)
        
        return normalized
    
    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two place names.
        
        Uses a combination of rapidfuzz metrics for robustness.
        
        Args:
            name1: First name
            name2: Second name
            
        Returns:
            Similarity score from 0 to 1
        """
        if not name1 or not name2:
            return 0.0
        
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)
        
        # Use multiple fuzzy matching strategies
        ratio = fuzz.ratio(norm1, norm2) / 100.0
        partial_ratio = fuzz.partial_ratio(norm1, norm2) / 100.0
        token_sort = fuzz.token_sort_ratio(norm1, norm2) / 100.0
        
        # Weighted combination favoring token_sort for business names
        similarity = (ratio * 0.3 + partial_ratio * 0.3 + token_sort * 0.4)
        
        return similarity
    
    def find_best_match(
        self,
        osm_place: OSMPlace,
        csv_places: List[Dict[str, Any]]
    ) -> Optional[Tuple[Dict[str, Any], float, float, float]]:
        """
        Find the best matching CSV place for an OSM place.
        
        Args:
            osm_place: The OSM place to match
            csv_places: List of CSV place dictionaries
            
        Returns:
            Tuple of (matched_csv_place, distance, similarity, confidence) or None
        """
        best_match = None
        best_confidence = 0.0
        best_distance = None
        best_similarity = None
        
        for csv_place in csv_places:
            # Get CSV coordinates
            try:
                csv_lat = float(csv_place.get('location/lat', 0))
                csv_lon = float(csv_place.get('location/lng', 0))
            except (ValueError, TypeError):
                continue
            
            if csv_lat == 0 or csv_lon == 0:
                continue
            
            # Calculate geographic distance
            distance = self.haversine_distance(
                osm_place.latitude, osm_place.longitude,
                csv_lat, csv_lon
            )
            
            # Skip if too far
            if distance > self.distance_threshold * 3:  # Wider initial filter
                continue
            
            # Calculate name similarity
            csv_name = csv_place.get('title', '') or csv_place.get('titleFormatted', '') or ''
            # Handle NaN values from pandas
            if isinstance(csv_name, float):
                csv_name = '' if str(csv_name) == 'nan' else str(csv_name)
            similarity = self.calculate_name_similarity(osm_place.name, csv_name)
            
            # Skip if name is too different
            if similarity < 0.5:  # Loose initial filter
                continue
            
            # Calculate confidence score
            # Distance score: 1.0 at 0m, 0.0 at threshold
            distance_score = max(0, 1 - (distance / self.distance_threshold))
            
            # Combined confidence
            confidence = (
                self.distance_weight * distance_score +
                self.name_weight * similarity
            )
            
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = csv_place
                best_distance = distance
                best_similarity = similarity
        
        if best_match and best_distance <= self.distance_threshold and best_similarity >= self.name_threshold:
            return (best_match, best_distance, best_similarity, best_confidence)
        
        # Also accept if very close geographically even with lower name match
        if best_match and best_distance is not None and best_distance <= 20 and best_similarity >= 0.6:
            return (best_match, best_distance, best_similarity, best_confidence)
        
        # Also accept if name is very similar even if a bit farther
        if best_match and best_similarity is not None and best_similarity >= 0.9 and best_distance <= self.distance_threshold * 2:
            return (best_match, best_distance, best_similarity, best_confidence)
        
        return None
    
    def match_all(
        self,
        osm_places: List[OSMPlace],
        csv_places: List[Dict[str, Any]],
        progress_callback: Optional[callable] = None
    ) -> List[MatchResult]:
        """
        Match all OSM places against CSV places.
        
        Args:
            osm_places: List of places from OSM
            csv_places: List of places from CSV
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of MatchResult objects
        """
        results = []
        matched_csv_ids = set()
        
        logger.info(f"Matching {len(osm_places)} OSM places against {len(csv_places)} CSV places")
        
        # First pass: Match OSM places to CSV
        for i, osm_place in enumerate(osm_places):
            if progress_callback and i % 100 == 0:
                progress_callback(f"Matching OSM places: {i}/{len(osm_places)}")
            
            match = self.find_best_match(osm_place, csv_places)
            
            if match:
                csv_place, distance, similarity, confidence = match
                csv_id = csv_place.get('placeId') or csv_place.get('cid') or id(csv_place)
                
                # Avoid duplicate matches
                if csv_id not in matched_csv_ids:
                    matched_csv_ids.add(csv_id)
                    results.append(MatchResult(
                        osm_place=osm_place,
                        csv_place=csv_place,
                        status=MatchStatus.MATCHED,
                        distance_meters=distance,
                        name_similarity=similarity,
                        confidence=confidence
                    ))
                else:
                    # This OSM place matches a CSV place that was already matched
                    # Mark it as new (duplicate in OSM)
                    results.append(MatchResult(
                        osm_place=osm_place,
                        csv_place=None,
                        status=MatchStatus.NEW,
                        confidence=0.0
                    ))
            else:
                # No match found - this is a new place
                results.append(MatchResult(
                    osm_place=osm_place,
                    csv_place=None,
                    status=MatchStatus.NEW,
                    confidence=0.0
                ))
        
        # Second pass: Find CSV places not matched (possibly closed)
        if progress_callback:
            progress_callback("Identifying potentially closed places...")
        
        for csv_place in csv_places:
            csv_id = csv_place.get('placeId') or csv_place.get('cid') or id(csv_place)
            
            if csv_id not in matched_csv_ids:
                results.append(MatchResult(
                    osm_place=None,
                    csv_place=csv_place,
                    status=MatchStatus.POSSIBLY_CLOSED,
                    confidence=0.0
                ))
        
        # Log summary
        matched_count = sum(1 for r in results if r.status == MatchStatus.MATCHED)
        new_count = sum(1 for r in results if r.status == MatchStatus.NEW)
        closed_count = sum(1 for r in results if r.status == MatchStatus.POSSIBLY_CLOSED)
        
        logger.info(f"Matching complete: {matched_count} matched, {new_count} new, {closed_count} possibly closed")
        
        return results
    
    def get_match_summary(self, results: List[MatchResult]) -> Dict[str, Any]:
        """
        Generate a summary of match results.
        
        Args:
            results: List of MatchResult objects
            
        Returns:
            Summary dictionary with statistics
        """
        matched = [r for r in results if r.status == MatchStatus.MATCHED]
        new = [r for r in results if r.status == MatchStatus.NEW]
        possibly_closed = [r for r in results if r.status == MatchStatus.POSSIBLY_CLOSED]
        
        avg_confidence = sum(r.confidence for r in matched) / len(matched) if matched else 0
        avg_distance = sum(r.distance_meters for r in matched if r.distance_meters) / len(matched) if matched else 0
        avg_similarity = sum(r.name_similarity for r in matched if r.name_similarity) / len(matched) if matched else 0
        
        return {
            'total_osm_places': len([r for r in results if r.osm_place]),
            'total_csv_places': len([r for r in results if r.csv_place]) + len(matched),
            'matched_count': len(matched),
            'new_count': len(new),
            'possibly_closed_count': len(possibly_closed),
            'average_confidence': round(avg_confidence, 3),
            'average_distance_meters': round(avg_distance, 1),
            'average_name_similarity': round(avg_similarity, 3),
        }



