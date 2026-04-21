# Plan — phase-1 Oriximiná Converse

## Tech context

This phase touches three top-level surfaces — `data/` (corpus only),
`belem_converse/` (one ingestion entry point and a small guard), and
`frontend/` (user-visible strings + app title). Per Constitution II this
is at the limit ("more than three" requires justification); we intentionally
stay at three or fewer. No `api/` change. No `docs/spec/` contract change.

### `data/` (corpus only — no commits)
- **Source CSV (single):** `data/Filtered/oriximina_places_formatted.csv`.
  All other CSVs under `data/Filtered/` and `data/Raw/` are ignored on the
  Oriximiná build.
- **Canonical artefact:** rebuilt `data/canonical_places.jsonl` containing
  only rows derived from the Oriximiná CSV.
- **Vector store:** rebuilt `data/chroma_db/` from that JSONL only.
- **Git:** none of the rebuilt artefacts are committed (Constitution X).
  The CSV stays in `data/Filtered/` exactly as today.

### `belem_converse/` (library)
- **Ingestion entry point:** introduce a single, branch-local one-shot
  script `belem_converse/tools/refresh_oriximina.py` that wraps the existing
  ingestion pipeline (`belem_converse/ingest/csv_ingestion.py`,
  `belem_converse/ingest/data_merger.py`,
  `belem_converse/ingest/vector_store.py`) and forces:
  - `csv_path = data/Filtered/oriximina_places_formatted.csv`
  - a clean rebuild of `canonical_places.jsonl` and `chroma_db/` (no merge
    with any other CSV).
  This avoids modifying `refresh_data.py` (which still serves Belém) and
  keeps the change additive.
- **Retrieval guard (test-only invariant):** add a small assertion-style
  test helper in `tests/` (no production code change) that loads the
  rebuilt `canonical_places.jsonl` and asserts every record has its
  `source_csv` (or equivalent provenance field — exact field name resolved
  during T03/T04) equal to `oriximina_places_formatted.csv`. If the
  ingestion pipeline does not currently record a per-record CSV provenance
  field, add it as a minimal additive field — no rename of existing fields.
- **No change** to planner, retriever, ranker, RAG agent, intent
  classifier, or the LLM contract (Constitution VII).

### `frontend/` (Flutter)
Replace user-visible occurrences of "Belém" / "BelemConverse" / "Belem
Converse" with "Oriximiná" / "Oriximiná Converse" in the screens listed
below. No theme/asset changes; no new state-management layer; no new
routing.

Concrete touch points (from current grep):
- `frontend/lib/main.dart` — `MaterialApp.title` `'BelemConverse'` → `'Oriximiná Converse'`. Class name `BelemConverseApp` is internal (not user-visible) and stays unchanged per Constitution II.
- `frontend/lib/screens/chat_screen.dart`:
  - L86 header `Text('BelemConverse')` → `'Oriximiná Converse'`.
  - L221–L222 welcome line → "Bem-vindo ao Oriximiná Converse!" / "Welcome to Oriximiná Converse!".
  - L231–L232 subtitle → replace "Belém do Pará" with "Oriximiná, Pará" (keeps the geographic framing) and adapt EN copy symmetrically.
  - L249, L255 example chips → replace "Belém" with "Oriximiná".
  - L383 `applicationName: 'BelemConverse'` → `'Oriximiná Converse'`.
  - L399 about-dialog body → replace "Belém do Pará" with "Oriximiná, Pará".
- `frontend/lib/config/constants.dart` L18 — comment-only "Belém center" stays (it documents the lat/long literal). The default coordinates themselves are addressed in the Risks section below.
- `frontend/lib/services/location_service.dart` — comments and method name `isInBelemArea` are internal/code-only, not user-visible. Per Constitution II we do not rename. The runtime semantics (geofence around Belém) are documented as a known limitation in `validation.md`.
- `frontend/lib/services/api_service.dart` — comment-only mention; no user-visible string.

### What stays Belém-named on purpose
- The Python package `belem_converse`, its modules, classes, the FastAPI
  app id, the `BELEM_*` env var names, and internal Dart class names like
  `BelemConverseApp`. Renaming any of these would violate Constitution II
  (Minimal, localized change) and is out of scope for a demo branch.

