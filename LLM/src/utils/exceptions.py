"""
Custom exceptions for the RAG-based travel guide agent.
"""

class RAGAgentError(Exception):
    """Base exception for RAG agent errors."""
    pass


class ModelLoadError(RAGAgentError):
    """Raised when there's an error loading the LLM or embedding model."""
    pass


class VectorStoreError(RAGAgentError):
    """Raised when there's an error with the vector store operations."""
    pass


class DataLoadError(RAGAgentError):
    """Raised when there's an error loading the data."""
    pass


class InferenceError(RAGAgentError):
    """Raised when there's an error during inference."""
    pass


class ConfigurationError(RAGAgentError):
    """Raised when there's an error with configuration."""
    pass 