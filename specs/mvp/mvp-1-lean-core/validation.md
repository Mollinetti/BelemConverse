# Validation — mvp-1

## Required gate

`pytest -q` passes from the repo root with no new skips and no network access.

### Test map for the P1 acceptance criteria

| Acceptance criterion (spec.md) | Test |
|---|---|
| Grounded answer: model answer used, ≤5 results, 1 model call | `tests/test_chat_api.py::test_llm_answer_used_once` |
| Grounded answer: stray place → template | `tests/test_grounding.py`, `tests/test_chat_api.py::test_ungrounded_answer_falls_back` |
| Grounded answer: language follows question | `tests/test_llm_client.py::test_system_prompt_per_language` |
| Clean catalog: ids, city/state, hours, municipality | `tests/test_catalog_build.py` (one test per fix) |
| Clean catalog: report reconciles | `tests/test_catalog_build.py::test_report_counts_reconcile` |
| Clean catalog: unrepairable name kept and flagged | `tests/test_catalog_build.py::test_unrepairable_title_flagged_needs_review` |
| Free hardware: no heavy packages imported or declared | `tests/test_runtime_footprint.py` |
| Always answers: 429 / timeout / unconfigured | `tests/test_llm_client.py`, `tests/test_chat_api.py::test_no_llm_returns_template` |
| Always answers: ready without a model | `tests/test_runtime_footprint.py::test_ready_without_llm`, `tests/test_chat_api.py::test_health_ready` |

### Supporting tests (P2/P3)

- `tests/test_tour_removed.py` and `tests/test_chat_api.py::test_tour_query_returns_places`.
- `tests/test_validate_osm.py`.
- `tests/test_bench_llm.py`.
- `tests/test_open_now_timezone.py`.
- `tests/test_category_inference.py`.
- `tests/test_catalog_loader.py`.

### Existing tests that must still pass unchanged

`test_category_matcher`, `test_distance_calculation`, `test_error_handling`,
`test_golden_queries`, `test_intent_classifier_fallback`,
`test_intent_classifier_model_version`, `test_intent_mapping`, `test_place_cache`,
`test_query_planner_refactoring`, `test_ranking_engine`,
`test_retrieval_strategy_selection`, `test_semantic_search`,
`test_unified_retriever`, and `test_e2e_integration` (minus its tour cases).

## Recommended gates

- `ruff check .` (the repo config is `E, F, I, B, UP`, line length 100).
- `mypy belem_converse api`, recorded but not blocking.
- **Memory**, recorded:

  ```bash
  /usr/bin/time -l uvicorn api.main:app --port 8000 &   # macOS; use /usr/bin/time -v on Linux
  for i in $(seq 20); do curl -s localhost:8000/api/chat -H 'content-type: application/json' \
    -d '{"message":"restaurantes perto da Praça da República","language":"pt-BR"}' >/dev/null; done
  kill %1   # read "maximum resident set size" — must be < 512 MB
  ```

## Manual walkthrough

### P1 — Grounded answer

1. Build the catalog:
   `python -m belem_converse.tools.build_catalog` (then `validate_osm`).
2. Start the API with the chosen model:
   `LLM_BASE_URL=… LLM_MODEL=… LLM_API_KEY=… uvicorn api.main:app --port 8000`.
3. Ask a question in Portuguese:

   ```bash
   curl -s localhost:8000/api/chat -H 'content-type: application/json' \
     -d '{"message":"restaurantes abertos perto da Estação das Docas","language":"pt-BR"}' | jq
   ```

   **Expected:**
   - The answer is fluent Portuguese.
   - Every place named in the answer appears in `results`.
   - `debug.answer_source` is `llm`.
4. Repeat in English. **Expected:** an English answer with the same grounding.
5. Capture both JSON responses and paste them below under Evidence.

### P1 — Clean catalog

1. Open `data/belem/cleaning_report.json`. **Expected:** the counts reconcile
   with the input rows.
2. Run these spot checks:

   ```bash
   sqlite3 data/belem/places.sqlite "select count(*), count(distinct placeId) from places;"   # equal
   sqlite3 data/belem/places.sqlite "select count(*) from places where title like '%?%';"      # only needs_review rows
   ```

### P1 — Always answers

1. Restart the API with `LLM_BASE_URL=http://127.0.0.1:9` (nothing listening
   there).
2. Ask any question. **Expected:** HTTP 200 with the template answer, in under
   12 s, and `answer_source` is `template`.

### P1 — Runs on free hardware

Run the memory procedure above and record the number.

## Evidence (fill in during the phase)

| Item | Value |
|---|---|
| Baseline pytest (T00) | 194 collected at `642c707`: 187 passed · 1 failed · 2 errors · 4 skipped. **Failed:** `test_e2e_integration.py::TestCompleteUserJourneys::test_journey_best_restaurants_open_now` (expects sort `popularity`, gets `best_match`; pre-existing). **Errors:** `test_llama31_model.py::test_portuguese_response`, `::test_instruction_following` (fixture `llm` not found; file deleted in T04). **Skipped:** 4 in `test_e2e_integration.py` (lines 334, 589, 611, 630: "Category matching issue … normalize() argument 2 must be str, not list"). |
| Diagnostic before (T00) | intent 83.2% · category 85.8% · proximity 93.8% · open-now 99.1% (n=113, v2.9 classifier; re-run at `642c707` matches) |
| Diagnostic after (T24) | intent 82.3% · category 85.8% · proximity 91.2% · open-now 99.1% (n=113, v3.0 classifier, no tour intent). Intent ≥ 80% ✓. The 3 former tour items were relabelled to the v3.0 routing (T02), so they score correct by construction; excluding them, intent is 90/110 = 81.8%. Proximity −2.6 pts vs baseline. |
| Catalog rows in → kept / merged / dropped | _tbd_ |
| Rows with parsed hours / needs_review | _tbd_ |
| OSM match rate / coordinate mismatches > 150 m (T15) | 142 of 2,901 places confirmed (4.9%) against 1,374 Overpass features for the Belém box (2026-10-11); 14 confirmed places more than 150 m off (153–886 m), listed in `osm_report.json` — mostly beaches/parks whose OSM point is an area centroid, plus a few name collisions to review (`Belém Hostel` ↔ `Itaóca Belém Hotel`, chain branches). Informational only; nothing deleted. |
| Peak RSS after 20 requests | _tbd_ MB |

**Model benchmark (T23):**

| Model | Provider | Grounded % | pt-BR OK /10 | p50 latency | Free requests/day | Chosen |
|---|---|---|---|---|---|---|
| _tbd_ | | | | | | |

## Definition of done

- [ ] All P1 acceptance criteria are covered by the tests in the map above, and
      those tests pass.
- [ ] The required gate (`pytest -q`) passes with no new skips; deleted tests
      are listed in their commit messages.
- [ ] `spec.md` has no `[NEEDS CLARIFICATION]` markers.
- [ ] The ground-rules check in `plan.md` is clean.
- [ ] Every Evidence row is filled in, and the chosen model is written into
      `../spec.md` D2 and `.env.example`.
- [ ] Peak RSS < 512 MB.
- [ ] Diagnostic intent accuracy ≥ 80%.
- [ ] README has no instructions pointing at removed endpoints or local model
      weights.
- [ ] The branch `mvp-1` is rebased on `main` with no conflicts. The PR is titled
      `mvp-1 — Lean grounded core`, links `specs/mvp/mvp-1-lean-core/`, and
      summarizes the Evidence table.
