# Requirements Document: Intent Detection and Retrieval Unification

## Introduction

This document specifies requirements for unifying and improving the intent detection and retrieval system in a RAG-based travel guide chatbot. The current implementation has multiple overlapping approaches for intent detection (TF-IDF classifier and keyword-based Query Planner) and retrieval strategies (two-stage retriever, filter-first, semantic fallback, deterministic retriever, OSM realtime search). This creates confusion, code duplication, and maintenance challenges. The goal is to establish a single, clear, consistent approach that eliminates ambiguity and improves system maintainability.

## Glossary

- **Intent_Classifier**: The TF-IDF-based machine learning classifier that detects user intents (location, popularity, price, business_hours, tour_planning, verification) and categories (restaurant, cafe, hotel, bar, etc.)
- **Query_Planner**: The component that converts user messages into structured Query Plans with language detection, intent classification, slot extraction, and retrieval strategy selection
- **Two_Stage_Retriever**: A retrieval system that performs semantic search followed by structured re-ranking using location, category, and popularity filters
- **Deterministic_Retriever**: A retrieval system that applies structured filters first (open hours, proximity, category) then ranks by intent-specific criteria
- **Filter_First_Retrieval**: The primary retrieval approach in Two_Stage_Retriever that filters all places by category then ranks by intent
- **Semantic_Search**: Vector-based similarity search using embeddings to find semantically relevant places
- **OSM_Fallback**: OpenStreetMap realtime search used when database results are insufficient
- **Retrieval_Strategy**: The approach used to find relevant places (structured_only, structured_then_lexical, structured_then_vector_fallback)
- **Category_Matching**: The process of determining if a place matches requested category keywords
- **Intent_Detection**: The process of identifying what the user wants (nearby places, popular places, price filtering, hours checking, tour planning, verification)
- **Unified_System**: The consolidated intent detection and retrieval architecture that eliminates duplication and confusion

## Requirements

### Requirement 1: Consolidate Intent Detection into Single Source of Truth

**User Story:** As a developer, I want a single authoritative intent detection system, so that I don't have conflicting or duplicate intent detection logic across the codebase.

#### Acceptance Criteria

1. THE Unified_System SHALL use Intent_Classifier as the sole source for intent detection
2. THE Query_Planner SHALL delegate all intent detection to Intent_Classifier
3. THE Query_Planner SHALL NOT implement duplicate keyword-based intent detection logic
4. WHEN Intent_Classifier fails or is unavailable, THEN THE Query_Planner SHALL use a minimal fallback with explicit logging
5. THE Unified_System SHALL remove all redundant intent detection code from Query_Planner

### Requirement 2: Establish Clear Retrieval Strategy Hierarchy

**User Story:** As a developer, I want a clear hierarchy of retrieval strategies, so that I understand when each approach is used and can predict system behavior.

#### Acceptance Criteria

1. THE Unified_System SHALL define exactly three retrieval strategies: Filter_First, Semantic_Search, and OSM_Fallback
2. THE Unified_System SHALL use Filter_First as the primary retrieval strategy for all queries
3. WHEN Filter_First returns zero results, THEN THE Unified_System SHALL fall back to Semantic_Search
4. WHEN database results are insufficient AND user location is available, THEN THE Unified_System SHALL supplement with OSM_Fallback
5. THE Unified_System SHALL document the conditions that trigger each retrieval strategy
6. THE Unified_System SHALL log which retrieval strategy is selected for each query

### Requirement 3: Unify Category Matching Logic

**User Story:** As a developer, I want consistent category matching across all retrieval components, so that the same query produces consistent results regardless of which retriever is used.

#### Acceptance Criteria

1. THE Unified_System SHALL implement category matching in a single shared module
2. THE Category_Matching module SHALL use Intent_Classifier category keywords as the authoritative source
3. THE Category_Matching module SHALL handle special cases (açaí vs cafe, hotel vs motel) consistently
4. THE Two_Stage_Retriever SHALL use the shared Category_Matching module
5. THE Deterministic_Retriever SHALL use the shared Category_Matching module
6. THE Query_Planner SHALL use the shared Category_Matching module for category extraction

### Requirement 4: Eliminate Retriever Duplication

**User Story:** As a developer, I want to remove duplicate retrieval implementations, so that I maintain only one codebase for each retrieval approach.

#### Acceptance Criteria

