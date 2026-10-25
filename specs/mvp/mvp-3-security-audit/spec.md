# mvp-3 — Security audit of the live MVP

**Status**: approved  ·  **Type**: audit + fix
**Branch**: mvp-3  ·  **Spec dir**: specs/mvp/mvp-3-security-audit/
**Overview**: [../spec.md](../spec.md)  ·  **Previous**: [mvp-2](../mvp-2-public-mvp/spec.md)

## Goal

Show that the live BelemConverse (public since 2026-10-18) leaks nothing and
has no serious hole:

- **No leaked secrets or personal data.** No API key or `.env` content appears
  in git history, the Docker image, the Flutter web bundle, notebooks, logs or
  API responses. No third-party personal data stays in the public git history.
- **No Critical or High vulnerability.** The public API holds up against the
  OWASP Top 10 and the OWASP Top 10 for LLM applications. Every Critical or High
  finding is fixed, with a regression test.
- **Repeatable.** The same scans can be run again with one command before every
  deploy.

This phase was planned as the go-live gate for mvp-2. On 2026-10-18 the owner
merged mvp-2 to `main` first, so it audits a **live** service: the API on
Render and the app on GitHub Pages, both deploying from the `mvp-2` branch.
A Critical finding is fixed and deployed at once, ahead of the rest of the
phase. The service is not essential, so the live Render service may be
pointed at `mvp-3` for the fix-verification checks, and may be down while the
audit runs (owner, 2026-10-18). When this phase merges into `main`, Render
and Pages switch from `mvp-2` to `main`.

## Step 0 — Tooling research (done 2026-10-13)

The phase starts from a survey of Claude Code skills and plugins for security
audits. The decision follows. **Re-check versions and advisories before T00**,
because this landscape changes quickly.

Main conclusion: the Claude skills reason well about code, but none of them
scans git history, built images or the web bundle for secrets. Those need
dedicated CLI scanners, and the skills run alongside them.

