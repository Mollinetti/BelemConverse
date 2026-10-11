# Plan — mvp-1

## Tech context

### api/ (FastAPI)

- **`api/routes.py`**
  - Delete the tour branch in `chat()` and `_is_tour_planning_query`.
  - Delete the second `intent_classifier.predict()` call. The planner's result
    already carries intent.
  - Delete `ingest_csv` (`POST /ingest/csv`) and `clear_history`
    (`POST /clear-history`).
  - `_load_places_index()` reads the SQLite catalog through a new loader instead
    of the JSONL file.
  - Keep `_generate_answer()` as the template fallback.
  - After retrieval, `chat()` awaits `summarize()` from the new LLM module.
- **`api/dependencies.py`**
  - `initialize_rag_system()` stops loading Chroma, the embedder, `ModelManager`
    and `EnhancedRAGAgent`.
  - "Ready" means the catalog is loaded. `is_system_ready()` currently requires
    `_rag_agent`; drop that condition.
- **`api/main.py`:** call `load_dotenv()` at startup. `python-dotenv` is already
  a dependency but is never called, so `.env` currently does nothing.
- **`api/schemas.py`:** no shape change in mvp-1. Remove `IngestionResponse` if
  nothing else uses it.

### belem_converse/ (library)

**Delete.** Importers were checked on 2026-10-11; every one is either deleted
too or listed here:

| Module | Remaining importers to fix |
|---|---|
| `core/tour_planner.py` | `core/__init__.py` |
| `core/enhanced_rag_agent.py` | `api/dependencies.py`, `core/__init__.py` |
| `core/two_stage_retriever.py` | none after the vector preprocessor goes |
| `core/search_fallback.py` | none once `two_stage_retriever.py` is deleted |
| `ingest/osm_realtime_search.py` | none once `search_fallback.py` is deleted |
| `ingest/vector_store.py`, `ingest/vector_database_preprocessor.py` | `api/dependencies.py`, `ingest/__init__.py` |
| `ingest/data_loader.py` | `api/dependencies.py`, `ingest/__init__.py` |
| `utils/models.py` (`ModelManager`, GGUF and embedder loader) | `api/dependencies.py`, `utils/__init__.py` |
| `utils/conversation_memory.py` | none after the agent goes |
| `tools/refresh_data.py` | none; replaced by `build_catalog` + `validate_osm`, and it imports `vector_store` |

**Tests to delete,** because they exercise only deleted code:
`test_tour_planning.py`, `test_prompt_leakage.py`, `test_two_stage_retrieval.py`,
`test_llama31_model.py`, `test_osm_fallback.py`.
In `test_e2e_integration.py`, delete only the tour cases.

All other tests import only modules that stay and must keep passing unchanged.

**Keep and reuse:**
- `core/place_cache.py`: `PlaceCache(places_data)` already takes a list of
  dicts, so it does not change.
- `core/unified_retriever.py`, `core/ranking_engine.py`,
  `core/category_matcher.py`, `core/query_planner.py`, `utils/bayesian_ranking.py`.
- `utils/business_hours_parser.py` (`BusinessHoursParser.parse()` →
  `BusinessHours.to_dict()`). The catalog build and the open-now filter both
  reuse it; no new parser.
- `ingest/csv_ingestion.py` (field mapping), `ingest/osm_fetcher.py`,
  `ingest/place_matcher.py`.

**Change:**
- **`core/query_planner.py`:** remove the `tour_planning` branch (around
  L256–272). Tour keywords no longer route anywhere special.
- **`classifiers/intent_classifier_TFIDF_simple.py`:**
  - Remove the `tour_planning` keywords, templates and `is_tour_planning_query`.
  - `MODEL_VERSION` "2.9" → "3.0".
  - Delete `models/simple_tfidf_models_v2.9.pkl`. A version mismatch already
    triggers retraining (L36, `train()` L626); commit the regenerated v3.0
    pickle.
