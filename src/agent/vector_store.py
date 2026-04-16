from langchain.document_loaders import CSVLoader
from langchain.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from .config import load_config
from .exceptions import DataError
from pathlib import Path
import sys
import logging

logger = logging.getLogger(__name__)
_path_config, _ = load_config()

def _setup_sqlite():
    """Configure SQLite backend for ChromaDB compatibility"""
    try:
        __import__('pysqlite3')
        sys.modules['sqlite3'] = sys.modules["pysqlite3"]
    except ImportError:
        logger.warning("pysqlite3 not found, using system sqlite3")

def get_embeddings():
    """Initialize sentence transformer embeddings with error handling"""
    try:
        return HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-mpnet-base-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
    except Exception as e:
        raise DataError(f"Embedding model initialization failed: {str(e)}") from e

def initialize_vectorstore() -> Chroma:
    """Initialize Chroma vector store with validation"""
    _setup_sqlite()
    
    try:
        # Validate data file exists
        if not _path_config.attractions_data.exists():
            raise FileNotFoundError(f"Data file {_path_config.attractions_data} not found")
        
        # Load documents
        loader = CSVLoader(
            file_path=str(_path_config.attractions_data),
            source_column="titleFormatted"
        )
        documents = loader.load()
        
        # Initialize Chroma
        return Chroma.from_documents(
            documents=documents,
            embedding=get_embeddings(),
            persist_directory=str(_path_config.chroma_db),
            collection_metadata={"hnsw:space": "cosine"}
        )
        
    except FileNotFoundError as e:
        raise DataError(f"Missing data file: {str(e)}") from e
    except Exception as e:
        raise DataError(f"Vector store initialization failed: {str(e)}") from e

def get_vectorstore() -> Chroma:
    """Get existing Chroma instance with persistence"""
    _setup_sqlite()
    try:
        return Chroma(
            persist_directory=str(_path_config.chroma_db),
            embedding_function=get_embeddings()
        )
    except Exception as e:
        raise DataError(f"Failed to load existing vector store: {str(e)}") from e
