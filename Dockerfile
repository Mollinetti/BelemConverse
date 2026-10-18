# BelemConverse API: FastAPI over the committed place catalog. The language
# model is a hosted service (LLM_* settings), so nothing heavy is installed.
#
#   docker build -t belemconverse .
#   docker run --rm -p 8000:8000 --env-file .env belemconverse
#
# Render sets $PORT; locally it defaults to 8000.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
# Dependencies first: this layer is reused until requirements.txt changes.
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY pyproject.toml README.md ./
COPY api ./api
COPY belem_converse ./belem_converse
COPY catalog ./catalog
RUN pip install --no-deps . && useradd --create-home app
USER app

EXPOSE 8000
CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
