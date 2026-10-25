# Findings — mvp-3

Audit of `mvp-3` (cut from `main` at 26877da), 2026-10-25. Scanner output stays in
`out/` (git-ignored). This file holds file, line and rule ID only.

## Tool versions

| Tool | Version |
|---|---|
| gitleaks | 8.30.1 |
| trufflehog | 3.99.7 (run with `--no-verification`: no found value left this machine) |
| osv-scanner | 2.7.0 |
| pip-audit | 2.10.1 |
| trivy | 0.76.1 (outside the compromised v0.69.4–0.69.6 range; Homebrew bottle) |
| semgrep | 1.182.1 (`p/python`, `p/owasp-top-ten`, `p/secrets`) |
| ruff | 0.17.2 (`--select S`) |

## Scan results

| Scan | Result |
|---|---|
| gitleaks, all history (103 commits) | 0 findings |
| gitleaks, `docs/app` bundle | 0 findings |
| gitleaks, working tree | 255 hits, all in untracked `frontend/.dart_tool` and `frontend/build` (Flutter caches): false positive |
| trufflehog, all history | 22 unverified hits, all false positives (below) |
| trufflehog, image `belemconverse:audit` | 0 |
| trivy, image (secret + vuln, HIGH/CRITICAL) | 0 secrets; 0 Python vulns; 44 Debian OS-package vulns, none with a fixed version |
| `.env*` anywhere in the image | none; image runs as uid 1000 |
| pip-audit on the image's `pip freeze` | no known vulnerabilities |
| osv-scanner on `frontend/pubspec.lock` | no issues (77 packages) |
| semgrep | 0 results |
| ruff `--select S` (excluding tests) | 3 hits: S104 (F05), S301 (K06), S608 (F06) |

## Findings

| ID | Sev. | Tool | Location | Status | Fix commit or reason |
|---|---|---|---|---|---|
| K01 | High | git, trufflehog | `data/` in commits bfc971c, 89e6e82 (3 commits) on `origin/main`, `mvp-2`, `old`, `phase-1` | fix (purge, owner go-ahead needed) | confirmed live; also 3 commits touch `notebooks/` and 3 touch the old model dir |
| K02 | High | route table | `/api/ingest/csv`, `/api/clear-history` | verified-gone | `tests/test_removed_routes.py` (5981e15); live: both 404 |
| K03 | High | `api/main.py:63-76` | CORS | verified-gone | `tests/test_cors.py::test_foreign_origin_rejected`, `::test_credentials_disabled` already pin it |
| K04 | High | read | `api/routes.py` 221 (`Retriever error: {exc}`), 320 (`Error converting place result: {exc}`), 101/173 (build hint in the detail), 266 (`debug` carries planner signals) | fixed | 4ce2892: one `internal_error` handler, fixed codes, `debug` = `answer_source` only; `test_error_handling.py::test_500_is_generic`, `::test_llm_failure_leaks_no_provider_url`, `::test_debug_only_answer_source`, `::test_catalog_not_loaded_503_gives_no_build_command` |
| K05 | High | `.dockerignore` | | fixed upstream | excluded since mvp-2; `test_deploy_files.py::test_dockerignore_excludes_secrets_and_data` (5981e15) |
| K06 | Medium | ruff S301 | `intent_classifier_TFIDF_simple.py:683` load without a hash, `:669` save, and `api/routes.py:85` calls `train()` at runtime | fixed | 419c956: SHA-256 sidecar checked before `pickle.loads`; `train()` writes nothing unless `save=True`; `tests/test_model_integrity.py` |
| K07 | Medium | grep | local `debug.log` writes | verified-gone | `tests/test_no_local_paths.py` (5981e15) |
| K08 | Medium | Dockerfile | root user | fixed upstream | `useradd` + `USER app`, uid 1000 (mvp-2); `test_deploy_files.py::test_dockerfile_non_root_user` (5981e15) |
| K09 | Medium | | `.env` readable by agents | fixed | commit "T00/T02"; the new-session check must be run by hand |
| K10 | Medium | manual | GitHub settings | open (manual, T14d) | |
| K11 | Medium | pip-audit | `python-multipart` | fixed | 5981e15: removed from `requirements.txt` and `pyproject.toml`; container smoke test passes without it; `test_python_multipart_is_not_a_dependency` |
| K12 | Low | read | `ChatFilters` bounds, `placeId`, `nowIso`, INFO logging of user text | backlog | |
| K13 | Low | git | `notebooks/` in history (3 commits) | accepted | owner decision 2026-10-25: not purged |
| K14 | Low | | `/docs`, `/redoc`, `/openapi.json` public | accepted | open-source demo; `/openapi.json` is the contract |
| F01 | Medium | trivy | 44 Debian OS-package CVEs in `python:3.12-slim` (util-linux, ncurses, systemd, perl-base) | backlog | no fixed version exists; re-scan after the next base-image rebuild |
| F02 | Low | trufflehog | 20 `Miro` hits in `catalog/belem.sqlite` and `data/` history | false-positive | every one starts with `ChIJ`: Google Place IDs, public |
| F03 | Low | trufflehog | 2 `Box` hits in `data/**/*.xlsx` history | false-positive | binary spreadsheet bytes; removed anyway by the K01 purge |
| F04 | Low | gitleaks | 255 hits in `frontend/.dart_tool`, `frontend/build` | false-positive | untracked build caches, not in git or the image |
| F05 | Low | ruff S104 | `api/main.py` binds `0.0.0.0` in the `__main__` dev block | accepted | dev entry point; the container runs uvicorn itself; inline `noqa: S104` |
| F06 | Low | ruff S608 | `tools/build_catalog.py:285` f-string SQL | false-positive | offline tool; the f-string interpolates fixed column names, values are `?` placeholders; inline `noqa: S608` |

