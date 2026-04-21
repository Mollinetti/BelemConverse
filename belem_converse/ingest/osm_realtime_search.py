"""
OSM Real-time Search - Query-specific OSM search for fallback scenarios.

This module provides lightweight, on-demand OSM queries when the database
search fails or returns poor results. Results are cached briefly to avoid
repeated API calls.
"""

import logging
import time
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from langchain_core.documents import Document

from .osm_fetcher import OSMFetcher, OSMPlace

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry for OSM search results."""
    results: List[Document]
    timestamp: datetime
    query_key: str


class OSMRealtimeSearch:
    """
    Performs real-time OSM searches based on user queries.
    
    Converts natural language queries to OSM tags and performs
    location-based searches with caching to reduce API load.
    """
    
    # Cache TTL in seconds (5 minutes)
    CACHE_TTL = 300
    
    # Maximum results to return from OSM
    MAX_RESULTS = 5
    
    # Query to OSM tag mappings
    QUERY_TAG_MAPPINGS = {
        # Restaurants and food
        r'\b(restaurant|restaurante|comida|food|eat|comer|almoço|jantar|lunch|dinner)\b': [
            ('amenity', 'restaurant'),
        ],
        r'\b(cafe|café|cafeteria|coffee|cappuccino)\b': [
            ('amenity', 'cafe'),
        ],
        r'\b(bar|pub|boteco|drinks|beer|cerveja)\b': [
            ('amenity', 'bar'),
            ('amenity', 'pub'),
        ],
        r'\b(açaí|acai|açai|acaí|assai)\b': [
            ('amenity', 'cafe'),
            ('amenity', 'ice_cream'),
        ],
        r'\b(pizza|pizzaria)\b': [
            ('amenity', 'restaurant'),
            ('cuisine', 'pizza'),
        ],
        r'\b(hamburguer|burger|hamburgueria|lanche)\b': [
            ('amenity', 'fast_food'),
            ('amenity', 'restaurant'),
        ],
        r'\b(padaria|bakery|pão|bread)\b': [
            ('shop', 'bakery'),
        ],
        r'\b(sorvete|ice cream|sorveteria|gelato)\b': [
            ('amenity', 'ice_cream'),
        ],
        
        # Hotels and accommodation
        r'\b(hotel|hotéis|hotels|hospedagem|accommodation)\b': [
            ('tourism', 'hotel'),
        ],
        r'\b(hostel|albergue)\b': [
            ('tourism', 'hostel'),
        ],
        r'\b(pousada|inn|guest.?house)\b': [
            ('tourism', 'guest_house'),
        ],
        
        # Tourism and attractions
        r'\b(museum|museu|museums)\b': [
            ('tourism', 'museum'),
        ],
        r'\b(park|parque|praça|square)\b': [
            ('leisure', 'park'),
            ('leisure', 'garden'),
        ],
        r'\b(church|igreja|cathedral|catedral|basílica)\b': [
            ('amenity', 'place_of_worship'),
            ('building', 'church'),
            ('building', 'cathedral'),
        ],
        r'\b(theater|teatro|theatre)\b': [
            ('amenity', 'theatre'),
        ],
        r'\b(beach|praia)\b': [
            ('natural', 'beach'),
            ('leisure', 'beach_resort'),
        ],
        r'\b(monument|monumento|memorial|statue|estátua)\b': [
            ('historic', 'monument'),
            ('historic', 'memorial'),
        ],
        r'\b(fort|forte|fortress|fortaleza)\b': [
            ('historic', 'fort'),
            ('historic', 'castle'),
        ],
        r'\b(zoo|zoológico)\b': [
            ('tourism', 'zoo'),
        ],
        r'\b(market|mercado|feira)\b': [
            ('amenity', 'marketplace'),
            ('shop', 'supermarket'),
        ],
        
        # Generic tourist attraction
        r'\b(tourist|turístico|attraction|atração|ponto turístico|sightseeing)\b': [
            ('tourism', 'attraction'),
            ('tourism', 'viewpoint'),
        ],
        
        # Services
        r'\b(pharmacy|farmácia|drogaria)\b': [
            ('amenity', 'pharmacy'),
        ],
        r'\b(hospital|emergência|emergency)\b': [
            ('amenity', 'hospital'),
        ],
        r'\b(bank|banco|atm|caixa)\b': [
            ('amenity', 'bank'),
            ('amenity', 'atm'),
        ],
        r'\b(gas station|posto|gasolina|fuel)\b': [
            ('amenity', 'fuel'),
        ],
    }
    
    # Default search radius in meters
    DEFAULT_RADIUS = 2000
    
    def __init__(
        self,
        cache_ttl: int = CACHE_TTL,
        max_results: int = MAX_RESULTS,
        default_radius: int = DEFAULT_RADIUS
    ):
        """
        Initialize the real-time searcher.
        
        Args:
            cache_ttl: Cache time-to-live in seconds
            max_results: Maximum number of results to return
            default_radius: Default search radius in meters
        """
        self.cache_ttl = cache_ttl
        self.max_results = max_results
        self.default_radius = default_radius
        self._cache: Dict[str, CacheEntry] = {}
        self._fetcher = OSMFetcher(timeout=30, retry_count=2, retry_delay=3)
        
    def _extract_place_name(self, query: str) -> Optional[str]:
        """
        Extract a specific place name from the query if present.
        
        Args:
            query: User query
            
        Returns:
            Extracted place name or None
        """
        # Patterns for extracting place names
        patterns = [
            r'"([^"]+)"',  # Quoted names
            r"'([^']+)'",  # Single-quoted names
            r'(?:called|named|chamad[ao])\s+(.+?)(?:\s+(?:is|está|still|ainda|open|aberto|closed|fechado)|$)',
            r'(?:find|encontr[ae]|procur[ae]|where is|onde fica|cadê)\s+(?:the\s+)?(.+?)(?:\s*\?|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Filter out generic terms
                if len(name) > 2 and not re.match(r'^(a|an|the|um|uma|o|a)$', name, re.IGNORECASE):
                    return name
        
        return None
    
    def _query_to_osm_tags(self, query: str) -> List[Tuple[str, str]]:
        """
        Convert a natural language query to OSM tags.
        
        Args:
            query: User query
            
        Returns:
            List of (key, value) tuples for OSM tags
        """
        query_lower = query.lower()
        tags = []
        
        for pattern, tag_list in self.QUERY_TAG_MAPPINGS.items():
            if re.search(pattern, query_lower, re.IGNORECASE):
                tags.extend(tag_list)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)
        
        return unique_tags
    
    def _build_overpass_query(
        self,
        tags: List[Tuple[str, str]],
        lat: float,
        lon: float,
        radius: int,
        place_name: Optional[str] = None
    ) -> str:
        """
        Build an Overpass query for the given tags and location.
        
        Args:
            tags: List of OSM tag tuples
            lat: Latitude
            lon: Longitude
            radius: Search radius in meters
            place_name: Optional specific place name to search for
            
        Returns:
            Overpass QL query string
        """
        query_parts = []
        
        for key, value in tags:
            if place_name:
                # Search for specific name
                query_parts.append(
                    f'  node["{key}"="{value}"]["name"~"{place_name}",i](around:{radius},{lat},{lon});'
                )
                query_parts.append(
                    f'  way["{key}"="{value}"]["name"~"{place_name}",i](around:{radius},{lat},{lon});'
                )
            else:
                # General category search
                query_parts.append(
                    f'  node["{key}"="{value}"]["name"](around:{radius},{lat},{lon});'
                )
                query_parts.append(
                    f'  way["{key}"="{value}"]["name"](around:{radius},{lat},{lon});'
                )
        
        query = f"""
