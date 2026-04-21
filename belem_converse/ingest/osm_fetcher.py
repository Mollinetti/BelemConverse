"""
OSM Data Fetcher - Queries OpenStreetMap Overpass API for POIs in Belém.

This module fetches points of interest from OpenStreetMap to supplement
and refresh the local database of establishments.
"""

import requests
import logging
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class OSMPlace:
    """Represents a place fetched from OpenStreetMap."""
    osm_id: int
    osm_type: str  # 'node', 'way', or 'relation'
    name: str
    latitude: float
    longitude: float
    category: str
    subcategories: List[str] = field(default_factory=list)
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    opening_hours: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for CSV export."""
        return {
            'osm_id': self.osm_id,
            'osm_type': self.osm_type,
            'name': self.name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'category': self.category,
            'subcategories': ';'.join(self.subcategories),
            'address': self.address or '',
            'phone': self.phone or '',
            'website': self.website or '',
            'opening_hours': self.opening_hours or '',
        }


class OSMFetcher:
    """
    Fetches POI data from OpenStreetMap using the Overpass API.
    
    Supports fetching various establishment types relevant to tourism:
    restaurants, cafes, bars, hotels, attractions, museums, parks, etc.
    """
    
    # Overpass API endpoints (with fallbacks)
    OVERPASS_ENDPOINTS = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    ]
    
    # Default endpoint
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"
    
    # Belém metropolitan area bounding box
    # Slightly expanded to catch establishments on the edges
    DEFAULT_BBOX = {
        'south': -1.55,
        'west': -48.60,
        'north': -1.35,
        'east': -48.35
    }
    
    # OSM tag mappings to categories
    CATEGORY_MAPPINGS = {
        # Amenities
        'amenity=restaurant': 'restaurant',
        'amenity=cafe': 'cafe',
        'amenity=bar': 'bar',
        'amenity=pub': 'bar',
        'amenity=fast_food': 'fast_food',
        'amenity=ice_cream': 'ice_cream',
        'amenity=food_court': 'food_court',
        
        # Tourism
        'tourism=hotel': 'hotel',
        'tourism=hostel': 'hostel',
        'tourism=guest_house': 'pousada',
        'tourism=motel': 'motel',
        'tourism=attraction': 'tourist_attraction',
        'tourism=museum': 'museum',
        'tourism=gallery': 'gallery',
        'tourism=viewpoint': 'viewpoint',
        'tourism=zoo': 'zoo',
        'tourism=theme_park': 'theme_park',
        
        # Leisure
        'leisure=park': 'park',
        'leisure=garden': 'garden',
        'leisure=beach_resort': 'beach',
        'leisure=nature_reserve': 'nature_reserve',
        'leisure=marina': 'marina',
        
        # Historic
        'historic=monument': 'monument',
        'historic=memorial': 'memorial',
        'historic=fort': 'fort',
        'historic=ruins': 'ruins',
        'historic=church': 'church',
        
        # Religious
        'amenity=place_of_worship': 'church',
        'building=church': 'church',
        'building=cathedral': 'cathedral',
        
        # Natural
        'natural=beach': 'beach',
        
        # Shops (selected relevant ones)
        'shop=supermarket': 'supermarket',
        'shop=bakery': 'bakery',
        'shop=confectionery': 'confectionery',
        'shop=chocolate': 'chocolate_shop',
        
        # Arts & Culture
        'amenity=theatre': 'theater',
        'amenity=cinema': 'cinema',
        'amenity=arts_centre': 'cultural_center',
        'amenity=community_centre': 'community_center',
    }
    
    def __init__(
        self,
        bbox: Optional[Dict[str, float]] = None,
        overpass_url: str = None,
        timeout: int = 180,
        retry_count: int = 3,
        retry_delay: int = 10
    ):
        """
        Initialize the OSM Fetcher.
        
        Args:
            bbox: Bounding box dict with 'south', 'west', 'north', 'east' keys
            overpass_url: Custom Overpass API endpoint
            timeout: Request timeout in seconds
            retry_count: Number of retries on failure
            retry_delay: Delay between retries in seconds
        """
        self.bbox = bbox or self.DEFAULT_BBOX
        self.overpass_url = overpass_url or self.OVERPASS_URL
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        
    def _build_query(self, categories: Optional[List[str]] = None) -> str:
        """
        Build Overpass QL query for the specified categories.
        
        Args:
            categories: List of category names to fetch. If None, fetches all.
            
        Returns:
            Overpass QL query string
        """
        bbox_str = f"{self.bbox['south']},{self.bbox['west']},{self.bbox['north']},{self.bbox['east']}"
        
        # Build tag filters based on categories
        if categories:
            # Filter to specific categories
            tag_filters = []
            for osm_tag, cat_name in self.CATEGORY_MAPPINGS.items():
                if cat_name in categories:
                    key, value = osm_tag.split('=')
                    tag_filters.append(f'["{key}"="{value}"]')
        else:
            # Fetch all mapped categories
            tag_filters = []
            seen_keys = set()
            for osm_tag in self.CATEGORY_MAPPINGS.keys():
                key, value = osm_tag.split('=')
                tag_filters.append(f'["{key}"="{value}"]')
        
        # Build query parts for nodes, ways, and relations
        query_parts = []
        for tag_filter in tag_filters:
            query_parts.append(f'  node{tag_filter}["name"]({bbox_str});')
            query_parts.append(f'  way{tag_filter}["name"]({bbox_str});')
        
        query = f"""
