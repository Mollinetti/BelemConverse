# Validation — mvp-3

## Required gate

`pytest -q` passes from the repo root with no new skips and no network access.

### Test map for the P1 acceptance criteria

| Acceptance criterion (spec.md) | Finding | Test |
|---|---|---|
| Errors carry a generic message: no exception text, URL, path or trace | K04 | `tests/test_error_handling.py::test_500_is_generic`, `::test_llm_failure_leaks_no_provider_url`, `::test_debug_only_answer_source` |
| `.dockerignore` excludes `.env*`, `data/`, `models/`; the image runs as non-root | K05, K08 | `tests/test_deploy_files.py::test_dockerignore_excludes_secrets_and_data`, `::test_dockerfile_non_root_user` |
| Nothing writes user questions or prompts to a hardcoded local file | K07 | `tests/test_no_local_paths.py` (`git ls-files '*.py'` contains no `/Users/`) |
| Foreign origin gets no allow-origin header; credentials never allowed | K03 | `tests/test_cors.py::test_foreign_origin_rejected`, `::test_credentials_disabled` |
| `/api/ingest/csv` and `/api/clear-history` don't exist | K02 | `tests/test_removed_routes.py` |
| A tampered model pickle is refused; nothing writes models at runtime | K06 | `tests/test_model_integrity.py` |
| Every new Critical or High (F-IDs) | F… | one named test per fix, added to this table during T08–T14 |

The history purge (K01) and the secret scans can't be pytest checks. They are
covered by the scan gate below.

## Scan gate (required)

Run from the repo root on the final `mvp-3` commit, with the tool versions
recorded in Evidence:

```bash
scripts/security_scan.sh                        # exit 0
gitleaks git --redact --log-opts="--all"        # "no leaks found"
git clone --mirror https://github.com/Mollinetti/BelemConverse.git /tmp/bc-verify.git \
  && git -C /tmp/bc-verify.git log --all --oneline -- data/ | wc -l   # 0 (after K01 push)
docker run --rm --entrypoint sh belemconverse:audit -c \
  'find / -name ".env*" -not -path "/proc/*" 2>/dev/null' | wc -l    # 0
docker run --rm --entrypoint id belemconverse:audit -u                # not 0
trivy image --scanners secret,vuln --severity HIGH,CRITICAL --exit-code 1 belemconverse:audit
```

## Recommended gates

- `ruff check .` and `ruff check --select S .`. Every remaining `S` hit has an
  inline `# noqa: S…` with a reason, or a backlog row in `findings.md`.
- `/security-review` on the `mvp-3` PR diff reports no Critical or High.
- `cd frontend && flutter analyze && flutter test` stays clean (no frontend
  change is expected).

## Manual checks (against the Render service pointed at `mvp-3`, T17)

### Live API

1. CORS from a foreign origin:

   ```bash
   curl -si -X OPTIONS https://<service>.onrender.com/api/chat \
     -H 'Origin: https://evil.example' -H 'Access-Control-Request-Method: POST' \
     | grep -ciE 'access-control-allow-(origin|credentials)'
   ```

   **Expected:** `0`. (Starlette's 400 for a disallowed origin still carries
   `allow-methods` and `allow-headers`, so the check looks only for the two
   headers that grant access.)
2. Removed routes:

   ```bash
   for p in ingest/csv clear-history; do curl -s -o /dev/null -w "$p %{http_code}\n" \
     -X POST https://<service>.onrender.com/api/$p; done
   ```

   **Expected:** 404 or 405 for both.
3. Error body: send a malformed JSON body to `/api/chat`. **Expected:** a 422
   with field errors only, and no Python trace or server path in the body.
4. The rate limit is still enforced: re-run the mvp-2 validation "Fair use"
   loop. **Expected:** one 429 at request 21.
5. In the Render logs, search for `LLM_API_KEY` values and for
   `Authorization`. **Expected:** no matches.

### Audit hygiene

1. A new Claude Code session in the repo refuses to `Read` `.env` and can read
   `.env.example`.
2. `git log -p mvp-2..mvp-3 | gitleaks stdin --redact` is clean: the audit
   commits added no secret.
3. GitHub → Settings → Code security shows Secret scanning, Push protection,
   Dependabot alerts and Private vulnerability reporting **enabled**.

### Repository cleanup (after T19)