- **`core/unified_retriever.py` `_filter_by_open_now`:** change only how "now" is
  computed. Today it uses naive `datetime.now()`, which is UTC on a server and
  3 hours off for Belém. Use
  `datetime.now(ZoneInfo(city.timezone))`. `zoneinfo` is stdlib. If the
  container lacks system time-zone data, add `tzdata` in mvp-2.

  Parsing stays as it is: the catalog supplies a **cleaned** `businessTime`
  string (garbage becomes null), and the existing retriever tests keep their
  fixtures. Pre-parsing per request is a ponytail upgrade, worth doing only if
  open-now latency ever matters.
- **`cities/base_city.py` and `cities/belem.py`:** add `timezone`
  (`"America/Belem"`), `municipalities` (`["Belém"]`, accent-insensitive, plus
  Mosqueiro and Outeiro district aliases), `catalog_path`, and
  `title_case_exceptions`.
- **`ingest/csv_ingestion.py`:** fix the category matcher. The
  `normalized in normalized_keyword` check matches both ways, so it must become
  whole-token matching. Read the sponsor flag from both `IsSponsored` and
  `isSponsored`.

**New:**
- **`belem_converse/catalog.py`:** `load_places(path) -> list[dict]` (SQLite →
  the dicts `PlaceCache` expects), about 20 lines.
- **`belem_converse/tools/build_catalog.py`:** the CLI. CSV in, then
  normalize → dedupe → repair → parse hours → filter municipality, then SQLite
  out plus `cleaning_report.json`. It uses pandas, which moves to a `tools`
  extra.
- **`belem_converse/tools/validate_osm.py`:** a thin CLI over `osm_fetcher` and
  `place_matcher`. It writes `osm_verified` and `osm_id` into the catalog plus
  `osm_report.json`, and it replaces `refresh_data.py`.
- **`belem_converse/llm.py`** (about 60 lines):
  - `async summarize(question, places, language) -> str | None`.
  - One `httpx.AsyncClient` POST to `{base_url}/chat/completions` per
    configured provider, in order primary → fallback.
  - Returns `None` when every provider fails, so the caller uses the template.
  - Also holds `PROMPT_PT`, `PROMPT_EN` and `is_grounded(answer, places, catalog_titles)`.
- **`belem_converse/tools/bench_llm.py`:** runs `GOLDEN_QUERIES_EN` and
  `GOLDEN_QUERIES_PT` (from `tests/test_golden_queries.py`) through
  retrieval + `summarize` for each model passed on the command line, and prints
  the results table.

### Data pipeline

- **Inputs:** `data/csvs/combined_all_data.csv` (3,446 rows), plus
  `data/Raw/*.csv` to repair garbled text by `placeId`.
- **Outputs:** `data/belem/places.sqlite`, `data/belem/cleaning_report.json` and
  `data/belem/osm_report.json`. All stay gitignored in mvp-1; mvp-2 moves the
  SQLite file to a tracked path.
- The Oriximiná `data/canonical_places.jsonl` leaves the runtime path; the files
  stay on disk.

## Architecture sketch

```
offline:  combined_all_data.csv ─┬─ build_catalog ──► places.sqlite + cleaning_report.json
          data/Raw/*.csv ────────┘        │
                                           └── validate_osm (Overpass) ──► osm_verified/osm_id + osm_report.json

runtime:  POST /api/chat
            → QueryPlanner (rules + TF-IDF, 1 classifier pass)
            → UnifiedRetriever over PlaceCache(load_places(places.sqlite))
            → RankingEngine → top 5
            → llm.summarize (primary → fallback provider; ≤1 successful call)
                 ├─ ok + is_grounded → strip **markers** → answer
                 └─ None / not grounded → _generate_answer (template)
```

## Data model deltas

SQLite `places` table, one row per `placeId`:

