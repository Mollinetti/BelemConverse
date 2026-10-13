# Plan — mvp-3

## Tech context

The audit runs against the `mvp-3` branch, which is cut from `mvp-2` after its
local container builds. By then mvp-1 has removed the agent, `/ingest/csv`,
`/clear-history`, Chroma, torch and llama-cpp. mvp-2 has added the input gate,
sessions, the rate limiter, the daily cap and narrowed CORS. Several Known
findings (spec.md) should already be gone. This phase proves they are gone and
fixes what is left.

### Toolchain

Every tool is free and runs locally, and none is a runtime dependency (ground
rule 2). Install them with Homebrew or `pipx`, record each version in the
Evidence table, and pin it.

| Tool | Install | Notes |
|---|---|---|
| gitleaks | `brew install gitleaks` | Always run with `--redact`. If it breaks, use betterleaks. |
| trufflehog | `brew install trufflehog` | `--results=verified` contacts the provider to check whether a key is live. That is fine for our own keys. Strip raw values from its output: `--json \| jq 'del(.Raw, .RawV2)'`. |
| osv-scanner | `brew install osv-scanner` | `frontend/pubspec.lock` and the image. |
| pip-audit | `pipx install pip-audit` | Run against the packages actually installed in the image (below), because there is no lockfile. |
| trivy | the release binary, with its checksum verified | **Not** v0.69.4–0.69.6 (CVE-2026-33634). |
| semgrep | `pipx install semgrep` | Needed by the ToB `static-analysis` skill. CodeQL is skipped: building its database is heavy for a codebase this small. |
| ruff `S` rules | already installed | bandit's checks, already built into ruff. No separate bandit install. |

### Claude skills and plugins

| Skill | Install | Run |
|---|---|---|
| `claude-security` (official) | `/plugin install claude-security@claude-plugins-official` | `/claude-security`, whole repo, SARIF output to `specs/mvp/mvp-3-security-audit/out/` (git-ignored) |
| ToB `insecure-defaults`, `static-analysis`, `sharp-edges`, `fp-check` | `/plugin marketplace add trailofbits/skills@<sha>`, then `/plugin install <name>@trailofbits` | `/insecure-defaults:audit`, `/static-analysis:semgrep-scan`, then `fp-check` on the merged findings |
| `owasp-llm-top10` | `npx skills add mastepanoski/claude-skills --skill owasp-llm-top10` (pinned) | Point it at `belem_converse/llm.py`, `api/routes.py` `chat()`, `belem_converse/gate.py` and the prompt template |
| `/security-review` (built in) | none | On the `mvp-3` PR diff, as a last check on the fixes themselves |

The exact Trail of Bits install syntax was inferred from the marketplace name.
Confirm it with `/plugin` before relying on it.

**Third-party vetting** (before the first run of each third-party skill):
1. Read `SKILL.md`, every hook and every script in the plugin.
2. Check that nothing sends repository content anywhere except the model, and
   that nothing reads `.env`.
3. Pin it to the commit SHA you reviewed and record the SHA in the Evidence
   table.
4. Run it in a session with the K09 deny rules active.

### Protecting secrets during the audit (K09)

The live `.env` holds working keys, and the audit itself is the most likely way
to leak them: scanner output or an agent's `Read` would put them into a
transcript.
- **`.claude/settings.json`** (new, tracked): `permissions.deny` lists
  `Read(./.env)`, `Read(./.env.*)` and `Bash(cat .env*)`, but not
  `.env.example`. Claude Code then refuses to read it in any session in this
  repo.
- **`.cursorignore`** (new, tracked): `.env*` plus `!.env.example`.
- **`.gitleaks.toml`** (new, tracked): extends the default rules and adds an
  allowlist of paths that are local by design: `.env`, `.venv/`, `data/`,
  `models/`, `graphify-out/` and `.claude/worktrees/`. Directory scans then do
  not report the real `.env`.
- **Rule:** findings are pasted only redacted, and only as file plus rule ID.
  No raw scanner JSON goes into `findings.md`, commits or PRs.

### Scan commands (run in T01–T04, scripted in T15)

```bash
OUT=specs/mvp/mvp-3-security-audit/out; mkdir -p $OUT   # run from the repo root
# Secrets: all branches, all commits
gitleaks git --redact --log-opts="--all" -r $OUT/gitleaks-history.json
trufflehog git file://. --results=verified,unknown --json | jq 'del(.Raw,.RawV2)' > $OUT/th-history.json
# Secrets: working tree and the built web bundle
gitleaks dir --redact -c .gitleaks.toml .
gitleaks dir --redact docs/app
# Secrets and packages: the image
docker build -t belemconverse:audit .
docker run --rm --entrypoint sh belemconverse:audit -c 'find / -name ".env*" -not -path "/proc/*" 2>/dev/null'   # expect no output
trufflehog docker --image belemconverse:audit --results=verified --json | jq 'del(.Raw,.RawV2)'
trivy image --scanners vuln,secret --severity HIGH,CRITICAL belemconverse:audit
# Dependencies
docker run --rm --entrypoint pip belemconverse:audit freeze > $OUT/image-freeze.txt
pip-audit -r $OUT/image-freeze.txt
osv-scanner scan -L frontend/pubspec.lock
# Python static analysis
ruff check --select S .
```

`out/` lives in the spec directory and is git-ignored. It holds raw scan output
for the phase only.

## Fix designs for the Known findings

Each fix starts from a failing test (tasks.md). Fixes use only the stdlib or
packages already installed.

