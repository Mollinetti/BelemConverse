# Plan — mvp-2

## Tech context

### api/ (FastAPI)

- **`api/schemas.py`:**
  - `ChatRequest` gains:
    - `session_id: UUID` (required);
    - `action: Literal["more"] | None = None`.
  - `message` becomes `Optional[str]` with `max_length=400`.
  - A `model_validator(mode="after")` does the gate work:
    - requires `message` unless `action == "more"`;
    - runs `gate.clean_message()`, NFC plus whitespace collapse;
    - replaces `message` with the cleaned text;
    - raises a localized `ValueError` (pt-BR or en from `language`), which
      FastAPI turns into 422.
  - `ChatResponse` gains `follow_ups: list[str] = []`, `has_more: bool = False`
    and `turns_left: int`.
  - Drop the legacy `response`, `places` and `source` fields if the Flutter
    parser no longer reads them. `api_service.dart` reads `answer`, then
    `response`, then `message`; update it to `answer` only.
- **`api/routes.py` `chat()`:**
  1. Look up the rate limit by client IP → 429.
  2. `sessions.get_or_create(session_id)`. An expired id gets a new session.
  3. **`action == "more"`:** page from `session.ranked_ids[cursor:cursor+5]`
     through `PlaceCache.get_by_id`, with a template answer line. Return
     without touching the planner, retriever or LLM. If there is no cached list,
     return 409 (`no_previous_results`).
  4. **Turns exhausted:** if `turns_used == 4`, return 409 with
     `{"turns_left": 0}`.
  5. Plan → merge with `session.last_plan` (rule below) → retrieve → keep
     `ranked_ids[:30]` → top 5 → `summarize` behind the daily cap → follow-ups.
  6. `turns_used += 1`, then store `last_plan`, `ranked_ids` and `cursor=5`.

  Validation failures (422) and 429s never consume a turn.
- **`api/main.py`:**
  - `CORSMiddleware(allow_origins=ALLOWED_ORIGINS.split(","), allow_credentials=False, allow_methods=["GET","POST"], allow_headers=["content-type"])`.
  - When `ALLOWED_ORIGINS` is unset (local dev), use
    `allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?"` instead of
    `*`.

### belem_converse/ (library)

All new modules are small single files, and none adds a dependency.

- **`gate.py`:** `ALLOWED_PUNCT = " ,.:"`,
  `clean_message(text: str, max_len=400) -> str`, and the `GateError(ValueError)`
  class with pt-BR and en messages.
- **`sessions.py`:**
  - A `Session` dataclass with `turns_used`, `last_plan`, `ranked_ids`, `cursor`
    and `touched_at`.
  - `SessionStore(ttl_s=1800, max_sessions=5000, clock=time.monotonic)` over an
    `OrderedDict`. `get_or_create()` evicts expired entries and the LRU tail.
  - Mark it with
    `# ponytail: in-process store; one Render instance. Move to a SQLite table if >1 instance.`
  - No lock is needed: the handler does not `await` between read and write of
    the session.
- **`plan_merge.py`** (or a function in `query_planner.py`):
  `merge(prev_slots, new_slots) -> slots`.
  - If `new_slots` has categories, return `new_slots` (fresh topic).
  - Otherwise return `prev_slots` updated with every "set" value from
    `new_slots`. "Set" means not `None`, `[]` or `False`, with one exception:
    `sort` always overrides.
- **`follow_ups.py`:** `build(slots, language, has_location) -> list[str]`.
  - Fixed pt-BR and en strings: "Abertos agora" / "Open now", "Mais perto de
    mim" / "Closest to me", "Melhor avaliados" / "Top rated".
  - A sibling category from a small dict, e.g. restaurant→cafe, bar→restaurant,
    cafe→acai, acai→ice_cream, hotel→restaurant. Category labels come from the
    city profile.
  - Skip any chip whose filter is already applied. Return 2–3 chips.
