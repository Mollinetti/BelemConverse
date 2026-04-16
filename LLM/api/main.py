"""
BelemConverse FastAPI Application

Main entry point for the REST API server.

Usage:
    uvicorn api.main:app --reload --port 8000
    
Or:
    python -m api.main
"""

import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add src to path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from .routes import router
from .dependencies import initialize_rag_system
from . import __version__

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Initializes the RAG system on startup and cleans up on shutdown.
    """
    # Startup
    logger.info("Starting BelemConverse API...")
    try:
        initialize_rag_system()
        logger.info("RAG system initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize RAG system: {e}")
        # Continue anyway - health endpoint will report status
    
    yield
    
    # Shutdown
    logger.info("Shutting down BelemConverse API...")


# Create FastAPI app
app = FastAPI(
    title="BelemConverse API",
    description="""
    REST API for BelemConverse - Your AI-powered guide to Belém do Pará.
    
    ## Features
    
    - **Chat**: Send messages and get AI-powered responses about places in Belém
    - **Location-aware**: Provide coordinates for location-based recommendations
    - **Multilingual**: Supports Portuguese and English
    
    ## Usage
    
    Send a POST request to `/api/chat` with your message and optional location.
    """,
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS for Flutter app
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:*",
        "http://127.0.0.1:*",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:5000",
        # Flutter web default ports
        "http://localhost:49152",
        "http://localhost:49153",
        # Allow all origins in development (restrict in production)
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api", tags=["chat"])


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "BelemConverse API",
        "version": __version__,
        "description": "AI-powered guide to Belém do Pará",
        "docs": "/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


