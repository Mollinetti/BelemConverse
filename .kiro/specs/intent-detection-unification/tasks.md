# Implementation Plan: Intent Detection and Retrieval Unification

## Overview

This implementation consolidates the intent detection and retrieval system by:
1. Creating shared modules (CategoryMatcher, RankingEngine, PlaceCache) for consistent behavior
2. Building a UnifiedRetriever that consolidates Two_Stage_Retriever and Deterministic_Retriever
3. Updating Query_Planner to use Intent_Classifier exclusively
4. Removing deprecated code and duplication
5. Implementing property-based tests for all 31 correctness properties

The implementation follows a filter-first architecture where deterministic filtering happens before LLM involvement.

## Tasks

- [x] 1. Set up shared modules foundation
  - [x] 1.1 Create CategoryMatcher shared module
    - Implement category matching logic using Intent_Classifier keywords
    - Handle special cases (açaí vs cafe, hotel vs motel)
    - Implement fuzzy matching for unknown categories
    - _Requirements: 3.1, 3.2, 3.3, 7.1, 7.3_
  
  - [x]* 1.2 Write property test for CategoryMatcher
    - **Property 30: Category Keyword Detection**
    - **Validates: Requirements 14.5**
  
  - [x] 1.3 Create RankingEngine shared module
    - Implement distance ranking (ascending with rating tiebreaker)
    - Implement rating ranking (descending with review count tiebreaker)
    - Implement popularity ranking (Bayesian score descending)
    - Implement best_match ranking (45% rating, 35% popularity, 20% proximity)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_
  
  - [x]* 1.4 Write property tests for RankingEngine
    - **Property 16: Distance Ranking Correctness**
    - **Property 17: Rating Ranking Correctness**
    - **Property 18: Popularity Ranking Correctness**
    - **Property 19: Best Match Ranking Correctness**
    - **Validates: Requirements 10.3, 10.4, 10.5, 10.6**
  
  - [x] 1.5 Create PlaceCache shared module
    - Implement unified caching for place data
    - Support lookup by placeId, title, and titleFormatted
    - Implement filter method with predicate functions
    - _Requirements: 11.1, 11.2, 11.3_
  
  - [x]* 1.6 Write property test for PlaceCache
    - **Property 20: Place Lookup by Multiple Keys**
    - **Validates: Requirements 11.3**

