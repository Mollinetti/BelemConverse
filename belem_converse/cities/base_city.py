"""
Base city configuration module.

Defines the CityConfig dataclass that holds all city-specific settings.
Each city should provide its own configuration implementing these fields.
"""

from dataclasses import dataclass, field


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
    supported_languages: list[str] = field(default_factory=lambda: ["pt", "en"])
    
    # Geographic bounds
    center_coordinates: tuple[float, float] = (0.0, 0.0)  # (lat, lng)
    bounds_min: tuple[float, float] = (0.0, 0.0)  # SW corner (lat, lng)
    bounds_max: tuple[float, float] = (0.0, 0.0)  # NE corner (lat, lng)
    
    # Timezone
    timezone: str = "UTC"

    # Short state code written to the catalog (e.g., "PA").
    state_code: str = ""
    # Catalog build: values of the export's `city` column that belong to this
    # municipality (matched accent-insensitively; districts included).
    municipalities: list[str] = field(default_factory=list)
    # Words left lowercase when an all-caps or all-lowercase title is recased.
    title_case_exceptions: list[str] = field(default_factory=list)
    
    # Data paths (relative to project root)
    csv_path: str = ""
    # Built place catalog, relative to the project root (committed to git).
    catalog_path: str = ""
    chroma_db_path: str = ""
    
    # Category mappings - map generic categories to city-specific terms
    category_mappings: dict[str, list[str]] = field(default_factory=dict)
    
    # Subcategory mappings - map subcategories to parent categories
    subcategory_mappings: dict[str, str] = field(default_factory=dict)
    
    # Follow-up chip text per category and language ({"bar": {"pt-BR": "Bares", "en": "Bars"}}).
    # Each label must be letters and spaces only, and the planner must read it as that category.
    category_labels: dict[str, dict[str, str]] = field(default_factory=dict)

    # Special local categories (unique to this city)
    local_categories: list[str] = field(default_factory=list)
    
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
    
    def get_category_terms(self, category: str) -> list[str]:
        """Get all search terms for a category."""
        return self.category_mappings.get(category, [category])
    
    def get_parent_category(self, subcategory: str) -> str | None:
        """Get parent category for a subcategory."""
        return self.subcategory_mappings.get(subcategory)
    
    def get_description(self, language: str = "en") -> str:
        """Get city description in specified language."""
        if language == "pt":
            return f"{self.name}, {self.state}, {self.country}"
        return f"{self.name}, {self.state}, {self.country}"
    
    def to_dict(self) -> dict:
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


