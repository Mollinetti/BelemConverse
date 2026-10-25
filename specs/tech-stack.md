# BelemConverse Tech Stack

**Updated**: 2026-10-17 (branch `mvp-2`) · **Replaces**: [archive/tech-stack.md](archive/tech-stack.md) (PoC stack: Chroma, LangChain, llama.cpp, all removed in mvp-1)

This file lists everything the project runs, builds with, talks to and stores.
It is also the **inventory for the mvp-3 security audit**
([mvp-3-security-audit/](mvp/mvp-3-security-audit/spec.md)). Keep it in sync with
`pyproject.toml`, `requirements.txt`, `frontend/pubspec.yaml`, `Dockerfile`,
`render.yaml` and `.env.example`.

## Architecture and trust boundaries

```
Browser ── https://mollinetti.github.io/BelemConverse/app/   (Flutter web, static, GitHub Pages)
   │  also fetches Poppins from fonts.googleapis.com / fonts.gstatic.com
   │  HTTPS, JSON, no cookies, no auth
   ▼
Render free web service (Docker, python:3.12-slim, 1 instance)
   uvicorn → FastAPI
     CORS (ALLOWED_ORIGINS) → RateLimiter (per-IP, X-Forwarded-For) → Pydantic + input gate (422)
     → TF-IDF intent classifier (pickle) → query planner → retriever/ranker over catalog/belem.sqlite (read-only)
     → in-memory SessionStore → DailyCap → hosted LLM (summary) → grounding check → template fallback
   │  HTTPS, Bearer API key
   ▼
Google AI Studio (Gemini, OpenAI-compatible)  ──fallback──▶  Groq (OpenAI-compatible)
```

| Boundary | Untrusted input | Controls in place |
|---|---|---|
| Browser → API | `message`, `session_id`, `location`, `filters`, `nowIso`, `language`, `action`, `placeId` path param, `X-Forwarded-For` | CORS allow-list, per-IP rate limit (20 per 10 min), Pydantic schemas, input gate (`belem_converse/gate.py`: letters, digits, ` ,.:?!`, ≤400 chars), 4 turns per session |
| API → LLM provider | Prompt holds user text + catalog rows | System prompt marks `<places>` as data; `is_grounded` rejects answers naming places outside the results; daily cap; shared timeout |
| LLM → API → browser | Model output | Grounding check, else template answer; Flutter renders text, not HTML |
| Catalog → browser | `website` / `url` fields from scraped data | Opened with `url_launcher` (`frontend/lib/widgets/place_card.dart`), **no scheme check** |
| Disk → process | `simple_tfidf_models_v3.0.pkl` | `pickle.load`, no integrity check (Known finding K06) |

## Surfaces

| Surface | Path | Exposure |
|---|---|---|
| HTTP API | `api/` | Public on Render. Entry: `uvicorn api.main:app` |
| Backend library | `belem_converse/` | Inside the API image |
| Offline tools | `belem_converse/tools/`, `belem_converse/ingest/` | Developer machine only (catalog build, OSM fetch, LLM benchmark) |
| Place catalog | `catalog/belem.sqlite` (+ `cleaning_report.json`, `osm_report.json`) | Committed; copied into the image |
| Flutter client | `frontend/` | Web build published to `docs/app/` (GitHub Pages); Android/iOS projects exist but are not shipped |
| Project site | `docs/*.html`, `docs/assets/` | GitHub Pages (`main:/docs`), static |
| Raw data | `data/` (gitignored) | Developer machine only; scraped Google exports with personal data (K01) |
| Notebooks | `notebooks/*.ipynb` | In git, not run; PoC LangChain/llama.cpp experiments with saved outputs (K13) |

## API endpoints

| Method | Path | Notes |
|---|---|---|
| POST | `/api/chat` | Main entry. Rate-limited. 429 `rate_limited`, 422 gate errors |
| GET | `/api/health` | Render health check; reports catalog state |
| GET | `/api/languages` | `en`, `pt-BR` |
| GET | `/api/places/{placeId}` | One place from the catalog |
| GET | `/` | Name, version, links |
| GET | `/docs`, `/redoc`, `/openapi.json` | Public by choice (K14) |

CORS: `allow_credentials=False`, methods `GET, POST`, header `content-type`.
Origins from `ALLOWED_ORIGINS`; unset means `http://localhost|127.0.0.1` on any port.

## Python backend

