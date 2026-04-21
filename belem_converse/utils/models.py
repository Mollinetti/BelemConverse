"""
Models module for LLM and embedding initialization.
"""
import sys
import logging
from typing import Optional
from pathlib import Path

from langchain_community.chat_models.llamacpp import ChatLlamaCpp
from langchain_core.callbacks import CallbackManager, StreamingStdOutCallbackHandler
from langchain_huggingface import HuggingFaceEmbeddings

from .exceptions import ModelLoadError
from .config import LLM_CONFIG, EMBEDDING_CONFIG

logger = logging.getLogger(__name__)


class ModelManager:
    """Manages LLM and embedding models with singleton pattern for efficiency."""
    
    _llm_instance: Optional[ChatLlamaCpp] = None
    _embedding_instance: Optional[HuggingFaceEmbeddings] = None
    
    @classmethod
    def get_llm(cls, force_reload: bool = False) -> ChatLlamaCpp:
        """
        Get or create the LLM instance.
        
        Args:
            force_reload: If True, reload the model even if already loaded
            
        Returns:
            ChatLlamaCpp instance
            
        Raises:
            ModelLoadError: If there's an error loading the model
        """
        if cls._llm_instance is not None and not force_reload:
            logger.info("Using existing LLM instance")
            return cls._llm_instance
            
        try:
            logger.info("Initializing LLM...")
            
            # Check if model file exists
            model_path = Path(LLM_CONFIG["model_path"])
            if not model_path.exists():
                raise ModelLoadError(f"Model file not found: {model_path}")
            
            # Set up callbacks for streaming
            callback_manager = CallbackManager([StreamingStdOutCallbackHandler()])
            
            # Initialize LLM
            llm = ChatLlamaCpp(
                model_path=str(model_path),
                temperature=LLM_CONFIG["temperature"],
                max_tokens=LLM_CONFIG["max_tokens"],
                n_ctx=LLM_CONFIG["n_ctx"],
                n_gpu_layers=LLM_CONFIG["n_gpu_layers"],
                top_p=LLM_CONFIG["top_p"],
                callback_manager=callback_manager,
                verbose=LLM_CONFIG["verbose"]
            )
            
            cls._llm_instance = llm
            logger.info("LLM initialized successfully")
            return llm
            
        except Exception as e:
            logger.error(f"Error initializing LLM: {str(e)}")
            raise ModelLoadError(f"Failed to initialize LLM: {str(e)}") from e
    
    @classmethod
    def get_embedding_model(cls, force_reload: bool = False) -> HuggingFaceEmbeddings:
        """
        Get or create the embedding model instance.
        
        Args:
            force_reload: If True, reload the model even if already loaded
            
        Returns:
            HuggingFaceEmbeddings instance
            
        Raises:
            ModelLoadError: If there's an error loading the model
        """
        if cls._embedding_instance is not None and not force_reload:
            logger.info("Using existing embedding model instance")
            return cls._embedding_instance
            
        try:
            logger.info("Initializing embedding model...")
            
            model_name = EMBEDDING_CONFIG["model_name"]
            model_path = Path(model_name)
            
            # Check if it's a local path that exists, otherwise use hub model name
            if model_path.exists():
                logger.info(f"Loading embedding model from local path: {model_path}")
                effective_model_name = str(model_path)
            else:
                # Use HuggingFace Hub name (will download automatically)
                hub_name = EMBEDDING_CONFIG.get("hub_fallback_name", "sentence-transformers/all-mpnet-base-v2")
                logger.info(f"Local model not found, downloading from HuggingFace Hub: {hub_name}")
                effective_model_name = hub_name
            
            # Initialize embedding model
            embedding_model = HuggingFaceEmbeddings(
                model_name=effective_model_name,
                model_kwargs=EMBEDDING_CONFIG["model_kwargs"]
            )
            
            cls._embedding_instance = embedding_model
            logger.info("Embedding model initialized successfully")
            return embedding_model
            
        except Exception as e:
            logger.error(f"Error initializing embedding model: {str(e)}")
            raise ModelLoadError(f"Failed to initialize embedding model: {str(e)}") from e
    
    @classmethod
    def cleanup(cls):
        """Clean up model instances."""
        cls._llm_instance = None
        cls._embedding_instance = None
        logger.info("Model instances cleaned up") 