# mvp-2 — Public conversational MVP

**Status**: approved  ·  **Type**: roadmap
**Branch**: mvp-2  ·  **Spec dir**: specs/mvp/mvp-2-public-mvp/
**Overview**: [../spec.md](../spec.md)  ·  **Previous**: [mvp-1](../mvp-1-lean-core/spec.md)  ·  **Audit**: [mvp-3 security audit](../mvp-3-security-audit/spec.md) (after go-live)

## Goal

Anyone with the link can open BelemConverse in a phone or desktop browser and
hold a short, safe conversation about places in Belém:

- **Short.** Up to 4 answered questions, with suggested follow-ups and an
  instant "see more" that costs nothing.
- **Safe.** Input is restricted to plain text, so the assistant cannot be easily
  manipulated, and no single visitor can exhaust the free allowances.

It all runs on free tiers for $0/month. This phase turns the mvp-1 core into the
public showcase.

## User stories (prioritized)

- **P1 — Open the link and chat.** As a visitor, I want to open a public link on
  my phone and start asking right away, with no install or sign-up, so that
  trying the product takes seconds.
- **P1 — Plain-text input.** As the showcase owner, I want the chat box to accept
  only letters, digits, spaces, commas, periods, colons, question marks and
  exclamation marks, up to 400 characters, and the server to enforce the same
  rule. `?` and `!` are allowed because visitors naturally type them; every
  other symbol stays out. That way crafted inputs
  cannot steer the assistant.
- **P1 — Short conversation with memory.** As a visitor, I want up to 4 answered
  questions in one conversation, and a follow-up such as "e abertos agora?" to
  refine my previous question, so that I can narrow down without repeating
  myself.
- **P1 — See more for free.** As a visitor, I want to see the next results from my
  last answer instantly, without spending one of my 4 questions, so that I can
  browse beyond the first five.
- **P2 — Suggested follow-ups.** As a visitor, I want a few one-tap follow-up
  suggestions after each answer, so that I know what else I can ask.
- **P2 — Nearby search only in Belém.** As the showcase owner, I want
  location-based search to work only for visitors who are in Belém, so that
  someone elsewhere is not shown meaningless distances ("4,000 km away") and
  understands why "near me" does not apply to them.
- **P2 — Fair use.** As the showcase owner, I want per-visitor and daily limits,
  so that one visitor or a script cannot use up the free allowances and break
  the demo for everyone.
- **P2 — Waking-up state.** As a visitor arriving after the server has slept, I
  want to see that it is waking up, so that I don't think the site is broken.
- **P3 — Start over.** As a visitor who has used all 4 questions, I want a clear
  "Nova conversa" action, so that I can keep exploring.
- **P3 — Docs match reality.** As a reader of the repository, I want the README
  and project site to describe the hosted, free-tier setup and how to deploy it
  for another town, so that the showcase is reproducible.

## Acceptance criteria

### Open the link and chat (P1)

- **Given** the deployed site, **When** a visitor opens the public link on a
  phone browser, **Then** the chat screen loads without install or login and
  accepts a question.
- **Given** the site is served from the project's public pages origin, **When**
  it calls the backend, **Then** the backend accepts that origin and rejects
  calls from other browser origins.

### Plain-text input (P1)

- **Given** the chat box, **When** a visitor types or pastes quotes, angle
  brackets, braces, brackets, slashes, `;`, `@`, `#`, `*`, `-`, `_` or any
  other symbol, newlines or emoji, **Then** those characters do not appear in
  the box. Letters with Portuguese accents, digits, spaces, `,`, `.`, `:`, `?`
  and `!` do appear.
- **Given** the chat box, **When** the text reaches 400 characters, **Then** no
  more can be typed.
- **Given** a direct call to the backend that bypasses the app, **When** the
  message contains a disallowed character, is empty or whitespace-only, or is
  longer than 400 characters, **Then** it is rejected with a clear validation
  error in the request's language, and nothing is retrieved and no model is
  called.
- **Given** the message
  `Restaurantes abertos perto da Praça da República, 20:00`, **When** it is sent,
  **Then** it is accepted. So is `Onde tem açaí?!`.

### Short conversation with memory (P1)

- **Given** a new conversation, **When** the visitor asks 4 questions, **Then**
  all 4 are answered, and each answer shows how many questions are left
  (3, 2, 1, 0).
