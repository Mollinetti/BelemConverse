# Tasks — mvp-2

## Conventions

- **IDs** are T01, T02, and so on.
- **`[P]`** means the task can run in parallel with any other `[P]` task in the
  same section.
- **`→ depends on`** lists hard dependencies.
- **Strict TDD.** Every implementation task is preceded by a failing-test task.
  The test names cited in `validation.md` are binding.
- **Commits** start with `mvp-2:`.
- **Backend API tests** use FastAPI `TestClient`, the mvp-1 `built_catalog`
  fixture, and `llm.summarize` monkeypatched with an `AsyncMock`. A
  `fresh_state` autouse fixture resets `SessionStore`, `RateLimiter` and
  `DailyCap` between tests.
- **Time-dependent units** (sessions, limiter, cap) take an injectable `clock`,
  so there are no sleeps in tests.
- **Flutter tests** use `package:http/testing.dart` `MockClient`, which ships
  with `http`, so there is no new dependency.

## Start

- **T00.** Cut `mvp-2` from `main` after the mvp-1 merge. Confirm the mvp-1
  Definition of done is fully checked. Record `pytest -q` as the baseline.

## Input gate (belem_converse/ + api/)

- **T01 [P]** Write failing tests in `tests/test_input_gate.py`.
  Unit tests on `gate.clean_message`:
  - **Accepted:** `Restaurantes abertos perto da Praça da República, 20:00`,
    `Onde tem açaí?!`, and accented letters `ãçéíóúâêô`.
  - **Rejected:** each of `" ' < > { } [ ] ; / \ @ # $ % & * = + - _ ~ | ^`,
    a newline, a tab, an emoji, 401 letters, `""` and `"   "`.
  - **Normalized:** NFD input (`Belém`) becomes NFC `Belém`, and runs of
    spaces collapse.

  API tests:
  - Bad input to `POST /api/chat` returns 422 with a pt-BR message when
    `language="pt-BR"` and an en message when `language="en"`.
  - The retriever spy and `summarize` are **not called** on 422.
  - A 422 does not consume a turn.
- **T02** Implement `belem_converse/gate.py` and the `ChatRequest` validator;
  `message` becomes optional when `action="more"`. → depends on T01

## Sessions and turn cap

- **T03 [P]** Write failing unit tests in `tests/test_sessions.py`:
  - `get_or_create` returns the same session within the TTL.
  - A new session is returned after `ttl_s` (with an injected clock).
  - The LRU evicts the oldest entry when `max_sessions` is exceeded.
  - A session starts with `turns_used == 0`.
- **T04 [P]** Write failing unit tests in `tests/test_plan_merge.py`:
  - `{"categories":["bar"], "min_rating":4}` + `{"open_now":True}` keeps
    `bar`, `4` and `True`.
  - A new `categories:["cafe"]` returns only the new slots.
  - A new `sort` overrides the old one.
  - `None`, `[]` and `False` values in the new slots do not erase old values.
- **T05 [P]** Write failing API tests in `tests/test_chat_conversation.py`:
  - **Turn countdown:** 4 questions on one `session_id` return
    `turns_left == 3, 2, 1, 0`.
  - **Cap:** the 5th returns 409 with `turns_left == 0` and code
    `conversation_finished`, and `summarize` is not called.
  - **New session:** a new `session_id` gets 4 fresh turns.
  - **Expiry:** after advancing the store clock past 30 min, the same id starts
    fresh.
  - **Refinement:** "bares bem avaliados", then "abertos agora", sends a plan to
    the retriever with category `bar` and `open_now=True` (spy on
    `UnifiedRetriever.retrieve`).
  - **Fresh topic:** a 3rd question, "cafés", sends `cafe` with no `open_now`.
- **T06** Implement `sessions.py` and `plan_merge.py`, and wire them into
  `chat()`. Add `turns_left` to `ChatResponse`. → depends on T02, T03, T04, T05

## Ranked-list cache and "see more"

