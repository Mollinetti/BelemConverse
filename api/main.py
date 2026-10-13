"""BelemConverse FastAPI Application.

Run locally:
    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import find_dotenv, load_dotenv

# Before anything reads the environment (data dirs, LLM_* settings). Searches
# upward from the working directory; never overrides variables already set.
load_dotenv(find_dotenv(usecwd=True))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from . import __version__  # noqa: E402
from .dependencies import initialize_rag_system  # noqa: E402
from .routes import router  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan: load the place catalog at startup."""
    logger.info("Starting BelemConverse API...")
    try:
        initialize_rag_system()
    except Exception as exc:  # pragma: no cover - startup logging path
        logger.error("Failed to load the place catalog: %s", exc)
        # Continue running so /api/health can report the degraded state.
    yield
    logger.info("Shutting down BelemConverse API...")


app = FastAPI(
    title="BelemConverse API",
    description=(
        "REST API for BelemConverse - Your AI-powered guide to Belem do Para.\n\n"
        "**Endpoints**\n"
        "- `POST /api/chat` - chat with location-aware grounding\n"
        "- `GET /api/health` - liveness + component readiness\n"
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)



def cors_options() -> dict:
    """Browser origins allowed to call the API: ALLOWED_ORIGINS (comma-separated),
    or only http://localhost / 127.0.0.1 on any port when it is unset (local dev)."""
    options = {
        "allow_credentials": False,
        "allow_methods": ["GET", "POST"],
        "allow_headers": ["content-type"],
    }
    origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    if origins:
        return {**options, "allow_origins": origins}
    return {**options, "allow_origin_regex": r"http://(localhost|127\.0\.0\.1)(:\d+)?"}


app.add_middleware(CORSMiddleware, **cors_options())

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