- [x] 2. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Implement UnifiedRetriever
  - [x] 3.1 Create UnifiedRetriever class structure
    - Define class with dependencies (PlaceCache, CategoryMatcher, RankingEngine)
    - Implement main retrieve() method orchestration
    - Add logging for strategy selection and execution
    - _Requirements: 4.1, 4.2, 4.3_
  
  - [x] 3.2 Implement filter-first retrieval path
    - Apply filters in precedence order (open_now → proximity → category → price → rating)
    - Implement radius escalation for proximity (0.5km → 1km → 2km)
    - Use CategoryMatcher for category filtering
    - Use RankingEngine for result ranking
    - _Requirements: 2.2, 8.1, 8.2, 8.3, 8.4, 9.1_
  
  - [x]* 3.3 Write property tests for filter-first path
    - **Property 1: Filter-First as Primary Strategy**
    - **Property 4: Multi-Filter Support**
    - **Property 7: Proximity Intent Handling**
    - **Property 14: Filter Precedence Order**
    - **Validates: Requirements 2.2, 4.2, 6.1, 6.2, 6.3, 6.4, 8.1, 8.2, 8.3, 8.4, 9.1**
  
  - [x] 3.4 Implement semantic search fallback path
    - Trigger only when filter-first returns zero results
    - Perform vector similarity search
    - Re-rank with structured filters
    - _Requirements: 2.3, 9.2_
  
  - [x]* 3.5 Write property test for semantic search fallback
    - **Property 2: Semantic Search Fallback**
    - **Validates: Requirements 2.3, 9.2**
  
  - [x] 3.6 Implement OSM fallback logic
    - Evaluate database result quality (empty, low scores, distant results)
    - Trigger OSM when: empty results, scores <0.3, nearest >5km with proximity intent, verification failure
    - Merge OSM results with database results
    - Log OSM trigger conditions
    - _Requirements: 2.4, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_
  
  - [x]* 3.7 Write property tests for OSM fallback
    - **Property 3: OSM Supplementation**
    - **Property 21: OSM Quality Evaluation**
    - **Property 22: OSM Trigger on Empty Results**
    - **Property 23: OSM Trigger on Low Quality**
    - **Property 24: OSM Trigger on Distant Results**
    - **Property 25: OSM Trigger on Verification Failure**
    - **Property 26: OSM Result Merging**
    - **Validates: Requirements 2.4, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6**
  
  - [x] 3.8 Implement intent-to-retrieval mapping
    - Map location intent to proximity filtering and distance ranking
    - Map popularity intent to popularity ranking
    - Map business_hours intent to open_now filtering
    - Map price intent to price range filtering
    - Map verification intent to exact name matching and OSM fallback
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.7_
  
  - [x]* 3.9 Write property tests for intent-to-retrieval mapping
    - **Property 8: Popularity Intent Ranking**
    - **Property 9: Business Hours Intent Filtering**
    - **Property 10: Price Intent Filtering**
    - **Property 12: Verification Intent Prioritization**
    - **Validates: Requirements 5.3, 5.4, 5.5, 5.7**
  
  - [x] 3.10 Implement distance calculation for all results
    - Calculate distance for display purposes regardless of proximity filtering
    - _Requirements: 6.5_
  
  - [x]* 3.11 Write property test for distance calculation
    - **Property 13: Distance Calculation Invariant**
    - **Validates: Requirements 6.5**

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Update Query_Planner to use Intent_Classifier exclusively
  - [x] 5.1 Refactor Query_Planner to delegate all intent detection
    - Remove duplicate keyword-based intent detection logic
    - Delegate all intent detection to Intent_Classifier
    - Extract slots from Intent_Classifier results
    - _Requirements: 1.1, 1.2, 1.3_
  
  - [x] 5.2 Implement Intent_Classifier fallback handling
    - Add try-catch around Intent_Classifier calls
    - Implement minimal keyword-based fallback on failure
    - Log errors with full context
    - Set confidence scores to 0.0 in fallback mode
    - _Requirements: 1.4_
  
  - [x] 5.3 Implement retrieval strategy selection
    - Set filter_first as default primary strategy
    - Enable semantic_search as fallback
    - Enable OSM when user location is available
    - Remove ENABLE_VECTOR_FALLBACK environment variable usage
    - Remove vibe keyword detection
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [x]* 5.4 Write property tests for Query_Planner
    - **Property 15: OSM Enabled with Location**
    - **Property 27: Proximity Keyword Detection**
    - **Property 28: Popularity Keyword Detection**
    - **Property 29: Business Hours Keyword Detection**
    - **Property 31: Query Plan Serialization Round-Trip**
    - **Validates: Requirements 9.3, 14.2, 14.3, 14.4, 14.6**
  
  - [x] 5.5 Update category keyword extraction
    - Extract category keywords directly from Intent_Classifier
    - Remove duplicate category keyword lists
    - _Requirements: 3.6, 7.2, 7.5_

- [x] 6. Implement tour planning intent routing
  - [x] 6.1 Add tour planning intent detection and routing
    - Detect tour_planning intent in Query_Planner
    - Route to tour planner component instead of standard retrieval
    - _Requirements: 5.6_
  
  - [x]* 6.2 Write property test for tour planning routing
    - **Property 11: Tour Planning Intent Routing**
    - **Validates: Requirements 5.6**

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Remove deprecated code and consolidate
  - [x] 8.1 Remove deprecated retriever implementation
    - Identify which retriever is deprecated (Two_Stage_Retriever or Deterministic_Retriever)
    - Remove deprecated retriever code
    - Update all imports to use UnifiedRetriever
    - _Requirements: 4.1, 4.4, 13.1_
  
  - [x] 8.2 Remove duplicate intent detection code
    - Remove keyword-based intent detection from Query_Planner
    - _Requirements: 1.5, 13.2_
  
  - [x] 8.3 Remove duplicate category matching logic
    - Remove category matching from Two_Stage_Retriever (if not already using shared module)
    - Remove category matching from Deterministic_Retriever (if not already using shared module)
    - Remove category matching from Query_Planner (if not already using shared module)
    - _Requirements: 3.4, 3.5, 13.3_
  
  - [x] 8.4 Remove deprecated environment variables and feature flags
    - Remove ENABLE_VECTOR_FALLBACK environment variable
    - Remove vibe keyword detection logic
    - _Requirements: 9.4, 9.5, 13.4, 13.5_
  
  - [x] 8.5 Update all imports and references
    - Update all files importing deprecated retrievers
    - Update all files importing duplicate modules
    - Verify no broken imports remain
    - _Requirements: 13.6_