| Column | Type | Notes |
|---|---|---|
| `placeId` | TEXT PK | required |
| `title` | TEXT | repaired and title-cased |
| `title_raw` | TEXT | original |
| `categories` | TEXT (JSON array) | union across merged duplicates |
| `categoryName` | TEXT | |
| `place_type` | TEXT | recomputed with the fixed matcher |
| `address` | TEXT | unified from `address`, `addressFormatted`, `adressFormatted` and `formattedAddress` |
| `neighborhood` | TEXT | |
| `municipality` | TEXT | |
| `lat`, `lng` | REAL | |
| `phone`, `website`, `url` | TEXT | |
| `rating` | REAL NULL | null when `reviewsCount` = 0 |
| `reviewsCount` | INTEGER | |
| `is_sponsored` | INTEGER 0/1 | |
| `hours` | TEXT (JSON) NULL | the `BusinessHours.to_dict()` shape |
| `hours_raw` | TEXT | |
| `needs_review` | INTEGER 0/1 | |
| `osm_verified` | INTEGER 0/1 | |
| `osm_id` | TEXT NULL | |

- FTS5 virtual table `places_fts(title, content='places')`.
- `price` is dropped (0 in every row).
- `load_places()` maps rows back to the dict keys the retriever and ranker read
  today: `location: {lat, lng}`, `totalScore` ← `rating`, `businessTime` ←
  `hours_raw`.

  `hours_raw` is the **cleaned** string: U+202F becomes a space, and
  serialized-Series garbage becomes null. `hours` holds the parsed JSON so the
  build can be verified and the hours can be shown later. The retriever stays
  untouched apart from the time-zone change.

## API contract deltas

- **Removed endpoints:** `POST /api/ingest/csv` and `POST /api/clear-history`.
- **`POST /api/chat`:** request and response shapes are unchanged. `answer` is
  now model-written when the model is available. `debug` (when present) gains
  `answer_source: "llm" | "llm_fallback" | "template"`.
- **`GET /api/health`:** reports ready once the catalog is loaded. It no longer
  depends on the LLM.
- The contract is FastAPI's `/openapi.json`; the archived YAML is not updated.

## Risks and trade-offs

- **Grounding check is heuristic.**
  - The prompt tells the model to put place names in `**bold**`.
  - `is_grounded` checks each bold span against the result titles with rapidfuzz
    (`ratio ≥ 85`; rapidfuzz is already a dependency).
  - It also scans the answer for any catalog title longer than 5 characters that
    is not in the results.
  - The ceiling: an unbolded, misspelled name slips through. Upgrade path: ask
    for numbered references `[1]`–`[5]`.
- **Model choice may change** as free tiers change. Mitigation: the provider is
  configured purely through env vars, and the benchmark tool lets anyone
  re-measure in minutes.
- **Low OSM match rate** is expected for Brazilian small businesses, so the flag
  is informational only and never filters results.
- **Deleting modules breaks tests that only exercised them.** Mitigation: those
  tests are deleted on purpose and listed in the commit message, never
  `skip`-ped.
- **Hours parsing coverage.** Some strings will not parse. They become `hours`
  null with `hours_raw` kept, and the open-now filter treats them as unknown
  (excluded when the user asks for "open now", as today).
- **The Flutter client still calls `POST /clear-history`.** In
  `ChatProvider.clearHistory`, that call now gets a 404. The call is
  best-effort, so the chat keeps working; mvp-2 replaces it with "Nova
  conversa". The `/chat` request and response shapes are unchanged, so the
  existing client works against the mvp-1 backend.
- **Synchronous LLM call** in the old code blocked the event loop. The new
  client is `httpx.AsyncClient`, so this is fixed by construction.

## Ground-rules alignment (spec.md → Ground rules)

1. **pytest gate:** every P1 criterion maps to a test in `tasks.md`, and failing
   tests come first.
2. **Dependencies:**
   - Net removal of chromadb, sentence-transformers, torch, langchain,
     langchain-core, langchain-community, langchain-huggingface and
     llama-cpp-python.
   - `httpx` moves from test to runtime.
   - `pandas` moves to the `tools` extra.
   - No new packages.
3. **No secrets in git:** `LLM_API_KEY` and `LLM_FALLBACK_API_KEY` exist only in
   `.env`, which is gitignored. `.env.example` lists the names.
4. **Untrusted data:** place fields go into the prompt inside a `<places>` block
   that the system prompt declares to be data. Output is capped at 250 tokens and
   grounding-checked.
5. **Data out of git:** the catalog outputs stay under the gitignored `data/` in
   mvp-1. The regenerated classifier pickle is a code artefact and is committed,
   as v2.9 was.
