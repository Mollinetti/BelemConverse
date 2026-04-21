# BelemConverse Mission

> AI-powered, location-aware place discovery for **Belém do Pará**.

## Why this exists
Belém has rich, dispersed local information (places, hours, categories,
neighborhoods) that today lives across CSVs, OSM, and tribal knowledge.
BelemConverse turns that into a **deterministic, grounded, conversational
experience**: a user asks in Portuguese or English, the system plans the
query, retrieves a small grounded result set, and an LLM summarizes — never
hallucinating beyond the retrieved facts.

## Who it's for
- **Visitors** to Belém who need quick, trustworthy answers about places,
  open hours, and routes.
- **Locals** who want a focused tour or itinerary for a neighborhood or theme.
- **Operators** who curate the canonical places dataset and want a stable
  ingestion → retrieval → answer loop.

## What success looks like
1. Every user-facing answer is **grounded** in ≤ 5 canonical places retrieved
   from the index; no hallucinated entities.
2. The deterministic pipeline (intent → plan → retrieve → rank → summarise)
   is **observable and reproducible** for any query.
3. The Flutter client is a thin, predictable consumer of the FastAPI
   `/api/*` contract documented in `docs/spec/05-openapi.yaml`.
4. Adding a new city profile, intent, or ranking signal is a **bounded spec**
   (one phase) rather than a refactor.
5. The data refresh path (CSV → canonical_places.jsonl → Chroma) can be run
   end-to-end without manual stitching.

## Non-goals
- Real-time crowdsourced data, user accounts, or social features.
- Replacing OSM/Google Maps for navigation.
- Multi-tenant SaaS hosting; the project ships a single-instance backend.
- Generative content beyond grounded summarisation.

## Current scope
The default city profile is **Belém do Pará**; supported response languages
are **`pt`** and **`en`**. The single supported summariser is a local GGUF
model (Llama 3.1 8B Instruct by default) loaded via `llama-cpp-python`.

## Alignment with specs
Every feature spec must connect at least one user story to one of the
success criteria above. If it cannot, either the spec is out of mission or
the mission needs an ADR-backed update.