- [x] 9. Implement backward compatibility support
  - [x] 9.1 Add Query_Plan backward compatibility
    - Ensure UnifiedRetriever processes legacy Query_Plan formats
    - Add migration logic for old slot names if needed
    - _Requirements: 4.5_
  
  - [x]* 9.2 Write property test for backward compatibility
    - **Property 6: Query Plan Backward Compatibility**
    - **Validates: Requirements 4.5**

- [x] 10. Implement comprehensive error handling
  - [x] 10.1 Add error handling for Intent_Classifier failures
    - Implement fallback logic with logging
    - Continue processing with default strategy
    - _Requirements: 1.4_
  
  - [x] 10.2 Add error handling for empty results
    - Log query and strategies attempted
    - Return empty result with metadata and suggestions
    - _Requirements: 2.1_
  
  - [x] 10.3 Add error handling for OSM API failures
    - Catch all OSM exceptions
    - Log errors with context
    - Return database results only
    - _Requirements: 12.7_
  
  - [x] 10.4 Add error handling for invalid Query_Plans
    - Validate Query_Plan before retrieval
    - Apply sensible defaults for invalid values
    - Log validation errors
    - _Requirements: 4.5_
  
  - [x] 10.5 Add error handling for database connection failures
    - Implement retry logic with exponential backoff
    - Fall back to OSM-only results if database unavailable
    - Log all database errors
    - _Requirements: 11.2_

- [x] 11. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x]* 12. Implement remaining property-based tests
  - [x]* 12.1 Write property test for multi-ranking support
    - **Property 5: Multi-Ranking Support**
    - **Validates: Requirements 4.3**
  
  - [x]* 12.2 Write unit tests for error handling
    - Test Intent_Classifier fallback behavior
    - Test OSM API failure handling
    - Test database connection failures
    - Test invalid Query_Plan handling
    - Test empty results handling

- [x] 13. Integration testing and wiring
  - [x]* 13.1 Write end-to-end integration tests
    - Test complete flow from user query to ranked results
    - Test proximity search flow
    - Test popularity search flow
    - Test verification flow
    - Test tour planning flow
    - Test OSM fallback integration
  
  - [x] 13.2 Verify all components are wired together
    - Query_Planner uses Intent_Classifier
    - Query_Planner creates Query_Plans for UnifiedRetriever
    - UnifiedRetriever uses CategoryMatcher, RankingEngine, PlaceCache
    - All error handling is in place
    - All logging is configured
    - _Requirements: 1.1, 2.1, 3.4, 3.5, 4.1, 11.4, 11.5_

- [x] 14. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Language detection improvements (v2.5)
  - [x] 15.1 Install and integrate `langdetect` library
    - Added `langdetect` to project dependencies
    - Import attempted once at `QueryPlanner.__init__` time; `_langdetect_available` flag set
    - _Requirements: 16.1, 16.2_
  
  - [x] 15.2 Replace `PT_BR_INDICATORS` list with `_PT_BR_KEYWORDS` set
    - Expanded from ~20 to 80+ unambiguous Portuguese words
    - Added slang/colloquial terms: `bora`, `massa`, `cara`, `tipo`, `sabe`
    - Added place-type nouns: `padaria`, `churrascaria`, `barbearia`, `petshop`, `balada`, etc.
    - _Requirements: 16.4, 16.5_
  
  - [x] 15.3 Rewrite `detect_language()` with three-step strategy
    - Step 1: honour explicit `language` parameter from client
    - Step 2: try `langdetect.detect()` — returns `pt-BR` if result is `"pt"`
    - Step 3: keyword intersection fallback against `_PT_BR_KEYWORDS`
    - _Requirements: 16.1, 16.2, 16.3, 16.6, 16.7_
  
  - [x] 15.4 Validate with Portuguese test suite
    - All 30 Portuguese complex queries now pass (up from 16/30 before fixes)
    - Tests cover typos, slang, mixed categories, colloquial phrasing