1. THE Unified_System SHALL consolidate Two_Stage_Retriever and Deterministic_Retriever into a single retriever implementation
2. THE consolidated retriever SHALL support all filtering modes (open hours, proximity, category, price, rating)
3. THE consolidated retriever SHALL support all ranking modes (distance, rating, popularity, best_match)
4. THE Unified_System SHALL remove the deprecated retriever implementation
5. THE consolidated retriever SHALL maintain backward compatibility with existing Query_Plan slots

### Requirement 5: Clarify Intent-to-Retrieval Mapping

**User Story:** As a developer, I want explicit documentation of how intents map to retrieval behavior, so that I can predict and debug system behavior.

#### Acceptance Criteria

1. THE Unified_System SHALL document the mapping from each intent type to retrieval behavior
2. WHEN location intent is detected, THEN THE Unified_System SHALL apply proximity filtering and distance ranking
3. WHEN popularity intent is detected, THEN THE Unified_System SHALL rank by Bayesian popularity score
4. WHEN business_hours intent is detected, THEN THE Unified_System SHALL filter by open status
5. WHEN price intent is detected, THEN THE Unified_System SHALL filter by price range
6. WHEN tour_planning intent is detected, THEN THE Unified_System SHALL route to the tour planner component
7. WHEN verification intent is detected, THEN THE Unified_System SHALL prioritize exact name matching and OSM_Fallback

### Requirement 6: Standardize Proximity Intent Detection

**User Story:** As a user, I want the system to only filter by proximity when I explicitly mention being close or nearby, so that I get city-wide results when I don't specify location preferences.

#### Acceptance Criteria

1. THE Intent_Classifier SHALL detect proximity intent only when proximity keywords are present in the query
2. THE Query_Planner SHALL set proximity_intent_detected flag based on Intent_Classifier results
3. WHEN proximity_intent_detected is false, THEN THE Unified_System SHALL NOT apply distance filtering
4. WHEN proximity_intent_detected is true AND user location is available, THEN THE Unified_System SHALL apply radius escalation (0.5km → 1km → 2km)
5. THE Unified_System SHALL calculate distance for display purposes even when proximity filtering is not applied

### Requirement 7: Simplify Category Keyword Management

**User Story:** As a developer, I want category keywords defined in one place, so that I can easily update and maintain the category taxonomy.

#### Acceptance Criteria

1. THE Intent_Classifier SHALL be the single source of truth for all category keywords
2. THE Query_Planner SHALL extract category keywords directly from Intent_Classifier
3. THE Category_Matching module SHALL use Intent_Classifier keywords for matching
4. WHEN category keywords are updated in Intent_Classifier, THEN THE Unified_System SHALL automatically retrain the classifier
5. THE Unified_System SHALL NOT duplicate category keyword lists in multiple files

### Requirement 8: Establish Filtering Precedence Rules

**User Story:** As a developer, I want clear precedence rules for applying multiple filters, so that I can predict which filters take priority when multiple intents are detected.

#### Acceptance Criteria

1. THE Unified_System SHALL apply filters in the following order: open_now, proximity, category, price, rating
2. WHEN open_now is detected, THEN THE Unified_System SHALL filter by business hours before any other filter
3. WHEN proximity_intent_detected is true, THEN THE Unified_System SHALL apply proximity filtering after open_now but before category
4. WHEN category is detected, THEN THE Unified_System SHALL apply category filtering after proximity but before price and rating
5. THE Unified_System SHALL document the rationale for the filtering precedence order

### Requirement 9: Improve Retrieval Strategy Selection Logic

**User Story:** As a developer, I want clear rules for when to use semantic search vs filter-first retrieval, so that I can optimize for both relevance and performance.

#### Acceptance Criteria

1. THE Query_Planner SHALL select Filter_First as the default retrieval strategy
2. THE Query_Planner SHALL select Semantic_Search only when Filter_First returns zero results
3. THE Query_Planner SHALL enable OSM_Fallback when user location is available
4. THE Query_Planner SHALL NOT use ENABLE_VECTOR_FALLBACK environment variable for strategy selection
5. THE Unified_System SHALL remove vibe keyword detection for retrieval strategy selection

### Requirement 10: Consolidate Ranking Logic

**User Story:** As a developer, I want consistent ranking behavior across all retrievers, so that the same query produces similarly ordered results regardless of the retrieval path.

#### Acceptance Criteria