[out:json][timeout:30];
(
{chr(10).join(query_parts)}
);
out body center;
"""
        return query
    
    def _osm_place_to_document(
        self,
        place: OSMPlace,
        user_lat: float,
        user_lon: float
    ) -> Document:
        """
        Convert an OSMPlace to a LangChain Document.
        
        Args:
            place: OSM place object
            user_lat: User's latitude
            user_lon: User's longitude
            
        Returns:
            LangChain Document
        """
        from .place_matcher import PlaceMatcher
        
        # Calculate distance
        distance = PlaceMatcher.haversine_distance(
            user_lat, user_lon,
            place.latitude, place.longitude
        )
        distance_km = distance / 1000
        
        # Build page content similar to CSV format
        content_parts = [
            f"title: {place.name}",
            f"categoryName: {place.category.replace('_', ' ').title()}",
            f"location/lat: {place.latitude}",
            f"location/lng: {place.longitude}",
        ]
        
        if place.address:
            content_parts.append(f"address: {place.address}")
        if place.phone:
            content_parts.append(f"phone: {place.phone}")
        if place.website:
            content_parts.append(f"website: {place.website}")
        if place.opening_hours:
            content_parts.append(f"businessTime: {place.opening_hours}")
        
        content_parts.append(f"distance_km: {distance_km:.2f}")
        
        page_content = "\n".join(content_parts)
        
        metadata = {
            'title': place.name,
            'categoryName': place.category.replace('_', ' ').title(),
            'location/lat': place.latitude,
            'location/lng': place.longitude,
            'address': place.address or '',
            'phone': place.phone or '',
            'website': place.website or '',
            'businessTime': place.opening_hours or '',
            'distance_km': distance_km,
            'data_source': 'osm_realtime',
            'osm_id': place.osm_id,
            'osm_type': place.osm_type,
            'totalScore': None,  # No ratings from OSM
            'reviewsCount': 0,
        }
        
        return Document(page_content=page_content, metadata=metadata)
    
    def _get_cache_key(
        self,
        query: str,
        lat: float,
        lon: float,
        radius: int
    ) -> str:
        """Generate a cache key for the search."""
        # Round coordinates to reduce cache misses for nearby locations
        lat_rounded = round(lat, 3)
        lon_rounded = round(lon, 3)
        return f"{query.lower().strip()}|{lat_rounded}|{lon_rounded}|{radius}"
    
    def _get_from_cache(self, cache_key: str) -> Optional[List[Document]]:
        """Get results from cache if still valid."""
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if datetime.now() - entry.timestamp < timedelta(seconds=self.cache_ttl):
                logger.debug(f"Cache hit for: {cache_key}")
                return entry.results
            else:
                # Expired, remove from cache
                del self._cache[cache_key]
        return None
    
    def _add_to_cache(self, cache_key: str, results: List[Document]) -> None:
        """Add results to cache."""
        self._cache[cache_key] = CacheEntry(
            results=results,
            timestamp=datetime.now(),
            query_key=cache_key
        )
        
        # Cleanup old entries if cache is getting large
        if len(self._cache) > 100:
            self._cleanup_cache()
    
    def _cleanup_cache(self) -> None:
        """Remove expired entries from cache."""
        now = datetime.now()
        expired = [
            key for key, entry in self._cache.items()
            if now - entry.timestamp > timedelta(seconds=self.cache_ttl)
        ]
        for key in expired:
            del self._cache[key]
    
    def search(
        self,
        query: str,
        user_coordinates: Tuple[float, float],
        radius: Optional[int] = None,
        categories: Optional[List[str]] = None
    ) -> List[Document]:
        """
        Perform a real-time OSM search.
        
        Args:
            query: User's search query
            user_coordinates: (latitude, longitude) tuple
            radius: Search radius in meters (optional)
            categories: Specific categories to search (optional)
            
        Returns:
            List of Documents from OSM
        """
        lat, lon = user_coordinates
        radius = radius or self.default_radius
        
        # Check cache
        cache_key = self._get_cache_key(query, lat, lon, radius)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        # Extract potential place name
        place_name = self._extract_place_name(query)
        
        # Convert query to OSM tags
        if categories:
            # Use provided categories
            tags = []
            for cat in categories:
                cat_lower = cat.lower()
                for pattern, tag_list in self.QUERY_TAG_MAPPINGS.items():
                    if cat_lower in pattern:
                        tags.extend(tag_list)
                        break
            if not tags:
                # Fallback to query-based extraction
                tags = self._query_to_osm_tags(query)
        else:
            tags = self._query_to_osm_tags(query)
        
        if not tags:
            logger.info(f"No OSM tags found for query: {query}")
            return []
        
        logger.info(f"OSM realtime search: {len(tags)} tags, radius={radius}m, name={place_name}")
        
        # Build and execute query
        overpass_query = self._build_overpass_query(tags, lat, lon, radius, place_name)
        
        try:
            import requests
            
            # Try each endpoint
            endpoints = OSMFetcher.OVERPASS_ENDPOINTS
            for endpoint in endpoints:
                try:
                    response = requests.post(
                        endpoint,
                        data={'data': overpass_query},
                        timeout=30,
                        headers={'User-Agent': 'BelemConverse/1.0 (tourism research)'}
                    )
                    response.raise_for_status()
                    data = response.json()
                    break
                except Exception as e:
                    logger.warning(f"Endpoint {endpoint} failed: {e}")
                    continue
            else:
                logger.error("All OSM endpoints failed")
                return []
            
            elements = data.get('elements', [])
            logger.info(f"OSM returned {len(elements)} elements")
            
            # Parse elements to OSMPlace objects
            places = []
            for element in elements:
                place = self._fetcher._parse_element(element)
                if place:
                    places.append(place)
            
            # Convert to Documents and sort by distance
            documents = []
            for place in places:
                doc = self._osm_place_to_document(place, lat, lon)
                documents.append(doc)
            
            # Sort by distance
            documents.sort(key=lambda d: d.metadata.get('distance_km', float('inf')))
            
            # Limit results
            documents = documents[:self.max_results]
            
            # Cache results
            self._add_to_cache(cache_key, documents)
            
            logger.info(f"OSM realtime search returned {len(documents)} documents")
            return documents
            
        except Exception as e:
            logger.error(f"OSM realtime search error: {e}")
            return []
    
    def search_by_name(
        self,
        name: str,
        user_coordinates: Tuple[float, float],
        radius: int = 5000
    ) -> List[Document]:
        """
        Search for a specific place by name.
        
        Args:
            name: Place name to search for
            user_coordinates: (latitude, longitude) tuple
            radius: Search radius in meters
            
        Returns:
            List of Documents matching the name
        """
        lat, lon = user_coordinates
        
        # Build a name-specific query
        query = f"""
