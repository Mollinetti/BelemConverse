# Tasks — mvp-1

## Conventions

- **IDs** are T01, T02, and so on.
- **`[P]`** means the task can run in parallel with any other `[P]` task in the
  same section.
- **`→ depends on`** lists hard dependencies.
- **Strict TDD.** Every implementation task is preceded by a failing-test task
  on the same code. Run the test first and see it fail for the right reason. The
  test names cited in `validation.md` are binding.
- **Commits** start with `mvp-1:`.
- **Shared test data:**
  - Tests use `tests/fixtures/catalog_raw_sample.csv` and
    `tests/fixtures/raw_repair_sample.csv` (T05). Both are small, hand-written
    text files.
  - A `built_catalog` fixture in `tests/conftest.py` runs the catalog build into
    `tmp_path` and yields the SQLite path, so no binary fixtures are committed.
- **No network in pytest.** HTTP goes through `httpx.MockTransport`, and the OSM
  fetcher is injected as a stub.

## Start

- **T00.** Start from a clean tree: discard the uncommitted WIP on `main` (it is
  archived on the `old` branch). Create branch `mvp-1`. Then capture two
  baselines:
  - `pytest -q`: record the pass/fail list in `validation.md`.
  - `python -m tests.diagnostics.run_diagnostic`: record the scores in
    `validation.md` → Evidence.

## Tour removal (api/ + belem_converse/)

- **T01 [P]** Write failing tests in `tests/test_tour_removed.py`:
  - `SimpleTFIDFIntentClassifier().intent_classifier.classes_` does not contain
    `"tour_planning"`, and `MODEL_VERSION == "3.0"`.
  - `QueryPlanner().create_query_plan("monte um roteiro de um dia em Belém")`
    has an intent other than `tour_planning`.
  - `belem_converse.core` exports no `TourPlanner`, and `api.routes` has no
    `_is_tour_planning_query`.
- **T02** Cut the tour feature per plan.md:
  - Edit `routes.py`, `query_planner.py`, `config.py` (prompts),
    `core/__init__.py` and the classifier.
  - Bump `MODEL_VERSION` to 3.0, delete the v2.9 pickle, retrain by loading
    once, and commit the v3.0 pickle.
  - Delete `tests/test_tour_planning.py` and the tour cases in
    `tests/test_e2e_integration.py`.
  - Remove the 3 `tour_planning` expectations in
    `tests/diagnostics/diagnostic_corpus.py`, relabelling them to the intent the
    query now routes to.
  - → depends on T00, T01

## Dead runtime weight (api/ + belem_converse/ + packaging)

- **T03 [P]** Write failing tests in `tests/test_runtime_footprint.py`:
  - **Import check.** In a subprocess, `import api.main`. Then assert that none
    of `chromadb`, `torch`, `sentence_transformers`, `llama_cpp`, or any
    `langchain*` module is in `sys.modules`.
  - **Dependency check.** Parse `pyproject.toml`. Assert those packages are absent
    from `[project].dependencies`, that `httpx` is present, and that `pandas` is
    only in `[project.optional-dependencies].tools`.
  - **Readiness.** `api.dependencies.is_system_ready()` is true after
    `initialize_rag_system()` with no `LLM_*` env vars and no `models/` directory
    (use `monkeypatch.delenv` and a temp working directory).
- **T04** Delete the modules and tests listed in plan.md → Delete. Then:
  - Update `core/__init__.py`, `ingest/__init__.py` and `utils/__init__.py`.
  - Rewrite `api/dependencies.py` so it loads the catalog only and readiness
    means the catalog is loaded.
  - Remove `/ingest/csv` and `/clear-history`.
  - Update `pyproject.toml` and mirror it to `requirements.txt`.
  - → depends on T02, T03

## Catalog build (data pipeline)

- **T05 [P]** Create the fixtures. About 20 rows in total, each row there to
  exercise exactly one fix.
  - `tests/fixtures/catalog_raw_sample.csv` must include:
    - a duplicate `placeId` pair with different categories and review counts;
    - a null-`placeId` row;
    - `city=Bel?m` / `state=Par?`;
    - a garbled title (`Conveni?ncia`) whose `placeId` also appears in the
      repair file;
    - a garbled title with no repair source;
    - hours samples:
      - 12h with U+202F (`8 AM to 2 PM`);
      - 24h (`19:00 to 23:30`);
      - `Atendimento 24 horas`;
      - a serialized-Series string (`… Name: openingHours/0/hours, dtype: object`);
      - an empty value;
    - title casing: an all-caps title (`RESTAURANTE DO PARÁ`) and an
      all-lowercase title;
    - a `totalScore=0, reviewsCount=0` row;
    - location rows: an Ananindeua row, a Mosqueiro row, and a row outside the
      bbox;
    - both `IsSponsored` and `isSponsored` columns;
    - a `Snack bar` category row.
  - `tests/fixtures/raw_repair_sample.csv`: the repair row with the correct
    accented title.