1. THE Unified_System SHALL implement ranking logic in a single shared module
2. THE ranking module SHALL support four modes: distance, rating, popularity, best_match
3. WHEN sort_preference is distance, THEN THE ranking module SHALL sort by distance ascending with rating as tiebreaker
4. WHEN sort_preference is rating, THEN THE ranking module SHALL sort by totalScore descending with reviewsCount as tiebreaker
5. WHEN sort_preference is popularity, THEN THE ranking module SHALL sort by Bayesian popularity score descending
6. WHEN sort_preference is best_match, THEN THE ranking module SHALL use composite scoring (45% rating, 35% popularity, 20% proximity)
7. THE Two_Stage_Retriever SHALL use the shared ranking module
8. THE Deterministic_Retriever SHALL use the shared ranking module

### Requirement 11: Standardize Place Data Access

**User Story:** As a developer, I want consistent place data access patterns, so that I don't have different caching and lookup strategies in different retrievers.

#### Acceptance Criteria

1. THE Unified_System SHALL implement place data access in a single shared module
2. THE place data module SHALL provide a unified cache for all retrievers
3. THE place data module SHALL support lookup by title, titleFormatted, and placeId
4. THE Two_Stage_Retriever SHALL use the shared place data module
5. THE Deterministic_Retriever SHALL use the shared place data module
6. THE Unified_System SHALL remove duplicate place caching logic

### Requirement 12: Improve OSM Fallback Integration

**User Story:** As a user, I want the system to seamlessly integrate OSM results when database results are insufficient, so that I always get relevant results even for places not in the database.

#### Acceptance Criteria

1. THE Unified_System SHALL evaluate database result quality before triggering OSM_Fallback
2. WHEN database results are empty, THEN THE Unified_System SHALL trigger OSM_Fallback
3. WHEN all database result scores are below 0.3, THEN THE Unified_System SHALL trigger OSM_Fallback
4. WHEN the nearest database result is beyond 5km AND proximity intent is detected, THEN THE Unified_System SHALL trigger OSM_Fallback
5. WHEN verification intent is detected AND specific place name is not found, THEN THE Unified_System SHALL trigger OSM_Fallback
6. THE Unified_System SHALL merge OSM results with database results in a single ranked list
7. THE Unified_System SHALL log when OSM_Fallback is triggered and why

### Requirement 13: Remove Deprecated Code Paths

**User Story:** As a developer, I want deprecated and unused code removed, so that the codebase is clean and maintainable.

#### Acceptance Criteria

1. THE Unified_System SHALL remove the deprecated retriever implementation after consolidation
2. THE Unified_System SHALL remove duplicate intent detection code from Query_Planner
3. THE Unified_System SHALL remove duplicate category matching logic from all components
4. THE Unified_System SHALL remove ENABLE_VECTOR_FALLBACK environment variable and related code
5. THE Unified_System SHALL remove vibe keyword detection logic
6. THE Unified_System SHALL update all imports and references to use the consolidated components

### Requirement 14: Establish Testing Strategy for Intent Detection

**User Story:** As a developer, I want comprehensive tests for intent detection, so that I can verify the system correctly identifies user intents.

#### Acceptance Criteria

1. THE Unified_System SHALL include property-based tests for Intent_Classifier
2. FOR ALL valid queries with proximity keywords, THE Intent_Classifier SHALL detect location intent
3. FOR ALL valid queries with popularity keywords, THE Intent_Classifier SHALL detect popularity intent
4. FOR ALL valid queries with business hours keywords, THE Intent_Classifier SHALL detect business_hours intent
5. FOR ALL valid queries with category keywords, THE Intent_Classifier SHALL detect the correct category
6. THE Unified_System SHALL include round-trip tests for Query_Plan serialization and deserialization

### Requirement 16: Multilingual Query Support (PT-BR / EN)

**User Story:** As a user writing in Brazilian Portuguese (including slang, typos, and colloquial phrasing), I want the system to correctly identify my language and process my query, so that I get accurate results regardless of how I phrase my request.

#### Acceptance Criteria

1. THE Query_Planner SHALL detect language using a three-step strategy: explicit override → `langdetect` library → keyword fallback
2. WHEN the `langdetect` library is installed, THE Query_Planner SHALL use it as the primary automatic detection method
3. WHEN `langdetect` is unavailable or returns low confidence, THE Query_Planner SHALL fall back to matching against the `_PT_BR_KEYWORDS` set
4. THE `_PT_BR_KEYWORDS` set SHALL contain only unambiguous Portuguese words (words that do not exist in English)
5. THE `_PT_BR_KEYWORDS` set SHALL include colloquial and slang terms common in Brazilian Portuguese (e.g. `bora`, `massa`, `cara`)
6. WHEN an explicit language is provided by the client, THE Query_Planner SHALL use it without running automatic detection
7. THE Query_Planner SHALL correctly classify queries containing typos, mixed-case, and missing accents as PT-BR when Portuguese words are present

