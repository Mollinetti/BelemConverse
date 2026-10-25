#!/usr/bin/env bash
# Repeatable secret, dependency and static scans. Run from the repo root; exits
# non-zero on any finding. Output is redacted: gitleaks gets --redact, raw JSON
# stays in the git-ignored out/ directory.
# ponytail: one script, no CI. Add an Action when pushes to main become frequent.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
OUT=specs/mvp/mvp-3-security-audit/out; mkdir -p "$OUT"

echo "== gitleaks: all history";  gitleaks git --redact --log-opts="--all" -c .gitleaks.toml -r "$OUT/gitleaks-history.json" .
echo "== gitleaks: working tree"; gitleaks dir --redact -c .gitleaks.toml -r "$OUT/gitleaks-tree.json" .
[ -d docs/app ] && { echo "== gitleaks: web bundle"; gitleaks dir --redact -r "$OUT/gitleaks-bundle.json" docs/app; }
echo "== ruff S (bandit rules)";  uvx ruff check --select S --exclude tests --output-format concise .
echo "== osv-scanner: pubspec.lock"; osv-scanner scan -L frontend/pubspec.lock
if docker image inspect belemconverse:audit >/dev/null 2>&1; then
  echo "== image: .env* files and user"
  [ -z "$(docker run --rm --entrypoint sh belemconverse:audit -c 'find / -name ".env*" -not -path "/proc/*" 2>/dev/null')" ]
  [ "$(docker run --rm --entrypoint id belemconverse:audit -u)" != 0 ]
  echo "== image: pip-audit"
  docker run --rm --entrypoint pip belemconverse:audit freeze | grep -v '^belem' > "$OUT/image-freeze.txt"
  pip-audit -r "$OUT/image-freeze.txt" --no-deps
  echo "== image: trivy (secrets; HIGH/CRITICAL vulns with a fix)"
  trivy image --scanners vuln,secret --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 belemconverse:audit
fi
echo "security_scan: clean"
