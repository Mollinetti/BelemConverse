# BelemConverse Tech Stack

Source of truth for the stack each surface uses. Keep this in sync with
`pyproject.toml`, `requirements.txt`, and `frontend/pubspec.yaml`. The
`feature-spec` skill reads this file before drafting `plan.md`.

## Surfaces

| Surface | Path | Purpose |
|---------|------|---------|
| HTTP API | `api/` | FastAPI app exposing `/api/*` endpoints. Entry: `uvicorn api.main:app`. |
| Backend library | `belem_converse/` | Planner, retrievers, ranker, RAG agent, ingestion, CLIs. Installable via `pip install -e .`. |
| Data pipeline | `data/`, `belem_converse/ingest/`, `belem_converse/tools/` | CSV → `canonical_places.jsonl` → Chroma vector store. Operational CLIs under `belem_converse/tools/`. |
| Frontend | `frontend/` | Flutter client consuming `/api/*`. |
| Specs & docs | `docs/spec/`, `specs/` | Behaviour specs, ADRs, and SDD spec directories. |
| Container | `Dockerfile`, `docker-compose.yml`, `docker/` | Local dev / single-instance deploy. |

## Python (api + belem_converse + data pipeline)

- **Python**: `>=3.10` (tested against 3.10–3.13).
- **Web framework**: FastAPI (`>=0.109`), Pydantic v2, `uvicorn[standard]`,
  `python-multipart`, `python-dotenv`.
- **Data + retrieval**: pandas, numpy, scipy, scikit-learn (TF-IDF intent
  classifier), rapidfuzz, h3, requests, tqdm.
- **LLM stack**: `llama-cpp-python` (GGUF summariser),
  `sentence-transformers` (embeddings), `chromadb` (vector store), and the
  `langchain` family (`langchain`, `langchain-core`, `langchain-community`,
  `langchain-huggingface`).
- **Optional**: `torch` under the `gpu` extra for MPS/CUDA detection.
- **Testing**: `pytest`, `pytest-asyncio`, `httpx` (FastAPI TestClient).
  Tests live under `tests/`; diagnostics under `tests/diagnostics/`.
  `pytest` is the **only required automated gate** per the constitution.
- **Lint / format / types** (recommended gates): `ruff` (`select = E, F, I, B, UP`,
  `line-length = 100`, `target-version = py310`), `black` (`line-length = 100`),
  `mypy>=1.8`.
- **Packaging**: `pyproject.toml` is canonical; `requirements.txt` mirrors
  the runtime list for `pip install -r` workflows.

## Flutter (frontend)

- **SDK**: Dart `^3.10.4`, Flutter 3.x with Material 3.
- **State management**: `provider` today; the `.cursorrules` recommends
  BLoC, and the `.cursor/rules/flutter/*` rules govern feature/presentation
  layout. New state-management approaches require an ADR.
- **HTTP**: `http` package against the `/api/*` contract.
- **Maps & location**: `flutter_map`, `latlong2`, `geolocator`,
  `permission_handler`.
- **Storage**: `shared_preferences`.
- **i18n**: `intl`, `flutter_localizations` (PT and EN per
  `docs/spec/08-i18n.md`).
- **Misc**: `google_fonts`, `cupertino_icons`, `url_launcher`.
- **Testing**: `flutter test` and `flutter analyze` (recommended gates when
  `frontend/` is touched).

## Data pipeline

- **Inputs**: CSVs under `data/Raw/` (raw places exports) and OSM helpers in
  `belem_converse/ingest/`.
- **Canonical artefact**: `data/canonical_places.jsonl` — single source of
  truth for the place index; schema per `docs/spec/01-domain-model.md` and
  `docs/spec/02-csv-mapping.md`.
- **Vector store**: `data/chroma_db/` (Chroma persisted directory; path
  overridable via `CHROMA_PERSIST_DIR`).
- **Refresh entry points**: `POST /api/ingest/csv` for one-shot ingestion;
  CLI under `belem_converse/tools/refresh_data.py` for scripted runs.
- **Smoke validation**: a small sample CSV + a TestClient call to
  `/api/ingest/csv` is the recommended gate for pipeline-touching specs.

## Behaviour specs

- `docs/spec/00-poc-charter.md` — scope and success criteria.
- `docs/spec/01-domain-model.md`, `02-csv-mapping.md` — canonical Place entity.
- `docs/spec/03-query-planner.md`, `04-ranking-spec.md` — retrieval/ranking.
- `docs/spec/05-openapi.yaml` — frozen API contract (consumed by Flutter).
- `docs/spec/06-llm-contract.md` — summariser-only, no hallucination.
- `docs/spec/07-ux-flutter.md`, `08-i18n.md` — frontend expectations.
- `docs/spec/09-eval-golden-queries.md`, `10-runbook.md`, `11-demo-script.md`
  — evaluation + ops.
- `docs/spec/12-intent-classifier-improvement-plan.md` — intent roadmap.
- `docs/spec/decisions/` — ADRs.

## Configuration

Env overrides documented in `.env.example`:
`MODEL_GGUF_PATH`, `LLM_N_GPU_LAYERS`, `BELEM_DATA_DIR`,
`CHROMA_PERSIST_DIR`, `BELEM_MODELS_DIR`, `BELEM_MODEL`, `BELEM_CITY`.
Defaults live in `belem_converse/utils/config.py`.

## Containerisation

`Dockerfile` builds the FastAPI service; `docker-compose.yml` wires local
dev. The GGUF model is **not** baked in — mount it from the host via
`-v $PWD/models:/app/models`.
