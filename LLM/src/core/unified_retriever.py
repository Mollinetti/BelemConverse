"""
UnifiedRetriever: Consolidated retriever implementation.

This module consolidates Two_Stage_Retriever and Deterministic_Retriever into a single
unified retriever that handles all retrieval strategies:
- Filter-first retrieval (primary strategy)
- Semantic search (fallback only)
- OSM fallback (supplement when needed)

The retriever uses shared modules (CategoryMatcher, RankingEngine, PlaceCache) for
consistent behavior across all retrieval paths.

Validates: Requirements 4.1, 4.2, 4.3, 2.2, 2.3, 2.4
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .place_cache import PlaceCache
from .category_matcher import CategoryMatcher
from .ranking_engine import RankingEngine, RankingMode, Location

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """
    Result from retrieval operation.
    
    Contains ranked places and metadata about the retrieval process.
    """
    places: List[Dict[str, Any]]
    strategy_used: str  # 'filter_first', 'semantic_search', 'osm_fallback'
    osm_triggered: bool
    filters_applied: List[str]
    ranking_mode: str
    total_candidates: int


class UnifiedRetriever:
    """
    Unified retriever that consolidates all retrieval strategies.
    
    This retriever implements a clear hierarchy:
    1. Filter-First (Primary): Deterministic filtering and ranking
    2. Semantic Search (Fallback): Vector similarity when filter-first returns zero results
    3. OSM Fallback (Supplement): Real-time data when database results are insufficient
    
    The retriever delegates to shared modules for consistent behavior:
    - CategoryMatcher: Consistent category matching logic
    - RankingEngine: Consistent ranking across all modes
    - PlaceCache: Unified place data access
    """
    
    def __init__(
        self,
        place_cache: PlaceCache,
        category_matcher: CategoryMatcher,
        ranking_engine: RankingEngine,
        vector_store: Optional[Any] = None,
        osm_client: Optional[Any] = None
    ):
        """
        Initialize UnifiedRetriever with dependencies.
        
        Args:
            place_cache: Shared place data cache
            category_matcher: Shared category matching logic
            ranking_engine: Shared ranking logic
            vector_store: Optional vector store for semantic search
            osm_client: Optional OSM client for real-time fallback
        """
        self.place_cache = place_cache
        self.category_matcher = category_matcher
        self.ranking_engine = ranking_engine
        self.vector_store = vector_store
        self.osm_client = osm_client
        
        logger.info(
            "UnifiedRetriever initialized with "
            f"vector_store={'enabled' if vector_store else 'disabled'}, "
            f"osm_client={'enabled' if osm_client else 'disabled'}"
        )
    
    def retrieve(self, query_plan: Dict[str, Any]) -> RetrievalResult:
        """
        Retrieve and rank places based on query plan.
        
        This is the main orchestration method that:
        1. Attempts filter-first retrieval (primary strategy)
        2. Falls back to semantic search if filter-first returns zero results
        3. Supplements with OSM fallback if database results are insufficient
        4. Ranks results using the appropriate ranking mode
        
        Args:
            query_plan: Structured query plan from Query_Planner
            
        Returns:
            RetrievalResult with ranked places and metadata
        """
        logger.info(f"Starting retrieval for query plan: {query_plan.get('intent', 'unknown')}")
        
        # Extract key information from query plan
        slots = query_plan.get('slots', {})
        retrieval_strategy = query_plan.get('retrieval_strategy', 'structured_only')
        
        # Determine ranking mode based on intents and slots
        ranking_mode = self._determine_ranking_mode(query_plan)
        logger.info(f"Selected ranking mode: {ranking_mode}")
        
        # Extract user location if available
        user_location = self._extract_user_location(slots)
        
        # Step 1: Attempt filter-first retrieval (primary strategy)
        logger.info("Executing filter-first retrieval (primary strategy)")
        db_results = self._filter_first(query_plan)
        
        filters_applied = self._get_filters_applied(slots)
        strategy_used = 'filter_first'
        osm_triggered = False
        
        # Step 2: Fall back to semantic search if filter-first returns zero results
        if not db_results and self.vector_store and 'vector_fallback' in retrieval_strategy:
            logger.info("Filter-first returned zero results, falling back to semantic search")
            db_results = self._semantic_search(query_plan)
            strategy_used = 'semantic_search'
        
        # Step 3: Evaluate if OSM fallback should be triggered
        if self.osm_client and self._should_trigger_osm(db_results, query_plan):
            logger.info("Triggering OSM fallback to supplement database results")
            osm_results = self._osm_fallback(query_plan, db_results)
            
            if osm_results:
                # Merge OSM results with database results
                db_results.extend(osm_results)
                osm_triggered = True
                logger.info(f"Added {len(osm_results)} OSM results to database results")
        
        # Step 4: Rank results using the appropriate ranking mode
        ranked_results = self.ranking_engine.rank(
            places=db_results,
            mode=ranking_mode,
            user_location=user_location
        )
        
        logger.info(
            f"Retrieval complete: {len(ranked_results)} results, "
            f"strategy={strategy_used}, osm_triggered={osm_triggered}"
        )
        
        return RetrievalResult(
            places=ranked_results,
            strategy_used=strategy_used,
            osm_triggered=osm_triggered,
            filters_applied=filters_applied,
            ranking_mode=ranking_mode,
            total_candidates=len(db_results)
        )
    
    def _filter_first(self, query_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Apply deterministic filters to database.
        
        This method implements the filter-first retrieval strategy by applying
        filters in precedence order:
        1. open_now (business hours) - FIRST
        2. proximity (distance from user) - SECOND, with radius escalation (0.5km → 1km → 2km)
        3. category (place type) - THIRD
        4. price (price range) - FOURTH
        5. rating (minimum rating) - FIFTH
        
        Args:
            query_plan: Structured query plan
            
        Returns:
            List of places that match all filters
        """
        logger.info("Applying filter-first retrieval")
        
        slots = query_plan.get('slots', {})
        proximity_intent_detected = query_plan.get('proximity_intent_detected', False)
        user_location = self._extract_user_location(slots)
        
        # Start with all places
        candidates = self.place_cache.get_all()
        logger.debug(f"Starting with {len(candidates)} total places")
        
        # STEP 1: Filter by open_now (business hours) - FIRST
        open_now = slots.get('open_now')
        if open_now:
            logger.info("Step 1: Filtering by open_now (business hours)")
            candidates = self._filter_by_open_now(candidates)
            logger.info(f"After open_now filter: {len(candidates)} candidates")
        else:
            logger.info("Step 1: No open_now filter requested")
        
        # STEP 2: Filter by proximity with radius escalation - SECOND
        # ONLY if proximity intent was detected AND user location is available
        radius_used = None
        if user_location and proximity_intent_detected:
            logger.info("Step 2: Applying proximity filter with radius escalation")
            candidates, radius_used = self._filter_by_proximity_with_escalation(
                candidates, user_location, min_results=5
            )
            logger.info(f"After proximity filter (radius={radius_used}km): {len(candidates)} candidates")
        else:
            if not user_location:
                logger.info("Step 2: No user location - skipping proximity filter")
            elif not proximity_intent_detected:
                logger.info("Step 2: Proximity intent not detected - skipping proximity filter")
            else:
                logger.info("Step 2: Skipping proximity filter")
        
        # STEP 3: Filter by category - THIRD
        categories = slots.get('categories') or (
            [slots.get('place_type')] if slots.get('place_type') else None
        )
        if categories:
            logger.info(f"Step 3: Filtering by categories: {categories}")
            candidates = self._filter_by_category(candidates, categories)
            logger.info(f"After category filter: {len(candidates)} candidates")
        else:
            logger.info("Step 3: No category filter requested")
        
        # STEP 4: Filter by price - FOURTH
        price_range = slots.get('price_range')
        price_max = slots.get('price_max')
        if price_range or price_max is not None:
            logger.info(f"Step 4: Filtering by price (range={price_range}, max={price_max})")
            candidates = self._filter_by_price(candidates, price_range, price_max)
            logger.info(f"After price filter: {len(candidates)} candidates")
        else:
            logger.info("Step 4: No price filter requested")
        
        # STEP 5: Filter by rating - FIFTH
        min_rating = slots.get('min_rating')
        if min_rating is not None:
            logger.info(f"Step 5: Filtering by min_rating >= {min_rating}")
            candidates = self._filter_by_rating(candidates, min_rating)
            logger.info(f"After rating filter: {len(candidates)} candidates")
        else:
            logger.info("Step 5: No rating filter requested")
        
        # Calculate distances for all results (for display purposes)
        if user_location:
            candidates = self._add_distances(candidates, user_location)
        
        logger.info(f"Filter-first complete: {len(candidates)} candidates")
        return candidates
    
    def _filter_by_open_now(self, places: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter places by open_now status.
        
        Args:
            places: List of places to filter
            
        Returns:
            List of places that are currently open or have unknown status
        """
        from datetime import datetime
        from utils.business_hours_parser import BusinessHoursParser
        
        parser = BusinessHoursParser()
        now = datetime.now()
        
        open_places = []
        unknown_places = []
        
        for place in places:
            business_time_str = place.get('businessTime')
            if not business_time_str:
                unknown_places.append(place)
                continue
            
            try:
                business_hours = parser.parse(business_time_str)
                
                if business_hours.parse_error:
                    unknown_places.append(place)
                    continue
                
                # Check for "Open 24 hours"
                time_str_lower = business_time_str.lower()
                if '24' in time_str_lower and ('hour' in time_str_lower or 'hora' in time_str_lower):
                    open_places.append(place)
                    continue
                
                # Check if open now
                day_name = now.strftime('%A')
                current_time = now.time()
                
                if business_hours.is_open_at(day_name, current_time):
                    open_places.append(place)
                # Closed places are excluded
                
            except Exception as e:
                logger.debug(f"Error checking open_now for place {place.get('placeId')}: {e}")
                unknown_places.append(place)
        
        # Return open places first, then unknown (to give benefit of doubt)
        result = open_places + unknown_places
        logger.debug(f"Open filter: {len(open_places)} open, {len(unknown_places)} unknown")
        return result
    
    def _filter_by_proximity_with_escalation(
        self,
        places: List[Dict[str, Any]],
        user_location: Location,
        min_results: int = 5
    ) -> tuple[List[Dict[str, Any]], float]:
        """
        Filter places by proximity with radius escalation.
        
        Tries radii in sequence: 0.5km → 1km → 2km
        Stops when we have at least min_results or reach max radius.
        
        Args:
            places: List of places to filter
            user_location: User's location
            min_results: Minimum number of results to aim for
            
        Returns:
            Tuple of (filtered places, radius used in km)
        """
        RADIUS_SEQUENCE = [0.5, 1.0, 2.0]
        
        for radius_km in RADIUS_SEQUENCE:
            filtered = []
            
            for place in places:
                location = place.get('location', {})
                place_lat = location.get('lat')
                place_lng = location.get('lng')
                
                if place_lat is None or place_lng is None:
                    continue
                
                distance_km = self._haversine_distance(
                    user_location.latitude, user_location.longitude,
                    place_lat, place_lng
                )
                
                if distance_km <= radius_km:
                    filtered.append(place)
            
            logger.debug(f"Radius {radius_km}km: {len(filtered)} places within radius")
            
            # Stop if we have enough results or this is the last radius
            if len(filtered) >= min_results or radius_km == RADIUS_SEQUENCE[-1]:
                return filtered, radius_km
        
        # Fallback (shouldn't reach here)
        return places, RADIUS_SEQUENCE[-1]
    
    def _filter_by_category(
        self,
        places: List[Dict[str, Any]],
        categories: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Filter places by category using CategoryMatcher.
        
        Args:
            places: List of places to filter
            categories: List of category keywords to match
            
        Returns:
            List of places that match any category
        """
        filtered = []
        
        for place in places:
            if self.category_matcher.matches(place, categories):
                filtered.append(place)
        
        return filtered
    
    def _filter_by_price(
        self,
        places: List[Dict[str, Any]],
        price_range: Optional[str],
        price_max: Optional[int]
    ) -> List[Dict[str, Any]]:
        """
        Filter places by price range or maximum price.
        
        Args:
            places: List of places to filter
            price_range: Price range string (e.g., "$", "$$", "$$$")
            price_max: Maximum price level (1-4)
            
        Returns:
            List of places within price constraints
        """
        filtered = []
        
        # Convert price_range to numeric if provided
        price_level_map = {"$": 1, "$$": 2, "$$$": 3, "$$$$": 4}
        max_price = None
        
        if price_range and price_range in price_level_map:
            max_price = price_level_map[price_range]
        elif price_max is not None:
            max_price = price_max
        
        if max_price is None:
            return places  # No price filter
        
        for place in places:
            place_price = place.get('price')
            
            # Include places with no price info (benefit of doubt)
            if place_price is None:
                filtered.append(place)
                continue
            
            # Filter by max price
            if place_price <= max_price:
                filtered.append(place)
        
        return filtered
    
    def _filter_by_rating(
        self,
        places: List[Dict[str, Any]],
        min_rating: float
    ) -> List[Dict[str, Any]]:
        """
        Filter places by minimum rating.
        
        Args:
            places: List of places to filter
            min_rating: Minimum rating threshold
            
        Returns:
            List of places with rating >= min_rating
        """
        filtered = []
        
        for place in places:
            place_rating = place.get('totalScore')
            
            # Exclude places with no rating or below threshold
            if place_rating is not None and place_rating >= min_rating:
                filtered.append(place)
        
        return filtered
    
    def _add_distances(
        self,
        places: List[Dict[str, Any]],
        user_location: Location
    ) -> List[Dict[str, Any]]:
        """
        Add distance field to all places for display purposes.
        
        Args:
            places: List of places
            user_location: User's location
            
        Returns:
            List of places with distanceKm field added
        """
        for place in places:
            location = place.get('location', {})
            place_lat = location.get('lat')
            place_lng = location.get('lng')
            
            if place_lat is not None and place_lng is not None:
                distance_km = self._haversine_distance(
                    user_location.latitude, user_location.longitude,
                    place_lat, place_lng
                )
                place['distanceKm'] = distance_km
            else:
                place['distanceKm'] = None
        
        return places
    
    def _haversine_distance(
        self,
        lat1: float,
        lng1: float,
        lat2: float,
        lng2: float
    ) -> float:
        """
        Calculate Haversine distance in km between two points.
        
        Args:
            lat1, lng1: First point coordinates
            lat2, lng2: Second point coordinates
            
        Returns:
            Distance in kilometers
        """
        import math
        
        R = 6371  # Earth's radius in km
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def _semantic_search(self, query_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search (fallback only).
        
        This method is only called when filter-first returns zero results.
        It performs semantic search using vector embeddings and then re-ranks
        with structured filters.
        
        Args:
            query_plan: Structured query plan
            
        Returns:
            List of semantically similar places
        """
        logger.info("Executing semantic search fallback")
        
        if not self.vector_store:
            logger.warning("Semantic search requested but vector_store not available")
            return []
        
        # Extract query text
        query_text = query_plan.get('slots', {}).get('original_query', '')
        if not query_text:
            logger.warning("No query text available for semantic search")
            return []
        
        logger.info(f"Performing vector search for: '{query_text}'")
        
        # Stage 1: Perform vector similarity search
        try:
            # Get semantic candidates with scores
            # similarity_search_with_score returns (document, distance) tuples
            # where lower distance = more similar
            results = self.vector_store.similarity_search_with_score(
                query_text,
                k=50  # Get more candidates for re-ranking
            )
            
            if not results:
                logger.info("No semantic candidates found")
                return []
            
            logger.info(f"Retrieved {len(results)} semantic candidates")
            
            # Convert documents to place data and calculate similarity scores
            candidates = []
            for doc, distance in results:
                # Convert distance to similarity score: 1 / (1 + distance)
                similarity_score = 1.0 / (1.0 + distance)
                
                # Extract place data from document metadata
                place_data = doc.metadata if hasattr(doc, 'metadata') else {}
                
                # Get full place data from cache if we have a placeId
                place_id = place_data.get('placeId')
                if place_id:
                    full_place = self.place_cache.get_by_id(place_id)
                    if full_place:
                        place_data = full_place
                
                if place_data:
                    # Add semantic score to place data for re-ranking
                    place_data['_semantic_score'] = similarity_score
                    candidates.append(place_data)
            
            logger.info(f"Extracted {len(candidates)} place candidates")
            
            if not candidates:
                return []
            
            # Stage 2: Re-rank with structured filters
            logger.info("Re-ranking candidates with structured filters")
            
            # Apply category filter if specified
            slots = query_plan.get('slots', {})
            categories = slots.get('categories', [])
            if categories:
                filtered_candidates = []
                for place in candidates:
                    if self.category_matcher.matches(place, categories):
                        filtered_candidates.append(place)
                logger.info(f"Category filter: {len(candidates)} → {len(filtered_candidates)} places")
                candidates = filtered_candidates
            
            if not candidates:
                logger.info("No candidates after category filtering")
                return []
            
            # Apply location scoring if user location available
            user_location = self._extract_user_location(slots)
            if user_location:
                # Calculate distances
                candidates = self._add_distances(candidates, user_location)
            
            # Calculate composite scores for re-ranking
            # Weights: 40% semantic, 30% rating, 20% popularity, 10% proximity
            for place in candidates:
                semantic_score = place.get('_semantic_score', 0.0)
                
                # Normalize rating (0-5 scale to 0-1)
                rating_score = place.get('totalScore', 0.0) / 5.0
                
                # Calculate popularity score (Bayesian average)
                reviews = place.get('reviewsCount', 0)
                rating = place.get('totalScore', 0.0)
                # Use global average of 4.0 and minimum 10 reviews
                popularity_score = (reviews * rating + 10 * 4.0) / (reviews + 10) / 5.0
                
                # Normalize proximity (closer = higher score)
                proximity_score = 0.0
                if user_location and 'distanceKm' in place:
                    distance = place['distanceKm']
                    # Score decreases with distance: 1.0 at 0km, 0.5 at 2km, 0.0 at 5km+
                    proximity_score = max(0.0, 1.0 - (distance / 5.0))
                
                # Calculate composite score
                composite_score = (
                    0.40 * semantic_score +
                    0.30 * rating_score +
                    0.20 * popularity_score +
                    0.10 * proximity_score
                )
                
                place['_composite_score'] = composite_score
            
            # Sort by composite score
            candidates.sort(key=lambda p: p.get('_composite_score', 0.0), reverse=True)
            
            # Remove temporary scoring fields
            for place in candidates:
                place.pop('_semantic_score', None)
                place.pop('_composite_score', None)
            
            logger.info(f"Semantic search returning {len(candidates)} re-ranked places")
            
            # Log top results for debugging
            if candidates:
                top = candidates[0]
                logger.info(
                    f"Top semantic result: {top.get('title', 'Unknown')} "
                    f"(rating: {top.get('totalScore', 'N/A')}, "
                    f"reviews: {top.get('reviewsCount', 'N/A')})"
                )
            
            return candidates
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}", exc_info=True)
            return []
    
    def _osm_fallback(
        self,
        query_plan: Dict[str, Any],
        db_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Supplement with OSM results if needed.
        
        This method queries OpenStreetMap for real-time place data when
        database results are insufficient. OSM results are merged with
        database results and ranked together.
        
        Args:
            query_plan: Structured query plan
            db_results: Current database results
            
        Returns:
            List of places from OSM
        """
        logger.info("Executing OSM fallback")
        
        if not self.osm_client:
            logger.warning("OSM fallback requested but osm_client not available")
            return []
        
        slots = query_plan.get('slots', {})
        user_location = self._extract_user_location(slots)
        
        if not user_location:
            logger.warning("OSM fallback requested but no user location available")
            return []
        
        # Extract query and categories
        original_query = query_plan.get('original_query', '')
        categories = slots.get('categories', [])
        if not categories:
            place_type = slots.get('place_type')
            if place_type:
                categories = [place_type]
        
        # Determine search radius (default 2km, wider for verification)
        intents = query_plan.get('intents', {})
        is_verification = intents.get('verification', 0) > 0.5
        radius_meters = 10000 if is_verification else 2000
        
        logger.info(
            f"Querying OSM: query='{original_query}', categories={categories}, "
            f"location=({user_location.latitude}, {user_location.longitude}), "
            f"radius={radius_meters}m"
        )
        
        try:
            # Query OSM using the realtime search client
            from langchain_core.documents import Document
            
            osm_documents = self.osm_client.search(
                query=original_query,
                user_coordinates=(user_location.latitude, user_location.longitude),
                radius=radius_meters,
                categories=categories
            )
            
            if not osm_documents:
                logger.info("OSM search returned no results")
                return []
            
            logger.info(f"OSM search returned {len(osm_documents)} results")
            
            # Convert OSM Documents to place dicts
            osm_places = []
            for doc in osm_documents:
                place_dict = self._document_to_place_dict(doc)
                if place_dict:
                    osm_places.append(place_dict)
            
            # Deduplicate OSM results against database results
            unique_osm_places = self._deduplicate_osm_results(db_results, osm_places)
            
            logger.info(
                f"OSM fallback complete: {len(osm_places)} total, "
                f"{len(unique_osm_places)} unique after deduplication"
            )
            
            return unique_osm_places
            
        except Exception as e:
            logger.error(f"OSM fallback failed: {e}", exc_info=True)
            return []
    
    def _should_trigger_osm(
        self,
        db_results: List[Dict[str, Any]],
        query_plan: Dict[str, Any]
    ) -> bool:
        """
        Determine if OSM fallback should be triggered.
        
        OSM fallback is triggered when:
        1. Database results are empty
        2. All database result scores are below 0.3 (low quality)
        3. Nearest database result is beyond 5km AND proximity intent detected
        4. Verification intent detected AND specific place name not found
        
        Args:
            db_results: Current database results
            query_plan: Structured query plan
            
        Returns:
            True if OSM fallback should be triggered
        """
        slots = query_plan.get('slots', {})
        intents = query_plan.get('intents', {})
        user_location = self._extract_user_location(slots)
        
        # OSM requires user location
        if not user_location:
            logger.debug("OSM not triggered: no user location available")
            return False
        
        # Condition 1: Empty database results
        if not db_results:
            logger.info("OSM trigger condition met: empty database results")
            return True
        
        # Condition 2: All scores below 0.3 (low quality)
        # Check if places have totalScore field
        scores = [place.get('totalScore', 0) for place in db_results if place.get('totalScore') is not None]
        if scores and all(score < 0.3 for score in scores):
            max_score = max(scores) if scores else 0
            logger.info(f"OSM trigger condition met: low quality scores (max={max_score:.2f})")
            return True
        
        # Condition 3: Nearest result beyond 5km AND proximity intent detected
        proximity_intent_detected = query_plan.get('proximity_intent_detected', False)
        if proximity_intent_detected:
            # Check if any result has distance_km field
            distances = [
                place.get('distance_km', float('inf'))
                for place in db_results
                if 'distance_km' in place
            ]
            
            if distances:
                nearest_distance = min(distances)
                if nearest_distance > 5.0:
                    logger.info(
                        f"OSM trigger condition met: nearest result is {nearest_distance:.1f}km "
                        f"away with proximity intent"
                    )
                    return True
        
        # Condition 4: Verification intent AND specific place name not found
        verification_intent = intents.get('verification', 0)
        if verification_intent > 0.5:
            # Extract place name from query
            original_query = query_plan.get('original_query', '')
            extracted_name = self._extract_place_name_from_query(original_query)
            
            if extracted_name:
                # Check if the name is found in results
                name_found = False
                for place in db_results:
                    title = place.get('title', '').lower()
                    title_formatted = place.get('titleFormatted', '').lower()
                    extracted_lower = extracted_name.lower()
                    
                    # Simple substring match
                    if extracted_lower in title or extracted_lower in title_formatted:
                        name_found = True
                        break
                
                if not name_found:
                    logger.info(
                        f"OSM trigger condition met: verification intent with "
                        f"place name '{extracted_name}' not found"
                    )
                    return True
        
        logger.debug("OSM not triggered: database results are satisfactory")
        return False
    
    def _determine_ranking_mode(self, query_plan: Dict[str, Any]) -> str:
        """
        Determine ranking mode based on query plan intents and slots.
        
        Ranking mode selection:
        - location intent → distance ranking
        - popularity intent → popularity ranking
        - business_hours intent → best_match ranking
        - price intent → best_match ranking
        - default → best_match ranking
        
        Args:
            query_plan: Structured query plan
            
        Returns:
            Ranking mode string
        """
        slots = query_plan.get('slots', {})
        debug = query_plan.get('debug', {})
        
        # Check for explicit sort preference in slots
        sort_pref = slots.get('sort_preference', '').lower()
        
        if sort_pref == 'distance' or 'distance' in sort_pref:
            return RankingMode.DISTANCE
        elif sort_pref == 'rating' or 'rating' in sort_pref:
            return RankingMode.RATING
        elif sort_pref == 'popularity' or 'popular' in sort_pref:
            return RankingMode.POPULARITY
        
        # Check debug info for detected intents
        detected_intents = debug.get('detected_intents', [])
        
        if 'location' in detected_intents or 'proximity' in detected_intents:
            return RankingMode.DISTANCE
        elif 'popularity' in detected_intents:
            return RankingMode.POPULARITY
        
        # Default to best_match for balanced results
        return RankingMode.BEST_MATCH
    
    def _extract_user_location(self, slots: Dict[str, Any]) -> Optional[Location]:
        """
        Extract user location from query plan slots.
        
        Args:
            slots: Query plan slots
            
        Returns:
            Location object or None if not available
        """
        user_loc = slots.get('user_location')
        
        if not user_loc:
            return None
        
        if isinstance(user_loc, dict):
            # Use explicit None check to handle 0.0 coordinates correctly
            lat = user_loc.get('lat') if user_loc.get('lat') is not None else user_loc.get('latitude')
            lng = user_loc.get('lng') if user_loc.get('lng') is not None else user_loc.get('longitude')
            
            if lat is not None and lng is not None:
                return Location(latitude=float(lat), longitude=float(lng))
        
        return None
    
    def _get_filters_applied(self, slots: Dict[str, Any]) -> List[str]:
        """
        Get list of filters that were applied based on slots.
        
        Args:
            slots: Query plan slots
            
        Returns:
            List of filter names
        """
        filters = []
        
        if slots.get('open_now'):
            filters.append('open_now')
        
        if slots.get('proximity_radius'):
            filters.append('proximity')
        
        if slots.get('categories') or slots.get('place_type'):
            filters.append('category')
        
        if slots.get('price_range') or slots.get('price_max') is not None:
            filters.append('price')
        
        if slots.get('min_rating'):
            filters.append('rating')
        
        return filters
    
    def _document_to_place_dict(self, doc) -> Optional[Dict[str, Any]]:
        """
        Convert a LangChain Document (from OSM) to a place dictionary.
        
        Args:
            doc: LangChain Document object
            
        Returns:
            Place dictionary or None if conversion fails
        """
        try:
            metadata = doc.metadata if hasattr(doc, 'metadata') else {}
            
            # Extract required fields
            title = metadata.get('title', '')
            if not title:
                return None
            
            # Build place dict matching the format used by UnifiedRetriever
            place_dict = {
                'title': title,
                'titleFormatted': title,  # OSM doesn't have formatted title
                'category': [metadata.get('categoryName', 'Unknown')],
                'location': {
                    'lat': metadata.get('location/lat'),
                    'lng': metadata.get('location/lng')
                },
                'totalScore': metadata.get('totalScore'),  # Usually None for OSM
                'reviewsCount': metadata.get('reviewsCount', 0),
                'priceRange': metadata.get('priceRange'),
                'address': metadata.get('address', ''),
                'phone': metadata.get('phone', ''),
                'website': metadata.get('website', ''),
                'businessTime': metadata.get('businessTime', ''),
                'distance_km': metadata.get('distance_km'),
                'data_source': metadata.get('data_source', 'osm_realtime'),
                'osm_id': metadata.get('osm_id'),
                'osm_type': metadata.get('osm_type'),
            }
            
            return place_dict
            
        except Exception as e:
            logger.warning(f"Failed to convert Document to place dict: {e}")
            return None
    
    def _deduplicate_osm_results(
        self,
        db_results: List[Dict[str, Any]],
        osm_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove OSM results that are duplicates of database results.
        
        Deduplication is based on:
        1. Exact title match (case-insensitive)
        2. Similar location (within 50 meters)
        
        Args:
            db_results: Database results
            osm_results: OSM results
            
        Returns:
            Deduplicated OSM results
        """
        if not db_results:
            return osm_results
        
        unique_osm = []
        
        for osm_place in osm_results:
            is_duplicate = False
            osm_title = osm_place.get('title', '').lower().strip()
            osm_loc = osm_place.get('location', {})
            osm_lat = osm_loc.get('lat')
            osm_lng = osm_loc.get('lng')
            
            # Skip OSM results without location data
            if osm_lat is None or osm_lng is None:
                logger.debug(f"Skipping OSM result without location: {osm_title}")
                continue
            
            for db_place in db_results:
                db_title = db_place.get('title', '').lower().strip()
                db_title_formatted = db_place.get('titleFormatted', '').lower().strip()
                
                # Check title match
                if osm_title and (osm_title == db_title or osm_title == db_title_formatted):
                    logger.debug(f"Duplicate by title: {osm_title}")
                    is_duplicate = True
                    break
                
                # Check location proximity (within 50 meters)
                db_loc = db_place.get('location', {})
                db_lat = db_loc.get('lat')
                db_lng = db_loc.get('lng')
                
                if db_lat is not None and db_lng is not None:
                    distance_m = self._haversine_distance(
                        osm_lat, osm_lng, db_lat, db_lng
                    ) * 1000  # Convert km to meters
                    
                    if distance_m < 50:  # Within 50 meters
                        logger.debug(
                            f"Duplicate by proximity: {osm_title} is {distance_m:.1f}m "
                            f"from {db_title}"
                        )
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                unique_osm.append(osm_place)
        
        logger.info(
            f"Deduplication: {len(osm_results)} OSM results, "
            f"{len(unique_osm)} unique after removing duplicates"
        )
        
        return unique_osm
    
    def _extract_place_name_from_query(self, query: str) -> Optional[str]:
        """
        Extract a specific place name from the query if present.
        
        This is used for verification queries to check if a specific
        place name is mentioned.
        
        Args:
            query: User query
            
        Returns:
            Extracted place name or None
        """
        import re
        
        # Patterns for extracting place names (in order of specificity)
        patterns = [
            r'"([^"]+)"',  # Quoted names - highest priority
            r"'([^']+)'",  # Single-quoted names
            r'(?:called|named|chamad[ao])\s+([\w\s]+?)(?:\s+(?:is|está|still|ainda|open|aberto|closed|fechado)|$)',
            # Extract after "where is" - matches Unicode word characters
            r'(?:where is|onde fica|cadê)\s+(?:the\s+)?([\w\s]+?)(?:\s*\?|$)',
        ]
        
        for i, pattern in enumerate(patterns):
            # Use IGNORECASE for quoted patterns, otherwise case-sensitive to catch proper nouns
            flags = re.IGNORECASE | re.UNICODE if i < 2 else re.UNICODE
            match = re.search(pattern, query, flags)
            if match:
                name = match.group(1).strip()
                # Filter out generic terms and very short names
                generic_terms = ['a', 'an', 'the', 'um', 'uma', 'o', 'restaurant', 'restaurants', 
                                'cafe', 'cafes', 'hotel', 'hotels', 'bar', 'bars', 'nearby', 'near']
                if len(name) > 2 and name.lower() not in generic_terms:
                    # Additional check: don't extract if it's just generic category words
                    words = name.lower().split()
                    if not all(word in generic_terms for word in words):
                        return name
        
        return None
