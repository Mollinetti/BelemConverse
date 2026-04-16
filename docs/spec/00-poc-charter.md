# PoC Charter — Places Nearby Chat (EN + pt-BR)

## Goal
Provide a chat experience that recommends nearby places (restaurants, bars, parks, etc.) using deterministic filtering + ranking (distance/openNow/rating/popularity), based on a CSV dataset. The LLM only summarizes curated results.

## Key Principle
Primary retrieval must NOT be semantic vector similarity. Vector search may exist only as a gated fallback and must not override geo/ranking constraints.

## In Scope
- CSV ingestion into a canonical Place model
- Place type inference from categoryName and categories[] with precedence
- Query understanding: parse user message into a structured Query Plan (EN + pt-BR)
  - **Intent classification using TF-IDF classifier** (SimpleTFIDFIntentClassifier)
  - Intent detection: location, popularity, price, business_hours, tour_planning, verification
  - Category detection: restaurant, cafe, hotel, bar, shopping, entertainment, tourist_attraction, acai, etc.
  - Keyword matching as fallback if classifier unavailable
- Deterministic retrieval with strict filtering precedence:
  1. Open hours filtering (if detected) - applied FIRST
  2. Proximity filtering with geo radius escalation: 0.5km → 1km → 2km (if user_location provided) - applied SECOND
  3. Category/classification filtering (if detected) - applied THIRD
  4. Other structured filters (type/city/neighborhood/price/min_rating/min_reviews) - applied FOURTH
  5. Popularity/rating used only in ranking, not filtering - applied FIFTH
- API:
  - /chat returns text answer + 5 structured results for UI cards
- Flutter web chat UI (web view container) with location permission

## Out of Scope (PoC)
- User accounts, auth, multi-tenancy
- Payments, bookings, moderation workflows
- External geocoding of addresses (unless explicitly added later)
- Production hardening (scaling, HA, WAF, etc.)

## Success Criteria
- One-command local run (runbook)
- Ingestion completes and produces a searchable index
- For golden queries, top 3 expected places appear in results in most cases
- Responses are bilingual (EN/pt-BR) based on user language
- Results always respect distance/openNow constraints (where data permits)

## Non-Goals
- “Creative” recommendations beyond dataset
- Hallucinating places or attributes not present in retrieved candidates
``