- **T07 [P]** Write failing API tests in `tests/test_see_more.py`:
  - **Setup:** monkeypatch the catalog loader to return 12 generated restaurant
    dicts with distinct ratings, so the ranked order is known.
  - **Paging:** `action:"more"` returns ids 6–10 in ranked order with
    `has_more == True`. The next `more` returns 11–12 with `has_more == False`.
  - **Free:** `UnifiedRetriever.retrieve` and `summarize` call counts do not
    change across `more` calls, and `turns_left` does not change.
  - **No prior list:** `more` on a session with no previous results returns 409
    with `no_previous_results`.
  - **Speed:** a `more` response takes ≤ 150 ms in the test client. Use a loose
    bound so CI is not flaky.
- **T08** Store `ranked_ids[:30]` and `cursor` in the session, and implement the
  `more` branch. Add `has_more` to `ChatResponse`. → depends on T06, T07

## Follow-ups

- **T09 [P]** Write failing unit tests in `tests/test_follow_ups.py`:
  - Returns 2–3 strings in pt-BR or en.
  - Every string passes `gate.clean_message` (test with every category the city
    profile knows).
  - Skips "Abertos agora" when `open_now` is already set.
  - Includes "Mais perto de mim" only when `has_location`.
  - The sibling category is never the current category.
- **T10** Implement `follow_ups.py`. Add `follow_ups` to `ChatResponse` (empty
  for `more`). → depends on T06, T09
- **T10a** Failing tests in `tests/test_category_retrieval.py` (real catalog),
  then the fixes plan.md lists under `follow_ups.py`: "Açaí", "Sorvete",
  "Sorveterias" and "Ice cream" bring back açaí or ice-cream shops; keywords
  never match inside other words; main-category matches rank first. Each
  category chip brings back its kind of place. → depends on T10

## Nearby search only in Belém

- **T12a** Failing tests in `tests/test_location_outside_city.py`: inside the
  bounds, distances as before; outside (São Paulo), a nearby question gets the
  localized notice, city-wide results with no `distanceKm` (also in what the
  model sees and in "see more"), and no "closest" chip; a non-nearby question
  gets no notice. Then implement in `chat()` per plan.md step 3a.
  → depends on T06, T10

## Fair use

- **T11 [P]** Write failing tests in `tests/test_rate_limit.py`.
  Unit tests on `RateLimiter`:
  - 20 hits are allowed and the 21st is denied.
  - After the window passes (injected clock), a hit is allowed again.

  API tests:
  - The 21st `/api/chat` from `X-Forwarded-For: 1.2.3.4, 10.0.0.1` returns 429
    with code `rate_limited`.
  - A different right-most IP is unaffected.
  - The left-most value is ignored: varying it does not reset the count.

  `DailyCap` tests:
  - With `LLM_DAILY_CAP=2`, the 3rd question gets the template answer and
    HTTP 200, and `summarize`'s HTTP layer is not reached.
  - The counter resets when the city-time-zone date changes (injected clock).
- **T12** Implement `limits.py` and wire it into `chat()` and around
  `summarize`. → depends on T06, T11

## CORS and config

- **T13 [P]** Write failing tests in `tests/test_cors.py`:
  - With `ALLOWED_ORIGINS=https://mollinetti.github.io`, a preflight from that
    origin gets `access-control-allow-origin`, and one from
    `https://evil.example` does not.
  - With the variable unset, `http://localhost:5173` is allowed.
  - `access-control-allow-credentials` is absent.
- **T14 [P]** Write a failing test in `tests/test_env_example.py`:
  - Every environment variable read via `os.getenv` / `os.environ` in `api/` and
    `belem_converse/` (found by grep over the source) is listed in
    `.env.example`.
  - Every key in `render.yaml` `envVars` is in `.env.example`.
- **T15** Implement the CORS config in `api/main.py`. Complete `.env.example`
  and add `render.yaml`. → depends on T13, T14

## Frontend (frontend/)

- **T16 [P]** Write failing tests in `test/input_gate_test.dart`. Applying
  `inputGateFormatters` to a `TextEditingValue`:
  - keeps `Praça da República, 20:00`;
  - keeps `?` and `!`, and strips `"<>{}` and `\n`;
  - truncates at 400 characters.
