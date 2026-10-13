# Tasks — mvp-3

## Conventions

- **IDs** are T00, T01, and so on. Finding IDs are K01–K14 (spec.md) and F01
  onward for new scan findings.
- **`[P]`** means the task can run in parallel with any other `[P]` task in the
  same section.
- **`→ depends on`** lists hard dependencies.
- **Strict TDD for fixes.** Every fix task is preceded by a failing-test task.
  The test names cited in `validation.md` are binding.
- **Commits** start with `mvp-3:`.
- **Redaction.** Scanner output stays in `out/`, which is git-ignored. Anything
  copied into `findings.md`, a commit or a PR is a file, line and rule ID only.
  It never includes a secret value or fragment.
- **🛑 marks a stop.** Work halts until the owner gives an explicit go-ahead in
  the conversation.

## Start

- **T00.** Set up the phase:
  - Confirm mvp-2 T22 (local container build) passes.
  - Cut `mvp-3` from `mvp-2` and record `pytest -q` as the baseline.
  - Add `specs/mvp/mvp-3-security-audit/out/` to `.gitignore`.
  - Re-check spec.md Step 0 for new advisories (trivy, gitleaks or the skills).
- **T01 [P] Early secret sweep of `main`.** Run the history and working-tree
  gitleaks and trufflehog scans from plan.md on the current repo. A **live**
  secret is Critical: jump to T13 straight away and rotate the key first. Record
  the results in `findings.md`.
- **T02 [P] Protect secrets during the audit (K09).**
  - Add `.claude/settings.json` with the `.env` deny rules, plus `.cursorignore`
    and `.gitleaks.toml`.
  - Check it: start a new Claude Code session and ask it to read `.env`. The
    read is refused. Ask it to read `.env.example`. That read works.
- **T03 Install and pin the tools.**
  - Install the CLI scanners, with trivy outside v0.69.4–0.69.6 and its
    checksum verified.
  - Vet and install the third-party skills (plan.md vetting steps), then install
    `claude-security`.
  - Record every version and SHA in the Evidence table.
  - → depends on T02

## Audit (find, don't fix)

- **T04 [P]** Secret scans on the `mvp-3` branch: history, working tree,
  `docs/app/` (if built) and the `belemconverse:audit` image, including the
  in-image `find` for `.env*`. → depends on T03
- **T05 [P]** Dependency scans: `pip-audit` on the image's `pip freeze`,
  `osv-scanner` on `frontend/pubspec.lock`, and `trivy image`. → depends on T03
- **T06 [P]** Static scans: `ruff check --select S .`, ToB
  `/static-analysis:semgrep-scan`, `/insecure-defaults:audit` and
  `sharp-edges`. → depends on T03
- **T07 [P]** LLM-assisted review:
  - `/claude-security` across the whole repo, with SARIF output to `out/`.
  - `owasp-llm-top10` on `llm.py`, `chat()`, `gate.py` and the prompt template.
  - → depends on T03
- **T08 Triage.**
  - Merge the T04–T07 output and run ToB `fp-check` on it.
  - De-duplicate against K01–K14.
  - Assign a severity per the spec.md rubric and write `findings.md`.
  - Each finding gets one status: `fix`, `verified-gone`, `false-positive`,
    `backlog` or `accepted`.
  - → depends on T04, T05, T06, T07
- **T09 🛑 Review the triage with the owner.** Show the findings table: counts by
  severity, with each Critical and High listed. The owner confirms the set to fix
  in this phase. → depends on T08

## Fix: verify gone (K02, K03, K07)

- **T10 [P]** Write the tests from validation.md for K02, K03 and K07. They
  should **pass** straight away on `mvp-3`. If one fails, the finding is still
  live: write a fix task for it in the next section. → depends on T09

## Fix: Critical and High (TDD)

For each finding marked `fix`, add a failing-test task and an implementation
task to this section. The Known ones are listed here.

- **T11a [P]** Failing tests for K04 in `tests/test_error_handling.py`:
  - A route that raises `RuntimeError("secret-ish /abs/path")` returns 500 with
    `{"detail": "internal_error"}`. The body contains neither the message nor
    `/`.
  - An upstream LLM failure (an `httpx.HTTPError` from the monkeypatched
    `summarize`) still returns a templated answer, and the response body holds
    no provider URL.
  - `ChatResponse.debug` has only the key `answer_source`.
