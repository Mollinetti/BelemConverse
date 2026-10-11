# Tasks — phase-1 Oriximiná Converse

Conventions:
- IDs: T01, T02, …
- `[P]` = parallelizable with any other `[P]` task at the same level.
- `→ depends on T0X` lists hard dependencies.
- TDD discipline: every implementation task is preceded by a failing-test
  task on the same area of code (Constitution IV).
- All commits start with `phase-1:` (Constitution XII).

## Library / ingestion (`belem_converse/`)

- **T01 [P]** Write failing pytest:
  `tests/test_oriximina_refresh.py::test_refresh_oriximina_uses_only_oriximina_csv`.
  Spins up the soon-to-exist `refresh_oriximina` entry point against a
  small fixture CSV (copied or trimmed from
  `data/Filtered/oriximina_places_formatted.csv`) under `tests/fixtures/`,
  runs ingestion into a `tmp_path` data dir, and asserts:
    1. The produced `canonical_places.jsonl` is non-empty.
    2. Every record's provenance points to the Oriximiná CSV (field name
       resolved in T03; placeholder assertion is fine until T03 lands).

- **T02** Implement `belem_converse/tools/refresh_oriximina.py` as a thin
  wrapper around the existing ingestion stack
  (`belem_converse/ingest/csv_ingestion.py`,
  `belem_converse/ingest/data_merger.py`,
  `belem_converse/ingest/vector_store.py`) that:
    1. Hard-codes the source CSV to
       `data/Filtered/oriximina_places_formatted.csv`.
    2. Performs a clean rebuild of `canonical_places.jsonl` and
       `chroma_db/` (no merge with any other CSV).
    3. Accepts `--data-dir` and `--csv-path` overrides for testability.
  → depends on T01

- **T03 [P]** Write failing pytest:
  `tests/test_oriximina_refresh.py::test_canonical_record_has_source_csv_field`.
  Using the same fixture-driven ingestion as T01, assert each emitted
  canonical record exposes a `source_csv` (or already-existing equivalent
  provenance) field equal to `oriximina_places_formatted.csv`.

- **T04** If the existing canonical schema lacks per-record CSV provenance,
  add a minimal additive `source_csv` field in
  `belem_converse/ingest/csv_ingestion.py` (or the closest existing point
  in the ingestion path), populated with the basename of the source CSV.
  Do not rename or remove any existing field. → depends on T03

- **T05 [P]** Write failing pytest:
  `tests/test_oriximina_refresh.py::test_no_belem_csv_rows_after_oriximina_refresh`.
  After running `refresh_oriximina` against the Oriximiná fixture, assert
  no canonical record has a `source_csv` matching any Belém CSV name from
  `data/Filtered/` (e.g., `restaurantes_Belem_ROI.csv`,
  `cafes_belem_ROI_formatted.csv`, etc.).

- **T06** Verify T02's clean-rebuild semantics actually clear any prior
  Belém artefact in the target data dir before writing
  (`canonical_places.jsonl` and Chroma persistent dir). Make T05 pass.
  → depends on T02, T04, T05

## Frontend (`frontend/`)

- **T07 [P]** Write failing Flutter widget test
  `frontend/test/branding_test.dart::app_title_and_chat_header_are_oriximina_converse`.
  Pumps the app and asserts:
    1. `MaterialApp.title` (or its rendered equivalent in tests) equals
       `'Oriximiná Converse'`.
    2. The chat screen header text is `'Oriximiná Converse'`.
    3. No widget on the initial chat screen renders the substring
       `'Belém'` or `'BelemConverse'` or `'Belem Converse'` in user-facing
       text (search the rendered widget tree).

- **T08** Update user-visible strings in
  `frontend/lib/main.dart` (`MaterialApp.title`),
  `frontend/lib/screens/chat_screen.dart` (header L86, welcome L221–L222,
  subtitle L231–L232 with "Oriximiná, Pará" geographic reframe, example
  chips L249/L255, `applicationName` L383, about-dialog body L399).
  Do NOT rename internal Dart classes (`BelemConverseApp`),
  service-internal methods (`isInBelemArea`), or comments. → depends on T07

- **T09 [P]** Write failing Flutter widget test
  `frontend/test/branding_test.dart::pt_and_en_both_render_oriximina_converse`.
  Toggles language to `pt` and to `en` and asserts the title and header
  read `'Oriximiná Converse'` in both, and that no `'Belém'` /
  `'BelemConverse'` substring appears in the rendered initial screen for
  either language.

- **T10** Adjust EN / PT copy in `chat_screen.dart` so both languages
  satisfy T09 (proper noun "Oriximiná" not translated). → depends on T08, T09

## Data pipeline smoke

- **T11 [P]** Write failing pytest
  `tests/test_oriximina_smoke.py::test_smoke_retrieval_returns_oriximina_place`.
  Using the fixture-driven ingestion from T02, build a small in-memory
  Chroma index and run a known place query (a row that exists in
  `data/Filtered/oriximina_places_formatted.csv`); assert that the
  retriever returns at least one candidate whose `source_csv` field equals
  `oriximina_places_formatted.csv`.

- **T12** Make T11 pass by ensuring `refresh_oriximina` (T02) produces a
  Chroma index whose vectors are queryable through the existing unified
  retriever with no code change to the retriever itself. → depends on T02, T11

## Wiring & docs

- **T13** Add a short "Oriximiná demo build" subsection to `README.md`
  under a clearly marked `phase-1` heading, describing the single command
  to rebuild the catalog (`python -m belem_converse.tools.refresh_oriximina`
  or equivalent) and the expectation that this branch is not merged to
  `main`. Per Constitution XI (Documentation alignment) and Constitution II
  (no broad rewrite of unrelated README sections).

- **T14** Confirm no file under `docs/spec/` is modified on this branch
  (grep diff against `main`). If anything changed, revert it (Constitution
  VII / VIII). No new ADR is created — see `plan.md` "Constitution
  alignment".

- **T15** Verify `data/canonical_places.jsonl` and `data/chroma_db/` are
  not added to git on this branch (Constitution X). Capture as a checklist
  item in `validation.md` definition-of-done; no commit work needed if
  `.gitignore` already covers them.

## Final gate

- **T16** Run the required gate: `pytest` from repo root passes with no
  new skips and all P1 acceptance criteria covered by tests T01–T11.
  → depends on T02, T04, T06, T08, T10, T12
