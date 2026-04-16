# Runbook (Local PoC)

## Goal
Start backend + (optional) llama runtime + Flutter web client with one command.

## Required Environment Variables
- MODEL_GGUF_PATH=/path/to/Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf
- CHROMA_PERSIST_DIR=./data/chroma
- PLACES_JSONL=./data/canonical_places.jsonl
- ENABLE_VECTOR_FALLBACK=false (default)

## Startup
- docker compose up --build
OR
- make dev

## Ingestion
- POST /ingest/csv (multipart file upload)
- produces:
  - ./data/canonical_places.jsonl
  - ./data/chroma (if used)
  - ./data/ingestion_report.json

## Testing
- run golden queries test runner (must be included)
- outputs pass/fail with debug plans

## Notes
- If llama runtime uses a local server, specify its URL/port and how backend calls it.
- If llama is embedded in backend process, specify memory constraints and model load time.
``