- **T17 [P]** Write failing tests in `test/api_service_test.dart` (`MockClient`):
  - The request body has `session_id`, plus `action:"more"` when paging.
  - It parses `follow_ups`, `has_more` and `turns_left`.
  - 409 → `ConversationFinished`, 429 → `TooManyRequests`, 422 →
    `InvalidInput`.
  - `newSessionId()` matches the UUID v4 regex, and 1,000 calls are unique.
- **T18 [P]** Write failing tests in `test/chat_provider_test.dart` (a fake
  `ApiService`):
  - **Countdown:** after 4 answers, `turnsLeft == 0` and `canSend == false`.
  - **Nova conversa:** `newConversation()` sets a new `sessionId`, empty
    messages, and `turnsLeft == 4`.
  - **See more:** `seeMore()` appends results without changing `turnsLeft`.
  - **Waking up:** `serverReady` is false until `checkHealth` returns true, and
    polling stops at 90 s (fake async).
  - **Fresh reload:** no history is restored from `SharedPreferences` on
    `initialize()`.
- **T19 [P]** Write failing tests in `test/chat_screen_test.dart` (widget tests
  with a fake provider):
  - Chips render for `followUps`, and "Ver mais" renders only when `hasMore`.
  - Chips render only on the latest assistant message.
  - The input is disabled and "Nova conversa" is visible at `turnsLeft == 0`.
  - The waking-up banner is visible while `!serverReady`.
  - Every empty-state example chip passes `allowedChars`.
  - Replace `test/widget_test.dart`'s title check if it conflicts.
- **T20** Implement the Flutter changes per plan.md:
  - `constants.dart`, `input_gate.dart`, `session_id.dart`, `message.dart`,
    `api_service.dart`, `chat_provider.dart`, `message_bubble.dart` and
    `chat_screen.dart`.
  - Then `flutter analyze` and `flutter test` pass.
  - → depends on T08, T10, T16–T19

## Deploy

- **T21 [P]** Write a failing test in `tests/test_deploy_files.py`:
  - **Dockerfile:** has no `cmake`, `build-essential` or `llama`; it copies
    `catalog/`; its `CMD` uses `$PORT`.
  - **Catalog:** `catalog/belem.sqlite` exists, is tracked (`git ls-files`), and
    `load_places` returns more than 1,000 rows.
  - **Cleanup:** `docker/` and `frontend/Dockerfile` are gone.
  - **Compose:** `docker-compose.yml` has no `models` mount.
- **T22** Implement:
  - Move the catalog to `catalog/` and update `cities/belem.py`.
  - Write the slim `Dockerfile`; simplify `docker-compose.yml`; delete the stub
    files.
  - Build and run locally: `docker build` + `docker run`, then a `curl` health
    check and one `/chat`.
  - Inside the container, check `ZoneInfo('America/Belem')`. Add `tzdata` only
    if that fails.
  - → depends on T15, T21
- **T23** Deploy the backend:
  - Create the Render service from `render.yaml` and enter the secrets in the
    dashboard.
  - Confirm `GET https://<service>.onrender.com/api/health`.
  - → depends on T22
- **T24** Deploy the frontend:
  - `flutter build web --release --base-href /BelemConverse/app/ --dart-define=API_BASE_URL=https://<service>.onrender.com/api`.
  - Copy the build to `docs/app/` and add `docs/.nojekyll`.
  - Confirm GitHub Pages serves `main:/docs`.
  - → depends on T20, T23

## Wiring & docs

- **T25** Rewrite the README sections listed in plan.md, including "Use it for
  another town": a new city profile, `build_catalog --csv`, and the Render and
  Pages steps. Update `docs/index.html` ("Running it yourself" copy and a "Try
  it" link). Remove the stale badges. → depends on T24
- **T26** Final gate:
  - `pytest -q` and `flutter test` are green.
  - `ruff check .` and `flutter analyze` are clean.
  - Complete the manual walkthrough and Evidence in `validation.md`.
  - Open the PR.
  - → depends on all
