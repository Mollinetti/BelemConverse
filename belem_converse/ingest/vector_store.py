"""
Vector store module for document loading and retrieval operations.
Enhanced with smart rebuilding logic and preprocessed CSV support.
"""
import sys
import logging
import hashlib
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

# Fix for pysqlite3 compatibility (optional on Python 3.13+)
try:
    __import__('pysqlite3')
    import pysqlite3
    sys.modules['sqlite3'] = sys.modules["pysqlite3"]
except ImportError:
    pass  # Use built-in sqlite3 on Python 3.13+

import chromadb
import pandas as pd
from langchain_community.document_loaders import CSVLoader
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from belem_converse.utils.exceptions import VectorStoreError, DataLoadError
from belem_converse.utils.config import VECTOR_STORE_CONFIG, DATA_CONFIG
from belem_converse.utils.models import ModelManager

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """Manages vector store operations including document loading and retrieval with smart rebuilding."""
    
    def __init__(self):
        self.vector_store: Optional[Chroma] = None
        self.embedding_model = None
        self.metadata_file = Path(VECTOR_STORE_CONFIG["persist_directory"]) / "vector_store_metadata.json"
        
    def _calculate_csv_hash(self, csv_path: str) -> str:
        """
        Calculate MD5 hash of CSV file to detect changes.
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            MD5 hash string
        """
        try:
            csv_file = Path(csv_path)
            if not csv_file.exists():
                return ""
            
            # Read file in chunks to handle large files efficiently
            hash_md5 = hashlib.md5()
            with open(csv_file, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating CSV hash: {str(e)}")
            return ""
    
    def _load_metadata(self) -> Dict[str, Any]:
        """
        Load vector store metadata.
        
        Returns:
            Metadata dictionary
        """
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading metadata: {str(e)}")
        
        return {}
    
    def _save_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Save vector store metadata.
        
        Args:
            metadata: Metadata dictionary to save
        """
        try:
            self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metadata: {str(e)}")
    
    def _needs_rebuild(self, csv_path: str) -> bool:
        """
        Check if vector store needs to be rebuilt based on CSV changes.
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            True if rebuild is needed, False otherwise
        """
        try:
            persist_dir = Path(VECTOR_STORE_CONFIG["persist_directory"])
            
            # If no existing vector store, needs rebuild
            if not persist_dir.exists():
                logger.info("No existing vector store found, rebuild needed")
                return True
            
            # Check if chroma.sqlite3 exists (indicates valid ChromaDB)
            chroma_db_file = persist_dir / "chroma.sqlite3"
            if not chroma_db_file.exists():
                logger.info("No valid ChromaDB found, rebuild needed")
                return True
            
            # Load metadata and check CSV hash
            metadata = self._load_metadata()
            current_hash = self._calculate_csv_hash(csv_path)
            
            if not current_hash:
                logger.warning("Could not calculate CSV hash, forcing rebuild")
                return True
            
            stored_hash = metadata.get('csv_hash', '')
            
            if current_hash != stored_hash:
                logger.info(f"CSV file changed (hash: {current_hash[:8]} vs {stored_hash[:8]}), rebuild needed")
                return True
            
            # Check if metadata has required fields
            if not all(key in metadata for key in ['csv_hash', 'created_at', 'document_count']):
                logger.info("Metadata incomplete, rebuild needed")
                return True
            
            logger.info("Vector store is up to date, no rebuild needed")
            return False
            
        except Exception as e:
            logger.error(f"Error checking rebuild status: {str(e)}")
            return True
    
    def load_documents(self, csv_path: Optional[str] = None) -> List[Document]:
        """
        Load documents from preprocessed CSV file.
        
        Args:
            csv_path: Path to CSV file. If None, uses default from config.
            
        Returns:
            List of loaded documents
            
        Raises:
            DataLoadError: If there's an error loading the documents
        """
        try:
            if csv_path is None:
                # Try to use the latest backup file first, then fall back to config
                backup_dir = Path(__file__).parent.parent.parent / "backup_data"
                if backup_dir.exists():
                    backup_files = list(backup_dir.glob("real_data_backup_*.csv"))
                    if backup_files:
                        # Use the most recent backup file
                        latest_backup = max(backup_files, key=lambda x: x.stat().st_mtime)
                        csv_path = str(latest_backup)
                        logger.info(f"Using latest backup file: {latest_backup.name}")
                    else:
                        csv_path = DATA_CONFIG["csv_path"]
                        logger.info("No backup files found, using default CSV path")
                else:
                    csv_path = DATA_CONFIG["csv_path"]
                    logger.info("No backup directory found, using default CSV path")
            
            csv_file = Path(csv_path)
            if not csv_file.exists():
                raise DataLoadError(f"CSV file not found: {csv_file}")
            
            logger.info(f"Loading documents from {csv_file}")
            
            # Load CSV with pandas first to validate and get info
            df = pd.read_csv(csv_file, low_memory=False)
            logger.info(f"CSV loaded: {len(df)} rows, {len(df.columns)} columns")
            
            # Check for required columns
            required_columns = ['title', 'address', 'categoryName']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                logger.warning(f"Missing required columns: {missing_columns}")
            
            # Use CSVLoader for document creation
            loader = CSVLoader(str(csv_file))
            documents = loader.load()
            
            logger.info(f"Loaded {len(documents)} documents")
            
            # Log some sample document info
            if documents:
                sample_doc = documents[0]
                logger.info(f"Sample document keys: {list(sample_doc.metadata.keys())}")
                logger.info(f"Sample document content length: {len(sample_doc.page_content)}")
            
            return documents
            
        except Exception as e:
            logger.error(f"Error loading documents: {str(e)}")
            raise DataLoadError(f"Failed to load documents: {str(e)}") from e
    
    def create_vector_store(self, documents: List[Document], force_recreate: bool = False) -> Chroma:
        """
        Create or load vector store from documents with smart rebuilding logic.
        
        Args:
            documents: List of documents to index
            force_recreate: If True, recreate the vector store even if it exists
            
        Returns:
            Chroma vector store instance
            
        Raises:
            VectorStoreError: If there's an error creating the vector store
        """
        try:
            persist_dir = Path(VECTOR_STORE_CONFIG["persist_directory"])
            
            # Check if rebuild is needed
            csv_path = DATA_CONFIG["csv_path"]
            if not force_recreate and not self._needs_rebuild(csv_path):
                # Load existing vector store
                logger.info(f"Loading existing vector store from {persist_dir}")
                self.embedding_model = ModelManager.get_embedding_model()
                self.vector_store = Chroma(
                    persist_directory=str(persist_dir),
                    embedding_function=self.embedding_model
                )
                logger.info("Vector store loaded successfully")
                return self.vector_store
            
            # Create new vector store
            logger.info("Creating new vector store...")
            
            # Ensure the persistence directory exists
            if not persist_dir.exists():
                logger.info(f"Creating persistence directory: {persist_dir}")
                persist_dir.mkdir(parents=True, exist_ok=True)
            
            self.embedding_model = ModelManager.get_embedding_model()
            
            self.vector_store = Chroma.from_documents(
                documents=documents,
                embedding=self.embedding_model,
                persist_directory=str(persist_dir)
            )
            
            # Save metadata
            metadata = {
                'csv_hash': self._calculate_csv_hash(csv_path),
                'created_at': datetime.now().isoformat(),
                'document_count': len(documents),
                'csv_path': csv_path,
                'embedding_model': str(self.embedding_model)
            }
            self._save_metadata(metadata)
            
            logger.info(f"Vector store created successfully with {len(documents)} documents")
            return self.vector_store
            
        except Exception as e:
            logger.error(f"Error creating vector store: {str(e)}")
            raise VectorStoreError(f"Failed to create vector store: {str(e)}") from e
    
    def get_retriever(self, search_kwargs: Optional[dict] = None) -> BaseRetriever:
        """
        Get retriever from vector store.
        
        Args:
            search_kwargs: Search parameters for retrieval
            
        Returns:
            Chroma retriever instance
            
        Raises:
            VectorStoreError: If vector store is not initialized
        """
        if self.vector_store is None:
            raise VectorStoreError("Vector store not initialized. Call create_vector_store() first.")
        
        if search_kwargs is None:
            search_kwargs = VECTOR_STORE_CONFIG["search_kwargs"]
        
        return self.vector_store.as_retriever(search_kwargs=search_kwargs)
    
    def initialize(self, force_recreate: bool = False) -> Chroma:
        """
        Initialize the complete vector store pipeline with smart rebuilding.
        
        Args:
            force_recreate: If True, recreate the vector store even if it exists
            
        Returns:
            Chroma vector store instance
        """
        try:
            # Check if we can load existing vector store without rebuilding
            if not force_recreate:
                persist_dir = Path(VECTOR_STORE_CONFIG["persist_directory"])
                chroma_db_file = persist_dir / "chroma.sqlite3"
                
                if chroma_db_file.exists() and not self._needs_rebuild(DATA_CONFIG["csv_path"]):
                    logger.info("Loading existing vector store without rebuilding...")
                    self.embedding_model = ModelManager.get_embedding_model()
                    try:
                        self.vector_store = Chroma(
                            persist_directory=str(persist_dir),
                            embedding_function=self.embedding_model
                        )
                        logger.info("Vector store loaded successfully")
                        return self.vector_store
                    except Exception as load_error:
                        # Check if this is a database corruption error
                        error_msg = str(load_error).lower()
                        logger.info(f"Caught exception during Chroma load: {type(load_error).__name__}: {load_error}")
                        if "malformed" in error_msg or "corrupt" in error_msg or "database disk image" in error_msg:
                            logger.warning(f"Database appears corrupted: {load_error}")
                            logger.info("Deleting corrupted database and rebuilding...")
                            import shutil
                            try:
                                shutil.rmtree(persist_dir, ignore_errors=True)
                                logger.info(f"Successfully deleted corrupted database at {persist_dir}")
                            except Exception as del_error:
                                logger.error(f"Failed to delete corrupted database: {del_error}")
                            # Fall through to rebuild
                        else:
                            logger.info(f"Exception not recognized as corruption, re-raising")
                            raise
            
            # Load documents and create/rebuild vector store
            logger.info("Loading documents and creating vector store...")
            documents = self.load_documents()
            vector_store = self.create_vector_store(documents, force_recreate=True)
            
            return vector_store
            
        except Exception as e:
            logger.error(f"Error initializing vector store: {str(e)}")
            raise VectorStoreError(f"Failed to initialize vector store: {str(e)}") from e
    
    def get_vector_store_info(self) -> Dict[str, Any]:
        """
        Get information about the current vector store.
        
        Returns:
            Dictionary with vector store information
        """
        try:
            persist_dir = Path(VECTOR_STORE_CONFIG["persist_directory"])
            metadata = self._load_metadata()
            
            info = {
                'exists': persist_dir.exists(),
                'chroma_db_exists': (persist_dir / "chroma.sqlite3").exists(),
                'metadata': metadata,
                'persist_directory': str(persist_dir)
            }
            
            if self.vector_store is not None:
                info['initialized'] = True
                info['embedding_model'] = str(self.embedding_model)
            else:
                info['initialized'] = False
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting vector store info: {str(e)}")
            return {'error': str(e)}
    
    def rebuild_from_csv(self, csv_path: Optional[str] = None) -> Chroma:
        """
        Force rebuild the vector store from a CSV file.
        
        This method is useful after data refresh operations to ensure
        the vector store reflects the latest data.
        
        Args:
            csv_path: Path to CSV file. If None, uses default from config.
            
        Returns:
            Chroma vector store instance
            
        Raises:
            VectorStoreError: If there's an error rebuilding the vector store
        """
        try:
            import shutil
            
            persist_dir = Path(VECTOR_STORE_CONFIG["persist_directory"])
            
            # Delete existing vector store if it exists
            if persist_dir.exists():
                logger.info(f"Deleting existing vector store at {persist_dir}")
                shutil.rmtree(persist_dir, ignore_errors=True)
            
            # Load documents from specified or default CSV
            if csv_path:
                logger.info(f"Loading documents from specified CSV: {csv_path}")
                csv_file = Path(csv_path)
                if not csv_file.exists():
                    raise DataLoadError(f"CSV file not found: {csv_file}")
                
                # Load CSV
                df = pd.read_csv(csv_file, low_memory=False)
                logger.info(f"Loaded {len(df)} rows from CSV")
                
                # Create documents using CSVLoader
                loader = CSVLoader(str(csv_file))
                documents = loader.load()
            else:
                documents = self.load_documents()
            
            logger.info(f"Rebuilding vector store with {len(documents)} documents...")
            
            # Create new vector store
            persist_dir.mkdir(parents=True, exist_ok=True)
            
            self.embedding_model = ModelManager.get_embedding_model()
            
            self.vector_store = Chroma.from_documents(
                documents=documents,
                embedding=self.embedding_model,
                persist_directory=str(persist_dir)
            )
            
            # Save metadata
            actual_csv_path = csv_path if csv_path else DATA_CONFIG["csv_path"]
            metadata = {
                'csv_hash': self._calculate_csv_hash(actual_csv_path),
                'created_at': datetime.now().isoformat(),
                'document_count': len(documents),
                'csv_path': actual_csv_path,
                'embedding_model': str(self.embedding_model),
                'rebuild_source': 'rebuild_from_csv'
            }
            self._save_metadata(metadata)
            
            logger.info(f"Vector store rebuilt successfully with {len(documents)} documents")
            return self.vector_store
            
        except Exception as e:
            logger.error(f"Error rebuilding vector store: {str(e)}")
            raise VectorStoreError(f"Failed to rebuild vector store: {str(e)}") from e