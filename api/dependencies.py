"""FastAPI startup state: the place catalog.

The API is ready once the catalog is loaded. Nothing else is loaded at
startup — the language model is a hosted service called per request, and
there is no vector store.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import List, Optional

from belem_converse.catalog import load_places
from belem_converse.cities import get_city_config
from belem_converse.utils.config import DATA_DIR

logger = logging.getLogger(__name__)

BUILD_HINT = "Build it with: python -m belem_converse.tools.build_catalog"

_catalog: Optional[List[dict]] = None


def _load_catalog() -> List[dict]:
    """Read the current city's place catalog from disk."""
    return load_places(DATA_DIR / get_city_config().catalog_path)


def initialize_rag_system() -> None:
    """Load the catalog once at startup; later calls are no-ops.

    A missing or unreadable catalog leaves the API not ready rather than
    crashing it, so /api/health can report the state.
    """
    global _catalog
    if _catalog is not None:
        return
    try:
        _catalog = _load_catalog()
    except (OSError, sqlite3.Error) as exc:
        logger.error("Place catalog could not be loaded: %s", exc)
        return
    logger.info("Place catalog loaded: %d places", len(_catalog))


def get_catalog() -> Optional[List[dict]]:
    return _catalog


def is_system_ready() -> bool:
    return _catalog is not None


def get_system_status() -> dict:
    return {
        "initialized": _catalog is not None,
        "catalog_places": len(_catalog) if _catalog is not None else 0,
        "llm_loaded": False,
        "vector_store_loaded": False,
    }