[out:json][timeout:{self.timeout}];
(
{chr(10).join(query_parts)}
);
out body center;
"""
        return query
    
    def _parse_element(self, element: Dict[str, Any]) -> Optional[OSMPlace]:
        """
        Parse a single OSM element into an OSMPlace object.
        
        Args:
            element: Raw OSM element from Overpass response
            
        Returns:
            OSMPlace object or None if parsing fails
        """
        try:
            tags = element.get('tags', {})
            name = tags.get('name')
            
            if not name:
                return None
            
            # Get coordinates (center for ways/relations)
            if element['type'] == 'node':
                lat = element.get('lat')
                lon = element.get('lon')
            else:
                center = element.get('center', {})
                lat = center.get('lat')
                lon = center.get('lon')
            
            if not lat or not lon:
                return None
            
            # Determine category from tags
            category = 'unknown'
            subcategories = []
            
            for osm_tag, cat_name in self.CATEGORY_MAPPINGS.items():
                key, value = osm_tag.split('=')
                if tags.get(key) == value:
                    if category == 'unknown':
                        category = cat_name
                    else:
                        subcategories.append(cat_name)
            
            # Extract address
            address_parts = []
            if tags.get('addr:street'):
                addr = tags.get('addr:street')
                if tags.get('addr:housenumber'):
                    addr = f"{addr}, {tags.get('addr:housenumber')}"
                address_parts.append(addr)
            if tags.get('addr:suburb'):
                address_parts.append(tags.get('addr:suburb'))
            if tags.get('addr:city'):
                address_parts.append(tags.get('addr:city'))
            if tags.get('addr:postcode'):
                address_parts.append(tags.get('addr:postcode'))
            
            address = ' - '.join(address_parts) if address_parts else None
            
            return OSMPlace(
                osm_id=element['id'],
                osm_type=element['type'],
                name=name,
                latitude=lat,
                longitude=lon,
                category=category,
                subcategories=subcategories,
                address=address,
                phone=tags.get('phone') or tags.get('contact:phone'),
                website=tags.get('website') or tags.get('contact:website'),
                opening_hours=tags.get('opening_hours'),
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse OSM element {element.get('id')}: {e}")
            return None
    
    def fetch(
        self,
        categories: Optional[List[str]] = None,
        progress_callback: Optional[callable] = None
    ) -> List[OSMPlace]:
        """
        Fetch POIs from OpenStreetMap.
        
        Args:
            categories: List of category names to fetch. If None, fetches all.
            progress_callback: Optional callback function for progress updates
            
        Returns:
            List of OSMPlace objects
        """
        query = self._build_query(categories)
        logger.info(f"Fetching OSM data for bbox: {self.bbox}")
        logger.debug(f"Query:\n{query}")
        
        # Try each endpoint
        endpoints_to_try = [self.overpass_url] + [e for e in self.OVERPASS_ENDPOINTS if e != self.overpass_url]
        
        for endpoint_idx, endpoint in enumerate(endpoints_to_try):
            logger.info(f"Trying endpoint {endpoint_idx + 1}/{len(endpoints_to_try)}: {endpoint}")
            
            # Retry logic for each endpoint
            for attempt in range(self.retry_count):
                try:
                    if progress_callback:
                        progress_callback(f"Querying {endpoint.split('/')[2]} (attempt {attempt + 1})...")
                    
                    response = requests.post(
                        endpoint,
                        data={'data': query},
                        timeout=self.timeout,
                        headers={'User-Agent': 'BelemConverse/1.0 (tourism research)'}
                    )
                    response.raise_for_status()
                    
                    data = response.json()
                    elements = data.get('elements', [])
                    
                    logger.info(f"Received {len(elements)} elements from OSM")
                    
                    if progress_callback:
                        progress_callback(f"Parsing {len(elements)} elements...")
                    
                    # Parse elements
                    places = []
                    for element in elements:
                        place = self._parse_element(element)
                        if place:
                            places.append(place)
                    
                    # Deduplicate by OSM ID
                    seen_ids = set()
                    unique_places = []
                    for place in places:
                        key = (place.osm_type, place.osm_id)
                        if key not in seen_ids:
                            seen_ids.add(key)
                            unique_places.append(place)
                    
                    logger.info(f"Successfully parsed {len(unique_places)} unique places")
                    return unique_places
                    
                except requests.exceptions.Timeout:
                    logger.warning(f"Timeout on {endpoint} (attempt {attempt + 1})")
                    if attempt < self.retry_count - 1:
                        time.sleep(self.retry_delay)
                        
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Request failed on {endpoint}: {e}")
                    if attempt < self.retry_count - 1:
                        time.sleep(self.retry_delay)
                    else:
                        # Move to next endpoint
                        break
                        
                except Exception as e:
                    logger.error(f"Unexpected error fetching OSM data: {e}")
                    raise
            
            # Try next endpoint after all retries failed
            logger.info(f"Moving to next endpoint after failures on {endpoint}")
        
        logger.error("All endpoints and retry attempts failed")
        return []
    
    def fetch_by_category_batch(
        self,
        categories: List[str],
        batch_size: int = 5,
        delay_between_batches: int = 5
    ) -> List[OSMPlace]:
        """
        Fetch POIs in batches to avoid overloading the Overpass API.
        
        Args:
            categories: List of all categories to fetch
            batch_size: Number of categories per batch
            delay_between_batches: Delay in seconds between batches
            
        Returns:
            List of all OSMPlace objects
        """
        all_places = []
        
        for i in range(0, len(categories), batch_size):
            batch = categories[i:i + batch_size]
            logger.info(f"Fetching batch {i // batch_size + 1}: {batch}")
            
            places = self.fetch(categories=batch)
            all_places.extend(places)
            
            if i + batch_size < len(categories):
                logger.info(f"Waiting {delay_between_batches}s before next batch...")
                time.sleep(delay_between_batches)
        
        # Final deduplication across batches
        seen_ids = set()
        unique_places = []
        for place in all_places:
            key = (place.osm_type, place.osm_id)
            if key not in seen_ids:
                seen_ids.add(key)
                unique_places.append(place)
        
        return unique_places


def get_all_categories() -> List[str]:
    """Get list of all supported category names."""
    return list(set(OSMFetcher.CATEGORY_MAPPINGS.values()))


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)
    fetcher = OSMFetcher()
    places = fetcher.fetch(categories=['restaurant', 'cafe'])
    print(f"Found {len(places)} places")
    for place in places[:5]:
        print(f"  - {place.name} ({place.category}) at {place.latitude}, {place.longitude}")

