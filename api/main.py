"""BelemConverse FastAPI Application.

Run locally:
    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .dependencies import initialize_rag_system
from .routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan: warm up RAG components at startup."""
    logger.info("Starting BelemConverse API...")
    try:
        initialize_rag_system()
    except Exception as exc:  # pragma: no cover - startup logging path
        logger.error("Failed to initialize RAG system: %s", exc)
        # Continue running so /api/health can report the degraded state.
    yield
    logger.info("Shutting down BelemConverse API...")


app = FastAPI(
    title="BelemConverse API",
    description=(
        "REST API for BelemConverse - Your AI-powered guide to Belem do Para.\n\n"
        "**Endpoints**\n"
        "- `POST /api/chat` - chat with location-aware grounding\n"
        "- `POST /api/ingest/csv` - ingest a places CSV into the canonical index\n"
        "- `GET /api/health` - liveness + component readiness\n"
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS for the Flutter web client. Production deploys should narrow this list.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api", tags=["chat"])


@app.get("/")
async def root() -> dict:
    return {
        "name": "BelemConverse API",
        "version": __version__,
        "description": "AI-powered guide to Belem do Para",
        "docs": "/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
