"""
Tour Planner Module for BelemConverse.

Creates optimized day tour itineraries considering:
- Geographic proximity (TSP optimization using greedy nearest neighbor)
- Business hours constraints
- User preferences (categories, duration)
- Time slot assignments

Medium complexity implementation as per requirements.
"""

import logging
import math
from datetime import datetime, time, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from utils.business_hours_parser import BusinessHoursParser, BusinessHours

logger = logging.getLogger(__name__)


@dataclass
class TourStop:
    """Represents a single stop in the tour itinerary."""
    place_id: str
    name: str
    category: str
    address: str
    coordinates: Tuple[float, float]
    rating: float
    review_count: int
    business_hours: Optional[BusinessHours]
    
    # Schedule info (filled during planning)
    arrival_time: Optional[time] = None
    departure_time: Optional[time] = None
    duration_minutes: int = 60  # Default stay duration
    travel_time_to_next: int = 0  # Minutes to next stop
    distance_to_next: float = 0.0  # km to next stop
    
    # Additional info
    phone: str = ""
    website: str = ""
    
    def is_open_at(self, check_time: time) -> bool:
        """Check if this stop is open at the given time."""
        if self.business_hours is None:
            return True  # Assume open if no hours data
        return self.business_hours.is_open_at(
            datetime.now().strftime('%A'), 
            check_time
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'category': self.category,
            'address': self.address,
            'coordinates': self.coordinates,
            'rating': self.rating,
            'review_count': self.review_count,
            'arrival_time': self.arrival_time.strftime('%H:%M') if self.arrival_time else None,
            'departure_time': self.departure_time.strftime('%H:%M') if self.departure_time else None,
            'duration_minutes': self.duration_minutes,
            'travel_time_to_next': self.travel_time_to_next,
            'distance_to_next': self.distance_to_next
        }


@dataclass
class TourItinerary:
    """Complete tour itinerary for a day."""
    stops: List[TourStop] = field(default_factory=list)
    start_time: time = field(default_factory=lambda: time(9, 0))
    end_time: Optional[time] = None
    total_distance_km: float = 0.0
    total_duration_minutes: int = 0
    day_of_week: str = ""
    user_start_coordinates: Optional[Tuple[float, float]] = None
    
    def add_stop(self, stop: TourStop) -> None:
        """Add a stop to the itinerary."""
        self.stops.append(stop)
        self._recalculate_totals()
    
    def _recalculate_totals(self) -> None:
        """Recalculate total distance and duration."""
        self.total_distance_km = sum(s.distance_to_next for s in self.stops)
        self.total_duration_minutes = sum(
            s.duration_minutes + s.travel_time_to_next for s in self.stops
        )
    
    def to_context_string(self) -> str:
        """Convert itinerary to context string for LLM."""
        lines = []
        lines.append(f"Tour Itinerary for {self.day_of_week}")
        lines.append(f"Start Time: {self.start_time.strftime('%I:%M %p')}")
        lines.append(f"Number of Stops: {len(self.stops)}")
        lines.append(f"Total Distance: {self.total_distance_km:.2f} km")
        lines.append(f"Estimated Duration: {self.total_duration_minutes // 60}h {self.total_duration_minutes % 60}m")
        lines.append("")
        
        for i, stop in enumerate(self.stops, 1):
            lines.append(f"Stop {i}: {stop.name}")
            lines.append(f"  Category: {stop.category}")
            lines.append(f"  Address: {stop.address}")
            if stop.arrival_time:
                lines.append(f"  Arrival: {stop.arrival_time.strftime('%I:%M %p')}")
            if stop.departure_time:
                lines.append(f"  Departure: {stop.departure_time.strftime('%I:%M %p')}")
            lines.append(f"  Suggested Duration: {stop.duration_minutes} minutes")
            lines.append(f"  Rating: {stop.rating}★ ({stop.review_count} reviews)")
            if stop.travel_time_to_next > 0 and i < len(self.stops):
                lines.append(f"  Travel to next: ~{stop.travel_time_to_next} min ({stop.distance_to_next:.2f} km)")
            lines.append("")
        
        if self.end_time:
            lines.append(f"Estimated End Time: {self.end_time.strftime('%I:%M %p')}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'stops': [s.to_dict() for s in self.stops],
            'start_time': self.start_time.strftime('%H:%M'),
            'end_time': self.end_time.strftime('%H:%M') if self.end_time else None,
            'total_distance_km': self.total_distance_km,
            'total_duration_minutes': self.total_duration_minutes,
            'day_of_week': self.day_of_week
        }
    
    def __str__(self) -> str:
        return self.to_context_string()


