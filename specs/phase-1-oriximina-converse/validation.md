# Validation — phase-1 Oriximiná Converse

## Required gates
- `pytest` passes from the repo root with no new skips. New tests cover
  every P1 acceptance criterion in `spec.md`:
  - **Stakeholder demo lookup (P1)** → `tests/test_oriximina_refresh.py`
    (T01, T03, T05) and `tests/test_oriximina_smoke.py` (T11).
  - **Local branding (P1)** → `frontend/test/branding_test.dart` (T07);
    Flutter tests are recommended (see below) but the *string-only*
    invariant ("no `'Belém'` / `'BelemConverse'` in user-facing text on
    the initial screens") MUST also be expressible as a `pytest` smoke
    that greps the Dart sources for known user-visible literals if the
    Flutter toolchain is unavailable in CI. Add such a pytest under
    `tests/test_oriximina_branding.py` if needed.

## Recommended (per surface touched)

- **Python (`belem_converse/`, ingestion changes from T02 / T04 / T06):**
  - `ruff check belem_converse api`
  - `mypy belem_converse api`

- **Frontend (`frontend/` from T08 / T10):**
  - `cd frontend && flutter analyze`
  - `cd frontend && flutter test` (executes `branding_test.dart`)

- **Data pipeline:** smoke-rebuild against the curated CSV by running the
  documented command from T13:
  ```
  python -m belem_converse.tools.refresh_oriximina
  ```
  Then verify:
  1. `data/canonical_places.jsonl` was rewritten and contains only
     records with `source_csv = oriximina_places_formatted.csv`.
  2. `data/chroma_db/` was rewritten and a sample retrieval for a known
     Oriximiná place returns that place.

- **OpenAPI:** no diff expected against `docs/spec/05-openapi.yaml`.
  Capture this by running `git diff main -- docs/spec/05-openapi.yaml` and
  confirming empty output (Constitution VIII).

## Manual walkthrough

For each P1 story, perform these steps with the demo build running.

### P1 — Stakeholder demo lookup
1. Check out `phase-1`, run `python -m belem_converse.tools.refresh_oriximina`.
2. Start the API: `uvicorn api.main:app --reload --port 8000`.
3. Start the Flutter client and pose a Portuguese query about a place that
   exists in `data/Filtered/oriximina_places_formatted.csv` (e.g., a known
   restaurant from that CSV).
4. **Expected:** answer is grounded; the cited places visibly correspond
   to entries in the Oriximiná CSV; no Belém-only place appears.
5. Pose a Belém-only query (e.g., a Belém neighborhood name).
6. **Expected:** the system returns the standard "no result / out-of-scope"
   response per the existing LLM contract; it does not invent an Oriximiná
   match.
7. Capture screenshots of both flows.

### P1 — Local branding
1. With the Flutter client open on the chat screen:
   - **Expected:** app/window title reads "Oriximiná Converse".
   - **Expected:** chat header reads "Oriximiná Converse".
   - **Expected:** welcome copy reads "Bem-vindo ao Oriximiná Converse!"
     (PT) and the subtitle references "Oriximiná, Pará".
2. Toggle UI language to English.
   - **Expected:** "Welcome to Oriximiná Converse!" and the EN subtitle
     references "Oriximiná, Pará".
3. Open the about dialog.
   - **Expected:** `applicationName` reads "Oriximiná Converse" and the
     body references "Oriximiná, Pará".
4. Capture screenshots in both languages.

### P2 — English parity
1. Repeat the P1 lookup walkthrough in English.
2. **Expected:** same Oriximiná-only grounding behavior; English answer.

### P2 — Reproducible demo build
1. From a clean checkout of `phase-1`, run the single command from T13.
2. **Expected:** command exits 0; `canonical_places.jsonl` and
   `chroma_db/` are produced in the expected location; the smoke
   retrieval test passes.

### P3 — No regression on `main`
1. `git checkout main && pytest`.
2. **Expected:** all tests pass; nothing on `main` was modified by work
   authored on `phase-1`.

## Known limitations to call out at the demo
- Default device coordinates and the "is in city area" geofence in
  `frontend/lib/services/location_service.dart` still target Belém. The
  "use my location" path may behave oddly outside the Oriximiná region.
  This is intentional for the demo (see `plan.md` Risks).
- Internal Python package name (`belem_converse`), env var prefix
  (`BELEM_*`), and internal Dart class names (e.g., `BelemConverseApp`)
  are unchanged. They are not user-visible.

## Definition of done
- [ ] All P1 acceptance criteria verified by automated `pytest` tests
      (T01–T11 implemented, passing).
- [ ] Required gate (`pytest` from repo root) passes with no new skips.
- [ ] `spec.md` has no `[NEEDS CLARIFICATION]` markers.
- [ ] Constitution check is clean — no exception section needed in
      `spec.md` (verify Constitution II surface count is ≤ 3).
- [ ] No diff against `docs/spec/` (especially `05-openapi.yaml`) — verify
      with `git diff main -- docs/spec/`.
- [ ] No tracked diff for `data/canonical_places.jsonl` or
      `data/chroma_db/` (Constitution X).
- [ ] `README.md` updated with a small `phase-1` Oriximiná demo subsection
      (T13).
- [ ] All commits on this branch use the `phase-1:` prefix; the PR title
      (if a PR is opened) is `phase-1 — Oriximiná Converse` and the body
      links to `specs/phase-1-oriximina-converse/`.
- [ ] Branch is rebased on `main` with no merge conflicts at the time the
      demo build is cut. (Note: the spec is explicit that this branch is
      not merged into `main`.)