| # | Tool | Kind | Used for here | Source |
|---|---|---|---|---|
| 1 | **gitleaks** + **trufflehog** | CLI | Secrets in all git history, the working tree, `docs/app/` and the built image. trufflehog can also check whether a key is live. | [gitleaks](https://github.com/gitleaks/gitleaks), [trufflehog](https://github.com/trufflesecurity/trufflehog) |
| 2 | **`claude-security`** | Official plugin (`claude-plugins-official`) | Scans the whole repo, builds a threat model, checks each finding before reporting it, and writes SARIF output. | [README](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/claude-security) |
| 3 | **Trail of Bits `trailofbits/skills`**: `insecure-defaults`, `static-analysis`, `sharp-edges`, `fp-check` | Third-party plugins | Fallback secrets, permissive CORS, debug leaks, Semgrep/CodeQL runs, dangerous APIs (`pickle`), and filtering false positives. | [repo](https://github.com/trailofbits/skills) |
| 4 | **osv-scanner**, **pip-audit**, **trivy**, plus bandit's checks via ruff `S` rules | CLI | Python and Dart dependencies, image packages, Python static analysis. ruff is already installed, so there is no separate bandit. | [osv-scanner](https://google.github.io/osv-scanner/), [pip-audit](https://github.com/pypa/pip-audit), [trivy](https://trivy.dev), [ruff S](https://docs.astral.sh/ruff/rules/#flake8-bandit-s) |
| 5 | **`owasp-llm-top10`** (mastepanoski/claude-skills) | Third-party skill | Prompt-injection and data-leak paths in the chat and LLM code. | [repo](https://github.com/mastepanoski/claude-skills) |
| 6 | **`/security-review`** (built in), **`security-guidance`** (official) | Built in / official plugin | Reviews each later PR's diff. Not a whole-repo audit: `/security-review` only sees the branch diff. | [docs](https://code.claude.com/docs/en/commands), [README](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/security-guidance) |

Considered and not used:
- **The `anthropics/claude-code-security-review` Action.** There is no CI. It
  also only sees the files a PR changes, and its own README says it is not
  hardened against prompt injection.
- **Partner plugins (SonarQube, Aikido, Semgrep, StackHawk).** They need vendor
  accounts.
- **Other community OWASP skills.** Unverified quality.

Supply-chain cautions:
- Third-party plugins run with your permissions. Read each plugin's `SKILL.md`
  and scripts, and pin it to a commit SHA, before using it (plan.md).
- **trivy** had a supply-chain compromise in March 2026: v0.69.4–0.69.6 were
  malicious (CVE-2026-33634). Use a release from outside that range and verify
  its checksum.
- **gitleaks** is in maintenance mode. If it stops working, use **betterleaks**,
  its maintainer's successor.

## User stories (prioritized)

- **P1 — No secret anywhere.** As the showcase owner, I want proof that no API
  key or `.env` content is in any commit, image, bundle or response. A public
  repo and a public URL must not hand out my free LLM quota.
- **P1 — No third-party personal data in public history.** As the repository
  owner, I want the scraped Google reviewer names and phone numbers removed
  from every branch's history, so that publishing the repo does not republish
  other people's data.
- **P1 — Public API is safe to expose.** As the showcase owner, I want the
  deployed API to have no Critical or High OWASP or OWASP LLM finding, so that
  opening it to anyone does not open the server to anyone.
- **P1 — Fixes stay fixed.** As a maintainer, I want every Critical and High fix
  covered by a pytest, so that a later change cannot quietly bring it back.
- **P2 — Dependencies triaged.** As a maintainer, I want every known
  vulnerability in the Python, Dart and image dependencies either fixed or
  recorded with a reason, so that nothing known ships unseen.
- **P2 — Repeatable in one command.** As a maintainer, I want one script that
  re-runs the secret, dependency and static scans, so that the audit can be
  repeated before every deploy.
- **P3 — Lean public repository.** As the repository owner, I want the
  public repo to hold only what builds, runs, tests or documents the current
  product, so that a visitor sees the real project and nothing stale (dead
  code, abandoned experiments, generated output) widens what the audit has to
  cover.
- **P3 — Findings on record.** As a reader of the repository, I want a findings
  report with severity, status and fix commit, and a backlog for what was
  deferred, so that the security state is visible.

## Acceptance criteria

### No secret anywhere (P1)

- **Given** the full history of every branch, **When** gitleaks and trufflehog
  scan it, **Then** there are 0 findings, or each one is a documented false
  positive or a key that has been rotated and purged.
- **Given** the built Docker image, **When** trufflehog and trivy scan it,
  **Then** there are 0 secret findings, and the image contains no `.env*` file.
- **Given** `.dockerignore`, **When** it is read, **Then** it excludes `.env*`,
  `data/` and `models/`. A future `COPY . .` could then not bake them in.
- **Given** the built Flutter web bundle (`docs/app/`), **When** gitleaks scans
  it, **Then** there are 0 findings. The only backend reference is the public
  Render URL.
- **Given** any HTTP error from the API, including an upstream LLM failure,
  **When** the response is read, **Then** it carries a generic message and code.
  It has no exception text, provider URL, file path or stack trace.
- **Given** the tracked source and tests, **When** they are searched, **Then**
  nothing writes user questions or prompts to a hardcoded local file such as
  `/Users/…/.cursor/debug.log`.

### No third-party personal data in public history (P1)

- **Given** every branch and tag on `origin` after the purge, **When**
  `git log --all -- data/` is run on a fresh clone, **Then** it is empty.
- **Given** the purge, **When** it is force-pushed, **Then** that happens only
  after the owner gives an explicit go-ahead (runbook below).

### Public API is safe to expose (P1)

- **Given** a browser request from a foreign origin, **When** it reaches the
  API, **Then** no `access-control-allow-origin` header is returned, and
  credentials are never allowed.
- **Given** the routes, **When** `/api/ingest/csv` or `/api/clear-history` is
  called, **Then** it returns 404 or 405, because the routes no longer exist.
- **Given** the TF-IDF model pickle, **When** its bytes differ from the SHA-256
  recorded at build time, **Then** the app refuses to load it. Model files are
  never written at runtime.
- **Given** `claude-security` and the OWASP LLM review, **When** they run on the
  `mvp-3` branch, **Then** every Critical or High finding is fixed or shown to
  be a false positive.

### Fixes stay fixed (P1)

- **Given** any finding fixed in this phase, **When** `pytest -q` runs, **Then**
  a named test fails if the fix is reverted (see the test map in validation.md).

### Dependencies triaged (P2)

- **Given** the Python dependencies, `frontend/pubspec.lock` and the image,
  **When** osv-scanner, pip-audit and trivy run, **Then** no High or Critical
  vulnerability is open unless `findings.md` records why it is not reachable.

### Repeatable in one command (P2)

- **Given** a clean checkout with the tools installed, **When**
  `scripts/security_scan.sh` runs, **Then** it runs the secret, dependency and
  static scans with redacted output. It exits non-zero on any new finding.

### Lean public repository (P3)

- **Given** the `mvp-3` branch after the cleanup (T18–T19), **When** the
  analysis in plan.md is re-run, **Then**:
  - no module under `belem_converse/` or `api/` is unreachable from the entry
    points (the API and the three `tools/` CLIs);
  - `git ls-files -ci --exclude-standard` lists nothing (no tracked file is
    also ignored);
  - every Flutter package in `frontend/pubspec.yaml` is imported somewhere.
- **Given** each candidate in "Cleanup candidates" below, **When** the phase
  ends, **Then** it is removed, or kept with a one-line reason in
  `findings.md`.
- **Given** the cleanup, **When** `pytest -q`, `flutter test` and the container
  smoke test run, **Then** they pass. Tests are removed only together with the
  dead code they exercise.

### Findings on record (P3)

- **Given** the end of the phase, **When** `findings.md` is read, **Then** every
  finding has an ID, severity, tool, location, status, and a fix commit or
  backlog reason.

## Severity rubric and fix rule

| Severity | Meaning here | Rule |
|---|---|---|
| Critical | A secret is exposed now, or code can be run remotely on the public service | Fix and deploy at once, ahead of the rest of the phase. |
| High | One plausible mistake or request exposes a secret or personal data, or the API gives a stranger write access or data they should not see | Fix in phase, with a test, and deploy when the phase merges. |
| Medium | Defence-in-depth gap or information disclosure with limited impact | Goes to the backlog in `findings.md`. Fix in phase only if the fix is small and an existing test covers it. |
| Low | Hardening or hygiene | Goes to the backlog. |

## Known findings (pre-audit scan of `main`, 2026-10-13)

A read-only scan before drafting this phase found the items below. The audit
must confirm or close each one. Many disappear with mvp-1 and mvp-2; those are
marked "verify gone" and only need a test proving they stay gone.

| ID | Sev. | Finding | Where (on `main`) | Expected status on `mvp-3` |
|---|---|---|---|---|
| K01 | High | Third-party personal data (reviewer names, phone numbers) in pushed history | `data/Raw/dataset_crawler-google-places_*.csv`, commits bfc971c and 89e6e82, on `origin/main`, `old` and `phase-1` | Purge (runbook) |
| K02 | High | Path traversal write and delete, with no auth and no size limit | `POST /api/ingest/csv`, `api/routes.py:390-406` | Verify gone (mvp-1 D4) |
| K03 | High | CORS `*` with `allow_credentials=True` | `api/main.py:55-61` | Verify gone (mvp-2) |
| K04 | High | Raw exception text in HTTP `detail`, absolute paths in responses, and a `debug` block in every chat response | `api/routes.py:87,163,257,296,403,426`; mvp-1 `routes.py:187,224` | Fix |
| K05 | High | `.dockerignore` does not exclude `.env*`, `data/` or `models/` | `.dockerignore` | Fix |
| K06 | Medium | `pickle.load` with no integrity check, and the model dir is rewritten at runtime | `belem_converse/classifiers/intent_classifier_TFIDF_simple.py:691,705` | Fix: SHA-256 check and load only |
| K07 | Medium | User question and full prompt appended to a hardcoded local `debug.log` | `belem_converse/core/enhanced_rag_agent.py:485-516`, `tests/test_prompt_leakage.py`, `tests/test_two_stage_retrieval.py` | Verify gone |
| K08 | Medium | Container runs as root and ships `build-essential` and `git` | `Dockerfile` | Fix if small, else backlog |
| K09 | Medium | AI coding agents (Claude Code, Cursor) can read the live `.env`, and scanner output can echo keys into transcripts | the working tree | Fix: deny rules, redacted scans |
| K10 | Medium | No secret scanning or push protection on the GitHub repo | repo settings | Enable (manual) |
| K11 | Medium | Python dependencies unpinned (`>=` floors only), no lockfile; `python-multipart>=0.0.9` has known DoS CVEs | `requirements.txt`, `pyproject.toml` | Triage |
| K12 | Low | `ChatFilters` has no bounds, `placeId` is not validated, an invalid `nowIso` is accepted, and user text is logged at INFO | `api/schemas.py`, `api/routes.py:191,210` | Backlog unless the audit raises it |
| K13 | Low | Notebooks keep saved outputs with server paths. Since mvp-2 `notebooks/` is gitignored and no longer tracked, but earlier commits still contain it; the stray result logs are gitignored and were never tracked | git history (`notebooks/*.ipynb`) | Owner decision at T13: purge with K01 (`--path notebooks/`), or accept |
| K14 | Low | `/docs`, `/redoc` and `/openapi.json` are public | `api/main.py:50-51` | Accept: an open-source demo with a public API, and `/openapi.json` is the contract |

The same scan found no secret ever committed: `.env` was never tracked, and a
key-pattern search across all history returned one false positive, a Google
photo URL. gitleaks and trufflehog must confirm this.

## Cleanup candidates (audit of `mvp-2`, 2026-10-18)

Found by the over-engineering audit after mvp-2 merged: reachability from the
entry points, `vulture`, tracked-but-ignored files and unused Flutter
packages. Lines are at the time of the audit. T18 re-runs the analysis and
T19 applies it (plan.md → Repository cleanup).

| ID | What | Where | Size | Action |
|---|---|---|---|---|
| C01 | Exploratory LangChain/llama.cpp notebooks | `notebooks/` | 6 files, ~6,200 lines | **Done on mvp-2** (gitignored and untracked, files kept locally). History: K13 |
| C02 | Generated diagnostic reports, tracked although `.gitignore` ignores them; every diagnostic run rewrites them | `tests/diagnostics/reports/` | 4 files, ~1,900 lines | Untrack (`git rm --cached`); keep the harness. **Done** |
| C03 | Vector-search and OSM fallback that production never enables (`vector_store` and `osm_client` are always `None`), and the tests that only exercise it | `belem_converse/core/unified_retriever.py`; `tests/test_semantic_search.py` and the OSM cases in `test_error_handling`, `test_retrieval_strategy_selection`, `test_intent_mapping`, `test_e2e_integration`, `test_distance_calculation` | 484 of 1,112 lines, plus ~320 test lines | Delete code and its tests together. **Done**: also dropped `osm_triggered` from `RetrievalResult`; `strategy_used` stays (the API logs it) |
| C04 | Unreachable module | `belem_converse/ingest/data_merger.py` | 459 lines | Delete. **Done** |
| C05 | Unused utilities: Bayesian ranker, exception classes, old Llama prompt templates and a second Belém bounding box | `belem_converse/utils/bayesian_ranking.py`, `exceptions.py`, most of `config.py` | ~500 lines | Delete; keep `BASE_DIR` and `DATA_DIR`. **Done**: `utils/__init__.py` no longer re-exports |
| C06 | Config file nothing reads (Mistral GGUF and Chroma paths) | `config.yaml` | 1 file | Delete. **Done** |
| C07 | Superseded intent-detection spec from another tool | `.kiro/` | 4 files | Delete. **Done** (and the `.dockerignore` line) |
| C08 | One-off reports nothing links to | `docs/frontend-compliance-analysis.md`, `docs/frontend-updates-summary.md`, `docs/README.md` | 3 files | Delete. **Done** |
| C09 | Flutter packages declared but never imported (`permission_handler` still registers a web plugin) | `frontend/pubspec.yaml`: `cupertino_icons`, `permission_handler`, `flutter_map`, `latlong2`, `intl`, `flutter_localizations`, and `generate: true` with no translations | 6 deps | Remove. **Done**: `flutter analyze`, `flutter test` and `flutter build web` pass |
| C10 | Unused methods (vulture) | `PlaceCache.get_by_title/invalidate/reload/get_count`, classifier `predict/force_retrain`, `csv_ingestion.ingest_csv/get_places_index`, `osm_fetcher.fetch_by_category_batch/get_all_categories`, `city_loader.register_city/is_city_available`, `CityConfig.get_parent_category/get_description`, `BusinessHours.get_open_hours_for_day` | ~15 methods | Delete, with any tests that only call them. **Done**, plus 4 found by the T18 re-run with no caller (`CategoryMatcher.get_match_score`, `CityConfig.get_category_terms`, `PlaceMatcher.get_match_summary`, `BusinessHours.get_hours_for_day`) and `PlaceCache`'s title indexes, which only `get_by_title` read |
| C11 | API surface no client uses: the `coordinates` request field, `GET /api/languages`, `GET /api/places/{id}`, and health's `llm_loaded`/`vector_store_loaded` (always false). Overlaps K12 (`placeId` is not validated) | `api/` | — | Remove; update the README API table. It is the public contract, so it goes in its own commit. **Done**; `get_system_status` went with the health fields |
| C12 | Android and iOS scaffolds; mvp-2 ships only the web client | `frontend/android/`, `frontend/ios/` | ~90 files | Owner decision (2026-10-25): **keep**. The README advertises native builds |

T18 re-run on `mvp-3` (2026-10-25): `scripts/reachability.py` listed only C04;
`git ls-files -ci --exclude-standard` listed only C02; the Flutter check found
the C09 set. `latlong2` was missed by the old check's `[a-z_]+` pattern, which
skips digits. The check now uses `[a-z_0-9]+`.

**Kept on purpose:** `tests/` (the required gate, cited by this spec and by
mvp-2's validation.md; `.dockerignore` already keeps it out of the image),
`specs/`, `catalog/belem.sqlite` (the image needs it), `docs/app/` (what Pages
serves). `.cursor/` and `.claude/` were untracked on 2026-10-25 (owner decision):
they stay on disk, git-ignored; the overview spec still names the `feature-spec` skill.

## Secret and personal-data runbook

When a live secret or personal data is found in git history:

1. **Rotate first** (secrets only). Revoke the key at the provider, put the new
   key in Render and the local `.env`, and confirm the old key is rejected.
2. **Purge.** On a fresh mirror clone, run `git filter-repo` (paths or
   `--replace-text`). This covers every branch and tag, including the unpushed
   `mvp-1`/`mvp-2` branches. Before starting, commit or stash the work in every
   worktree and remove the worktrees.
3. **Verify locally.** gitleaks on `--all`, plus `git log --all -- <path>`,
   returns nothing.
4. **Stop and ask the owner.** No force-push happens without their explicit
   go-ahead.
5. **Force-push** all branches and tags. Re-clone every working copy.
6. **Ask GitHub to finish the job.** GitHub keeps cached views and pull-request
   refs, so request removal through GitHub Support. Forks and clones made before
   the purge cannot be recalled; record that in `findings.md`.

## Success metrics

| Metric | Target |
|---|---|
| Unrotated secrets in history, image, bundle or working-tree scans | 0 |
| Third-party personal data in `origin` history | 0 paths |
| Open Critical / High findings | 0 / 0 |
| Critical or High fixes without a regression test | 0 |
| Open High or Critical dependency vulnerabilities without a written reason | 0 |
| Commands needed to re-run every scan | 1 |
| Added cost | $0 (free and open-source tools only) |
| Modules unreachable from the entry points, after cleanup | 0 |
| Tracked files that `.gitignore` ignores, after cleanup | 0 |

## Out of scope

- Pentesting the Render, GitHub Pages or LLM provider infrastructure.
- Load or DoS testing. The mvp-2 rate limit and daily cap are checked only for
  being present and correct.
- WAF, CAPTCHA, user auth.
- Paid or account-bound scanners (SonarQube, Aikido, Snyk, StackHawk).
- A CI pipeline. The scan script is written so that a CI job can call it later.

## Open questions

None. Decisions made by the owner on 2026-10-13:

- **Scope:** audit, then fix Critical and High in this phase. Medium and Low go
  to the backlog.
- **Timing:** this phase gates mvp-2 go-live. A quick secret sweep of `main` runs
  first (T01). *Superseded on 2026-10-18, see below.*
- **Skills:** Anthropic-official tools plus vetted third-party skills, each
  pinned to a reviewed commit.
- **Leaked secret:** rotate, then rewrite history. Force-push only after an
  explicit go-ahead.
- **Personal data in history:** purge from every branch with the same runbook.

Decided by the owner on 2026-10-18:

- **mvp-2 went live first.** It merged to `main` before this audit. mvp-3
  branches from `main`, audits the live service and merges into `main`; then
  the Render blueprint and GitHub Pages move from `mvp-2` to `main`.

- **Repository cleanup** joins this phase as its last work (T18–T19), driven
  by the "Cleanup candidates" table. `notebooks/` was already untracked on
  mvp-2.

## Branch, commit and PR convention

- **Branch:** `mvp-3`, cut from `main` (mvp-2 merged there on 2026-10-18).
  Merge into `main`, then switch the Render blueprint and GitHub Pages from
  `mvp-2` to `main`. The history purge (K01) is a repo-wide operation outside
  any branch; run it at a quiet point when no branch has uncommitted work. It
  rewrites `main` and `mvp-2`, which Render and Pages deploy from, so both
  redeploy after the force-push.
- **Commits:** every commit starts with `mvp-3:`.
- **PR title:** `mvp-3 — Security audit of the live MVP`.
- **PR body:** links `specs/mvp/mvp-3-security-audit/`, summarizes
  `findings.md` (counts by severity and status) and the Evidence table, and
  includes **no secret values, even redacted fragments**.
