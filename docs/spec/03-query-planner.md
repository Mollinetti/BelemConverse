# Query Understanding & Planner Spec (EN + pt-BR)

## Overview
Every user chat message MUST be converted into a deterministic Query Plan JSON. The planner decides intent, slots, and retrieval strategy.

The planner must support English and Brazilian Portuguese.

**Intent Classifier Requirement:**
- The Query Planner MUST use a trained TF-IDF intent classifier (SimpleTFIDFIntentClassifier) for intent and category detection.
- The classifier provides confidence scores and handles variations better than simple keyword matching.
- Keyword matching serves as a fallback if the classifier is unavailable or fails.
- The classifier detects:
  - Intents: location, popularity, price, business_hours, tour_planning, verification
  - Categories: restaurant, cafe, hotel, bar, shopping, entertainment, tourist_attraction, acai (and others)

## Planner Output Schema (JSON)
{
  "language": "en | pt-BR",
  "intent": "find_places | place_details | compare_places | smalltalk | help",
  "slots": {
    "place_type": ["restaurant|bar|park|other"],
    "categories": ["string"],
    "city": "string|null",
    "neighborhood": "string|null",
    "open_now": "boolean|null",
    "price_max": "number|null",
    "min_rating": "number|null",
    "min_reviews": "number|null",
    "user_location": { "lat": "number", "lng": "number" } | null,
    "radius_strategy": "auto_escalate_0.5_1_2_km",
    "keywords": ["string"],
    "sort_preference": "distance | rating | popularity | best_match"
  },
  "retrieval_strategy": "structured_only | structured_then_lexical | structured_then_vector_fallback",
  "debug": {
    "detected_signals": ["string"]
  }
}

## Language Detection
- If message contains strong PT-BR indicators (e.g., "perto", "melhor", "aberto agora"), set language=pt-BR.
- Otherwise language=en.
- If client passes language explicitly, trust it.

## Intent Classification
The Query Planner MUST use the TF-IDF intent classifier for intent detection:
- find_places: user asking for recommendations or a list.
- place_details: user asks about a specific place by name or placeId.
- compare_places: user compares two or more places.
- smalltalk/help: non-search queries.

The classifier analyzes the message and provides:
- Primary intent with confidence score
- Multiple intents if detected (e.g., location + business_hours)
- Category predictions (e.g., "acai", "restaurant", "tourist_attraction")

If ambiguous or classifier unavailable, default to find_places.

## Signal/Slot Extraction (bilingual)
### Distance intent
EN triggers: "near", "near me", "closest", "within", "around", "walking distance"
PT-BR triggers: "perto", "perto de mim", "mais próximo", "próximo", "a até", "num raio de"

If distance intent detected AND user_location exists => sort_preference=distance.

### Rating intent
EN: "best", "top rated", "highest rated", "4.5+", "good rating"
PT-BR: "melhor", "mais bem avaliado", "nota", "4,5+"

### Popularity intent
EN: "popular", "most reviewed", "many reviews"
PT-BR: "popular", "mais avaliações", "muitas avaliações"

### Type/category intent
**Primary method: TF-IDF Classifier**
- Use the TF-IDF classifier's `predict_category()` method to detect categories.
- The classifier handles variations, misspellings, and context better than keyword matching.
- Categories detected include: restaurant, cafe, hotel, bar, shopping, entertainment, tourist_attraction, acai, ice_cream, etc.
- Map detected categories to place_type using the same dictionary approach as domain model.
- Also capture specific category keywords like "pizza", "sushi", "steak", "açaí".

**Fallback method: Keyword Matching**
- If classifier unavailable or confidence too low, use keyword matching.
- Extract explicit words for restaurant/bar/park/cafe etc.
- Map extracted strings to place_type using the same dictionary approach as domain model.

### Open now intent
**Primary method: TF-IDF Classifier**
- Use the TF-IDF classifier's `predict_intent()` method to detect "business_hours" intent.
- If business_hours intent detected with confidence >= 0.3 AND message contains open/aberto keywords => open_now=true.

**Fallback method: Keyword Matching**
EN: "open now", "open", "currently open", "is open", "are open"
PT-BR: "aberto agora", "aberto", "funcionando agora", "esteja aberta", "está aberto", "aberta", "abertos", "abertas"
If detected => open_now=true.

### Price intent
Detect patterns:
- EN: "cheap", "$", "price <= 2", "inexpensive"
- PT-BR: "barato", "preço", "até"
Map to price_max if possible; else add to keywords.

### Location slots
- user_location must come from client GPS (preferred).
- City/neighborhood extracted only if explicitly stated, not guessed.

## Conflict Resolution / Precedence
When multiple sort signals exist:
1) If "closest/near" detected and user_location exists => sort_preference=distance
2) Else if "best/top rated" => sort_preference=rating
3) Else if "popular/most reviewed" => sort_preference=popularity
4) Else => best_match

If user requests both distance and rating:
- distance is primary, rating is tie-breaker (implemented in ranking spec).

## Retrieval Strategy Selection
Default: structured_then_lexical
Vector fallback is OFF by default. It can be enabled only when:
- structured_then_lexical returns fewer than 5 results after radius escalation
- AND query contains "vibe" keywords (e.g., "romantic", "quiet", "cozy", "instagrammable") that are not represented as structured fields
- AND a feature flag ENABLE_VECTOR_FALLBACK is true

When vector fallback is used, it MUST still apply geo radius and openNow constraints first.