### Requirement 17: Expanded Category Coverage

**User Story:** As a user searching for health, beauty, automotive, wellness, pet, nightlife, kids, or sports services, I want the system to correctly identify my category intent, so that I get relevant results for these domains.

#### Acceptance Criteria

1. THE Intent_Classifier SHALL support at least 16 category domains including the 8 new domains: `health`, `beauty`, `automotive`, `wellness`, `pets`, `nightlife`, `kids`, `sports`
2. EACH new category domain SHALL have at least 15 PT-BR keywords and 5 EN keywords
3. THE Intent_Classifier SHALL correctly classify queries mentioning `clínica`, `farmácia`, `médico` as `health`
4. THE Intent_Classifier SHALL correctly classify queries mentioning `salão`, `cabeleireiro`, `manicure`, `barbearia` as `beauty`
5. THE Intent_Classifier SHALL correctly classify queries mentioning `oficina`, `mecânica`, `lava-jato` as `automotive`
6. THE Intent_Classifier SHALL correctly classify queries mentioning `academia`, `spa`, `massagem`, `pilates` as `wellness`
7. THE Intent_Classifier SHALL correctly classify queries mentioning `petshop`, `veterinário`, `banho e tosa` as `pets`
8. THE Intent_Classifier SHALL correctly classify queries mentioning `balada`, `boate`, `show ao vivo` as `nightlife`
9. THE Intent_Classifier SHALL correctly classify queries mentioning `brinquedoteca`, `parquinho`, `buffet infantil` as `kids`
10. THE Intent_Classifier SHALL correctly classify queries mentioning `quadra`, `piscina`, `estádio` as `sports`
11. WHEN category keywords are updated, THE MODEL_VERSION SHALL be incremented to force model retraining

### Requirement 18: Robust Filter Extraction for PT-BR Queries

**User Story:** As a user writing in Portuguese, I want the system to correctly extract filters like open_now, min_rating, and price_max from my query, so that I get filtered results that match my stated preferences.

#### Acceptance Criteria

1. THE `extract_open_now()` function SHALL detect open-now intent via direct phrase matching independent of the primary intent
2. THE `extract_open_now()` function SHALL recognise PT-BR phrases: `aberto agora`, `funcionando agora`, `aberto 24 horas`, `que esteja aberto`, `ainda aberto`, `aberto hoje`
3. THE `extract_open_now()` function SHALL recognise EN phrases: `open now`, `currently open`, `open right now`, `still open`, `open today`
4. THE `extract_open_now()` function SHALL use the Intent_Classifier `business_hours` signal as a secondary check only when direct phrase matching fails
5. THE `extract_min_rating()` function SHALL support at least 10 PT-BR numeric regex patterns including `nota acima de N`, `acima de N estrelas`, `pelo menos N estrelas`, `mínimo de N`, `N estrelas ou mais`
6. THE `extract_min_rating()` function SHALL map qualitative PT-BR terms to numeric thresholds: `altamente avaliado→4.5`, `bem avaliado→4.0`, `excelente→4.5`, `ótimo→4.0`
7. THE `extract_price_max()` function SHALL be language-agnostic (no language-conditional branching)
8. THE `extract_price_max()` function SHALL recognise PT-BR cheap keywords: `econômico`, `em conta`, `bom preço`, `acessível`, `custo-benefício`, `não muito caro`, `preço baixo`
9. THE `extract_price_max()` function SHALL recognise luxury keywords in both PT-BR and EN and map them to `price_max=4.0`
10. THE `extract_categories()` function SHALL use a single consolidated keyword-scan fallback path that covers all 16+ category domains

### Requirement 15: Document Architecture Decisions

**User Story:** As a developer, I want clear documentation of architecture decisions, so that I understand why the system is designed this way.

#### Acceptance Criteria

1. THE Unified_System SHALL document why Filter_First is the primary retrieval strategy
2. THE Unified_System SHALL document why Intent_Classifier is preferred over keyword matching
3. THE Unified_System SHALL document the filtering precedence rationale
4. THE Unified_System SHALL document when to use each ranking mode
5. THE Unified_System SHALL document the OSM_Fallback trigger conditions and rationale
6. THE Unified_System SHALL include architecture diagrams showing component relationships
