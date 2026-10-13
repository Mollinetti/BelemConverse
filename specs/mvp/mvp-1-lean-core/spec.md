# mvp-1 — Lean grounded core

**Status**: approved  ·  **Type**: roadmap
**Branch**: mvp-1  ·  **Spec dir**: specs/mvp/mvp-1-lean-core/
**Overview**: [../spec.md](../spec.md)  ·  **Next**: [mvp-2](../mvp-2-public-mvp/spec.md)

## Goal

The chat backend answers Belém place questions from a **clean, verified
catalog**. Each answer is a **short natural-language reply written by a small,
free hosted language model**. The reply may name only places the system
actually retrieved; if the model is unavailable or strays, the user gets a
plain templated answer instead.

The backend runs on a free-tier machine with **no local model and no GPU**. Tour
building is gone from the chat. This phase gives mvp-2 a trustworthy core to put
in front of the public.

## User stories (prioritized)

- **P1 — Grounded answer.** As a visitor, I want to ask in Portuguese or English
  and get a short, readable answer that recommends only real places from the
  catalog, so that I can trust the suggestion.
- **P1 — Clean catalog.** As the operator, I want one command that rebuilds the
  Belém catalog from the raw exports and tells me exactly what it fixed, so that
  duplicates, broken accents and unreadable opening hours never reach users.
- **P1 — Runs on free hardware.** As the showcase owner, I want the backend to
  run within a free-tier memory budget with no model weights on disk, so that
  hosting costs nothing.
- **P1 — Always answers.** As a visitor, I want an answer even when the language
  model is slow, rate-limited or down, so that the chat never breaks.
- **P2 — Tour requests degrade gracefully.** As a visitor who asks for an
  itinerary, I want ordinary place suggestions instead of an error, so that the
  removed feature is invisible.
- **P2 — Independent verification.** As the operator, I want to see which
  places an independent open map source also knows about, so that I know which
  entries are confirmed and which need review.
- **P2 — Provider by configuration.** As the showcase owner, I want to switch
  language-model provider or model without code changes, and to have measured
  evidence of which model is good enough, so that I can follow the best free
  tier.
- **P3 — Intent detection still fit.** As a maintainer, I want intent and
  category accuracy measured before and after this phase, so that keeping the
  lightweight classifier is a measured choice.

## Acceptance criteria

### Grounded answer (P1)

- **Given** the clean catalog and a working model, **When** a visitor asks
  "restaurantes abertos perto da Estação das Docas" in Portuguese, **Then** the
  reply is in Portuguese, has at most 5 results, and every place it names is
  among those results.
- **Given** the same setup, **When** the same question is asked in English,
  **Then** the reply is in English with the same grounding.
- **Given** a model reply that names a place not among the results, **When** the
  answer is assembled, **Then** the visitor gets the templated answer instead.
- **Given** any answered question, **When** it is processed, **Then** the
  language model is called **at most once**.

### Clean catalog (P1)

- **Given** the raw Belém exports, **When** the operator runs the catalog build,
  **Then** the catalog has:
  - no duplicate place ids;
  - no replacement characters (`?`) in city or state;
  - opening hours either in one normalized per-day format or explicitly
    unknown;
  - only places in the Belém municipality, including the Mosqueiro and Outeiro
    districts.
- **Given** a completed build, **When** the operator opens the build report,
  **Then** it lists a count for every kind of fix, and the input row count equals
  kept rows plus merged duplicates plus dropped rows.
- **Given** a place whose name was garbled and that has no repairable source,
  **When** the build runs, **Then** the place is kept and flagged for review,
  not silently dropped.

### Runs on free hardware (P1)

- **Given** a fresh install from the dependency list, **When** the backend
  starts and serves 20 chat requests, **Then** its resident memory stays under
  512 MB.
- **Given** the dependency list, **When** it is inspected, **Then** it contains
  no local-inference, vector-database or deep-learning package.

### Always answers (P1)

- **Given** the model provider returns a rate-limit error or times out, **When**
  a visitor asks a question, **Then** a fallback provider is tried if one is
  configured. Failing that, the visitor gets the templated answer with a success
  status, in under 12 seconds.
- **Given** no model is configured at all, **When** the backend starts, **Then**
  it reports ready and answers with templated answers.

### Tour requests degrade gracefully (P2)

- **Given** the tour feature is removed, **When** a visitor asks "monte um
  roteiro de um dia em Belém", **Then** the visitor gets ordinary place results
  with a success status and no itinerary.

### Independent verification (P2)

- **Given** the clean catalog, **When** the operator runs the validation pass,
  **Then** every place is marked confirmed or unconfirmed by the open map source.
  Places whose coordinates disagree by more than 150 m are listed in a report.
  No place is deleted.

### Provider by configuration (P2)

- **Given** two model providers configured only through environment settings,
  **When** the primary is changed, **Then** no code change is needed.
- **Given** the golden question set, **When** the benchmark runs against each
  candidate model, **Then** a table of grounding pass rate, Portuguese quality
  and median latency is recorded. The chosen model is the smallest that reaches
  the success metrics below.

### Intent detection still fit (P3)

- **Given** the diagnostic question set, **When** it runs before and after this
  phase, **Then** both scores are recorded, and intent accuracy after is at least
  80% with no tour intent left.

## Success metrics

| Metric | Target |
|---|---|
| Backend resident memory after 20 requests | < 512 MB |
| Language-model calls per answered question | exactly 1 (0 when unconfigured or over budget) |
| Grounding pass rate on the golden set (chosen model) | ≥ 95% |
| Portuguese spot-check (10 answers, chosen model) | ≥ 9/10 judged natural and correct |
| Median language-model latency (chosen model) | ≤ 2.5 s |
| Median backend time excluding the model | ≤ 100 ms |
| Catalog duplicate ids / `?` in city or state | 0 / 0 |
| Catalog rows with parsed opening hours | reported; at least the pre-cleaning non-null count minus garbage rows |
| Intent accuracy on the diagnostic set | ≥ 80% (baseline 83.2%) |
| Free daily request allowance of the chosen model | ≥ 1,000 |

## Out of scope

- Input restrictions, conversation sessions, the turn limit, "see more", follow-up
  suggestions, rate limiting (all in mvp-2).
- Any frontend change.
- Public deployment.
- Tour or itinerary building in any form.
- Semantic or vector search.
- Paid model tiers or self-hosted models in production.

## Open questions

None. Defaults chosen at drafting time:

- **Municipality.** The catalog covers the Belém municipality (including the
  Mosqueiro and Outeiro districts). Neighbouring municipalities such as
  Ananindeua and Marituba are excluded. The city profile can change this.
- **Optional re-scrape.** Re-scraping the original listing source for missing
  opening hours is optional. It runs only if it fits within that source's free
  monthly credit.

## Branch, commit and PR convention

- **Branch:** `mvp-1`.
- **Commits:** every commit starts with `mvp-1:`.
- **PR title:** `mvp-1 — Lean grounded core`.
- **PR body:** links `specs/mvp/mvp-1-lean-core/` and summarizes the evidence in
  `validation.md`.