- **T11b** Implement the K04 fix (plan.md). → depends on T11a
- **T12a [P]** Failing tests for K05 and K08 in `tests/test_deploy_files.py`:
  - `.dockerignore` lines include `.env`, `.env.*`, `data/` and `models/`.
  - The `Dockerfile` has a `USER` line that is not root.
- **T12b** Implement them, rebuild `belemconverse:audit` and re-run the in-image
  `.env*` `find`. → depends on T12a
- **T13 K01 history purge, and any leaked-secret purge** (runbook in spec.md):
  1. **Secrets only:** rotate the key at the provider, update Render and the
     local `.env`, and confirm the old key is rejected.
  2. Commit or stash the work in every worktree, then remove
     `.claude/worktrees/*`.
  3. Mirror backup: `git clone --mirror <origin> ../BelemConverse-backup-YYYYMMDD.git`.
  4. On a fresh mirror, run `git filter-repo --invert-paths --path data/ --path
     LLM/src/classifiers/models/`, plus `--replace-text` for any leaked secret.
  5. Verify: `git log --all -- data/` is empty, and gitleaks on `--all` is
     clean.
  6. 🛑 **Owner go-ahead to force-push.**
  7. Force-push every branch and tag. Re-clone the working copy and recreate the
     worktrees.
  8. File the GitHub Support request to clear cached views and pull-request
     refs. Record the residual risk (forks and earlier clones) in
     `findings.md`.
  9. → depends on T09. It may run before or after T10–T12, but the T15 re-scan
     happens after it.

## Fix: Medium where small

- **T14a [P]** Failing test for K06 in `tests/test_model_integrity.py`:
  - Loading the classifier with a pickle whose bytes differ from its `.sha256`
    raises.
  - The real model loads.
  - No code path under `api/` writes into the models directory (inspected via
    a monkeypatched `open` or `Path.write_bytes` during a `/chat` call).
- **T14b** Implement K06. Generate the `.sha256` for the shipped model.
  → depends on T14a
- **T14c [P]** K11: remove `python-multipart` if `pytest -q` and the container
  smoke test pass without it. Otherwise raise its floor. Raise floors for any
  other High or Critical dependency vulnerability from T05.
- **T14d (manual)** K10: enable GitHub Secret scanning, Push protection,
  Dependabot alerts and Private vulnerability reporting. Take a screenshot for
  the Evidence table.

Any other Medium or Low goes to the backlog section of `findings.md`.

## Re-scan and make it repeatable

- **T15** Write `scripts/security_scan.sh` (plan.md). Run it on the fixed
  branch. It exits 0, or every remaining hit is listed in `findings.md` as
  `false-positive` or `accepted` and allowlisted in `.gitleaks.toml`.
  → depends on T10–T14
- **T16** Re-run the LLM review on the fix diff: `/security-review` on the
  `mvp-3` branch. Its findings go back to T08. → depends on T15

## Live checks (Render URL, not yet shared)

- **T17** Deploy `mvp-3` to the Render service, then run the validation.md
  live checks. If the service does not exist yet, create it from `render.yaml`
  as in mvp-2 T23, but don't link it anywhere. The checks:
  - CORS from a foreign origin.
  - A 500-path request.
  - Removed routes.
  - The rate limit is still enforced.
  - → depends on T16

## Wiring & docs

- **T18** Fill in the Evidence table and Definition of done in `validation.md`,
  and finish `findings.md`. Add a short "Security" section to the README: how
  to report a vulnerability and how to run `scripts/security_scan.sh`. Add a
  one-line `SECURITY.md` pointing to GitHub private vulnerability reporting.
  → depends on T17
- **T19** Final gate:
  - `pytest -q` is green and `ruff check .` is clean.
  - The scan script exits 0.
  - Open the PR into `mvp-2`. Its body has the counts only and no secret
    fragments.
  - After it merges, mvp-2 continues with T23–T26 and the link can be shared.
  - → depends on all