```bash
git ls-files -ci --exclude-standard                       # expect: nothing
uvx vulture belem_converse api --min-confidence 80        # expect: only false positives, listed in findings.md
cd frontend && for d in $(sed -n '/^dependencies:/,/^dev_dependencies:/p' pubspec.yaml \
  | grep -oE '^  [a-z_]+:' | tr -d ' :' | grep -v '^flutter$'); do
  grep -rqs "package:$d/" lib || echo "unused: $d"; done   # expect: nothing
```

**Expected:** every C-row in spec.md is removed or has a kept-with-reason
line in `findings.md`; plan.md's reachability check reports no unreachable
module.

## Evidence (fill in during the phase)

| Item | Value |
|---|---|
| Tool versions: gitleaks / trufflehog / osv-scanner / pip-audit / trivy / semgrep / ruff | 8.30.1 / 3.99.7 / 2.7.0 / 2.10.1 / 0.76.1 / 1.182.1 / 0.17.2 |
| Cleanup: candidates removed / kept with a reason; lines, files and Flutter packages removed | C02–C11 removed; C12 kept (README advertises native builds); about 23,600 lines across 44 files (C02's ~1,900 untracked, not deleted); 6 Flutter packages |
| Plugin pins: `claude-security` / ToB skills SHA / `owasp-llm-top10` SHA | none installed: plugin installs can't run from the audit session; a fresh-context review agent and the built-in `/security-review` stood in (findings.md) |
| Findings by severity before fixes (C/H/M/L) | 0 / 2 / 8 / 9 (live on the `mvp-3` cut; K02, K03, K05, K07, K08 were already gone) |
| Findings by severity after fixes, open (C/H/M/L) | 0 / 0 / 2 / 9. The Mediums are F01 (no fix exists) and F08 (backlog). K01's only residue is the two PR refs, accepted by the owner |
| False positives dismissed (count) | 278: 255 gitleaks (untracked Flutter caches), 22 trufflehog, 1 ruff S608 |
| History purge: date, paths removed, backup location, force-push approved by 2026-10-25; paths `data/` and `LLM/src/classifiers/models/`; backup `../BelemConverse-backup-20261025.git`; force-push approved by the owner in the session conversation, 2026-10-25 |
| GitHub Support cache-purge ticket | not filed: owner decision 2026-10-25 (the two PR refs still reach the old commits; accepted as bloat) |
| Keys rotated (provider + date only, no values) | none: no secret was found in history, image, bundle or working tree |
| Dependency vulns High+ open with written reason | 44 Debian OS-package CVEs in the base image, none with a fixed version (F01); 0 Python or Dart |
| `scripts/security_scan.sh` exit code on the final commit | 0 on faf79a7 (re-run on the final commit) |
| Live checks 1–5 pass | against https://belemconverse.onrender.com running `mvp-3`, 2026-10-25: 1 pass (foreign origin: 0 grant headers; the Pages origin is allowed); 2 pass (`ingest/csv`, `clear-history`, `languages`, `places/x` all 404); 3 pass (422 with field errors only); 4 pass (200 for the first 20 requests, 429 from the 21st, `X-RateLimit-Remaining: 0`; a forged `X-Forwarded-For` still gets 429); 5 pass, as reported by the owner after reading the Render logs (all requests 200, nothing flagged). `debug` holds only `answer_source`. |

## Definition of done

- [ ] Repository cleanup: every "Cleanup candidates" row (spec.md) is removed
      or kept with a reason in `findings.md`, the checks above pass, and the
      gates still pass after it.

- [ ] Every P1 acceptance criterion is covered by the tests in the map above or
      by the scan gate, and both pass.
- [ ] The required gate (`pytest -q`) passes with no new skips.
- [ ] `findings.md` lists every finding with a status. No Critical or High is
      open.
- [ ] K01 purge is pushed (with the owner's recorded go-ahead), and a fresh
      mirror clone has no `data/` history.
- [ ] Any secret that was ever exposed has been rotated, and the old key is
      confirmed dead.
- [ ] The manual checks pass, and the Evidence table is filled in. It contains
      no secret values.
- [ ] `spec.md` has no `[NEEDS CLARIFICATION]` markers.
- [ ] The PR `mvp-3 — Security audit of the live MVP` is merged into `main`.
- [ ] **The live service runs the audited code:** the Render blueprint and
      GitHub Pages deploy from `main`, and the T17 checks pass against the live
      URLs.