## Architecture sketch

End-to-end on `phase-1` is identical to `main` except where marked `[*]`:

```
data/Filtered/oriximina_places_formatted.csv  [*]
        │
        ▼
refresh_oriximina.py  [*]   (wraps existing csv_ingestion → data_merger → vector_store)
        │
        ▼
data/canonical_places.jsonl  (rebuilt, Oriximiná-only)  [*]
        │
        ▼
data/chroma_db/  (rebuilt from above only)  [*]
        │
        ▼
unchanged: planner → unified retriever → ranker → RAG agent → /api/chat
        │
        ▼
Flutter UI with rebranded strings  [*]
```

## Data model deltas
- Optional minimal additive field on each canonical record: `source_csv`
  (string, the CSV file name from which the row was ingested). If this
  field already exists in `belem_converse/ingest/csv_ingestion.py` /
  `data_merger.py`, reuse it as-is. If not, add it as an additive,
  optional field — never remove or rename existing fields.
- No change to the documented Place schema in
  `docs/spec/01-domain-model.md`; the field, if added, is an internal
  provenance field and not part of the API response shape.

## API contract deltas
**None.** No route in `api/routes.py` is added, removed, or changed. No
schema in `api/schemas.py` is modified. `docs/spec/05-openapi.yaml` is
not touched. (Constitution VIII satisfied.)

## Risks and trade-offs
- **Default coordinates pin to Belém.** `frontend/lib/config/constants.dart`
  defaults to Belém lat/long, and `location_service.dart` geofences Belém.
  Changing them would expand the blast radius beyond user-visible strings
  and require map/region validation. Decision: **leave defaults unchanged**
  for the demo and document this in `validation.md` so the demo operator
  knows the "use my location" path may behave oddly outside the Oriximiná
  region.
- **Single-CSV catalog is small.** Some user queries the LLM contract is
  trained to handle (e.g., neighborhoods, certain intents) may simply have
  no grounded answer in the Oriximiná corpus. This is acceptable: the
  existing "no result / out-of-scope" path applies. We do **not** disable
  intents (per the user's "exact parity" decision).
- **Provenance field add.** If `source_csv` is not already recorded, adding
  it touches ingestion code. Mitigation: keep the change additive (new
  optional field), with a failing test (T03) preceding the implementation
  (T04) per Constitution IV.
- **Branch hygiene.** This branch must never be merged to `main` without an
  explicit decision; it is a demo fork. Captured as a P3 acceptance
  criterion and reinforced in the PR convention.

## Constitution alignment
- **I. Review-first posture.** Plan defers any change to the planner /
  ranker / LLM contract; only data and visible strings move.
- **II. Minimal, localized change.** Three top-level surfaces touched
  (`data/`, `belem_converse/`, `frontend/`); no public Python or Dart
  interface renamed; the `belem_converse` package keeps its name. Below the
  three-directory threshold that requires extra justification.
- **III. Spec / plan separation.** This document carries all HOW; `spec.md`
  carries WHAT/WHY only.
- **IV. Test-driven, pytest-gated.** `tasks.md` orders failing tests before
  implementation and uses `pytest` as the single required gate.
- **V. Dependency discipline.** No new runtime dependency required.
- **VI. Infrastructure and secrets.** No infra/CI/secrets change.
- **VII. Deterministic retrieval contract.** Pipeline behaviour unchanged;
  only the corpus changes. No ADR required.
- **VIII. Frozen API contract.** No `/api/*` change; OpenAPI not touched.
- **IX. Frontend architecture continuity.** No new state-management or
  routing pattern; only string literals (and one `MaterialApp.title`).
- **X. Data and model artefacts stay out of git.** Rebuilt JSONL and
  Chroma directory remain gitignored.
- **XI. Documentation alignment.** `validation.md` instructs to update
  `README.md` only on this branch (or note the branch in a small section);
  no `docs/spec/` change is needed because no contract changes.
- **XII. Versioning and traceability.** Branch `phase-1`, spec dir
  `specs/phase-1-oriximina-converse/`, commit prefix `phase-1:`.
