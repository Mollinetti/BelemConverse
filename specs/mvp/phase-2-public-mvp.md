# Phase 2 — Public conversational MVP

**Spec**: [spec.md](spec.md) · **Previous**: [phase-1-lean-core.md](phase-1-lean-core.md)

## Goal

Anyone with the link can hold a gated conversation of up to 4 turns, with cached
"see more" and follow-up suggestions. It runs on Render free and GitHub Pages
for $0/month.

## Scope

- **In:** `api/`, `belem_converse/` (session and rate-limit code), `frontend/`,
  `Dockerfile`, `docs/` (Pages app plus site links), `README.md`.
- **Out:** tour building, accounts, analytics, a custom domain.

## Tasks (in order)

### 1. Input gate (spec D5)

- **Server:** Pydantic validator on `ChatRequest.message`.
  - NFC-normalise, then collapse whitespace.
  - Require 1–400 characters.
  - Allow only characters that pass `isalpha()` or `isdigit()`, plus space, `,`,
    `.` and `:`.
  - Return 422 with a pt-BR or en message on failure.
- **Client:**
  - `maxLength: 400`.
  - `FilteringTextInputFormatter.allow(RegExp(r"[\p{L}\p{N} ,.:]", unicode: true))`.
  - Pasted text is filtered the same way.

### 2. Session store and 4-turn cap (spec D6)

- One small module, `belem_converse/core/sessions.py`.
  - An `OrderedDict` keyed by `session_id`, with a 30-minute TTL and an LRU cap
    (e.g. 5,000 sessions).
  - Each session holds `turns_used`, `last_plan`, `ranked_ids` and `cursor`.
- A new message with no category or location inherits those from `last_plan`.
- The 5th answered message returns 409 with `turns_left: 0`.

### 3. Ranked-list cache and `action: "more"` (spec D7)

- Retrieval stores up to 30 ranked ids.
- A `more` request pages forward 5 at a time from the cache, with no retrieval,
  no LLM call and a template answer line.
- It does not use up a turn and it returns `has_more`.

### 4. Follow-up chips (spec D8)

`follow_ups[]` comes from the plan:
- "Ver mais" / "See more", only if `has_more`.
- "Abertos agora" / "Open now".
- "Mais perto" / "Closest".
- "Melhor avaliados" / "Top rated".
- One sibling category.

Chip text must pass the gate. A unit test guarantees this.

### 5. Abuse and quota protection (spec D9)

- In-memory limit per IP: 20 messages per 10 minutes, returning 429. Read the
  client IP from the `X-Forwarded-For` header set by the Render proxy.
- Global daily LLM-call counter with the cap in `LLM_DAILY_CAP`. Past the cap,
  answers use the template.

### 6. Flutter

- `config/constants.dart`:
  - `apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://localhost:8000/api')`.
  - `maxMessageLength = 400`.
- `api_service.dart`: send `session_id` (UUID made once per conversation) and
  `action`; parse `follow_ups`, `has_more` and `turns_left`.
- `message_bubble.dart`: a row of chips under the place cards. "Ver mais" sends
  `action: "more"`.
- `chat_screen.dart`:
  - A `turns_left` hint.
  - At 0, disable input and show a "Nova conversa" button that resets the
    session id.
  - On load, call `GET /api/health`. While it is pending, show "Acordando o
    servidor… (até 1 min)" to cover Render's cold start.
- `flutter analyze` and `flutter test` must pass.

### 7. Deploy

- **Backend image:**
  - `Dockerfile` based on `python:3.12-slim`, without `build-essential` or
    `cmake`.
  - Bake in `places.sqlite` and the classifier pickle.
  - Commit `places.sqlite` at a tracked path such as `catalog/belem.sqlite`,
    since `data/` is gitignored and Render builds from git.
  - Delete the stub `docker/` files.
- **Render free web service**, built from the GitHub repo:
  - Env vars: `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, the optional
    `LLM_FALLBACK_*`, `LLM_DAILY_CAP` and `ALLOWED_ORIGINS`.
  - Health check path: `/api/health`.
- **Frontend:**
  - Build with `flutter build web --release --base-href /BelemConverse/app/ --dart-define=API_BASE_URL=https://<render-app>.onrender.com/api`.
  - Copy the output to `docs/app/`.
  - Link to it from `docs/index.html`.
  - Rebuilding is manual. A GitHub Action can come later if redeploys get
    frequent.
- **CORS:** `ALLOWED_ORIGINS=https://mollinetti.github.io`.

### 8. Docs

- Rewrite these README sections for the MVP: What it does, How it works, Getting
  started, Configuration, API, Running with Docker (becomes "Deploy"), and a new
  "Cost" section.
- Update the "Running it yourself" copy in `docs/index.html`. It currently says
  "local GGUF, no cloud inference".
- Fill in `.env.example` with every variable above.

## Acceptance criteria

- **(pytest) Gate:**
  - Accepts `Restaurantes abertos perto da Praça da República, 20:00`.
  - Rejects `<`, `{`, `"`, `?`, `!`, newline, a 401-character string and an
    empty or whitespace-only message.
- **(pytest) Turn cap:**
  - 4 answered turns succeed.
  - The 5th returns 409 with `turns_left == 0`.
  - A new `session_id` starts over.
- **(pytest) Cache:** `action: "more"` makes zero calls to the retriever and the
  LLM (mocks), does not change `turns_used`, and returns the next 5 ids in
  ranked order. `has_more` turns false at the end of the list.
- **(pytest) Plan inheritance:** "restaurantes no Umarizal" followed by "abertos
  agora" keeps the restaurant category and the Umarizal area.
- **(pytest) Follow-ups:** every chip passes the gate, and "Ver mais" appears only
  when `has_more`.
- **(pytest) Rate limit:** the 21st message from one IP within 10 minutes returns
  429. When the daily LLM cap is reached, the answer is the template and HTTP is
  200.
- **(manual) Public test on a phone browser via the Pages URL:**
  - One pt-BR and one en conversation, each 4 turns, using "Ver mais" and a chip.
  - The browser network tab shows one `/chat` per message.
  - The Render logs show one LLM call per answered turn and none for "more".
- **(manual) Cold start:** after more than 15 minutes idle, the first visit shows
  the waking-up state and then works.

## Verification

```bash
pytest -q
cd frontend && flutter analyze && flutter test
docker build -t belemconverse . && docker run -p 8000:8000 --env-file .env belemconverse
curl -s localhost:8000/api/health
```

Then repeat the manual checks above against the deployed URLs.