class TourPlanner:
    """
    Plans optimized tour itineraries.
    
    Uses greedy nearest-neighbor algorithm for route optimization
    and considers business hours for scheduling.
    """
    
    # Default durations by category (minutes)
    CATEGORY_DURATIONS = {
        # Food & Drink
        'restaurant': 90,
        'cafe': 45,
        'bar': 60,
        'acai': 30,  # Açaí stops are quick
        'açaí': 30,
        'ice cream': 30,
        'sorveteria': 30,
        # Tourist attractions
        'tourist_attraction': 90,
        'museum': 120,
        'park': 60,
        'beach': 120,
        'praia': 120,
        'church': 30,
        'igreja': 30,
        'cathedral': 45,
        'catedral': 45,
        'monument': 20,
        'monumento': 20,
        'statue': 15,
        'memorial': 20,
        'plaza': 30,
        'praça': 30,
        'square': 30,
        'fortress': 60,
        'fortaleza': 60,
        'fort': 60,
        'forte': 60,
        'ruins': 45,
        'ruínas': 45,
        'historical': 60,
        'histórico': 60,
        'garden': 45,
        'jardim': 45,
        'botanical': 60,
        'theater': 90,
        'teatro': 90,
        'cultural center': 60,
        'market': 90,  # Ver-o-Peso type markets
        'mercado': 90,
        # Other
        'shopping': 90,
        'default': 60
    }
    
    # Tourist attraction category aliases for flexible matching
    TOURIST_CATEGORIES = {
        'museum', 'museu', 'park', 'parque', 'church', 'igreja', 'cathedral', 'catedral',
        'monument', 'monumento', 'fortress', 'fortaleza', 'fort', 'forte', 'ruins', 'ruínas',
        'beach', 'praia', 'plaza', 'praça', 'square', 'largo', 'theater', 'teatro',
        'garden', 'jardim', 'botanical', 'botânico', 'historical', 'histórico', 'heritage',
        'memorial', 'statue', 'estátua', 'cultural', 'tourist_attraction', 'attraction',
        'landmark', 'waterfront', 'orla', 'pier', 'dock', 'doca', 'port', 'porto',
        'island', 'ilha', 'zoo', 'zoológico', 'chapel', 'capela', 'temple', 'templo',
        'monastery', 'mosteiro', 'convent', 'convento', 'archaeological', 'arqueológico'
    }
    
    # Açaí category aliases for strict matching
    ACAI_CATEGORIES = {
        'açaí', 'acai', 'açai', 'acaí', 'açaí shop', 'acai shop', 'açaizeiro', 'acaizeiro',
        'açaí place', 'acai place', 'açaí spot', 'acai spot'
    }
    
    # Categories to EXCLUDE from tourist attraction searches
    TOURIST_EXCLUSIONS = {
        # Hotels and lodging (tourists don't visit hotels as attractions)
        'hotel', 'motel', 'hostel', 'pousada', 'inn', 'resort', 'lodging', 'accommodation',
        'hospedagem', 'albergue', 'bed and breakfast',
        # Bars, pubs, restaurants (NOT tourist attractions, even if named "Palácio do bar")
        'bar', 'pub', 'boteco', 'brazilian boteco', 'cocktail bar', 'wine bar', 'beer bar',
        'restaurant', 'restaurante', 'lunch restaurant', 'dinner', 'steakhouse', 'churrascaria',
        'cafe', 'cafeteria', 'coffee shop', 'bakery', 'padaria', 'confeitaria',
        'açaí', 'acai', 'ice cream', 'sorveteria', 'sorvete',
        # Shops and retail (NOT tourist attractions)
        'shop', 'loja', 'store', 'chocolate shop', 'chocolateria', 'candy', 'doces',
        'gift shop', 'souvenir', 'supermarket', 'supermercado', 'grocery',
        'boutique', 'jewelry', 'joalheria', 'perfume', 'cosmetics',
        # Sports venues (not tourist attractions)
        'sports bar', 'sports pub', 'gym', 'academia', 'fitness', 'sports club',
        'ginásio', 'ginasio', 'estádio', 'estadio', 'arena',
        # Fast food and casual dining
        'fast food', 'hamburger', 'pizza', 'pizzaria', 'sushi', 'lanchonete',
        'convenience store', 'loja de conveniência', 'gas station', 'posto de gasolina',
        # Generic services
        'hair salon', 'salão', 'barbershop', 'barbearia', 'clinic', 'clínica',
        'pharmacy', 'farmácia', 'dentist', 'dentista', 'hospital',
        'bank', 'banco', 'atm', 'caixa eletrônico',
        # Shopping malls and generic stores
        'clothing store', 'loja de roupas', 'shoe store', 'sapataria',
        'electronics', 'eletrônicos', 'cell phone', 'celular',
        'shopping center', 'shopping mall', 'mall'
    }
    
    # Famous tourist markets/places that should be included despite category
    FAMOUS_TOURIST_SPOTS = {
        'ver-o-peso', 'ver o peso', 'mercado ver-o-peso', 'mercado ver o peso',
        'estação das docas', 'estacao das docas', 'mangal das garças', 'mangal das garcas',
        'bosque rodrigues alves', 'theatro da paz', 'teatro da paz',
        'forte do presépio', 'forte do castelo', 'feliz lusitânia',
        'basílica de nazaré', 'basilica de nazare', 'catedral da sé',
        'palácio lauro sodré', 'museu de arte sacra', 'museu emílio goeldi',
        'casa das onze janelas', 'portal da amazônia'
    }
    
    # Walking speed in km/h
    WALKING_SPEED = 4.5
    
    def __init__(self, data_loader):
        """
        Initialize the tour planner.
        
        Args:
            data_loader: DataLoader for accessing place data
        """
        self.data_loader = data_loader
        self.hours_parser = BusinessHoursParser()
        
        # Cache for place data
        self._places_cache: Optional[List[Dict[str, Any]]] = None
    
    def _load_places(self) -> List[Dict[str, Any]]:
        """Load all places from data loader."""
        if self._places_cache is None:
            self._places_cache = self.data_loader.load_all_places()
        return self._places_cache
    
    def plan_tour(
        self,
        user_coordinates: Tuple[float, float],
        duration_hours: int = 8,
        start_time: str = "09:00",
        categories: Optional[List[str]] = None,
        num_stops: int = 5,
        day_of_week: Optional[str] = None
    ) -> TourItinerary:
        """
        Plan a tour itinerary.
        
        Args:
            user_coordinates: Starting point (lat, lng)
            duration_hours: Total tour duration in hours
            start_time: Tour start time (HH:MM format)
            categories: List of preferred categories (None = all)
            num_stops: Number of stops to include
            day_of_week: Day of week for checking hours (None = today)
            
        Returns:
            TourItinerary with optimized route
        """
        logger.info(f"Planning tour: {num_stops} stops, {duration_hours}h duration")
        
        # Parse start time
        try:
            hour, minute = map(int, start_time.split(':'))
            tour_start = time(hour, minute)
        except Exception:
            tour_start = time(9, 0)
        
        # Get day of week
        if day_of_week is None:
            day_of_week = datetime.now().strftime('%A')
        
        # Create itinerary
        itinerary = TourItinerary(
            start_time=tour_start,
            day_of_week=day_of_week,
            user_start_coordinates=user_coordinates
        )
        
        try:
            # Step 1: Get candidate places
            candidates = self._get_candidate_places(
                user_coordinates, categories, num_stops * 4
            )
            logger.info(f"Found {len(candidates)} candidate places")
            
            if not candidates:
                logger.warning("No candidate places found")
                return itinerary
            
            # Step 2: Filter by business hours
            candidates = self._filter_by_hours(candidates, day_of_week, tour_start)
            logger.info(f"After hours filter: {len(candidates)} places")
            
            # Step 3: Optimize route using greedy nearest neighbor
            # Check if this is a mixed tour (has both tourist attractions and restaurants)
            tourist_category_terms = ['tourist_attraction', 'museum', 'park', 'parque', 'monument', 
                                     'church', 'teatro', 'fortress', 'historical', 'beach', 
                                     'plaza', 'cathedral', 'ecological', 'zoo', 'garden']
            restaurant_category_terms = ['restaurant', 'restaurante', 'food', 'traditional', 'regional']
            
            has_tourist_cat = categories and any(
                any(term in cat.lower() for term in tourist_category_terms) for cat in categories
            )
            has_restaurant_cat = categories and any(
                any(term in cat.lower() for term in restaurant_category_terms) for cat in categories
            )
            is_mixed_tour = has_tourist_cat and has_restaurant_cat
            
            route = self._optimize_route(
                user_coordinates, candidates, num_stops, ensure_mix=is_mixed_tour
            )
            logger.info(f"Optimized route with {len(route)} stops")
            
            # Step 4: Assign time slots
            self._assign_time_slots(route, tour_start, duration_hours)
            
            # Add stops to itinerary
            for stop in route:
                itinerary.add_stop(stop)
            
            # Calculate end time
            if route:
                last_stop = route[-1]
                if last_stop.departure_time:
                    itinerary.end_time = last_stop.departure_time
            
            logger.info(f"Tour planned: {len(itinerary.stops)} stops, "
                       f"{itinerary.total_distance_km:.2f}km")
            
        except Exception as e:
            logger.error(f"Error planning tour: {e}")
        
        return itinerary
    
    def _get_candidate_places(
        self,
        user_coordinates: Tuple[float, float],
        categories: Optional[List[str]],
        limit: int
    ) -> List[TourStop]:
        """Get candidate places for the tour."""
        all_places = self._load_places()
        candidates = []
        
        user_lat, user_lng = user_coordinates
        
        for place in all_places:
            try:
                # Get coordinates
                place_lat = float(place.get('location/lat', 0))
                place_lng = float(place.get('location/lng', 0))
                
                if place_lat == 0 and place_lng == 0:
                    continue
                
                # Calculate distance
                distance = self._haversine_distance(
                    user_lat, user_lng, place_lat, place_lng
                )
                
                # Filter by reasonable distance (within 10km)
                if distance > 10:
                    continue
                
                # Get category
                category = place.get('categoryName', '').lower()
                
                # Filter by category if specified
                if categories:
                    category_match = self._matches_tour_category(place, categories)
                    if not category_match:
                        continue
                
                # Parse business hours
                hours_str = place.get('businessTime', '')
                business_hours = None
                if hours_str:
                    business_hours = self.hours_parser.parse(hours_str)
                
                # Create tour stop
                stop = TourStop(
                    place_id=place.get('placeId', ''),
                    name=place.get('title', place.get('titleFormatted', 'Unknown')),
                    category=place.get('categoryName', 'Unknown'),
                    address=place.get('address', place.get('addressFormatted', '')),
                    coordinates=(place_lat, place_lng),
                    rating=float(place.get('totalScore', 0) or 0),
                    review_count=int(place.get('reviewsCount', 0) or 0),
                    business_hours=business_hours,
                    phone=str(place.get('phone', '')),
                    website=str(place.get('website', ''))
                )
                
                # Set duration based on category
                stop.duration_minutes = self._get_duration_for_category(category)
                
                # Add distance for sorting
                stop._distance_from_start = distance
                
                candidates.append(stop)
                
            except Exception as e:
                logger.debug(f"Error processing place: {e}")
                continue
        
        # Sort by a combination of distance and rating
        candidates.sort(key=lambda x: (
            x._distance_from_start - (x.rating * 0.5)
        ))
        
        
        # For mixed category requests, ensure we include some of each type
        # before applying the limit
        if categories and len(categories) >= 4:  # Likely a mixed tour request
            tourist_keywords = ['museum', 'theater', 'teatro', 'church', 'igreja', 'park', 
                               'parque', 'fort', 'forte', 'market', 'mercado', 'palace',
                               'basilica', 'monument', 'memorial', 'garden', 'ecological',
                               'performing arts', 'wholesale']
            
            tourists = [c for c in candidates 
                       if any(k in c.category.lower() for k in tourist_keywords)]
            restaurants = [c for c in candidates 
                          if 'restaurant' in c.category.lower()]
            others = [c for c in candidates 
                     if c not in tourists and c not in restaurants]
            
            
            # Ensure we get a good mix: prioritize top-rated tourist spots
            # Sort tourists by rating (descending), not distance
            tourists.sort(key=lambda x: (-x.rating, x._distance_from_start))
            restaurants.sort(key=lambda x: (x._distance_from_start - (x.rating * 0.5)))
            
            # Build a balanced list: take top N from each category
            tourist_limit = min(len(tourists), max(5, limit // 3))
            restaurant_limit = min(len(restaurants), max(5, limit // 3))
            other_limit = max(0, limit - tourist_limit - restaurant_limit)
            
            balanced = tourists[:tourist_limit] + restaurants[:restaurant_limit] + others[:other_limit]
            
            
            logger.info(f"Category-balanced candidates: {len(tourists[:tourist_limit])} tourist, "
                       f"{len(restaurants[:restaurant_limit])} restaurant, "
                       f"{len(others[:other_limit])} other")
            
            return balanced
        
        return candidates[:limit]
    
    def _filter_by_hours(
        self,
        candidates: List[TourStop],
        day: str,
        start_time: time
    ) -> List[TourStop]:
        """Filter candidates by business hours."""
        filtered = []
        
        for stop in candidates:
            # If no hours data, assume open
            if stop.business_hours is None:
                filtered.append(stop)
                continue
            
            # Check if open during tour time
            schedule = stop.business_hours.get_hours_for_day(day)
            
            if schedule is None or schedule.is_closed:
                continue
            
            # Check if any time range overlaps with tour start
            for tr in schedule.time_ranges:
                # Place should be open sometime after start_time
                if tr.end >= start_time or tr.start <= start_time:
                    filtered.append(stop)
                    break
        
        return filtered
    
    def _optimize_route(
        self,
        start_coordinates: Tuple[float, float],
        candidates: List[TourStop],
        num_stops: int,
        ensure_mix: bool = False
    ) -> List[TourStop]:
        """
        Optimize route using greedy nearest-neighbor algorithm.
        
        This is a simple TSP approximation that visits the nearest
        unvisited location at each step.
        
        If ensure_mix is True, ensures a balanced mix of categories
        (tourist attractions and restaurants for default tours).
        """
        if not candidates:
            return []
        
        # For mixed tours, separate candidates into categories
        if ensure_mix:
            tourist_keywords = ['museum', 'theater', 'teatro', 'church', 'igreja', 'park', 
                               'parque', 'fort', 'forte', 'market', 'mercado', 'palace',
                               'palace', 'basilica', 'monument', 'memorial', 'garden']
            
            tourists = [c for c in candidates if any(k in c.category.lower() for k in tourist_keywords)]
            restaurants = [c for c in candidates if 'restaurant' in c.category.lower()]
            
            # Sort by rating (higher first) and distance from start
            tourists.sort(key=lambda x: (x.rating, -self._haversine_distance(
                start_coordinates[0], start_coordinates[1], 
                x.coordinates[0], x.coordinates[1])), reverse=True)
            restaurants.sort(key=lambda x: (x.rating, -self._haversine_distance(
                start_coordinates[0], start_coordinates[1],
                x.coordinates[0], x.coordinates[1])), reverse=True)
            
            # Create a balanced mix: 60% tourist attractions, 40% restaurants
            # For 6 stops: 4 tourist, 2 restaurants
            tourist_count = max(1, int(num_stops * 0.6))
            restaurant_count = max(1, num_stops - tourist_count)
            
            selected_tourists = tourists[:tourist_count] if tourists else []
            selected_restaurants = restaurants[:restaurant_count] if restaurants else []
            
            # If not enough of one type, fill with the other
            if len(selected_tourists) < tourist_count and restaurants:
                extra_needed = tourist_count - len(selected_tourists)
                selected_restaurants = restaurants[:restaurant_count + extra_needed]
            if len(selected_restaurants) < restaurant_count and tourists:
                extra_needed = restaurant_count - len(selected_restaurants)
                selected_tourists = tourists[:tourist_count + extra_needed]
            
            # Combine and sort by distance for route optimization
            balanced_candidates = selected_tourists + selected_restaurants
            logger.info(f"Mixed tour balance: {len(selected_tourists)} tourist attractions, "
                       f"{len(selected_restaurants)} restaurants")
            
            # Fall through to route optimization with balanced candidates
            candidates = balanced_candidates if balanced_candidates else candidates
        
        # Start from user location
        current_lat, current_lng = start_coordinates
        route = []
        remaining = candidates.copy()
        
        while len(route) < num_stops and remaining:
            # Find nearest unvisited place
            nearest = None
            nearest_distance = float('inf')
            
            for stop in remaining:
                distance = self._haversine_distance(
                    current_lat, current_lng,
                    stop.coordinates[0], stop.coordinates[1]
                )
                
                # Prefer higher-rated places with slight distance penalty
                adjusted_distance = distance - (stop.rating * 0.1)
                
                if adjusted_distance < nearest_distance:
                    nearest_distance = distance
                    nearest = stop
            
            if nearest:
                # Add to route
                if route:
                    # Calculate travel time from previous stop
                    prev_stop = route[-1]
                    prev_stop.distance_to_next = nearest_distance
                    prev_stop.travel_time_to_next = self._calculate_travel_time(
                        nearest_distance
                    )
                
                route.append(nearest)
                remaining.remove(nearest)
                current_lat, current_lng = nearest.coordinates
            else:
                break
        
        return route
    
    def _assign_time_slots(
        self,
        route: List[TourStop],
        start_time: time,
        duration_hours: int
    ) -> None:
        """Assign arrival and departure times to each stop."""
        if not route:
            return
        
        current_time = datetime.combine(datetime.today(), start_time)
        end_time = current_time + timedelta(hours=duration_hours)
        
        for i, stop in enumerate(route):
            # Set arrival time
            stop.arrival_time = current_time.time()
            
            # Calculate departure time
            departure = current_time + timedelta(minutes=stop.duration_minutes)
            
            # Check if we're exceeding tour duration
            if departure > end_time:
                # Adjust duration to fit
                remaining_minutes = int((end_time - current_time).total_seconds() / 60)
                stop.duration_minutes = max(15, remaining_minutes)
                departure = end_time
            
            stop.departure_time = departure.time()
            
            # Add travel time for next stop
            current_time = departure + timedelta(minutes=stop.travel_time_to_next)
    
    def _get_duration_for_category(self, category: str) -> int:
        """Get suggested duration for a category."""
        category_lower = category.lower()
        
        for cat_key, duration in self.CATEGORY_DURATIONS.items():
            if cat_key in category_lower:
                return duration
        
        return self.CATEGORY_DURATIONS['default']
    
    def _matches_tour_category(
        self, 
        place: Dict[str, Any], 
        target_categories: List[str]
    ) -> bool:
        """
        Check if a place matches any of the target tour categories.
        
        Uses flexible matching for tourist attractions and strict matching for açaí.
        """
        # Get place categories
        main_category = place.get('categoryName', '').lower()
        title = place.get('title', '').lower()
        
        # Collect all sub-categories
        sub_categories = []
        for i in range(9):
            sub_cat = place.get(f'categories/{i}', '').lower()
            if sub_cat:
                sub_categories.append(sub_cat)
        
        all_place_cats = [main_category] + sub_categories
        
        # Normalize target categories
        target_lower = [cat.lower() for cat in target_categories]
        
        # Check if this is an açaí search (STRICT)
        is_acai_search = any(
            acai_term in cat for cat in target_lower 
            for acai_term in ['açaí', 'acai', 'açai', 'acaí']
        )
        
        if is_acai_search:
            # Strict açaí matching - only match actual açaí shops
            for place_cat in all_place_cats:
                for acai_term in self.ACAI_CATEGORIES:
                    if acai_term in place_cat:
                        return True
            # Also check title for açaí
            for acai_term in self.ACAI_CATEGORIES:
                if acai_term in title:
                    return True
            return False
        
        # Check if this is a tourist attraction search (STRICT with exclusions)
        is_tourist_search = any(
            tourist_term in cat for cat in target_lower 
            for tourist_term in ['tourist', 'attraction', 'museum', 'park', 'church', 
                                  'monument', 'fortress', 'beach', 'praia', 'historical',
                                  'plaza', 'praça', 'cathedral', 'teatro', 'theater']
        )
        
        # Check if this is a MIXED search (tourist + restaurants together)
        # This happens for default tours where we want both sightseeing AND places to eat
        is_restaurant_search = any(
            food_term in cat for cat in target_lower 
            for food_term in ['restaurant', 'restaurante', 'traditional', 'regional', 'food']
        )
        is_mixed_search = is_tourist_search and is_restaurant_search
        
        # For mixed searches, restaurants should be allowed through
        if is_mixed_search:
            all_cats_text = ' '.join(all_place_cats)
            
            # FIRST: Check MAIN CATEGORY exclusions - açaí shops, ice cream, cafes, bars
            # should NOT be included in default tours even if they have "restaurant" as sub-category
            main_cat_exclusions = ['açaí', 'acai', 'ice cream', 'sorveteria', 'sorvete',
                                   'cafe', 'cafeteria', 'coffee', 'bar', 'pub', 'boteco',
                                   'shop', 'loja', 'store', 'boutique', 'supermarket']
            for exclusion in main_cat_exclusions:
                if exclusion in main_category:
                    return False  # Exclude based on MAIN category
            
            # Also check title for açaí - these are definitely açaí shops
            if any(acai in title for acai in ['açaí', 'acai', 'açai', 'acaí']):
                return False  # Title has açaí = açaí shop, not a restaurant
            
            # SECOND: Check if this is a PROPER restaurant (main category is restaurant type)
            restaurant_main_indicators = ['restaurant', 'restaurante', 'buffet', 'steakhouse', 
                                          'churrascaria', 'lunch restaurant', 'dinner', 'pizzeria',
                                          'seafood', 'brazilian', 'italian', 'japanese', 'chinese']
            is_proper_restaurant = any(ind in main_category for ind in restaurant_main_indicators)
            if is_proper_restaurant:
                return True  # It's a proper restaurant
            
            # THIRD: Check other exclusions (hotels, etc.)
            non_restaurant_exclusions = {'hotel', 'motel', 'hostel', 'pousada', 'inn', 'resort', 
                                         'hospedagem', 'albergue'}
            for exclusion in non_restaurant_exclusions:
                if exclusion in all_cats_text:
                    return False
            
            # Check if it's a tourist attraction
            tourist_category_indicators = [
                'theater', 'teatro', 'museum', 'museu', 'park', 'parque',
                'church', 'igreja', 'cathedral', 'catedral', 'basilica', 'basílica',
                'monument', 'monumento', 'memorial', 'fort', 'forte', 'fortress',
                'palace', 'palácio', 'historical', 'histórico', 'heritage',
                'gallery', 'galeria', 'garden', 'jardim', 'botanical',
                'beach', 'praia', 'pier', 'dock', 'doca', 'waterfront',
                'performing arts', 'cultural center', 'centro cultural'
            ]
            for place_cat in all_place_cats:
                for indicator in tourist_category_indicators:
                    if indicator in place_cat:
                        return True
            
            # Check famous spots
            for famous_spot in self.FAMOUS_TOURIST_SPOTS:
                if title == famous_spot or title.startswith(famous_spot):
                    return True
                if famous_spot in title and len(famous_spot) >= len(title) * 0.7:
                    return True
            
            return False
        
        if is_tourist_search:
            all_cats_text = ' '.join(all_place_cats)
            
            # FIRST: Check exclusions - bars, restaurants, hotels, etc. should NEVER be tourist attractions
            # This check takes absolute precedence - even if a place has "portal" in its name
            for exclusion in self.TOURIST_EXCLUSIONS:
                if exclusion in all_cats_text:
                    return False  # Category is excluded, reject immediately
            
            # SECOND: Check if category indicates a true tourist attraction
            # (performing arts theater, museum, park, etc.)
            tourist_category_indicators = [
                'theater', 'teatro', 'museum', 'museu', 'park', 'parque',
                'church', 'igreja', 'cathedral', 'catedral', 'basilica', 'basílica',
                'monument', 'monumento', 'memorial', 'fort', 'forte', 'fortress',
                'palace', 'palácio', 'historical', 'histórico', 'heritage',
                'gallery', 'galeria', 'garden', 'jardim', 'botanical',
                'beach', 'praia', 'pier', 'dock', 'doca', 'waterfront',
                'performing arts', 'cultural center', 'centro cultural'
            ]
            
            for place_cat in all_place_cats:
                for indicator in tourist_category_indicators:
                    if indicator in place_cat:
                        return True
            
            # THIRD: Check if this is an EXACT famous tourist spot (not just substring)
            # Only match if title is very close to famous spot name
            for famous_spot in self.FAMOUS_TOURIST_SPOTS:
                # Exact match or title starts with famous spot
                if title == famous_spot or title.startswith(famous_spot):
                    return True
                # Famous spot is the dominant part of title (>80% of title length)
                if famous_spot in title and len(famous_spot) >= len(title) * 0.7:
                    return True
            
            # FOURTH: Check title for common tourist keywords (stricter)
            # Only if category wasn't already excluded
            tourist_title_keywords = [
                'museum', 'museu', 'church', 'igreja', 'park', 'parque', 
                'fort', 'forte', 'theater', 'teatro', 'cathedral', 'catedral',
                'beach', 'praia', 'monument', 'memorial', 'basílica', 'basilica',
                'praça da república', 'jardim', 'bosque', 'mangal das garças'
            ]
            for keyword in tourist_title_keywords:
                if keyword in title:
                    return True
            
            return False
        
        # Standard category matching for other types
        # Exclude places whose main category is clearly wrong (e.g., hostel for restaurant search)
        main_category_exclusions = ['hostel', 'hotel', 'motel', 'pousada', 'inn', 'resort', 'albergue']
        if any(excl in main_category for excl in main_category_exclusions):
            # Don't match hotels/hostels just because they have a restaurant sub-category
            return False
        
        for target in target_lower:
            for place_cat in all_place_cats:
                if target in place_cat or place_cat in target:
                    return True
            # Check title as fallback
            if target in title:
                return True
        
        return False
    
    def _calculate_travel_time(self, distance_km: float) -> int:
        """Calculate travel time in minutes assuming walking."""
        hours = distance_km / self.WALKING_SPEED
        return int(hours * 60)
    
    def _haversine_distance(
        self,
        lat1: float, lng1: float,
        lat2: float, lng2: float
    ) -> float:
        """Calculate haversine distance in km."""
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
    
    def get_quick_suggestions(
        self,
        user_coordinates: Tuple[float, float],
        category: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get quick place suggestions without full itinerary planning.
        
        Useful for "what's nearby" type queries.
        """
        candidates = self._get_candidate_places(
            user_coordinates,
            [category] if category else None,
            limit * 2
        )
        
        # Sort by combined score
        candidates.sort(key=lambda x: (
            x.rating * 2 + (10 - getattr(x, '_distance_from_start', 5))
        ), reverse=True)
        
        return [
            {
                'name': c.name,
                'category': c.category,
                'address': c.address,
                'rating': c.rating,
                'review_count': c.review_count,
                'distance_km': getattr(c, '_distance_from_start', 0)
            }
            for c in candidates[:limit]
        ]
98
