"""
Cities module for multi-city support in BelemConverse.

This module provides city-specific configurations that can be easily
swapped to support different cities without modifying core code.

Usage:
    from cities import get_city_config, load_city
    
    # Load default city (from environment or fallback to belem)
    city_config = get_city_config()
    
    # Load specific city
    city_config = load_city("belem")
"""

from .base_city import CityConfig
from .city_loader import get_city_config, load_city, list_available_cities

__all__ = [
    'CityConfig',
    'get_city_config',
    'load_city',
    'list_available_cities'
]


