from langchain.chains import RetrievalQA
from .llm_setup import get_llm
from .vector_store import get_vectorstore, initialize_vectorstore
from .prompts import get_system_prompt
from .exceptions import QAError, VectorStoreError
import logging

logger = logging.getLogger(__name__)

def create_qa_chain(use_existing: bool = True, recreate_vectorstore: bool = False) -> RetrievalQA:
    """Create a configured RetrievalQA chain for question answering.
    
    Args:
        use_existing: Whether to use existing vector store if available
        recreate_vectorstore: Force create new vector store even if exists
    
    Returns:
        Configured RetrievalQA chain instance
    
    Raises:
        QAError: If chain creation fails
    """
    try:
        llm = get_llm()
        prompt = get_system_prompt()
        
        vectorstore = (get_vectorstore() if use_existing and not recreate_vectorstore 
                      else initialize_vectorstore())
        
        return RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=vectorstore.as_retriever(search_kwargs={"k": 2}),
            return_source_documents=False,
            chain_type_kwargs={"prompt": prompt}
        )
        
    except Exception as e:
        logger.error(f"QA chain creation failed: {str(e)}")
        raise QAError(f"Failed to create QA pipeline: {str(e)}") from e