- **Runtime**: Python 3.12 in the image (`python:3.12-slim`); `requires-python >=3.10`, local dev on 3.13.
- **Packaging**: setuptools; `pyproject.toml` is canonical, `requirements.txt`
  mirrors it. **No lockfile, `>=` floors only** (K11). The image installs
  `requirements.txt`, then the package with `--no-deps`.

Runtime dependencies. "Installed" is the local `.venv` on 2026-10-17. The image
resolves its own versions at build time, so pip-audit must run inside the image.

| Package | Declared | Installed | Used for |
|---|---|---|---|
| fastapi | >=0.109.0 | 0.128.0 | HTTP API |
| starlette | (via fastapi) | 0.50.0 | ASGI, CORS middleware |
| uvicorn[standard] | >=0.27.0 | 0.40.0 | ASGI server; pulls httptools 0.7.1, uvloop 0.22.1, websockets 16.0, watchfiles 1.1.1, h11 0.16.0 |
| pydantic | >=2.0.0 | 2.12.5 (core 2.41.5) | Request/response schemas, input gate hook |
| python-multipart | >=0.0.9 | 0.0.26 | **Not used** (no form/upload endpoints left); attack surface only |
| python-dotenv | >=1.0.0 | 1.1.1 | Loads `.env` at startup (`find_dotenv(usecwd=True)` searches upward) |
| httpx | >=0.27 | 0.28.1 | LLM client (`belem_converse/llm.py`), TestClient |
| anyio, certifi | (transitive) | 4.12.1, 2025.6.15 | Async I/O, CA bundle for LLM HTTPS |
| numpy | >=1.26 | 2.3.1 | Ranking, classifier |
| scipy | >=1.11 | 1.17.0 | Classifier |
| scikit-learn | >=1.8,<1.9 | 1.8.0 | TF-IDF + LogisticRegression intent classifier (pickled models) |
| joblib | (via scikit-learn) | 1.5.3 | |
| rapidfuzz | >=3.0 | 3.14.3 | Category matching, grounding check |
| h3 | >=3.7 | 4.4.1 | Geo indexing |
| requests | >=2.31 | 2.32.5 | Only `ingest/osm_fetcher.py` (offline); urllib3 2.3.0 |
| tqdm | >=4.66 | — | **Not imported** by any module |

Extras: `tools` = pandas (2.3.0, offline catalog build). `dev` = pytest,
pytest-asyncio, ruff (rules `E F I B UP`), black, mypy.

Stdlib modules worth probing: `pickle` (classifier load/dump), `sqlite3`
(catalog opened `?mode=ro` via URI; build and OSM tools open it read-write),
`zoneinfo` (America/Belem day for the cap).

### In-process state (per instance, lost on restart)

| Component | File | Limits |
|---|---|---|
| `SessionStore` | `belem_converse/sessions.py` | Keyed by client-chosen UUID; 4 turns; 30 min idle; 5 000 sessions, LRU eviction |
| `RateLimiter` | `belem_converse/limits.py` | 20 hits / 600 s per IP, 10 000 keys; IP = right-most `X-Forwarded-For` entry |
| `DailyCap` | `belem_converse/limits.py` | `LLM_DAILY_CAP` model calls per Belém calendar day |

### Logging

stdlib `logging` at INFO to stdout (Render log stream). Logs include the query
plan and request timing; user text reaches INFO logs (K12). The old `debug.log`
writer is K07.

## Language model (hosted)

OpenAI-compatible `POST {base_url}/chat/completions`, Bearer key, one call per
answered question, primary then fallback within one shared `LLM_TIMEOUT_S`.

| Role | Provider | Base URL | Model |
|---|---|---|---|
| Primary | Google AI Studio (free tier) | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-3.5-flash-lite` |
| Fallback | Groq (free tier) | `https://api.groq.com/openai/v1` | `qwen/qwen3.8-27b` |
| Local option | Ollama | `http://localhost:11434/v1` | `gemma4:e4b` (dev only) |

No `LLM_BASE_URL` means no model: every answer is the template answer.

## Configuration and secrets

All configuration is environment variables, read from the process env, then
from `.env` (gitignored, excluded by `.dockerignore`). In production they are
Render env vars; the secrets are `sync: false`, so they are entered in the
dashboard and never committed.

