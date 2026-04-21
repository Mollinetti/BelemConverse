# Tech stack — BelemConverse

**Canonical specs:** [PoC charter](../00-poc-charter.md) · [Query planner](../03-query-planner.md) · [Ranking](../04-ranking-spec.md) · [LLM contract](../06-llm-contract.md) · [OpenAPI](../05-openapi.yaml)

## Summary

| Layer | Technology | Role |
|--------|------------|------|
| Client | Flutter (web + mobile targets per UX spec) | Chat UI, location, filters, result cards — [UX spec](../07-ux-flutter.md) |
| API | FastAPI (`/chat`, `/ingest/csv`, health, places) | Query planning, deterministic retrieval, response shaping — [OpenAPI](../05-openapi.yaml) |
| Query understanding | TF-IDF intent classifier (`SimpleTFIDFIntentClassifier`) + planner slots | Intents, categories, open-now signals; keyword fallback if needed — [Query planner](../03-query-planner.md) |
| Retrieval | Deterministic retriever | Haversine distance, radius escalation, open-hours phases, category matching, ranking modes — [Ranking spec](../04-ranking-spec.md) |
| Data | CSV → canonical `Place` (JSONL index) | Ingestion and domain mapping — [CSV mapping](../02-csv-mapping.md), [domain model](../01-domain-model.md) |
| LLM | GGUF instruct model (see LLM contract) | **Summarization only** over curated results — [LLM contract](../06-llm-contract.md) |
| Embeddings (when used) | sentence-transformers / all-mpnet-base-v2 (per contract) | Supporting RAG paths where enabled — [LLM contract](../06-llm-contract.md) |
| Vector store (optional) | Chroma | Metadata / optional fallback retrieval — [ADR-0002](../decisions/ADR-0002-vector-search-fallback.md) |

## Runtime and operations

- **Environment and startup** are described in the [runbook](../10-runbook.md) (e.g. model path, Chroma dir, places JSONL, `ENABLE_VECTOR_FALLBACK`).
- **Vector search** is **off by default** and gated; geo and open-now constraints still apply first when fallback is on — [ADR-0002](../decisions/ADR-0002-vector-search-fallback.md).

## Gaps (prioritized)

### 1. Intent and retrieval (highest priority)

Aligned with product risk: wrong or brittle **query plans** (language, categories, proximity intent, open-now) directly hurt trust for both tourists and locals.

- **Planner + classifier alignment** — Keep TF-IDF categories/keywords, slot extraction, and [filtering precedence](../04-ranking-spec.md) consistent and tested.
- **Evaluation** — Golden queries and regression checks — [eval spec](../09-eval-golden-queries.md).

### 2. Secondary (brief)

- **Data freshness / coverage** — CSV quality and update cadence affect results; not a substitute for fixing planner/retrieval logic.
- **LLM ops** — Load time, latency, and hosting of the GGUF runtime; summarization prompts per [LLM contract](../06-llm-contract.md).
- **Client polish** — i18n, location denial flows, cards — [UX](../07-ux-flutter.md).
- **Production hardening** — Explicitly out of PoC scope unless scope expands — [charter](../00-poc-charter.md).

## Related

- **Demo flow:** [demo script](../11-demo-script.md)
- **Traceability:** [traceability matrix](../../traceability-matrix.md) (if maintained at repo root)
