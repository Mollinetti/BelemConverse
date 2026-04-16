from .config.schema import BelemError

class ModelError(BelemError):
    """Errors related to LLM operations"""

class VectorStoreError(BelemError):
    """Errors related to vector database operations"""

class QAError(BelemError):
    """Errors during question answering process"""

class ValidationError(BelemError):
    """Data validation errors"""
