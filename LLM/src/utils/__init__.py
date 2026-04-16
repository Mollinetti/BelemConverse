"""
Utilities module for BelemConverse.

Contains configuration, model management, data tools, and helper utilities.
"""

from .config import (
    get_config,
    LLM_CONFIG,
    EMBEDDING_CONFIG,
    VECTOR_STORE_CONFIG,
    DATA_CONFIG,
    SELECTED_MODEL,
    SELECTED_CITY,
    CURRENT_CITY_NAME,
    CITY_CENTER,
    CITY_BOUNDS,
    is_in_city_bounds,
    get_category_terms
)
from .models import ModelManager
from .bayesian_ranking import BayesianRankingSystem, bayesian_ranker
from .business_hours_parser import BusinessHoursParser, BusinessHours, business_hours_parser
from .exceptions import (
    RAGAgentError,
    ModelLoadError,
    VectorStoreError,
    DataLoadError
)

__all__ = [
    # Config
    'get_config',
    'LLM_CONFIG',
    'EMBEDDING_CONFIG',
    'VECTOR_STORE_CONFIG',
    'DATA_CONFIG',
    'SELECTED_MODEL',
    'SELECTED_CITY',
    'CURRENT_CITY_NAME',
    'CITY_CENTER',
    'CITY_BOUNDS',
    'is_in_city_bounds',
    'get_category_terms',
    
    # Models
    'ModelManager',
    
    # Ranking
    'BayesianRankingSystem',
    'bayesian_ranker',
    
    # Business hours
    'BusinessHoursParser',
    'BusinessHours',
    'business_hours_parser',
    
    # Exceptions
    'RAGAgentError',
    'ModelLoadError',
    'VectorStoreError',
    'DataLoadError'
]