| Variable | Secret | Default |
|---|---|---|
| `LLM_API_KEY`, `LLM_FALLBACK_API_KEY` | **yes** | unset |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_FALLBACK_BASE_URL`, `LLM_FALLBACK_MODEL` | no | unset (Render sets them) |
| `LLM_TIMEOUT_S`, `LLM_MAX_TOKENS`, `LLM_DAILY_CAP` | no | 10, 250, 800 |
| `ALLOWED_ORIGINS` | no | localhost only |
| `BELEM_DATA_DIR`, `BELEMCONVERSE_CITY` | no | repo `data/`, `belem` |
| `PORT` | no | 8000 (Render injects it) |
| `API_BASE_URL` (Flutter `--dart-define`, compile time) | no | `http://localhost:8000/api`; ends up in the public JS bundle |

`config.yaml` at the repo root is a PoC leftover (Mistral GGUF, Chroma paths).
Nothing reads it.

## Flutter client

- **SDK**: Dart `>=3.10.4 <4.0.0`, Flutter `>=3.38.4`, Material 3, `generate: true`.
- **Build**: `flutter build web --release --base-href /BelemConverse/app/ --dart-define=API_BASE_URL=https://<service>.onrender.com/api`,
  then copied to `docs/app/` and committed (no CI).
- **Session id**: UUID v4 from `Random.secure()` (`frontend/lib/utils/session_id.dart`).
- **Input gate**: `frontend/lib/utils/input_gate.dart` mirrors the server gate.
  It only helps the user; the server gate is the real control.

| Package | Locked | Used |
|---|---|---|
| http | 1.6.0 | API calls with timeouts (`services/api_service.dart`) |
| provider | 6.1.5+1 | State management |
| geolocator | 11.1.0 | Browser/device location, sent to `/api/chat` |
| shared_preferences | 2.5.4 | Settings (localStorage on web) |
| url_launcher | 6.3.2 | Opens catalog `website`/`url` in an external app/tab |
| google_fonts | 6.3.3 | Poppins, **fetched at runtime from Google** |
| cupertino_icons | ^1.0.8 | Icons |
| flutter_localizations, intl | SDK, 0.20.2 | Declared; no generated l10n in `lib/` |
| flutter_map, latlong2 | 6.2.1, 0.9.1 | **Declared, not imported** |
| permission_handler | 11.4.0 | **Declared, not imported** |
| flutter_lints, flutter_test | dev | `flutter analyze`, `flutter test` |

Full transitive set: `frontend/pubspec.lock` (scan with osv-scanner).

## Hosting and delivery

| Piece | Where | Notes |
|---|---|---|
| API | Render free web service, Docker runtime, `render.yaml` blueprint | Health check `/api/health`; sleeps after 15 min idle; HTTPS and proxy by Render |
| Image | `Dockerfile`: `python:3.12-slim`, runs as non-root `app`, `uvicorn` on `${PORT:-8000}` | Contents: `api/`, `belem_converse/`, `catalog/`, `pyproject.toml`, `README.md`. No build tools |
| Local container | `docker-compose.yml` | Port 8000, `.env` optional, `restart: unless-stopped` |
| Web client + project site | GitHub Pages from `main:/docs` | `https://mollinetti.github.io/BelemConverse/` (site), `/app/` (client) |
| Project site third parties | Google Fonts (Archivo, Source Serif 4) | Links out to GitHub, LinkedIn, cop30.br |
| Source | GitHub `Mollinetti/BelemConverse` | No CI, no GitHub Actions; secret scanning / push protection not yet on (K10) |

## Offline data pipeline (developer machine)

- `python -m belem_converse.tools.build_catalog`: raw CSV exports under
  `BELEM_DATA_DIR` → pandas cleaning → `catalog/belem.sqlite`.
- `belem_converse/ingest/osm_fetcher.py`: OpenStreetMap Overpass API
  (`overpass-api.de`, `overpass.kumi.systems`, `maps.mail.ru` mirrors) over `requests`.
- `python -m belem_converse.tools.validate_osm`, `python -m belem_converse.tools.bench_llm`
  (calls the configured LLM providers).

## Developer tooling

- **Tests**: pytest (+ pytest-asyncio, httpx TestClient) under `tests/`;
  `flutter test` under `frontend/test/`.
- **Lint**: `ruff check .`, black, mypy; `flutter analyze`.
- **AI agents with repo access**: Claude Code (`.claude/`), Cursor (`.cursor/`,
  `.cursorrules`), Kiro (`.kiro/`). They can read the working tree, including a
  local `.env` (K09).
- **Audit tooling** (mvp-3, not runtime): gitleaks, trufflehog, osv-scanner,
  pip-audit, trivy, semgrep, ruff `S` rules. See
  [mvp-3 plan](mvp/mvp-3-security-audit/plan.md).
