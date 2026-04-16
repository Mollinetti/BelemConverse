# Traceability Matrix

Requirement → Code Files → Tests mapping for PoC compliance.

## 00-poc-charter.md

| Requirement | Code Files | Tests |
|------------|------------|-------|
| CSV ingestion into canonical Place model | `LLM/src/data/csv_ingestion.py` | `LLM/tests/test_golden_queries.py` |
| Place type inference from categoryName and categories[] | `LLM/src/data/csv_ingestion.py::PlaceTypeInference` | `LLM/tests/test_golden_queries.py` |
| Query understanding: parse user message into Query Plan JSON | `LLM/src/core/query_planner.py` | `LLM/tests/test_golden_queries.py` |
| Deterministic retrieval: geo radius escalation 0.5km → 1km → 2km | `LLM/src/core/deterministic_retriever.py::DeterministicRetriever.retrieve()` | `LLM/tests/test_golden_queries.py` |
| Deterministic retrieval: openNow filtering | `LLM/src/core/deterministic_retriever.py::filter_by_open_now()` | `LLM/tests/test_golden_queries.py` |
| Deterministic retrieval: structured filters | `LLM/src/core/deterministic_retriever.py::is_eligible()` | `LLM/tests/test_golden_queries.py` |
| Deterministic ranking (distance + rating + popularity) | `LLM/src/core/deterministic_retriever.py::rank_candidates()` | `LLM/tests/test_golden_queries.py` |
| API: /chat returns text answer + 5 structured results | `LLM/api/routes.py::chat()` | `LLM/tests/test_golden_queries.py` |
| One-command local run | `docs/spec/10-runbook.md` | - |

## 01-domain-model.md

| Requirement | Code Files | Tests |
|------------|------------|-------|
| Canonical Place entity with all fields | `LLM/src/data/csv_ingestion.py::process_row()` | `LLM/tests/test_golden_queries.py` |
| Place type inference: categoryName first, then categories/0..8 | `LLM/src/data/csv_ingestion.py::PlaceTypeInference.infer_place_type()` | `LLM/tests/test_golden_queries.py` |
| Place type mapping dictionary (restaurant/bar/park/other) | `LLM/src/data/csv_ingestion.py::PlaceTypeInference.TYPE_MAPPINGS` | `LLM/tests/test_golden_queries.py` |
| placeId required, skip if missing | `LLM/src/data/csv_ingestion.py::process_row()` | `LLM/tests/test_golden_queries.py` |

## 02-csv-mapping.md

| Requirement | Code Files | Tests |
|------------|------------|-------|
| Map adressFormatted (typo) → addressFormatted | `LLM/src/data/csv_ingestion.py::process_row()` | - |
| Build categories[] from categories/0..8 + categoryName | `LLM/src/data/csv_ingestion.py::build_categories()` | - |
| Normalize all fields (trim, empty→null, parse numbers) | `LLM/src/data/csv_ingestion.py::normalize_*()` | - |
| Parse isSponsored boolean | `LLM/src/data/csv_ingestion.py::normalize_bool()` | - |
| Output canonical_places.jsonl | `LLM/src/data/csv_ingestion.py::ingest_csv()` | - |
| Output ingestion_report.json | `LLM/src/data/csv_ingestion.py::ingest_csv()` | - |

## 03-query-planner.md

| Requirement | Code Files | Tests |
|------------|------------|-------|
| Output Query Plan JSON schema | `LLM/src/core/query_planner.py::QueryPlan` | `LLM/tests/test_golden_queries.py` |
| Language detection (EN/pt-BR) | `LLM/src/core/query_planner.py::detect_language()` | `LLM/tests/test_golden_queries.py` |
| Intent classification | `LLM/src/core/query_planner.py::classify_intent()` | `LLM/tests/test_golden_queries.py` |
| Extract place_type slots | `LLM/src/core/query_planner.py::extract_place_types()` | `LLM/tests/test_golden_queries.py` |
| Extract categories, city, neighborhood | `LLM/src/core/query_planner.py::extract_*()` | `LLM/tests/test_golden_queries.py` |
| Extract open_now, price_max, min_rating, min_reviews | `LLM/src/core/query_planner.py::extract_*()` | `LLM/tests/test_golden_queries.py` |
| Determine sort_preference (distance/rating/popularity/best_match) | `LLM/src/core/query_planner.py::determine_sort_preference()` | `LLM/tests/test_golden_queries.py` |
| Determine retrieval_strategy | `LLM/src/core/query_planner.py::determine_retrieval_strategy()` | `LLM/tests/test_golden_queries.py` |
| Include debug.detected_signals | `LLM/src/core/query_planner.py::create_query_plan()` | `LLM/tests/test_golden_queries.py` |

## 04-ranking-spec.md

