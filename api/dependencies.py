"""FastAPI dependencies for RAG agent initialization.

Provides a singleton RAG agent that is initialized once at startup and reused
across all requests.
"""

from __future__ import annotations

import logging
from typing import Optional

from belem_converse.core.enhanced_rag_agent import EnhancedRAGAgent
from belem_converse.ingest.data_loader import DataLoader
from belem_converse.ingest.vector_store import VectorStoreManager
from belem_converse.utils.models import ModelManager

logger = logging.getLogger(__name__)

_rag_agent: Optional[EnhancedRAGAgent] = None
_llm_model = None
_vector_store_manager: Optional[VectorStoreManager] = None
_is_initialized: bool = False


def initialize_rag_system() -> None:
    """Initialize the RAG system (LLM, vector store, agent).

    Called once at application startup; subsequent calls are no-ops.
    """
    global _rag_agent, _llm_model, _vector_store_manager, _is_initialized

    if _is_initialized:
        return

    logger.info("Initializing RAG system...")

    logger.info("Loading vector store...")
    _vector_store_manager = VectorStoreManager()
    _vector_store_manager.initialize()

    logger.info("Loading LLM model...")
    _llm_model = ModelManager.get_llm()

    logger.info("Creating RAG agent...")
    _rag_agent = EnhancedRAGAgent(
        vector_store_manager=_vector_store_manager,
        llm_model=_llm_model,
    )

    _is_initialized = True
    logger.info("RAG system initialized successfully")


def get_rag_agent() -> EnhancedRAGAgent:
    """Return the singleton RAG agent (raises if not initialised)."""
    if not _is_initialized or _rag_agent is None:
        raise RuntimeError(
            "RAG system not initialized. Call initialize_rag_system() first."
        )
    return _rag_agent


def get_llm_model():
    return _llm_model


def get_vector_store_manager() -> Optional[VectorStoreManager]:
    return _vector_store_manager


def is_system_ready() -> bool:
    return _is_initialized and _rag_agent is not None


def get_system_status() -> dict:
    return {
        "initialized": _is_initialized,
        "llm_loaded": _llm_model is not None,
        "vector_store_loaded": _vector_store_manager is not None,
        "agent_ready": _rag_agent is not None,
    }
