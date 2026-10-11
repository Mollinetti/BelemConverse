# ADR-0002 — Vector Search Usage

## Decision
Vector similarity search is NOT used as primary retrieval because it ignores essential ranking factors (distance/openNow/rating/popularity).

## Allowed Uses
1) Metadata store (Chroma can store documents + metadata).
2) Optional fallback ONLY IF:
   - structured + lexical + radius escalation returns <5 results
   - query contains "vibe" adjectives not represented in structured fields
   - ENABLE_VECTOR_FALLBACK=true
   - geo and openNow constraints still apply first

## Default
ENABLE_VECTOR_FALLBACK=false