- [x] 16. Expanded category taxonomy (v2.5)
  - [x] 16.1 Add 8 new category domains to `SimpleTFIDFIntentClassifier`
    - `health`: clínica, farmácia, médico, UBS, UPA, dentista, exames, …
    - `beauty`: salão, cabeleireiro, manicure, barbearia, depilação, estética, …
    - `automotive`: oficina, mecânica, lava-jato, borracharia, funilaria, …
    - `wellness`: academia, spa, massagem, pilates, yoga, crossfit, fisioterapia, …
    - `pets`: petshop, veterinário, banho e tosa, adestramento, canil, …
    - `nightlife`: balada, boate, show ao vivo, karaokê, rooftop, open bar, …
    - `kids`: brinquedoteca, parquinho, buffet infantil, escolinha, …
    - `sports`: quadra, piscina, estádio, futebol, natação, ciclismo, …
    - _Requirements: 17.1, 17.2, 17.3–17.10_
  
  - [x] 16.2 Bump `MODEL_VERSION` from `"2.4"` to `"2.5"`
    - Forces invalidation of cached `.pkl` model file
    - Classifier retrains automatically on next startup
    - _Requirements: 17.11_
  
  - [x] 16.3 Consolidate duplicate fallback path in `extract_categories()`
    - Merged two separate keyword-scan fallback blocks into one clean path
    - Fallback now covers all 16+ category domains including new ones
    - _Requirements: 18.10_

- [x] 17. Improved filter extraction (v2.5)
  - [x] 17.1 Rewrite `extract_open_now()` with two-strategy approach
    - Strategy 1: direct phrase list check (language-agnostic, independent of primary intent)
    - Strategy 2: Intent_Classifier `business_hours` signal as secondary check
    - Covers PT-BR: `aberto agora`, `funcionando agora`, `aberto 24 horas`, `que esteja aberto`, `ainda aberto`, `aberto hoje`
    - Covers EN: `open now`, `currently open`, `open right now`, `still open`, `open today`
    - _Requirements: 18.1, 18.2, 18.3, 18.4_
  
  - [x] 17.2 Rewrite `extract_min_rating()` with PT-BR patterns + qualitative map
    - Added 10 PT-BR regex patterns: `nota acima de N`, `acima de N estrelas`, `pelo menos N estrelas`, `mínimo de N`, `N estrelas ou mais`, `no mínimo N`, `score >= N`
    - Added qualitative map: `altamente avaliado→4.5`, `bem avaliado→4.0`, `excelente→4.5`, `ótimo→4.0`, `highly rated→4.5`, `great→4.0`, etc.
    - _Requirements: 18.5, 18.6_
  
  - [x] 17.3 Rewrite `extract_price_max()` as language-agnostic
    - Removed language-conditional branching
    - Added PT-BR cheap keywords: `econômico`, `em conta`, `bom preço`, `acessível`, `custo-benefício`, `não muito caro`, `preço baixo`
    - Added luxury keywords (PT-BR + EN) mapping to `price_max=4.0`
    - _Requirements: 18.7, 18.8, 18.9_

- [x] 18. Validation test suites
  - [x] 18.1 Created `test_intent_system_validation.py` (13 tests, all passing)
    - Covers proximity, popularity, category extraction, filters, consistency, distance vs popularity tradeoff
    - Test location: Travessa Curuzu, 1475, Belém, PA (lat: -1.4557549, lon: -48.4901799)
  
  - [x] 18.2 Created `test_portuguese_complex_queries.py` (30 tests, all passing after v2.5 fixes)
    - Covers typos, mixed categories (3-4 simultaneously), colloquial/badly phrased sentences, regional slang
    - Before fixes: 16/30 passed; after fixes: 30/30 passed

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (31 total)
- Unit tests validate specific examples and edge cases
- The design uses Python, so all implementation should be in Python
- Filter-first architecture minimizes LLM calls by using deterministic filtering before LLM involvement
