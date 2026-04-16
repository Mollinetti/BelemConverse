"""
FastAPI dependencies for RAG agent initialization.

Provides a singleton RAG agent that's initialized once and reused
across all requests for efficiency.
"""

import sys
import logging
from pathlib import Path
from typing import Optional

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

logger = logging.getLogger(__name__)

# Global singleton for the RAG agent
_rag_agent = None
_llm_model = None
_vector_store_manager = None
_is_initialized = False


def initialize_rag_system():
    """
    Initialize the RAG system (LLM, vector store, agent).
    
    This is called once at startup and the components are reused.
    """
    global _rag_agent, _llm_model, _vector_store_manager, _is_initialized
    
    if _is_initialized:
        return
    
    try:
        logger.info("Initializing RAG system...")
        
        # Import components
        from utils.models import ModelManager
        from data.vector_store import VectorStoreManager
        from data.data_loader import DataLoader
        from core.enhanced_rag_agent import EnhancedRAGAgent
        
        # Initialize vector store
        logger.info("Loading vector store...")
        _vector_store_manager = VectorStoreManager()
        _vector_store_manager.initialize()
        
        # Initialize LLM
        logger.info("Loading LLM model...")
        _llm_model = ModelManager.get_llm()
        
        # Initialize RAG agent
        logger.info("Creating RAG agent...")
        _rag_agent = EnhancedRAGAgent(
            vector_store_manager=_vector_store_manager,
            llm_model=_llm_model
        )
        
        _is_initialized = True
        logger.info("RAG system initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize RAG system: {e}")
        raise


def get_rag_agent():
    """
    Get the singleton RAG agent instance.
    
    Raises:
        RuntimeError: If the RAG system is not initialized
    """
    global _rag_agent
    
    if not _is_initialized or _rag_agent is None:
        raise RuntimeError("RAG system not initialized. Call initialize_rag_system() first.")
    
    return _rag_agent


def get_llm_model():
    """Get the LLM model instance."""
    global _llm_model
    return _llm_model


def get_vector_store_manager():
    """Get the vector store manager instance."""
    global _vector_store_manager
    return _vector_store_manager


def is_system_ready() -> bool:
    """Check if the RAG system is ready."""
    return _is_initialized and _rag_agent is not None


def get_system_status() -> dict:
    """Get detailed system status."""
    return {
        "initialized": _is_initialized,
        "llm_loaded": _llm_model is not None,
        "vector_store_loaded": _vector_store_manager is not None,
        "agent_ready": _rag_agent is not None
    }


