# LLM Contract (Summarization Only)

## Models
- Embeddings: sentence-transformers/all-mpnet-base-v2
- LLM: distilled Meta-Llama-3.1-8B-Instruct-Q5_K_M (GGUF)

## Core Rule
The LLM must NOT perform retrieval. It only summarizes the curated `results[]` from deterministic retrieval.

## Prompt Contract
System message MUST include:
- "Only use the provided candidates. Do not invent places."
- "If results are empty, ask a clarifying question or suggest widening constraints."
- Bilingual output based on language.

## Inputs to the LLM
- User message
- Query Plan (optional for debug)
- A list of up to 5 PlaceResult objects

## Output
- Natural language answer in EN or pt-BR
- Must mention why each result matches (distance/rating/openNow) when available
- If openNow requested and some results are unknown, clearly label them as such
- Avoid citations and avoid referencing internal scoring

## Empty / Low-Result Behavior
- If 0 results after full radius escalation:
  - Ask for broader radius, different type, or disable openNow filter.
``