# BelemConverse backend (FastAPI + GGUF summarizer + Chroma vector store)
#
# Build:
#   docker build -t belem-converse-api .
# Run (with model + data mounted from host):
#   docker run --rm -p 8000:8000 \
#     -v $(pwd)/models:/app/models \
#     -v $(pwd)/data:/app/data \
#     belem-converse-api
#
# Notes:
# - The GGUF model file (>1 GB) is intentionally NOT baked into the image.
#   Mount it from the host or a persistent volume.
# - llama-cpp-python is built from source for portability; this can take a few
#   minutes the first time. Enable BLAS by setting CMAKE_ARGS at build-time.

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps for llama-cpp-python, scipy/sklearn wheels, sentence-transformers.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        curl \
        ca-certificates \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (better layer caching).
COPY pyproject.toml README.md ./
COPY belem_converse/ ./belem_converse/
COPY api/ ./api/
RUN pip install --upgrade pip setuptools wheel \
    && pip install -e .

# Default model + data live on mounted volumes; create the mount points.
RUN mkdir -p /app/models/llm /app/data /app/data/chroma_db

# Configurable runtime overrides (see belem_converse/utils/config.py).
ENV BELEM_DATA_DIR=/app/data \
    CHROMA_PERSIST_DIR=/app/data/chroma_db \
    BELEM_MODELS_DIR=/app/models \
    LLM_N_GPU_LAYERS=0

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
