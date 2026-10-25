"""
UnifiedRetriever: Consolidated retriever implementation.

Filter-first retrieval over the catalog: deterministic filtering, then ranking.
It uses shared modules (CategoryMatcher, RankingEngine, PlaceCache).

Validates: Requirements 4.1, 4.2, 4.3, 2.2, 2.3, 2.4
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from belem_converse.cities import get_city_config

from .category_matcher import CategoryMatcher
from .place_cache import PlaceCache
from .ranking_engine import Location, RankingEngine, RankingMode

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """
    Result from retrieval operation.
    
    Contains ranked places and metadata about the retrieval process.
    """
    places: list[dict[str, Any]]
    strategy_used: str  # always 'filter_first'
    filters_applied: list[str]
    ranking_mode: str
    total_candidates: int


class UnifiedRetriever:
    """
    Filter-first retriever: deterministic filtering and ranking.

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
    ):
        """
        Initialize UnifiedRetriever with dependencies.
        
        Args:
            place_cache: Shared place data cache
            category_matcher: Shared category matching logic
            ranking_engine: Shared ranking logic
        """
        self.place_cache = place_cache
        self.category_matcher = category_matcher
        self.ranking_engine = ranking_engine
        # "Open now" is judged on the city's clock, not the server's (UTC).
        self.timezone = ZoneInfo(get_city_config().timezone)
        
        logger.info("UnifiedRetriever initialized")
    
    def retrieve(self, query_plan: dict[str, Any]) -> RetrievalResult:
        """
        Retrieve and rank places based on query plan.
        
        This is the main orchestration method that:
        1. Runs filter-first retrieval
        2. Ranks results using the appropriate ranking mode
        
        Args:
            query_plan: Structured query plan from Query_Planner
            
        Returns:
            RetrievalResult with ranked places and metadata
        """
        logger.info(f"Starting retrieval for query plan: {query_plan.get('intent', 'unknown')}")
        
        # Extract key information from query plan
        slots = query_plan.get('slots', {})
        
        # Determine ranking mode based on intents and slots
        ranking_mode = self._determine_ranking_mode(query_plan)
        logger.info(f"Selected ranking mode: {ranking_mode}")
        
        # Extract user location if available
        user_location = self._extract_user_location(slots)
        
        db_results = self._filter_first(query_plan)
        filters_applied = self._get_filters_applied(slots)
        strategy_used = 'filter_first'

        # Rank results using the appropriate ranking mode
        ranked_results = self.ranking_engine.rank(
            places=db_results,
            mode=ranking_mode,
            user_location=user_location
        )
        # Places whose main category was asked for come first, then places
        # matched only by a secondary tag (an açaí shop also tagged
        # "Restaurant"); within each, open before unknown hours. The sort is
        # stable, so each group keeps its ranked order.
        asked = self._asked_categories(slots)

        def secondary_only(place: dict[str, Any]) -> bool:
            main = place.get('categoryName')
            return bool(asked and main) and not self.category_matcher.matches(
                {'categories': [main]}, asked
            )

        ranked_results.sort(
            key=lambda p: (secondary_only(p), p.get('openNowStatus') == 'unknown')
        )

        logger.info(
            f"Retrieval complete: {len(ranked_results)} results, "
            f"strategy={strategy_used}"
        )
        
        return RetrievalResult(
            places=ranked_results,
            strategy_used=strategy_used,
            filters_applied=filters_applied,
            ranking_mode=ranking_mode,
            total_candidates=len(db_results)
        )
    
    def _filter_first(self, query_plan: dict[str, Any]) -> list[dict[str, Any]]:
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
        categories = self._asked_categories(slots)
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
    
    @staticmethod
    def _asked_categories(slots: dict[str, Any]) -> list[str] | None:
        """The categories a plan asks for: its categories, else its place types."""
        # The planner gives place_type as a list; wrapping it again ([[...]])
        # crashed the category matcher for questions with no category words.
        place_type = slots.get('place_type')
        if isinstance(place_type, str):
            place_type = [place_type]
        return slots.get('categories') or place_type or None

    def _filter_by_open_now(self, places: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Judge each place's businessTime against the current time in the city.

        Returns copies labelled ``openNowStatus``: "open" places first, then
        "unknown" (no or unparseable hours, given the benefit of the doubt).
        Closed places are dropped. Cached places are never modified.
        """
        from belem_converse.utils.business_hours_parser import BusinessHours, BusinessHoursParser

        parser = BusinessHoursParser()
        now = datetime.now(self.timezone)
        day_name = BusinessHours.DAY_NAMES[now.weekday()]  # not strftime: locale-proof
        current_time = now.time()

        open_places = []
        unknown_places = []

        for place in places:
            business_time_str = place.get('businessTime')
            if not business_time_str:
                unknown_places.append({**place, 'openNowStatus': 'unknown'})
                continue

            try:
                business_hours = parser.parse(business_time_str)
                if business_hours.parse_error:
                    unknown_places.append({**place, 'openNowStatus': 'unknown'})
                elif business_hours.is_open_at(day_name, current_time):
                    open_places.append({**place, 'openNowStatus': 'open'})
                # Closed places are excluded
            except Exception as e:
                logger.debug(f"Error checking open_now for place {place.get('placeId')}: {e}")
                unknown_places.append({**place, 'openNowStatus': 'unknown'})

        logger.debug(f"Open filter: {len(open_places)} open, {len(unknown_places)} unknown")
        return open_places + unknown_places

    def _filter_by_proximity_with_escalation(
        self,
        places: list[dict[str, Any]],
        user_location: Location,
        min_results: int = 5
    ) -> tuple[list[dict[str, Any]], float]:
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
        places: list[dict[str, Any]],
        categories: list[str]
    ) -> list[dict[str, Any]]:
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
        places: list[dict[str, Any]],
        price_range: str | None,
        price_max: int | None
    ) -> list[dict[str, Any]]:
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
        places: list[dict[str, Any]],
        min_rating: float
    ) -> list[dict[str, Any]]:
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
        places: list[dict[str, Any]],
        user_location: Location
    ) -> list[dict[str, Any]]:
        """
        Add distance field to all places for display purposes.
        
        Args:
            places: List of places
            user_location: User's location
            
        Returns:
            Copies of the places with a distanceKm field. The input dicts are
            the shared catalog, so they are never written to: one visitor's
            distances must not show up in another visitor's results.
        """
        annotated = []
        for place in places:
            location = place.get('location') or {}
            place_lat = location.get('lat')
            place_lng = location.get('lng')

            distance_km = None
            if place_lat is not None and place_lng is not None:
                distance_km = self._haversine_distance(
                    user_location.latitude, user_location.longitude,
                    place_lat, place_lng
                )
            annotated.append({**place, 'distanceKm': distance_km})
        return annotated
    
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
    
    def _determine_ranking_mode(self, query_plan: dict[str, Any]) -> str:
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
    
    def _extract_user_location(self, slots: dict[str, Any]) -> Location | None:
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
    
    def _get_filters_applied(self, slots: dict[str, Any]) -> list[str]:
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