[out:json][timeout:30];
(
  node["name"~"{name}",i](around:{radius},{lat},{lon});
  way["name"~"{name}",i](around:{radius},{lat},{lon});
);
out body center;
"""
        
        cache_key = f"name:{name.lower()}|{round(lat, 3)}|{round(lon, 3)}|{radius}"
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        try:
            import requests
            
            for endpoint in OSMFetcher.OVERPASS_ENDPOINTS:
                try:
                    response = requests.post(
                        endpoint,
                        data={'data': query},
                        timeout=30,
                        headers={'User-Agent': 'BelemConverse/1.0'}
                    )
                    response.raise_for_status()
                    data = response.json()
                    break
                except Exception:
                    continue
            else:
                return []
            
            elements = data.get('elements', [])
            documents = []
            
            for element in elements:
                place = self._fetcher._parse_element(element)
                if place:
                    doc = self._osm_place_to_document(place, lat, lon)
                    documents.append(doc)
            
            documents.sort(key=lambda d: d.metadata.get('distance_km', float('inf')))
            documents = documents[:self.max_results]
            
            self._add_to_cache(cache_key, documents)
            return documents
            
        except Exception as e:
            logger.error(f"OSM name search error: {e}")
            return []


# Singleton instance for reuse
_realtime_searcher: Optional[OSMRealtimeSearch] = None


def get_realtime_searcher() -> OSMRealtimeSearch:
    """Get or create the singleton OSM realtime searcher."""
    global _realtime_searcher
    if _realtime_searcher is None:
        _realtime_searcher = OSMRealtimeSearch()
    return _realtime_searcher


