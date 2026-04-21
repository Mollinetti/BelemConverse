# BelemConverse

AI-powered, location-aware place discovery for **Belém do Pará**.

The repository is split into two cleanly separated apps:

| Path        | What it is                                                                  |
| ----------- | --------------------------------------------------------------------------- |
| `api/`      | FastAPI HTTP layer (`uvicorn api.main:app`) — the **backend** entry point.  |
| `belem_converse/` | The backend Python package (planner, retrievers, RAG agent, ingest).  |
| `frontend/` | Flutter client that consumes the `/api/*` endpoints.                        |

The deterministic retrieval pipeline is documented in `docs/spec/`.

## Architecture (one-liner)

```
HTTP /api/chat  →  QueryPlanner (TF-IDF intent + slots)
                →  UnifiedRetriever (open-hours → proximity → category → rank)
                →  EnhancedRAGAgent (LLM summarises ≤ 5 grounded results)
                →  ChatResponse
```

Tour-planning intents (`"plan a tour"`, `"roteiro"`, …) are routed to
`EnhancedRAGAgent._handle_tour_planning` which uses the `TourPlanner` to
build an itinerary from the canonical place index.

## Repository layout

```
.
├── api/                      # FastAPI app (main.py, routes.py, schemas.py, dependencies.py)
├── belem_converse/           # Backend package (installable via `pip install -e .`)
│   ├── cities/               # City profiles (Belém by default)
│   ├── classifiers/          # TF-IDF intent classifier (+ trained .pkl artefacts)
│   ├── core/                 # Query planner, retrievers, ranking, tour planner, RAG agent
│   ├── ingest/               # CSV ingestion → canonical_places.jsonl, vector store, OSM helpers
│   ├── tools/                # Operational CLIs (e.g. data refresh)
│   └── utils/                # Config, models, exceptions, helpers
├── data/                     # Runtime data (canonical_places.jsonl, chroma_db, raw CSVs)
├── docs/                     # Specs (`spec/`), traceability matrix, frontend notes
├── docker/                   # Docker compose helpers
├── frontend/                 # Flutter client
├── models/                   # GGUF LLM weights + sentence-transformer cache (gitignored)
├── notebooks/                # Exploratory notebooks (read-only history)
├── scripts/                  # Standalone scripts (currently empty after cleanup)
├── tests/                    # pytest suite (+ `tests/diagnostics/` for eval harnesses)
├── pyproject.toml            # Single source of truth for dependencies + package config
├── requirements.txt          # Mirror of pyproject for `pip install -r` workflows
├── Dockerfile                # Container image: `uvicorn api.main:app`
├── docker-compose.yml        # Local dev compose
└── .env.example              # Documented env overrides (model paths, data dirs, …)
```

> The previous monolithic `LLM/` folder and the legacy `src/` (LangChain agent,
> scrapers, `DataTools`) have been removed. All backend code now lives in
> `api/` + `belem_converse/`.

## Quickstart

```bash
# 1. Create a venv and install the backend in editable mode.
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"            # or: pip install -r requirements.txt

# 2. Drop the GGUF model into models/llm/ (default name in utils/config.py):
#       Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf
#    or override with MODEL_GGUF_PATH (see .env.example).

# 3. Build the canonical places index from a CSV (one-shot):
curl -F "file=@data/Raw/oriximina-places-raw.csv" \
     http://localhost:8000/api/ingest/csv
#    or manually drop a pre-built canonical_places.jsonl into data/.

# 4. Run the backend:
uvicorn api.main:app --reload --port 8000

# 5. Smoke test:
curl -s http://localhost:8000/api/health | jq
```

OpenAPI docs: <http://localhost:8000/docs> · ReDoc: <http://localhost:8000/redoc>.

## API surface

All endpoints are mounted under `/api`:

| Method + path           | Purpose                                                  |
| ----------------------- | -------------------------------------------------------- |
| `GET  /api/health`      | Liveness + component readiness (LLM / vector store).     |
| `GET  /api/languages`   | Supported response languages (`pt`, `en`).               |
| `GET  /api/places/{id}` | Lookup a canonical place by `placeId`.                   |
| `POST /api/chat`        | Plan → retrieve → summarise (≤ 5 grounded results).      |
| `POST /api/ingest/csv`  | Ingest a places CSV → `data/canonical_places.jsonl`.     |
| `POST /api/clear-history` | Clear the in-memory conversation history.              |

Request/response shapes live in `api/schemas.py` and mirror
`docs/spec/05-openapi.yaml`.

## Running tests

```bash
pip install -e ".[dev]"
pytest                       # full suite (units + integration)
pytest tests/test_query_planner_refactoring.py -v   # single file
```

`tests/conftest.py` ensures the project root is importable even before
`pip install -e .`.

## Docker

```bash
docker build -t belem-converse-api .
docker run --rm -p 8000:8000 \
    -v "$PWD/models:/app/models" \
    -v "$PWD/data:/app/data" \
    belem-converse-api
```

See `Dockerfile` and `docker-compose.yml` for the full setup; the GGUF model is
intentionally **not** baked into the image (mount it from the host).

## Configuration

Environment overrides are documented in `.env.example`:

- `MODEL_GGUF_PATH` — absolute path to the GGUF summariser.
- `LLM_N_GPU_LAYERS` — layers offloaded to GPU (`0` = CPU, `35` = M-series default).
- `BELEM_DATA_DIR`, `CHROMA_PERSIST_DIR`, `BELEM_MODELS_DIR` — relocate runtime
  artefacts (useful for Docker / shared volumes).
- `BELEM_MODEL`, `BELEM_CITY` — switch model variant / city profile.

Defaults live in `belem_converse/utils/config.py`.

## Specifications

Authoritative behaviour specs live under `docs/spec/`:

- `00-poc-charter.md` — scope, success criteria.
- `01-domain-model.md` / `02-csv-mapping.md` — canonical Place entity.
- `03-query-planner.md` / `04-ranking-spec.md` — retrieval + ranking rules.
- `05-openapi.yaml` — frozen API contract (consumed by Flutter).
- `06-llm-contract.md` — summariser-only, no-hallucination rules.
- `07-ux-flutter.md` / `08-i18n.md` — frontend expectations.
- `09-eval-golden-queries.md` / `10-runbook.md` / `11-demo-script.md` — evaluation + ops.
- `12-intent-classifier-improvement-plan.md` — TF-IDF roadmap.

`docs/spec/decisions/` contains ADRs for major architecture choices.

## License

MIT. See `pyproject.toml` for authors and metadata.