- **K01 — personal data in history.** Run `git filter-repo --invert-paths
  --path data/ --path LLM/src/classifiers/models/` on a fresh `--mirror` clone.
  The second path is the old pickles in history, which go while we are already
  rewriting. Then follow the spec.md runbook.
  - Before running it: every worktree has its work committed (mvp-1 has
    uncommitted changes today), and `.claude/worktrees/*` is removed.
  - Requires `brew install git-filter-repo` and a full backup:
    `git clone --mirror` to a dated folder outside the repo.
  - Purging `data/` also drops any small catalog committed under `data/`. The
    mvp-2 catalog lives in `catalog/`, so it is not affected. Check this.
- **K02, K03, K07 — verify gone.** Each gets a pytest that pins the removal:
  - **K02:** the route table has no `ingest` or `clear-history` path.
  - **K03:** a foreign origin gets no allow-origin header, and
    `allow_credentials` is False. Extend mvp-2's `tests/test_cors.py`.
  - **K07:** `git grep -n "/Users/" -- '*.py'` is empty, run as a test over
    `git ls-files`.
- **K04 — error disclosure.**
  - One `@app.exception_handler(Exception)` in `api/main.py`. It logs the
    exception server-side (`logger.exception`) and returns
    `{"detail": "internal_error"}` with status 500.
  - Every `HTTPException(detail=str(exc))` becomes a fixed code string.
  - Responses carry no filesystem paths.
  - `debug` keeps only `answer_source`, which the mvp-2 walkthrough uses. The
    detected signals and slots are dropped.
  - mvp-1's `tests/test_error_handling.py` already exists. Extend it rather than
    adding a new file.
- **K05 — `.dockerignore`.** Add `.env`, `.env.*`, `!.env.example`, `data/`,
  `models/`, `.venv/`, `notebooks/`, `graphify-out/`, `.claude/` and `.git/`.
  The existing `tests/test_deploy_files.py` asserts these lines are present.
- **K06 — pickle integrity.**
  - The training/save step writes `<model>.pkl.sha256` next to the pickle using
    `hashlib.sha256`.
  - The loader compares hashes before `pickle.load` and raises on a mismatch.
  - Remove the runtime write path (`:691`) from the request path; models are
    built offline only.
  - `# ponytail: hash check, not a signature. Upgrade to signing only if models
    ever come from outside the repo.`
- **K08 — container user.** Add `RUN useradd -r app` and `USER app` after the
  `COPY` in the slim mvp-2 `Dockerfile`. Use a multi-stage build only if
  `build-essential` is still needed at all; mvp-1 removed llama-cpp, so it
  probably is not, and the line can simply go.
- **K09** — as above.
- **K10 — GitHub settings (manual).** Enable Secret scanning, Push protection,
  Dependabot alerts and Private vulnerability reporting under Settings → Code
  security. All are free for public repos.
- **K11 — dependencies.**
  - Remove `python-multipart` if nothing needs it after `/ingest/csv` is gone
    (FastAPI only needs it for form or file parsing). Otherwise raise its floor
    to the first patched release.
  - Any other High or Critical: raise the floor or record why it is not
    reachable.
  - A full lockfile is backlog.
- **K12–K14** go to the backlog in `findings.md` unless a scan raises their
  severity.

New findings from the scans follow the same pattern: a failing test, the
smallest fix, then a re-scan.

## Repeatable scan (`scripts/security_scan.sh`)

- About 30 lines of bash with `set -euo pipefail`.
- Runs the history and working-tree gitleaks scans, the `docs/app` scan,
  `ruff --select S`, `osv-scanner` on `pubspec.lock`, and, if
  `belemconverse:audit` exists, the image checks.
- Exits non-zero on any finding. Prints only redacted output.
- No CI job: there is none yet. A future GitHub Action calls this script.
- `# ponytail: one script, no CI. Add an Action when pushes to main become
  frequent.`

## Outputs

- **`findings.md`** (new in this dir): one table with ID, severity, tool,
  location, status (`fixed`, `verified-gone`, `false-positive`, `backlog`,
  `accepted`), and fix commit or reason. The Known findings K01–K14 are the
  first rows; scan findings continue as F01 onward.
- **Fix commits** prefixed `mvp-3:`. A one-line findings summary goes in the PR
  body.

## Risks and trade-offs

- **History rewrite.** It changes every commit hash. Open PRs, forks, clones
  and local worktrees go stale. Mitigations:
  - Run it once, at a quiet point, after a mirror backup.
  - The force-push needs explicit owner approval.
  - After the push, every clone is re-cloned.
- **GitHub caches.** Cached views and pull-request refs can keep the purged
  blobs reachable by SHA until GitHub Support clears them. Forks made earlier
  keep them for good. These are recorded as residual risk.
- **Third-party skills are code with your permissions.** Mitigated by the
  vetting steps, the SHA pin and the `.env` deny rules.
- **LLM-based scanners produce false positives and miss things.** `fp-check`
  and the manual triage filter out false positives. The deterministic scanners
  (gitleaks, trufflehog, osv, ruff `S`) are the floor, not the skills.
- **trufflehog `--results=verified`** sends any key it finds to that key's
  provider for checking. That is acceptable for our own provider keys. Run it
  without verification if the owner prefers.

## Ground-rules alignment (../spec.md → Ground rules)

1. **pytest gate:** every Critical or High fix and every "verify gone" has a
   named test (validation.md).
2. **Dependencies:** no runtime dependency is added. One may be removed
   (`python-multipart`). The scanners are local dev tools, not project
   dependencies.
3. **No secrets in git:** this phase proves it. The `.env` deny rules and
   redacted output keep the audit itself from leaking them.
4. **Untrusted input:** the OWASP LLM review exercises the gate and prompt
   fencing from mvp-1 and mvp-2.
5. **Data out of git:** K01 enforces this for the past as well, by removing
   `data/` from history.
