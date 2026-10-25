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
| K02 | High | route table | `/api/ingest/csv`, `/api/clear-history` | verified-gone | `/openapi.json` lists only `/`, `/api/chat`, `/api/health`; test in T10 |
| K03 | High | `api/main.py:63-76` | CORS | verified-gone | `allow_credentials=False`, explicit origins; test in T10 |
| K04 | High | read | `api/routes.py` 221 (`Retriever error: {exc}`), 320 (`Error converting place result: {exc}`), 101/173 (build hint in the detail), 266 (`debug` carries planner signals) | fix | |
| K05 | High | `.dockerignore` | | fixed upstream | `.env`, `.env.*`, `data/`, `models/` are excluded (mvp-2); test in T12 |
| K06 | Medium | ruff S301 | `intent_classifier_TFIDF_simple.py:683` load without a hash, `:669` save, and `api/routes.py:85` calls `train()` at runtime | fix | |
| K07 | Medium | grep | local `debug.log` writes | verified-gone | no `/Users/` in tracked `*.py` except one assertion; test in T10 |
| K08 | Medium | Dockerfile | root user | fixed upstream | `useradd` + `USER app`, uid 1000 (mvp-2) |
| K09 | Medium | | `.env` readable by agents | fixed | commit "T00/T02"; the new-session check must be run by hand |
| K10 | Medium | manual | GitHub settings | open (manual, T14d) | |
| K11 | Medium | pip-audit | `python-multipart` | fix if small | no route uses forms or files; no known vuln in 0.0.32 |
| K12 | Low | read | `ChatFilters` bounds, `placeId`, `nowIso`, INFO logging of user text | backlog | |
| K13 | Low | git | `notebooks/` in history (3 commits) | owner decision at T09 | purge with K01, or accept |
| K14 | Low | | `/docs`, `/redoc`, `/openapi.json` public | accepted | open-source demo; `/openapi.json` is the contract |
| F01 | Medium | trivy | 44 Debian OS-package CVEs in `python:3.12-slim` (util-linux, ncurses, systemd, perl-base) | backlog | no fixed version exists; re-scan after the next base-image rebuild |
| F02 | Low | trufflehog | 20 `Miro` hits in `catalog/belem.sqlite` and `data/` history | false-positive | every one starts with `ChIJ`: Google Place IDs, public |
| F03 | Low | trufflehog | 2 `Box` hits in `data/**/*.xlsx` history | false-positive | binary spreadsheet bytes; removed anyway by the K01 purge |
| F04 | Low | gitleaks | 255 hits in `frontend/.dart_tool`, `frontend/build` | false-positive | untracked build caches, not in git or the image |
| F05 | Low | ruff S104 | `api/main.py:95` binds `0.0.0.0` in the `__main__` dev block | accepted | the container needs it; the Dockerfile uses uvicorn directly |
| F06 | Low | ruff S608 | `tools/build_catalog.py:285` f-string SQL | false-positive | offline tool; the f-string interpolates fixed column names, values are `?` placeholders |

| F07 | Medium | LLM review | `limits.py:48-61`, `api/routes.py:149-153` (L01): `client_ip` returns the left-most, client-controlled entry when the chain has fewer entries than `TRUSTED_PROXY_HOPS`, and the key has no length cap | backlog (small fix proposed: fail closed to the socket peer, cap the key) | verified by reading; holds on Render (3 hops), fails open on any host without the proxy chain |
| F08 | Medium | LLM review | `limits.py:87-95`, `api/routes.py:332` (L02): the daily cap of 800 is global, so one IP at 20 per 10 min drains it in about 7 h; one `take()` can pay for two provider calls | backlog | loses the LLM answer (templated fallback), not unbounded cost |
| F09 | Medium | LLM review | `api/schemas.py:21-28`, `routes.py:202,212,225` (L03): `filters.city`, `neighborhood` and `placeType` have no length limits and no body-size limit; they are kept in `session.last_plan` (5000 sessions) and logged | backlog (small fix proposed: `Field(max_length=…)` on the filters) | verified: no `max_length` on those fields |
| F10 | Medium | LLM review | `api/routes.py:191,212` (L04): the INFO log holds exact visitor lat/lng and filter strings; `nowIso` is logged raw (log forging with a newline) | backlog (small fix proposed: log intent and slot keys; drop the unused `nowIso`) | |
| F11 | Low | LLM review | `sessions.py`, `schemas.py:32` (L05): the 4-question cap resets with a new client-chosen `session_id`; a flood evicts real sessions | backlog | the real limits are F07 and F08 |
| F12 | Low | LLM review | `llm.py:118-121,183-222` (L06): the question is not fenced; `is_grounded` checks bold names only, not URLs, phone numbers or hours | backlog | asker's own answer only; no tools, `max_tokens` 250; the Flutter client renders plain text |
| F13 | Low | LLM review | `routes.py:339-340`, `llm.py:211` (L07): grounding check folds all 2,901 titles per answer on the event loop | backlog | tens of ms per answer |
| F14 | Low | LLM review | `limits.py:33-35` (L08): the rate-limiter prune keeps every key active in the window, so many source IPs grow the dict | backlog | needs many IPs or F07 |
| F15 | Low | LLM review | `llm.py:99-121` (L09): place text goes into the prompt unescaped | backlog | catalog is trusted; strip `<`, `>`, `**` from titles |
| K04+ | | LLM review | `api/dependencies.py:19`: `BUILD_HINT` in the 503 detail exposes an internal command | fix (part of K04) | |

LLM-assisted review (T07): done by a fresh-context read-only agent in place of
`claude-security` and `owasp-llm-top10`, which are plugin installs that this
session cannot run. It found no Critical or High. It reported no issue in:
system-prompt leakage, excessive agency, secrets in error paths and logs, CORS,
session guessing, or the `turns_used` race. The Medium and Low rows above are its
findings, each re-read by hand before it was written down.