- **`limits.py`:**
  - `RateLimiter(max_hits=20, window_s=600, clock=…)`: a dict of IP → `deque` of
    timestamps.
  - `DailyCap(cap=int(os.getenv("LLM_DAILY_CAP", 800)))`: a counter reset when
    the date in the city time zone changes. It wraps `llm.summarize`, and once
    the cap is reached it returns `None` without HTTP.
  - Client IP: the **right-most** `X-Forwarded-For` entry (the one appended by
    Render's proxy), else `request.client.host`.
  - Mark it with `# ponytail: per-process memory, resets on restart`.

### frontend/ (Flutter, provider)

No new packages (spec ground rule 2).

- **`lib/config/constants.dart`:**
  - `apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://localhost:8000/api')`.
  - `maxMessageLength = 400`, `maxTurns = 4`.
  - Remove `maxHistoryMessages` and `chatHistoryKey`.
- **`lib/utils/input_gate.dart`:**
  - `final allowedChars = RegExp(r'[\p{L}\p{N} ,.:]', unicode: true);`
  - `final inputGateFormatters = [FilteringTextInputFormatter.allow(allowedChars), LengthLimitingTextInputFormatter(400)];`
- **`lib/utils/session_id.dart`:** `String newSessionId()`, a UUID v4 built from
  `Random.secure()` in about 8 lines. That avoids adding the `uuid` package.
- **`lib/models/message.dart`:** add `followUps`, `hasMore` and `turnsLeft` to
  assistant messages.
- **`lib/services/api_service.dart`:**
  - `sendMessage(..., required String sessionId, String? action)`.
  - Parse the new fields.
  - Map 409 → `ConversationFinished`, 429 → `TooManyRequests` and 422 →
    `InvalidInput` exceptions.
  - Delete `clearHistory()`.
  - Keep `checkHealth()`.
- **`lib/providers/chat_provider.dart`:**
  - State: `sessionId`, `turnsLeft`, and `serverReady`.
  - `initialize()` polls `checkHealth()` every 3 s for up to 90 s. Polling
    instead of a single call is deliberate: Render cold start.
  - `sendMessage`, `seeMore()` and `newConversation()`.
  - Remove `_loadHistory`, `_saveHistory` and the `shared_preferences` history
    use, so a reload starts fresh. `shared_preferences` stays for settings.
- **`lib/widgets/message_bubble.dart`:** under the place cards of the **latest**
  assistant message, a `Wrap` of `ActionChip`s, one per `followUps` entry, plus
  "Ver mais" / "See more" when `hasMore`.
- **`lib/screens/chat_screen.dart`:**
  - `TextField(inputFormatters: inputGateFormatters, maxLength: 400, maxLines: 4, keyboardType: TextInputType.text)`.
    Newlines are filtered out, and Enter sends.
  - A "N perguntas restantes" hint.
  - When `turnsLeft == 0`, the input is disabled and a "Nova conversa" button
    shows.
  - A waking-up banner while `!serverReady`.
  - The existing clear-history action becomes "Nova conversa".
  - Example chips on the empty state must pass the gate. Today's examples
    contain `?`; rewrite them.

### Packaging and deploy

- **Catalog:**
  - `build_catalog --out catalog/` writes `catalog/belem.sqlite`, and
    `cities/belem.py` `catalog_path` points there.
  - Commit it. It is about 3k rows, so a few MB. This is the exception to ground
    rule 5 that the spec already records.
  - `cleaning_report.json` and `osm_report.json` are committed next to it for
    traceability.
- **`Dockerfile`:**

  ```dockerfile
  FROM python:3.12-slim
  WORKDIR /app
  COPY pyproject.toml ./
  COPY api ./api
  COPY belem_converse ./belem_converse
  COPY catalog ./catalog
  RUN pip install --no-cache-dir .
  CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
  ```

  Add `tzdata` to the dependencies only if
  `python -c "from zoneinfo import ZoneInfo; ZoneInfo('America/Belem')"` fails
  inside the image.
- **`render.yaml`** (Render blueprint, about 15 lines):
  - One free `web` service, `runtime: docker`, `healthCheckPath: /api/health`.
  - Env vars: `LLM_BASE_URL`, `LLM_MODEL`, `LLM_FALLBACK_BASE_URL` and
    `LLM_FALLBACK_MODEL` as values; `LLM_API_KEY` and `LLM_FALLBACK_API_KEY` as
    `sync: false` (secrets entered in the dashboard); plus `LLM_DAILY_CAP` and
    `ALLOWED_ORIGINS=https://mollinetti.github.io`.
- **Cleanup:**
  - `docker-compose.yml`: keep a single `api` service with no model mount; drop
    the `web` profile.
  - Delete `frontend/Dockerfile` and the stub `docker/` directory.
- **Frontend hosting:**
  - `flutter build web --release --base-href /BelemConverse/app/ --dart-define=API_BASE_URL=https://<service>.onrender.com/api`.
  - `rm -rf docs/app && cp -r frontend/build/web docs/app`.
  - Add `docs/.nojekyll`.
  - GitHub Pages serves `main:/docs`. Verify that in the repo settings.
- **Docs:**
  - README rewrite: What it does, How it works, Getting started, Configuration,
    API, Deploy (Render + Pages), Cost, Use it for another town.
  - `docs/index.html`: replace the "Running it yourself" copy and add a "Try it"
    link to `app/`.
  - `.env.example` gets every variable.

## Architecture sketch

```
Browser ── https://mollinetti.github.io/BelemConverse/app/  (Flutter web, static)
   │  POST /api/chat {session_id, message|action, language, userLocation?}
   ▼
Render free (Docker) ── FastAPI
   CORS(pages origin) → RateLimiter(ip) → Pydantic gate (422)
   → SessionStore[session_id]
        ├─ action=more → ranked_ids[cursor:+5] → PlaceCache → template line      (0 LLM, 0 retrieval)
        └─ question → turns_used<4 ? (else 409)
              → QueryPlanner → merge(last_plan) → UnifiedRetriever → ranked_ids[:30]
              → top 5 → DailyCap(llm.summarize) → is_grounded ? answer : template
              → follow_ups.build → turns_used+1
   ▼
{answer, results[≤5], follow_ups[], has_more, turns_left}
```

## Data model deltas

- **Session (in memory):** `turns_used: int`, `last_plan: dict`,
  `ranked_ids: list[str]` (≤30), `cursor: int`, `touched_at: float`.
- **Catalog:** unchanged from mvp-1. Only its location moves to the tracked
  `catalog/`.
- **Client:** no persisted chat history anymore.

## API contract deltas

| | Before (mvp-1) | After (mvp-2) |
|---|---|---|
| `ChatRequest.session_id` | none | required UUID |
| `ChatRequest.action` | none | `"more"` or absent |
| `ChatRequest.message` | 1–2000 chars, any | 1–400 chars, letters/digits/space `, . :`; optional when `action="more"` |
| `ChatResponse.follow_ups` | none | `list[str]`, 2–3 items, empty for `more` |
| `ChatResponse.has_more` | none | bool |
| `ChatResponse.turns_left` | none | int 0–4 |
| `ChatResponse` legacy fields | `response`, `places`, `source` | removed |
| Errors | 422 (schema) | 422 gate (localized), 409 `conversation_finished` / `no_previous_results`, 429 `rate_limited` |
| CORS | `*` with credentials | `ALLOWED_ORIGINS` only, no credentials |

## Risks and trade-offs

- **Cold start (about 1 min)** after 15 min idle is inherent to Render free.
  Mitigated by the waking-up banner and health polling. Rejected: a keep-alive
  ping, which is against the free tier's spirit and burns the 750 h/month.
- **In-memory sessions and limits reset** on restart or redeploy. Acceptable for
  a showcase: the worst case is that a visitor gets a fresh 4 turns.
- **X-Forwarded-For spoofing.** Taking the right-most hop trusts only Render's
  proxy. If Render's header behaviour differs, the limiter falls back to the
  socket address, so it is still bounded per proxy IP. Verify once against a
  deploy (validation.md).
- **The gate blocks `?` and `!`,** which users naturally type. The client filters
  them silently while typing. Pasted text loses them, and the hint text explains
  the allowed characters. This was the user's explicit choice.
- **Flutter web bundle size.** CanvasKit is a few MB, so a first load ≤ 5 s on 4G
  is tight. Measure it, and if it misses, try `--wasm`/skwasm or accept and
  record.
- **Committed `docs/app/` build output** makes diffs noisy. It is the price of no
  CI. Upgrade path: a Pages GitHub Action when rebuilds become frequent.
- **The model provider's free tier can change.** The daily cap plus the template
  fallback keep the app working, and switching providers is only an env-var
  change.

## Ground-rules alignment (../spec.md → Ground rules)

1. **pytest gate:** every P1 criterion maps to a backend test. Flutter tests
   cover the client side as a recommended gate.
2. **Dependencies:** no new Python or Dart packages. UUID, the input filter and
   the session store are built from stdlib or the Flutter SDK.
3. **No secrets in git:** the LLM keys are Render `sync: false` env vars and the
   local `.env` only. `render.yaml` holds names, not values.
4. **Untrusted input:** the server-side gate plus the mvp-1 prompt fencing and
   grounding check.
5. **Data out of git:** the exception for `catalog/belem.sqlite` is recorded in
   the overview spec. `data/` and `models/` stay ignored.
