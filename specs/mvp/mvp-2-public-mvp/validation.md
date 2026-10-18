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
- `tests/test_category_retrieval.py` (açaí, ice cream and restaurant questions
  on the real catalog)
- `tests/test_location_outside_city.py` (nearby search only inside Belém)
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

1. Type `Onde tem açaí?! "já"`. **Expected:** the box shows
   `Onde tem açaí?! já`: `?` and `!` stay, the quotes never appear.
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

### P2 — Nearby search only in Belém

```bash
curl -s https://<service>.onrender.com/api/chat -H 'content-type: application/json' \
  -d "{\"session_id\":\"$(uuidgen)\",\"message\":\"bares perto de mim\",\"language\":\"pt-BR\",\"userLocation\":{\"lat\":-23.55,\"lng\":-46.63}}" \
  | jq '.answer[:90], [.results[].distanceKm], .debug.location_outside_city'
```

**Expected:** the answer starts with "A busca por proximidade só funciona em
Belém…", every `distanceKm` is `null`, and `location_outside_city` is `true`.
The same call with `{"lat":-1.4527,"lng":-48.4914}` returns distances.

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
| Backend URL / frontend URL | https://belemconverse.onrender.com · https://mollinetti.github.io/BelemConverse/app/ (Pages temporarily serves `mvp-2:/docs` until the merge) |
| Frontend first load on 4G | **3.8 s** median of 5 (3.6–4.6 s): Chrome "Fast 4G" throttling (9 Mbps / 60 ms), cold cache, 390×844, until the input field exists; 2.89 MB on the wire. Was 10.6 s before the flag emoji (0.7 MB color-emoji font) was replaced by PT/EN |
| Cold start until first answer | **39.4 s** after 20 idle minutes (target ≤ 90 s): the waking-up banner showed at 2.7 s ([cold-banner.png](evidence/cold-banner.png)), the server answered `/api/health` at 33.9 s, and the first question was answered by the model at 39.4 s ([cold-answer.png](evidence/cold-answer.png)) |
| Warm answered question p50 (10 samples) | **4,102 ms** round trip from Tokyo (3,414–10,308); 9 model answers, 1 template after the 10 s budget. Misses the 3 s target: the Google primary takes ~3–4 s (15.7 s once during the phase); Groq answered the same prompt in 0.3 s |
| Warm "Ver mais" p50 (10 samples) | **253 ms** round trip from Tokyo (185–497). An empty `/api/health` round trip is 225 ms from here (Cloudflare NRT → Render), so "Ver mais" itself adds ~30 ms; in the container it took 2 ms |
| Model calls in the logs per answered question / per "Ver mais" | 1 / 0 by `debug.answer_source` (`llm` or `template` per question, `see_more` per page; a question makes a second provider request only when the primary times out). Render log check: _pending (owner)_ |
| Nearby search outside Belém (live) | São Paulo location + "bares perto de mim": answer opens "A busca por proximidade só funciona em Belém…", all `distanceKm` null, no "Mais perto de mim" chip, `location_outside_city: true`, question counted (3 left); the English note likewise. Praça da República location: distances 0.32–0.43 km, `location_outside_city: false` |
| Rate-limit run: count of 429s at request 21 | **1** (20 allowed, the 21st is 429 `rate_limited`, `X-RateLimit-Remaining: 0`); a forged `X-Forwarded-For` is still 429. Needed `TRUSTED_PROXY_HOPS=3`: Render's header is `visitor, Cloudflare edge, Render proxy`, the last two changing per request (the plan's right-most entry limited nobody) |
| Monthly cost shown on Render, model provider and GitHub billing pages | $0 / $0 / $0 expected (free plan, free tiers, public repo). Billing pages: _pending (owner)_ |
| Manual walkthrough (pt-BR and en) | Pass, scripted with Playwright on the live URLs: typing `Onde tem açaí?! "já" <b>{x}` leaves `Onde tem açaí?! já bx`; questions count 3 → 2 → 1 → 0; "Ver mais" keeps the count (126–178 ms); the "Abertos agora" chip refines the bars; "cafés" starts fresh (chips then offer Açaí); at 0 the input is disabled and "Nova conversa" restarts with 4. Found and fixed on the way: chips were announced as checkboxes, then lost keyboard focus. Known limit: "perto da Praça da República" sorts by the visitor's location, not the landmark's, so with no location it returns places anywhere in Belém (landmark geocoding is out of scope) |
| Screenshots (pt-BR, en) | [evidence/](evidence/): steps 1, 2, 5 and 6 of the walkthrough in each language, plus the cold start (scripted with Playwright on the live URLs, 390×844). The en screenshots predate the PT/EN button and still show the flag |

## Definition of done

- [x] All P1 acceptance criteria are covered by the backend tests in the map
      above, and those tests pass.
- [x] The required gate (`pytest -q`) passes with no new skips. (540 passed, 0
      skipped; `ruff check .` is clean too.)
- [x] `flutter analyze` and `flutter test` are clean. (No issues; 30 passed.)
- [x] `spec.md` has no `[NEEDS CLARIFICATION]` markers.
- [x] The ground-rules check in `plan.md` is clean. The `catalog/belem.sqlite`
      exception is the only data in git (the classifier pickle is mvp-1's model
      artifact, pinned by its own version test).
- [x] The manual walkthrough is completed on the deployed URLs in both
      languages, and the Evidence table is filled in. (Two rows await the
      owner: the Render log check and the billing pages. Two targets are missed
      and recorded: answered p50 4.1 s vs 3 s, and "Ver mais" 253 ms vs 150 ms
      round trip from Tokyo, ~30 ms of it server-side.)
- [x] No secret appears in the repo: `git grep -nE "(gsk_|AIza|sk-)[A-Za-z0-9]{10,}"`
      returns nothing.
- [x] The README and project site describe the free-tier deploy and "use it for
      another town", with no local-model instructions left.
- [ ] The [mvp-3 security audit](../mvp-3-security-audit/validation.md) Definition
      of done is checked. Until then the PR is not merged and the link is not shared.
- [x] The branch `mvp-2` is rebased on `main` with no conflicts. The PR is titled
      `mvp-2 — Public conversational MVP`, links `specs/mvp/mvp-2-public-mvp/`,
      and includes the URLs and the Evidence table. ([#2](https://github.com/Mollinetti/BelemConverse/pull/2),
      a draft until the mvp-3 audit.)
