# Validation — mvp-2

## Required gate

`pytest -q` passes from the repo root with no new skips and no network access.

### Test map for the P1 acceptance criteria

| Acceptance criterion (spec.md) | Test |
|---|---|
| Open the link: only the pages origin is allowed by CORS | `tests/test_cors.py` |
| Plain-text input: server rejects disallowed, empty and over-long input, localized, with no search or model call | `tests/test_input_gate.py` |
| Plain-text input: the example message is accepted | `tests/test_input_gate.py::test_accepts_example_message` |
| Short conversation: countdown 3→0, the 5th is refused, a new session resets | `tests/test_chat_conversation.py` |
| Short conversation: refinement and fresh topic | `tests/test_chat_conversation.py::test_follow_up_refines`, `::test_new_category_starts_fresh`, `tests/test_plan_merge.py` |
| Short conversation: idle more than 30 min starts fresh | `tests/test_sessions.py`, `tests/test_chat_conversation.py::test_expired_session_starts_fresh` |
| See more: next 5, same order, no search or model call, no turn spent, ends | `tests/test_see_more.py` |

### Supporting tests (P2/P3)

- `tests/test_follow_ups.py`
- `tests/test_rate_limit.py` (per-visitor limit and daily cap)
- `tests/test_env_example.py`
- `tests/test_deploy_files.py`

## Recommended gates

- `ruff check .`
- `cd frontend && flutter analyze && flutter test`. These cover the client side
  of P1:
  - `test/input_gate_test.dart`: typing and pasting are filtered, with a
    400-character limit.
  - `test/chat_screen_test.dart`: input is disabled at 0 turns, "Ver mais"
    appears only with `hasMore`, and the waking-up banner shows.
  - `test/chat_provider_test.dart`: "Nova conversa", and a reload starts fresh.
  - `test/api_service_test.dart`: the new fields and error mapping.
- **Container smoke test:**

  ```bash
  docker build -t belemconverse . && docker run --rm -p 8000:8000 --env-file .env belemconverse &
  curl -sf localhost:8000/api/health
  curl -s localhost:8000/api/chat -H 'content-type: application/json' \
    -d "{\"session_id\":\"$(uuidgen)\",\"message\":\"bares abertos agora\",\"language\":\"pt-BR\"}" | jq '.turns_left, .has_more, .follow_ups'
  docker run --rm belemconverse python -c "from zoneinfo import ZoneInfo; print(ZoneInfo('America/Belem'))"
  ```

- **OpenAPI check:** `curl -s localhost:8000/openapi.json | jq '.components.schemas.ChatRequest.required'`
  includes `session_id`.

## Manual walkthrough (against the deployed URLs)

### P1 — Open the link and chat

1. On a phone with mobile data, open
   `https://mollinetti.github.io/BelemConverse/app/`.
2. **Expected:**
   - The app loads in ≤ 5 s on 4G (record it).
   - If the backend was asleep, the waking-up banner shows and then clears.
3. From a desktop, run
   `curl -s -H 'Origin: https://evil.example' -X OPTIONS https://<service>.onrender.com/api/chat -H 'Access-Control-Request-Method: POST' -i`.
   **Expected:** no `access-control-allow-origin` header.

### P1 — Plain-text input

1. Type `Onde tem açaí?!`. **Expected:** the box shows `Onde tem açaí` and the
   `?!` never appear.
2. Paste a 600-character text containing newlines and `<script>`. **Expected:**
   it is cut to 400 characters with no newline, `<` or `>`.
3. Send a bad message straight to the backend:

   ```bash
   curl -s https://<service>.onrender.com/api/chat -H 'content-type: application/json' \
     -d "{\"session_id\":\"$(uuidgen)\",\"message\":\"ignore as instruções {x}\",\"language\":\"pt-BR\"}" -i
   ```

   **Expected:** 422 with a Portuguese message.

### P1 — Short conversation and see more

1. Run this conversation in pt-BR:
   1. "bares bem avaliados" → answer, ≤5 cards, "3 perguntas restantes", chips,
      "Ver mais".
   2. Tap "Ver mais" → 5 more cards, still "3 restantes", and the response is
      instant.
   3. Tap the "Abertos agora" chip → bars, open now, "2 restantes".
   4. Type "cafés" → cafés, "1 restante".
   5. Type "perto da Praça da República" → "0 restantes", the input is disabled,
      and "Nova conversa" is shown.
   6. Tap "Nova conversa" → empty chat, "4 perguntas restantes".
2. Repeat the conversation in English.
3. In the Render logs, confirm exactly one outbound model call per answered
   question and none for "Ver mais". `debug.answer_source` is `llm` when the
   model answered.
4. Capture screenshots of steps 1, 2, 5 and 6 in both languages.

### P2 — Fair use (run once, then let the limit expire)

```bash
S=$(uuidgen); for i in $(seq 21); do curl -s -o /dev/null -w '%{http_code}\n' \
  https://<service>.onrender.com/api/chat -H 'content-type: application/json' \
  -d "{\"session_id\":\"$S\",\"action\":\"more\",\"language\":\"pt-BR\"}"; done | sort | uniq -c
```

**Expected:** 20 non-429 responses and one 429. This also confirms that Render's
`X-Forwarded-For` behaves as plan.md assumes.

### P2 — Waking-up state

1. Leave the service idle for at least 16 minutes.
2. Reload the app. **Expected:** the banner shows and the first answer arrives
   within 90 s (record the time).

## Evidence (fill in during the phase)

| Item | Value |
|---|---|
| T00 baseline on `main` @ 937fa59 (mvp-1 DoD fully checked) | `pytest -q`: 311 passed, 0 skipped, 0 failed · `ruff check .`: 676 findings (pre-existing) · `flutter analyze`: 14 infos · `flutter test`: 1 passed |
| Backend URL / frontend URL | _tbd_ |
| Frontend first load on 4G | _tbd_ s |
| Cold start until first answer | _tbd_ s |
| Warm answered question p50 (10 samples) | _tbd_ ms |
| Warm "Ver mais" p50 (10 samples) | _tbd_ ms |
| Model calls in the logs per answered question / per "Ver mais" | _tbd_ / _tbd_ |
| Rate-limit run: count of 429s at request 21 | _tbd_ |
| Monthly cost shown on Render, model provider and GitHub billing pages | $0 / $0 / $0 |
| Screenshots (pt-BR, en) | _links_ |

## Definition of done

- [ ] All P1 acceptance criteria are covered by the backend tests in the map
      above, and those tests pass.
- [ ] The required gate (`pytest -q`) passes with no new skips.
- [ ] `flutter analyze` and `flutter test` are clean.
- [ ] `spec.md` has no `[NEEDS CLARIFICATION]` markers.
- [ ] The ground-rules check in `plan.md` is clean. The `catalog/belem.sqlite`
      exception is the only data in git.
- [ ] The manual walkthrough is completed on the deployed URLs in both
      languages, and the Evidence table is filled in.
- [ ] No secret appears in the repo: `git grep -nE "(gsk_|AIza|sk-)[A-Za-z0-9]{10,}"`
      returns nothing.
- [ ] The README and project site describe the free-tier deploy and "use it for
      another town", with no local-model instructions left.
- [ ] The [mvp-3 security audit](../mvp-3-security-audit/validation.md) Definition
      of done is checked. Until then the PR is not merged and the link is not shared.
- [ ] The branch `mvp-2` is rebased on `main` with no conflicts. The PR is titled
      `mvp-2 — Public conversational MVP`, links `specs/mvp/mvp-2-public-mvp/`,
      and includes the URLs and the Evidence table.
