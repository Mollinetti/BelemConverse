# Phase 1 — Lean grounded core

**Spec**: [spec.md](spec.md) · **Next**: [phase-2-public-mvp.md](phase-2-public-mvp.md)

## Goal

`/api/chat`, run locally, answers from **clean Belém data loaded from SQLite**,
with the **tour feature removed**, **slim dependencies**, and **one call to a
small hosted LLM per turn**. A template fallback covers any LLM failure.
Everything is verifiable with pytest and curl, with no frontend work.

## Scope

- **In:** `belem_converse/`, `api/`, `tests/`, `pyproject.toml` and
  `requirements.txt`, and the data build tools.
- **Out:** Flutter, deploy, sessions, gate, cache, follow-ups (all Phase 2).

## Tasks (in order)

### 1. Cut the tour feature

Remove it at every point where it attaches:

- `api/routes.py`: the tour branch inside `/chat` and `_is_tour_planning_query`.
- `belem_converse/core/enhanced_rag_agent.py`: tour routing in `query()`, plus
  `_is_tour_planning_query`, `_handle_tour_planning`, `_parse_tour_parameters`
  and `_generate_tour_response`.
- `belem_converse/core/tour_planner.py` and its exports in
  `belem_converse/core/__init__.py`.
- `TOUR_PLANNER_PROMPT_EN` and `TOUR_PLANNER_PROMPT_PT` in
  `belem_converse/utils/config.py`.
- `belem_converse/core/query_planner.py`: the `tour_planning` intent. Those
  queries now route to `find_places`.
- The classifier: drop the `tour_planning` keywords and templates, retrain the
  pickle, bump `MODEL_VERSION` to 3.0, and delete the old `.pkl`.
- Tests: delete `tests/test_tour_planning.py` and the tour cases in
  `test_e2e_integration.py` and `test_prompt_leakage.py`.

Keep the `tourist_attraction` **category**. It is unrelated to tours.

The pending uncommitted fixes to the tour path in `routes.py` and
`enhanced_rag_agent.py` become moot. Commit or discard them first, so this cut
starts from a clean tree.

### 2. Remove dead runtime weight

- **Code:**
  - Delete the Chroma vector-store path, `two_stage_retriever.py`, the parts of
    `EnhancedRAGAgent` that are not reused, and `utils/conversation_memory.py`.
  - Drop the `/ingest/csv` and `/clear-history` endpoints.
  - In `api/dependencies.py`, stop loading the LLM, embedder and Chroma at boot.
- **Dependencies:**
  - Remove `chromadb`, `sentence-transformers`, `torch`, all `langchain*`
    packages and `llama-cpp-python`.
  - Promote `httpx` to a runtime dependency.
  - Keep `pandas` only if `build_catalog` needs it. It is offline tooling, so it
    can move to a `tools` extra.
- **Before deleting each module**, grep its importers and delete or adjust the
  tests that only exercised dead code. Note the deleted test files in the commit
  message.

### 3. Data cleaning: `belem_converse/tools/build_catalog.py`

The tool reads `data/csvs/combined_all_data.csv`, with `data/Raw/*` for
repairs. It reuses the field mapping in `ingest/csv_ingestion.py` and fixes that
module's category bug (substring match in both directions).

It writes `places.sqlite` and `cleaning_report.json` (a count for every fix
below).

| Problem | Fix |
|---|---|
| 306 duplicate `placeId`s; 1 null `placeId` | Merge on `placeId`, union the categories, keep the row with the most reviews. Drop the null-id row. |
| Mojibake in `city` / `state` | Normalise to `Belém` / `PA` / `BR`. |
| Mojibake in titles and addresses (67 / 82) | Repair from the `data/Raw/*` row with the same `placeId`. If none exists, set `needs_review=1`. |
| `businessTime` formats | Parse 12h (with U+202F), 24h and "24 horas" into per-day `{"mon": "08:00-14:00", …}`. Serialized-Series garbage becomes null. |
| 267 all-caps and 12 all-lowercase titles | Title-case them. Keep the list of exceptions in the city profile. |
| 3 address columns, 2 sponsor columns | Unify into `address` and `is_sponsored`. |
| `price` = 0 everywhere | Drop the column. |
| `totalScore` 0 with 0 reviews | Set `rating` to null. |
| 71 rows outside the bbox | Tag `municipality`. Drop rows outside the city-profile bbox. Whether to keep Ananindeua is a city-profile setting. |
| Inferred `place_type` | Recompute it with the fixed matcher. |