| Requirement | Code Files | Tests |
|------------|------------|-------|
| Candidate eligibility: location.lat/lng required | `LLM/src/core/deterministic_retriever.py::is_eligible()` | `LLM/tests/test_golden_queries.py` |
| Candidate eligibility: place_type, city, neighborhood filters | `LLM/src/core/deterministic_retriever.py::is_eligible()` | `LLM/tests/test_golden_queries.py` |
| Candidate eligibility: price_max, min_rating, min_reviews | `LLM/src/core/deterministic_retriever.py::is_eligible()` | `LLM/tests/test_golden_queries.py` |
| Radius escalation: 0.5km → 1km → 2km | `LLM/src/core/deterministic_retriever.py::retrieve()` | `LLM/tests/test_golden_queries.py` |
| Haversine distance computation | `LLM/src/core/deterministic_retriever.py::haversine_distance()` | `LLM/tests/test_golden_queries.py` |
| OpenNow filtering: two-phase (strict then relaxed) | `LLM/src/core/deterministic_retriever.py::filter_by_open_now()` | `LLM/tests/test_golden_queries.py` |
| Sort mode: distance (distanceKm ASC, tie-breakers) | `LLM/src/core/deterministic_retriever.py::_rank_by_distance()` | `LLM/tests/test_golden_queries.py` |
| Sort mode: rating (totalScore DESC, tie-breakers) | `LLM/src/core/deterministic_retriever.py::_rank_by_rating()` | `LLM/tests/test_golden_queries.py` |
| Sort mode: popularity (reviewsCount DESC, tie-breakers) | `LLM/src/core/deterministic_retriever.py::_rank_by_popularity()` | `LLM/tests/test_golden_queries.py` |
| Sort mode: best_match (composite score) | `LLM/src/core/deterministic_retriever.py::_rank_by_best_match()` | `LLM/tests/test_golden_queries.py` |
| Return exactly 5 results (or fewer) | `LLM/src/core/deterministic_retriever.py::retrieve()` | `LLM/tests/test_golden_queries.py` |
| Output fields: distanceKm, openNowStatus | `LLM/src/core/deterministic_retriever.py::PlaceResult` | `LLM/tests/test_golden_queries.py` |

## 05-openapi.yaml

| Requirement | Code Files | Tests |
|------------|------------|-------|
| /health endpoint | `LLM/api/routes.py::health_check()` | - |
| /ingest/csv endpoint (multipart file upload) | `LLM/api/routes.py::ingest_csv()` | - |
| /places/{placeId} endpoint | `LLM/api/routes.py::get_place()` | - |
| /chat endpoint: request schema (message, language, userLocation, nowIso, filters) | `LLM/api/schemas.py::ChatRequest` | `LLM/tests/test_golden_queries.py` |
| /chat endpoint: response schema (language, answer, results, debug) | `LLM/api/schemas.py::ChatResponse` | `LLM/tests/test_golden_queries.py` |
| Place schema (all fields) | `LLM/api/schemas.py::Place` | - |
| PlaceResult schema (Place + distanceKm + openNowStatus) | `LLM/api/schemas.py::PlaceResult` | - |

## 06-llm-contract.md

| Requirement | Code Files | Tests |
|------------|------------|-------|
| LLM only summarizes provided results | `LLM/api/routes.py::generate_llm_answer()` | `LLM/tests/test_golden_queries.py` |
| System message: "Only use the provided candidates. Do not invent places." | `LLM/src/utils/config.py::TRAVEL_GUIDE_PROMPT_*` | - |
| Empty results: ask clarifying question or suggest widening constraints | `LLM/api/routes.py::generate_llm_answer()` | `LLM/tests/test_golden_queries.py` |
| Bilingual output based on language | `LLM/api/routes.py::generate_llm_answer()` | `LLM/tests/test_golden_queries.py` |
| Mention why each result matches (distance/rating/openNow) | `LLM/api/routes.py::generate_llm_answer()` | - |
| Label unknown openNowStatus clearly | `LLM/api/routes.py::generate_llm_answer()` | - |

## 09-eval-golden-queries.md

| Requirement | Code Files | Tests |
|------------|------------|-------|
| Golden queries test runner | `LLM/tests/test_golden_queries.py` | - |
| Verify Query Plan JSON output | `LLM/tests/test_golden_queries.py::test_query_plan()` | - |
| Verify radius escalation | `LLM/tests/test_golden_queries.py::test_radius_escalation()` | - |
| Verify exactly <=5 results | `LLM/tests/test_golden_queries.py::test_results_count()` | - |
| Verify ranking follows sort mode | `LLM/tests/test_golden_queries.py::test_ranking()` | - |
| Verify LLM only references returned places | `LLM/tests/test_golden_queries.py` (implicit) | - |

## ADR-0002-vector-search-fallback.md

| Requirement | Code Files | Tests |
|------------|------------|-------|
| Vector search NOT used as primary retrieval | `LLM/src/core/deterministic_retriever.py` (primary) | - |
| Vector fallback gated by ENABLE_VECTOR_FALLBACK flag | `LLM/src/core/query_planner.py::determine_retrieval_strategy()` | - |
| Vector fallback only if structured+lexical+radius escalation returns <5 | `LLM/src/core/query_planner.py::determine_retrieval_strategy()` | - |
| Vector fallback only if query contains "vibe" keywords | `LLM/src/core/query_planner.py::determine_retrieval_strategy()` | - |
| Geo and openNow constraints still apply with vector fallback | `LLM/src/core/query_planner.py` (strategy selection) | - |

## Business Hours Parser

| Requirement | Code Files | Tests |
|------------|------------|-------|
| Parse JSON-like weekly structure | `LLM/src/utils/business_hours_parser.py::parse()` | - |
| Parse semicolon-delimited text | `LLM/src/utils/business_hours_parser.py::parse()` | - |
| Parse "Open 24 hours" / "24 horas" | `LLM/src/utils/business_hours_parser.py::parse()` | - |
| Return openNowStatus: "open" | "closed" | "unknown" | `LLM/src/core/deterministic_retriever.py::check_open_now()` | `LLM/tests/test_golden_queries.py` |

## Summary

- **Total Requirements**: ~60+ requirements mapped
- **Code Files**: 8 main implementation files
- **Test Files**: 1 comprehensive test suite (`test_golden_queries.py`)
- **Coverage**: All PoC requirements from specs 00-06, 09, and ADR-0002