| F07 | Medium | LLM review | `limits.py:48-61`, `api/routes.py:149-153` (L01): `client_ip` returns the left-most, client-controlled entry when the chain has fewer entries than `TRUSTED_PROXY_HOPS`, and the key has no length cap | fixed | 5312672: a short chain or a non-address entry uses the socket peer; `test_rate_limit.py::test_fewer_entries_than_hops_uses_the_socket_peer`, `::test_an_entry_that_is_not_an_address_uses_the_socket_peer` |
| F08 | Medium | LLM review | `limits.py:87-95`, `api/routes.py:332` (L02): the daily cap of 800 is global, so one IP at 20 per 10 min drains it in about 7 h; one `take()` can pay for two provider calls | backlog | loses the LLM answer (templated fallback), not unbounded cost |
| F09 | Medium | LLM review | `api/schemas.py:21-28`, `routes.py:202,212,225` (L03): `filters.city`, `neighborhood` and `placeType` have no length limits and no body-size limit; they are kept in `session.last_plan` (5000 sessions) and logged | fixed | 4ce2892: `max_length` on `city`, `neighborhood`, `placeType` and its items; `tests/test_input_limits.py` |
| F10 | Medium | LLM review | `api/routes.py:191,212` (L04): the INFO log holds exact visitor lat/lng and filter strings; `nowIso` is logged raw (log forging with a newline) | fixed | 4ce2892: the log holds intent and slot names; `nowIso` is no longer parsed or logged; `test_logs_hold_no_visitor_location_or_raw_now` |
| F11 | Low | LLM review | `sessions.py`, `schemas.py:32` (L05): the 4-question cap resets with a new client-chosen `session_id`; a flood evicts real sessions | backlog | the real limits are F07 and F08 |
| F12 | Low | LLM review | `llm.py:118-121,183-222` (L06): the question is not fenced; `is_grounded` checks bold names only, not URLs, phone numbers or hours | backlog | asker's own answer only; no tools, `max_tokens` 250; the Flutter client renders plain text |
| F13 | Low | LLM review | `routes.py:339-340`, `llm.py:211` (L07): grounding check folds all 2,901 titles per answer on the event loop | backlog | tens of ms per answer |
| F14 | Low | LLM review | `limits.py:33-35` (L08): the rate-limiter prune keeps every key active in the window, so many source IPs grow the dict | backlog | needs many IPs or F07 |
| F15 | Low | LLM review | `llm.py:99-121` (L09): place text goes into the prompt unescaped | backlog | catalog is trusted; strip `<`, `>`, `**` from titles |
| K04+ | Medium | LLM review | `api/dependencies.py:19`: `BUILD_HINT` in the 503 detail exposed an internal command | fixed | 4ce2892: now logged server-side only |

LLM-assisted review (T07): done by a fresh-context read-only agent in place of
`claude-security` and `owasp-llm-top10`, which are plugin installs that this
session cannot run. It found no Critical or High. It reported no issue in:
system-prompt leakage, excessive agency, secrets in error paths and logs, CORS,
session guessing, or the `turns_used` race. The Medium and Low rows above are its
findings, each re-read by hand before it was written down.

## Re-scan and fix-diff review

- `scripts/security_scan.sh` exits 0 on the fixed branch: gitleaks on all history, the working tree and `docs/app` find nothing; ruff `S` is clean; osv-scanner finds nothing; the image has no `.env*`, runs as uid 1000, passes pip-audit, and trivy finds no secret and no fixable HIGH/CRITICAL (the 44 Debian CVEs have no fix, F01). The working-tree scan allowlists the Flutter caches (F04) and the git-ignored `out/` directory.
- `/security-review` on the `mvp-3` diff against `main` (T16): no findings. It checked the pickle hash (same bytes hashed and unpickled), the generic error handler, the reduced `debug` block, the rate-limit key and the scan script.

## Open

- **K01** (High): the history purge. Prepared, not pushed. Steps 3–5 of the T13 runbook are done and verified (2026-10-25): a mirror backup of `origin`; `git filter-repo --invert-paths --path data/ --path LLM/src/classifiers/models/` on a copy of it; the tip tree of `main` is unchanged; `git log --all -- data/` is empty; gitleaks and trufflehog on the rewritten mirror find nothing. Replaying the same rewrite on a clone of the working repo gives the same `main` (97775ef), so `mvp-3` can be re-synced. Waiting on the owner's go-ahead to force-push (step 6).
- **K10** (Medium): the GitHub settings, by hand.
- **Not run:** the live checks (T17) against Render; the new-session `.env` read check (K09).
