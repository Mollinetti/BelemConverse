# phase-1 — Oriximiná Converse (stakeholder demo fork)

**Status**: draft  ·  **Type**: feature
**Branch**: phase-1  ·  **Spec dir**: specs/phase-1-oriximina-converse/

## Goal
Deliver a hard-fork variant of BelemConverse, on the `phase-1` branch only,
that demonstrates the full conversational place-discovery experience to
stakeholders in the city of **Oriximiná (Pará)**. The branch behaves
identically to the Belém build in every respect except (a) its place catalog
is restricted to a single curated CSV and (b) every user-visible occurrence
of "Belém" / "Belem Converse" is replaced with "Oriximiná" / "Oriximiná
Converse". The Belém experience on `main` must remain untouched.

## User stories (prioritized)

- **P1 — Stakeholder demo lookup.** As an Oriximiná stakeholder watching the
  demo, I want to ask the chat about a place in Oriximiná (e.g., a restaurant
  or point of interest) in Portuguese and get a grounded answer that only
  references entities from the demo catalog, so that the demo never surfaces
  Belém-specific places.
- **P1 — Local branding.** As an Oriximiná stakeholder, I want the app's
  title, headings, greetings, and prominent copy to read "Oriximiná
  Converse" / "Oriximiná" (instead of "Belém Converse" / "Belém"), so that
  the product clearly addresses my city.
- **P2 — English parity.** As an English-speaking observer at the demo, I
  want to ask in English and receive an English answer with the same
  Oriximiná-only grounding and the same rebranded copy, so that the
  experience is consistent across the two supported languages.
- **P2 — Reproducible demo build.** As the demo operator, I want a
  documented, single command/runbook step to (re)build the Oriximiná
  catalog and vector index from the curated CSV on this branch, so that I
  can rebuild before the presentation without manual stitching.
- **P3 — No regression on `main`.** As a maintainer, I want `main` (Belém
  build) to continue to pass `pytest` and to retrieve Belém places exactly
  as before, so that the demo branch does not block ongoing Belém work.

## Acceptance criteria

### Stakeholder demo lookup (P1)
- **Given** the Oriximiná build is running and the index is built from
  `data/Filtered/oriximina_places_formatted.csv`,
  **When** a user asks a place-discovery question in Portuguese whose answer
  exists in that CSV,
  **Then** the response cites only entities whose source row is from that
  CSV, and no Belém-only entity appears in the grounded result set.
- **Given** the same setup,
  **When** a user asks about a Belém-only place (e.g., a Belém neighborhood
  or a place that exists only in the Belém CSVs),
  **Then** the answer must not fabricate an Oriximiná match; it must follow
  the existing "no result / out-of-scope" path defined by the LLM contract.

### Local branding (P1)
- **Given** the Oriximiná build of the Flutter client,
  **When** the app starts,
  **Then** the application title, the chat screen header, and any prominent
  greeting copy display "Oriximiná Converse" / "Oriximiná" with no
  user-visible occurrence of "Belém" or "Belem Converse" remaining in the
  default UI flows.
- **Given** the Oriximiná build,
  **When** the user switches the UI language between Portuguese and English,
  **Then** the rebranded strings remain "Oriximiná" / "Oriximiná Converse"
  in both languages (proper noun, not translated).

### English parity (P2)
- **Given** the Oriximiná build with `en` selected,
  **When** the user asks an Oriximiná place question whose answer exists in
  the curated CSV,
  **Then** the grounded answer is returned in English with the same
  Oriximiná-only grounding behavior as the Portuguese flow.

### Reproducible demo build (P2)
- **Given** a clean checkout of the `phase-1` branch,
  **When** the documented "build the Oriximiná demo index" step is executed,
  **Then** the resulting Chroma index contains entries derived from
  `data/Filtered/oriximina_places_formatted.csv` and from no other CSV, and
  a smoke retrieval for a known Oriximiná place returns that place.

### No regression on `main` (P3)
- **Given** `main` is checked out and unchanged by this branch,
  **When** `pytest` is run from the repo root,
  **Then** it passes with the same set of tests as before (no Belém
  acceptance criteria broken by anything authored on `phase-1`).

## Success metrics
- 100% of grounded results during demo queries on `phase-1` come from the
  Oriximiná CSV (verified by an automated test that asserts every place
  returned by the planner/retriever has a `source` traceable to that CSV).
- 0 user-visible occurrences of the substring "Belém" or "Belem Converse"
  in the default Flutter screens of the `phase-1` build (verified by a
  Flutter widget test or a string-grep test, per `plan.md`).
- `pytest` passes from repo root on `phase-1` with all new P1 criteria
  covered by automated tests.
- `main` continues to pass `pytest` after `phase-1` is merged or discarded
  (verified by a clean rebase / no-touch policy on `main`-only files).

## Out of scope
- Any change to the supported intents, planner, ranker, or LLM contract.
- Any change to the FastAPI HTTP contract in `docs/spec/05-openapi.yaml`.
- Logo, color palette, icon, or other visual-asset rebranding (text only).
- Adding or removing supported languages; pt and en remain the only two.
- Multi-city profile selection at runtime (the branch is a hard fork, not a
  city switcher).
- Merging `phase-1` into `main`. This branch is short-lived and exists for
  the stakeholder demo only.
- Deployment, CI/CD, container image publication, or hosted demo URLs.
- Adding new rows to, or otherwise editing, the curated Oriximiná CSV.

## Open questions
None at draft time. The user confirmed: hard-fork on `phase-1`, exact parity
with Belém except data + visible wording, preserve Belém on `main`, demo-only.
The clarifications below are deliberately deferred to `plan.md`:
- Exact mechanism for restricting the index to a single CSV (config flag vs.
  a one-shot rebuild script vs. branch-local default in
  `belem_converse/tools/refresh_data.py`).
- Exact location of the rebrand strings (Flutter constants, theme,
  per-screen literals, i18n ARB files).

## Constitution alignment (preview)
- **II. Minimal, localized change.** The spec is intentionally narrow: data
  source restriction + visible string replacement. No public interface is
  renamed; the `belem_converse` package keeps its name. Plan must show the
  blast radius stays within `data/`, `belem_converse/tools/` (or equivalent
  one-shot script), `frontend/lib/` user-visible strings, and the spec dir.
  If the plan ends up touching more than three top-level directories it
  must justify why.
- **VII. Deterministic retrieval contract.** No change to intent → plan →
  retrieve → rank → summarise. Only the underlying corpus changes.
- **VIII. Frozen API contract.** No `/api/*` change planned;
  `docs/spec/05-openapi.yaml` is not touched.
- **X. Data and model artefacts stay out of git.** The Oriximiná CSV is
  already under `data/Filtered/` (gitignored at runtime per repo policy).
  The branch must not commit `data/canonical_places.jsonl` or
  `data/chroma_db/` rebuilt outputs.
- **XII. Versioning and traceability.** Branch `phase-1`, spec dir
  `specs/phase-1-oriximina-converse/`. All commits on this branch use the
  prefix `phase-1:`; the PR title (if any) is `phase-1 — Oriximiná Converse`.

## Commit / PR convention (binding for this branch)
- Every commit on `phase-1` starts with `phase-1:`.
- PR title (if a PR is opened): `phase-1 — Oriximiná Converse`.
- PR body links to `specs/phase-1-oriximina-converse/` and summarizes the
  validation evidence captured in `validation.md`.