- **T06 [P]** Write failing tests in `tests/test_catalog_build.py`, one test per
  fix in plan.md, all using `built_catalog`:
  - `test_no_duplicate_place_ids` and `test_duplicates_merge_categories_and_keep_most_reviews`.
  - `test_null_place_id_dropped`.
  - `test_city_state_normalized`: no `?`; city `Belém`, state `PA`.
  - `test_garbled_title_repaired_from_raw` and
    `test_unrepairable_title_flagged_needs_review` (the row is kept).
  - `test_hours_parsed_to_schema`, covering each sample:
    - 12h becomes `08:00:00–14:00:00` ranges;
    - "24 horas" covers all days;
    - garbage gives null `hours` **and** null `hours_raw`;
    - U+202F is removed from `hours_raw`.
  - `test_titles_title_cased_with_exceptions` (`Restaurante do Pará`).
  - `test_zero_reviews_rating_null`.
  - `test_municipality_filter`: Mosqueiro kept, Ananindeua and out-of-bbox rows
    dropped.
  - `test_sponsor_columns_unified`.
  - `test_price_column_absent`.
  - `test_fts_finds_title`: `SELECT … FROM places_fts WHERE places_fts MATCH 'restaurante'`.
  - `test_report_counts_reconcile`: input = kept + merged + dropped, and every
    fix key is present.
- **T07 [P]** Write failing tests in `tests/test_category_inference.py`:
  - `Snack bar` → `restaurant`; `Wine bar` → `bar`; `Bar` → `bar`;
    `Hotel` → `other`; `Cafe` → `restaurant`.
  - Regression check: no category maps through a reverse substring.
- **T08** Implement `belem_converse/tools/build_catalog.py`. Fix the category
  matcher and sponsor reading in `ingest/csv_ingestion.py`. Add
  `title_case_exceptions` and `municipalities` to `cities/belem.py`.
  - CLI: `python -m belem_converse.tools.build_catalog [--csv …] [--raw-dir …] [--out data/belem/]`.
  - → depends on T05, T06, T07
- **T09 [P]** Write failing tests in `tests/test_catalog_loader.py`:
  - `load_places(built_catalog)` returns dicts with `placeId`, `title`,
    `categories` (list), `location.lat/lng`, `totalScore`, `reviewsCount` and
    `businessTime`.
  - `PlaceCache(load_places(...)).get_by_id(<id>)` works.
  - `UnifiedRetriever` with category `restaurant` returns at least one place.
- **T10** Implement `belem_converse/catalog.py`. Point `_load_places_index` in
  `api/routes.py` at `city.catalog_path`. When the catalog is missing, return
  503 with a hint to run `build_catalog`, instead of the old ingest hint.
  → depends on T08, T09
- **T11 [P]** Write failing tests in `tests/test_open_now_timezone.py`:
  - Setup: a place open `08:00–12:00` every day. Monkeypatch the retriever's
    clock to return `2026-10-11 13:30 UTC`, which is 10:30 in Belém.
  - The `open_now` filter keeps the place.
  - At `16:30 UTC` (13:30 in Belém) the filter drops it.
- **T12** Implement the time-zone fix:
  - Move the `datetime` import in `unified_retriever.py` to module level so the
    clock can be patched.
  - Use `datetime.now(ZoneInfo(city.timezone))`.
  - Add `timezone` to the city profile.
  - → depends on T11

## OSM validation (data pipeline)

- **T13 [P]** Write failing tests in `tests/test_validate_osm.py`:
  - Setup: a stub fetcher returns OSM features for a 3-place catalog:
    - one with the same name 40 m away;
    - one with the same name 400 m away;
    - nothing for the third.
  - Then:
    - `osm_verified` is `[1, 1, 0]` and `osm_id` is set for the matches;
    - the report lists only the 400 m place under `coordinate_mismatch`;
    - the row count is unchanged;
    - no HTTP happens.
- **T14** Implement `belem_converse/tools/validate_osm.py` (the fetcher is
  injectable). Delete `tools/refresh_data.py`. → depends on T08, T13
- **T15** Manual: run `python -m belem_converse.tools.validate_osm` against live
  Overpass. Record the match rate and mismatch count in `validation.md`. Do not
  run it in CI. → depends on T14

## LLM (belem_converse/)

