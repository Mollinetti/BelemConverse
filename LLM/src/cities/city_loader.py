"""
City loader module.

Provides functions to load city configurations dynamically
based on environment variables or explicit selection.
"""

import os
import logging
from typing import Dict, Optional, List
from pathlib import Path

from .base_city import CityConfig

logger = logging.getLogger(__name__)

# Registry of available cities
_CITY_REGISTRY: Dict[str, callable] = {}

# Default city if none specified
DEFAULT_CITY = "belem"

# Environment variable for city selection
CITY_ENV_VAR = "BELEMCONVERSE_CITY"


def register_city(slug: str):
    """
    Decorator to register a city configuration.
    
    Usage:
        @register_city("manaus")
        def get_manaus_config() -> CityConfig:
            return CityConfig(...)
    """
    def decorator(func):
        _CITY_REGISTRY[slug.lower()] = func
        return func
    return decorator


def _load_builtin_cities():
    """Load built-in city configurations."""
    # Import Belem config
    try:
        from .belem import get_belem_config
        _CITY_REGISTRY["belem"] = get_belem_config
    except ImportError as e:
        logger.warning(f"Could not load Belem config: {e}")


def load_city(slug: str) -> Optional[CityConfig]:
    """
    Load a city configuration by slug.
    
    Args:
        slug: City slug (e.g., "belem", "manaus")
        
    Returns:
        CityConfig for the specified city, or None if not found
    """
    # Ensure builtin cities are loaded
    if not _CITY_REGISTRY:
        _load_builtin_cities()
    
    slug_lower = slug.lower()
    
    if slug_lower not in _CITY_REGISTRY:
        logger.error(f"City '{slug}' not found. Available: {list(_CITY_REGISTRY.keys())}")
        return None
    
    try:
        config = _CITY_REGISTRY[slug_lower]()
        logger.info(f"Loaded city configuration for {config.name}")
        return config
    except Exception as e:
        logger.error(f"Error loading city '{slug}': {e}")
        return None


def get_city_config() -> CityConfig:
    """
    Get the current city configuration.
    
    Reads from environment variable BELEMCONVERSE_CITY, 
    falls back to DEFAULT_CITY if not set.
    
    Returns:
        CityConfig for the current city
        
    Raises:
        ValueError: If the city cannot be loaded
    """
    city_slug = os.getenv(CITY_ENV_VAR, DEFAULT_CITY)
    
    config = load_city(city_slug)
    
    if config is None:
        # Try default city
        logger.warning(f"Could not load city '{city_slug}', trying default '{DEFAULT_CITY}'")
        config = load_city(DEFAULT_CITY)
    
    if config is None:
        raise ValueError(f"Could not load any city configuration. "
                        f"Tried: {city_slug}, {DEFAULT_CITY}")
    
    return config


def list_available_cities() -> List[str]:
    """
    List all available city slugs.
    
    Returns:
        List of city slugs that can be loaded
    """
    if not _CITY_REGISTRY:
        _load_builtin_cities()
    
    return list(_CITY_REGISTRY.keys())


def is_city_available(slug: str) -> bool:
    """Check if a city is available."""
    if not _CITY_REGISTRY:
        _load_builtin_cities()
    
    return slug.lower() in _CITY_REGISTRY


# Example of how to add a new city:
# 
# @register_city("manaus")
# def get_manaus_config() -> CityConfig:
#     return CityConfig(
#         name="Manaus",
#         slug="manaus",
#         country="Brazil",
#         country_code="BR",
#         state="Amazonas",
#         primary_language="pt",
#         center_coordinates=(-3.1190, -60.0217),
#         bounds_min=(-3.2, -60.2),
#         bounds_max=(-3.0, -59.8),
#         timezone="America/Manaus",
#         csv_path="data/csvs/manaus_data.csv",
#         chroma_db_path="data/chroma_db_manaus",
#         # ... other settings
#     )


