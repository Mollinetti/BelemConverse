# Mission — BelemConverse

**Canonical specs:** [PoC charter](../00-poc-charter.md) · [Query planner](../03-query-planner.md) · [LLM contract](../06-llm-contract.md)

## Purpose

BelemConverse helps people discover places in and around **Belém** through a **chat-first** experience that respects **real data**: restaurants, bars, parks, cafés, attractions, and more, grounded in an ingested dataset—not invented listings.

## Who we serve

We optimize for **both**:

- **Visitors and tourists** who want trustworthy, localized suggestions (food, culture, sights) without wading through generic global recommendations.
- **Local residents** who want practical, nearby results with filters that match how people actually ask (open now, type, quality, distance when they ask for it).

Language and tone follow **English and Brazilian Portuguese (pt-BR)** as first-class; see [i18n spec](../08-i18n.md).

## Cultural positioning (Belém)

The product should feel **rooted in Belém**: regional food and drink (e.g. açaí, churrascarias, botecos), tourist and everyday attractions, and **natural phrasing** in Portuguese—including informal and regional usage where the planner and UX support it. Culture shapes **how we explain and prioritize**, not which facts we invent: every place card and summary must remain **tied to retrieved candidates** from the index.

## Non-negotiables

1. **Deterministic retrieval first** — Ranking and eligibility come from structured filters, geo, open-hours logic, and explicit sort preferences—not from “vibes-only” semantic search as the primary path. See [ranking spec](../04-ranking-spec.md).
2. **No hallucinated venues** — The LLM **summarizes** curated `results[]` only; it does not retrieve or fabricate places. See [LLM contract](../06-llm-contract.md).
3. **Bilingual experience** — User-facing answers and UI strings align with EN / pt-BR expectations in the specs.
4. **PoC boundaries** — Accounts, payments, and production-grade scaling are out of scope until explicitly expanded; see [PoC charter](../00-poc-charter.md).

## Success (directional)

Users get **up to five** relevant, explainable results per query when data allows; golden-query behavior and runbook-driven local runs remain the acceptance baseline ([eval](../09-eval-golden-queries.md), [runbook](../10-runbook.md)).