- **T16 [P]** Write failing tests in `tests/test_llm_client.py` (all via
  `httpx.MockTransport`):
  - **Success:** returns the content.
  - **Request shape:** the body has `model`, `max_tokens == 250` and
    `temperature ≤ 0.3`. The system message for `pt-BR` is `PROMPT_PT` (and
    `PROMPT_EN` for `en`). The user message wraps places in `<places>…</places>`.
    The `Authorization: Bearer` header is present.
  - **Fallback:** primary 429 → fallback provider called → its content is
    returned.
  - **Timeout:** primary times out with no fallback → `None`, after at most
    `LLM_TIMEOUT_S`.
  - **Unconfigured:** no `LLM_BASE_URL` → `None`, and the transport is never
    called.
  - **Prompt injection fixture:** a place title containing "ignore previous
    instructions" stays inside `<places>` and is not repeated in the system
    message.
- **T17 [P]** Write failing tests in `tests/test_grounding.py`:
  - `is_grounded` is true when every `**bold**` name fuzzy-matches a result
    title, ignoring case and accents (`**Estacao das Docas**` matches
    `Estação das Docas`).
  - False when a bold name matches no result.
  - False when an unbolded catalog title outside the results appears in the
    text.
  - True when there are no bold spans and no stray catalog titles.
  - `strip_markers` removes `**`.
- **T18** Implement `belem_converse/llm.py` (`summarize`, `PROMPT_PT`,
  `PROMPT_EN`, `is_grounded`, `strip_markers`). Env vars: `LLM_BASE_URL`,
  `LLM_MODEL`, `LLM_API_KEY`, `LLM_FALLBACK_BASE_URL`, `LLM_FALLBACK_MODEL`,
  `LLM_FALLBACK_API_KEY`, `LLM_TIMEOUT_S` (default 10), `LLM_MAX_TOKENS`
  (default 250). → depends on T16, T17

## Chat endpoint (api/)

- **T19 [P]** Write failing tests in `tests/test_chat_api.py`:
  - **Setup:** FastAPI `TestClient`. Point the catalog at `built_catalog` through
    `monkeypatch`, and monkeypatch `llm.summarize` with an `AsyncMock`.
  - **Model answer:** a pt-BR question returns 200 with ≤5 results.
    `answer` equals the mock text with markers stripped. `summarize` was awaited
    **exactly once**, and `debug.answer_source == "llm"`.
  - **Not grounded:** the mock returns an ungrounded answer → `answer` equals
    `_generate_answer(...)`, with `answer_source == "template"`.
  - **No model answer:** the mock returns `None` → 200 with the template answer.
  - **No results:** zero results → template "no results" answer, and
    `summarize` is not awaited (no model call wasted).
  - **Tour query:** "monte um roteiro de um dia em Belém" → 200, results present,
    no itinerary text.
  - **Removed endpoints:** `POST /api/ingest/csv` and `POST /api/clear-history`
    → 404.
  - **Health:** `GET /api/health` is ready with no `LLM_*` env vars.
- **T20** Wire `summarize` + `is_grounded` + the template fallback into `chat()`.
  Add `debug.answer_source` and `load_dotenv()` in `api/main.py`.
  → depends on T04, T10, T18, T19

## Benchmark (tools)

- **T21 [P]** Write a failing smoke test in `tests/test_bench_llm.py`:
  - Setup: `bench_llm.run(models=["fake"], queries=2)` with a `MockTransport`
    returning a grounded answer.
  - It returns rows with `model`, `grounded_pct`, `p50_ms` and `n`.
  - Over 2 queries, `grounded_pct == 100`.
- **T22** Implement `belem_converse/tools/bench_llm.py`. It reuses the
  `GOLDEN_QUERIES_EN` and `GOLDEN_QUERIES_PT` lists, the retriever, `summarize`
  and `is_grounded`, and prints a markdown table. → depends on T20, T21
- **T23** Manual: benchmark the candidates from spec D2 against the real
  `built_catalog`.
  - Spot-check 10 pt-BR answers per finalist.
  - Fill in `validation.md` → Evidence.
  - Pick the smallest model meeting the success metrics.
  - Write it into `.env.example` and `../spec.md` D2.
  - → depends on T22

## Classifier review

- **T24** Rerun `python -m tests.diagnostics.run_diagnostic` and record the
  scores next to the T00 baseline. Intent must be ≥ 80%. If it is lower, stop
  and raise it as a blocker (spec D3 revisit trigger). → depends on T02

## Wiring & docs

- **T25** Update `.env.example` with the `LLM_*` variables, `BELEM_CITY` and the
  catalog path. Update the README sections that would otherwise be wrong:
  - **Getting started:** run `build_catalog`, not `POST /ingest/csv`.
  - **Configuration:** the `LLM_*` variables.
  - **API:** drop the removed endpoints.
  - **Badges:** drop llama.cpp, Llama 3.1, ChromaDB and Sentence Transformers.

  The full README rewrite is mvp-2. → depends on T20
- **T26** Final gate:
  - `pytest -q` is green with no new skips.
  - `ruff check .` passes.
  - Measure memory per `validation.md`.
  - Fill in the Definition of done.
  - → depends on all
