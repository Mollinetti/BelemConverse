"""
Base city configuration module.

Defines the CityConfig dataclass that holds all city-specific settings.
Each city should provide its own configuration implementing these fields.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from pathlib import Path


@dataclass
class CityConfig:
    """
    Configuration for a specific city.
    
    This dataclass holds all the city-specific settings needed
    for the BelemConverse system to operate in different cities.
    """
    
    # Basic info
    name: str  # City name (e.g., "Belém")
    slug: str  # URL-friendly name (e.g., "belem")
    country: str  # Country name (e.g., "Brazil")
    country_code: str  # ISO country code (e.g., "BR")
    state: str  # State/Province (e.g., "Pará")
    
    # Languages
    primary_language: str  # Main language (e.g., "pt")
    supported_languages: List[str] = field(default_factory=lambda: ["pt", "en"])
    
    # Geographic bounds
    center_coordinates: Tuple[float, float] = (0.0, 0.0)  # (lat, lng)
    bounds_min: Tuple[float, float] = (0.0, 0.0)  # SW corner (lat, lng)
    bounds_max: Tuple[float, float] = (0.0, 0.0)  # NE corner (lat, lng)
    
    # Timezone
    timezone: str = "UTC"
    
    # Data paths (relative to project root)
    csv_path: str = ""
    chroma_db_path: str = ""
    
    # Category mappings - map generic categories to city-specific terms
    category_mappings: Dict[str, List[str]] = field(default_factory=dict)
    
    # Subcategory mappings - map subcategories to parent categories
    subcategory_mappings: Dict[str, str] = field(default_factory=dict)
    
    # Special local categories (unique to this city)
    local_categories: List[str] = field(default_factory=list)
    
    # Default search radius in km
    default_search_radius: float = 5.0
    
    # Currency
    currency_code: str = "USD"
    currency_symbol: str = "$"
    
    def is_within_bounds(self, lat: float, lng: float) -> bool:
        """Check if coordinates are within city bounds."""
        return (
            self.bounds_min[0] <= lat <= self.bounds_max[0] and
            self.bounds_min[1] <= lng <= self.bounds_max[1]
        )
    
    def get_category_terms(self, category: str) -> List[str]:
        """Get all search terms for a category."""
        return self.category_mappings.get(category, [category])
    
    def get_parent_category(self, subcategory: str) -> Optional[str]:
        """Get parent category for a subcategory."""
        return self.subcategory_mappings.get(subcategory)
    
    def get_description(self, language: str = "en") -> str:
        """Get city description in specified language."""
        if language == "pt":
            return f"{self.name}, {self.state}, {self.country}"
        return f"{self.name}, {self.state}, {self.country}"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'slug': self.slug,
            'country': self.country,
            'country_code': self.country_code,
            'state': self.state,
            'primary_language': self.primary_language,
            'supported_languages': self.supported_languages,
            'center_coordinates': self.center_coordinates,
            'bounds': {
                'min': self.bounds_min,
                'max': self.bounds_max
            },
            'timezone': self.timezone,
            'csv_path': self.csv_path,
            'chroma_db_path': self.chroma_db_path,
            'default_search_radius': self.default_search_radius,
            'currency': {
                'code': self.currency_code,
                'symbol': self.currency_symbol
            }
        }
    
    def __str__(self) -> str:
        return f"CityConfig({self.name}, {self.country})"
    
    def __repr__(self) -> str:
        return self.__str__()