**SQLite schema:**
- One `places` table with typed columns.
- `hours` stored as JSON text.
- An FTS5 virtual table over the title.

### 4. Validation scrape pass (OSM, no API key)

- Reuse `belem_converse/tools/refresh_data.py` and `ingest/osm_fetcher.py` with
  `place_matcher.py`. Match catalog rows to OSM features by name and distance.
- Write `osm_verified` (0/1) and `osm_id`. Add a distance-delta report for
  coordinates that disagree by more than 150 m.
- Never auto-delete unmatched rows; just flag them. A low OSM match rate is
  normal in Brazil.
- **Optional:** re-scrape with the Apify Google Places crawler, within its free
  monthly credit, only for rows whose `hours` is null after cleaning. Merge by
  `placeId`.

### 5. Load from SQLite

- `PlaceCache` (`belem_converse/core/`) reads from `places.sqlite`, with the path
  taken from the city profile.
- `UnifiedRetriever` and `RankingEngine` stay unchanged.
- Remove the Oriximiná `canonical_places.jsonl` from the runtime path.
- Teach the open-now filter the new per-day `hours` format.

### 6. TF-IDF review

- Run `python -m tests.diagnostics.run_diagnostic` **before** task 1 and **after**
  task 6. Record both scores here.
- Drop the duplicate `predict` call in `/chat`.
- Decision rule (spec D3): keep TF-IDF unless intent accuracy is below 80%.

| Run | Intent | Category | Proximity | Open-now |
|---|---|---|---|---|
| Baseline (v2.9, 2026-10) | 83.2% | 85.8% | 93.8% | 99.1% |
| After Phase 1 | _tbd_ | _tbd_ | _tbd_ | _tbd_ |

### 7. LLM client, prompt and benchmark

- **Client:** about 40 lines in `belem_converse/utils/llm.py`. It does one
  `httpx` POST to `{LLM_BASE_URL}/chat/completions`.
  - Timeout 10 s.
  - A second provider from the `LLM_FALLBACK_*` env vars.
  - Then the template `_generate_answer`.
- **Prompt:** new compact pt-BR and en system prompts that summarise the ≤5 given
  places and nothing else.
  - Place data is wrapped in a delimited block marked as data.
  - Output is capped at 250 tokens.
- **Grounding check:** every place name the answer mentions must be one of the
  retrieved titles (fuzzy match). If not, use the template answer.
- **Benchmark:** `belem_converse/tools/bench_llm.py` runs the golden queries
  (`GOLDEN_QUERIES_EN` and `GOLDEN_QUERIES_PT` in
  `tests/test_golden_queries.py`) against each candidate model from spec D2.
- **Record the results here.** Pick the smallest model that passes, and note its
  name in spec D2 and in `.env.example`.

| Model | Grounding pass % | pt-BR OK (10 spot-checks) | p50 latency | Free requests/day |
|---|---|---|---|---|
| _tbd_ | | | | |

## Acceptance criteria

- **(pytest) Catalog:**
  - No duplicate `placeId`.
  - No `?` in `city` or `state`.
  - Every non-null `hours` parses to the schema.
  - Every row is inside the bbox.
  - `cleaning_report.json` counts add up to the input row count.
- **(pytest) Classifier:**
  - `MODEL_VERSION` matches the pickle (existing test).
  - `tour_planning` is not in the intent labels.
- **(pytest) Tour removed:** a tour-style query ("roteiro de um dia") returns
  normal place results with HTTP 200.
- **(pytest) Grounding:** a mocked LLM answer that names a place not in the
  results makes the endpoint return the template answer.
- **(pytest) Fallback:** a mocked LLM that returns 429 or times out still yields
  HTTP 200 with the template answer.
- **(pytest) LLM budget:** a normal turn makes exactly one call to the LLM client
  (mock call count).
- **(manual) Memory:** the API starts and serves `/chat` at < 512 MB RSS
  (`/usr/bin/time -l uvicorn …`, or `ps` after a few requests).
- **(manual) Recorded results:** benchmark and diagnostic tables above are
  filled in.

## Verification

```bash
pip install -e . && pytest -q
python -m belem_converse.tools.build_catalog            # → places.sqlite + cleaning_report.json
LLM_BASE_URL=… LLM_MODEL=… LLM_API_KEY=… uvicorn api.main:app --port 8000
curl -s localhost:8000/api/chat -H 'content-type: application/json' \
  -d '{"message":"restaurantes abertos perto da Estação das Docas","language":"pt-BR"}' | jq
```
