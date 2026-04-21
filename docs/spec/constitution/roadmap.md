# Roadmap — small phases

**Canonical specs:** [Query planner](../03-query-planner.md) · [Ranking](../04-ranking-spec.md) · [Eval](../09-eval-golden-queries.md) · [UX](../07-ux-flutter.md) · [ADR-0002](../decisions/ADR-0002-vector-search-fallback.md)

Phases are intentionally **small** (each phase: one to three shippable outcomes). Order favors **intent and retrieval** first, then evaluation, client polish, optional vector fallback.

---

## Phase 0 — Baseline

**Outcomes**

- Constitution and spec cross-links are the single “why / how” entry for contributors.
- [Golden queries](../09-eval-golden-queries.md) list is the agreed smoke set; test location(s) documented.

**Exit:** Team can run the app locally per [runbook](../10-runbook.md) and manually run at least one golden query end-to-end.

---

## Phase 1 — Intent, planner, and retrieval consistency

**Outcomes**

- Query planner behavior matches [03-query-planner.md](../03-query-planner.md): language, TF-IDF usage, slots (including proximity only when intended), categories, open-now.
- Deterministic retriever follows [04-ranking-spec.md](../04-ranking-spec.md) precedence (open hours → proximity when applicable → category → other filters → ranking).

**Exit:** Golden queries P1/Q1-style scenarios pass at a defined threshold (e.g. correct filters + plausible top results for fixed coordinates).

---

## Phase 2 — Evaluation and regression

**Outcomes**

- Automated or scripted runner for [golden queries](../09-eval-golden-queries.md) (pass/fail + debug plan or log).
- Regressions on planner/retrieval changes before release candidates.

**Exit:** CI or local `make test`-style step runs golden checks; failures block merge or are explicitly waived.

---

## Phase 3 — Client UX polish

**Outcomes**

- Alignment with [07-ux-flutter.md](../07-ux-flutter.md): cards, filters, location messaging, external links.
- [08-i18n.md](../08-i18n.md) strings reviewed for key flows.

**Exit:** Demo script [11-demo-script.md](../11-demo-script.md) can be executed without UX blockers on web (and mobile if in scope).

---

## Phase 4 — Optional vector fallback (gated)

**Outcomes**

- `ENABLE_VECTOR_FALLBACK` behavior matches [ADR-0002](../decisions/ADR-0002-vector-search-fallback.md): only when structured path is insufficient and “vibe” terms appear; geo/open-now still enforced first.

**Exit:** Documented test cases for fallback on/off; no default reliance on vectors for primary ranking.

---

## Not in these phases (PoC charter)

Auth, payments, multi-tenant SaaS, and full production SRE are **out of scope** unless [charter](../00-poc-charter.md) is revised.