- **Given** 0 questions left, **When** the visitor tries to ask a 5th, **Then**
  input is disabled in the app, and the backend refuses the request with a
  "conversation finished" status.
- **Given** a first question "bares bem avaliados", **When** the follow-up is
  "abertos agora", **Then** the results are well-rated bars that are open now.
- **Given** that conversation, **When** the next question names a different kind
  of place ("cafés"), **Then** it starts a fresh search for cafés and does not
  carry over the earlier filters.
- **Given** a conversation idle for more than 30 minutes, **When** the visitor
  asks again, **Then** it is treated as a new conversation.

### See more for free (P1)

- **Given** an answer with more than 5 matching places, **When** the visitor taps
  "Ver mais", **Then** the next 5 places in the same order appear immediately.
  The questions-left count does not change, and no new search or model call
  happens.
- **Given** the last page has been shown, **When** results run out, **Then** "Ver
  mais" is no longer offered.

### Suggested follow-ups (P2)

- **Given** any answered question, **When** the answer is shown, **Then** 2–4
  follow-up suggestions appear in the answer's language. Tapping one asks it as a
  normal question. Every suggestion would itself pass the input rule.

### Nearby search only in Belém (P2)

- **Given** a visitor whose shared location is inside the city profile's
  bounds, **When** they ask for places near them, **Then** results are filtered
  and sorted by distance, as before.
- **Given** a visitor whose shared location is outside those bounds, **When**
  they ask for places near them ("perto de mim"), **Then** the answer opens with
  a short note in their language saying that searching nearby only works in
  Belém, followed by places from the whole city. No distance appears on any
  card, and the question counts as answered.
- **Given** a visitor outside the bounds, **When** they ask anything else,
  **Then** their location is ignored without a note, and "Mais perto de mim" is
  never suggested.

### Fair use (P2)

- **Given** one visitor, **When** they send more than 20 messages within 10
  minutes, **Then** further messages are refused with a "too many requests"
  status until the window passes.
- **Given** the daily model-call budget is used up, **When** anyone asks, **Then**
  they still get a templated answer with results, never an error.

### Waking-up state (P2)

- **Given** the backend has been idle long enough to sleep, **When** a visitor
  opens the site, **Then** a "waking up the server (up to 1 min)" message shows
  until the backend responds. After that the chat works normally.

### Start over (P3)

- **Given** any state, **When** the visitor taps "Nova conversa", **Then** the
  screen clears and a fresh conversation with 4 questions begins. Reloading the
  page also starts fresh.

### Docs match reality (P3)

- **Given** the repository README and project site, **When** a reader follows the
  deploy section, **Then** it covers the free backend host, the static frontend
  host, the model provider settings, and how to build a catalog for another town.
  Nothing mentions local model weights or vector databases.

## Success metrics

| Metric | Target |
|---|---|
| Monthly hosting + model cost | $0 |
| Model calls per answered question / per "see more" | 1 / 0 |
| "See more" response time (warm server) | ≤ 150 ms |
| Answered-question response time, p50 (warm server) | ≤ 3 s |
| Cold-start time until first answer | ≤ 90 s, with the waking-up state visible |
| Disallowed inputs reaching search or the model | 0 (server-side tests) |
| Conversations exceeding 4 answered questions | 0 |
| Frontend first load on mobile 4G | ≤ 5 s |

## Out of scope

- Tour or itinerary building.
- Accounts, persistent history across visits, analytics.
- Custom domain, CDN tuning, multiple backend instances.
- Abuse protection beyond per-visitor and daily limits (no CAPTCHA, no WAF).
- Paid tiers of any service.

## Open questions

None. Defaults chosen at drafting time:

- **"See more" is free.** It does not count toward the 4 questions.
- **Follow-up chips are ordinary questions.** Tapping one spends a question,
  except "Ver mais".
- **Fresh start on reload.** Conversations are not restored after a reload.
- **Rejected input is explained.** The app shows a short localized explanation
  instead of silently dropping the message.

## Branch, commit and PR convention

- **Branch:** `mvp-2`, cut from `main` after mvp-1 is merged.
- **Commits:** every commit starts with `mvp-2:`.
- **PR title:** `mvp-2 — Public conversational MVP`.
- **PR body:** links `specs/mvp/mvp-2-public-mvp/`, includes the public URLs, and
  summarizes the evidence in `validation.md`.
