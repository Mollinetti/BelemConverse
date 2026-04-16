"""
Two-Stage Retriever for improved RAG performance.

This module implements a two-stage retrieval approach:
1. Stage 1: Pure semantic search to get a large pool of candidates
2. Stage 2: Apply structured filters (location, category, price) as re-ranking

This fixes the issue where pre-filtering loses semantic relevance.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from langchain_core.documents import Document

import h3

from utils.bayesian_ranking import bayesian_ranker

logger = logging.getLogger(__name__)

# Lazy import for fallback orchestrator to avoid circular imports
_fallback_orchestrator = None

def get_fallback_orchestrator():
    """Lazy load the fallback orchestrator."""
    global _fallback_orchestrator
    if _fallback_orchestrator is None:
        from core.search_fallback import get_fallback_orchestrator as _get_orchestrator
        _fallback_orchestrator = _get_orchestrator()
    return _fallback_orchestrator


@dataclass
class RetrievalConfig:
    """Configuration for two-stage retrieval."""
    # Stage 1: Semantic search
    initial_candidates: int = 50  # Number of candidates from semantic search
    
    # Stage 2: Re-ranking weights
    semantic_weight: float = 0.5  # Weight for semantic similarity score
    location_weight: float = 0.3  # Weight for location proximity score
    category_weight: float = 0.15  # Weight for category match score
    popularity_weight: float = 0.05  # Weight for popularity score
    
    # Location filtering
    max_distance_nearby: float = 1.0  # km for "nearby" queries
    max_distance_city: float = 10.0  # km for general city queries
    
    # Final results
    top_k: int = 5  # Final number of results to return


@dataclass
class ScoredDocument:
    """Document with combined relevance scores."""
    document: Document
    semantic_score: float = 0.0
    location_score: float = 0.0
    category_score: float = 0.0
    popularity_score: float = 0.0
    combined_score: float = 0.0
    distance_km: Optional[float] = None
    place_data: Dict[str, Any] = field(default_factory=dict)


class TwoStageRetriever:
    """
    Two-stage retrieval system that combines semantic search with structured filtering.
    
    Stage 1: Get a large pool of semantically relevant candidates
    Stage 2: Re-rank using structured filters (location, category, popularity)
    """
    
    def __init__(
        self, 
        vector_store_manager,
        data_loader,
        config: Optional[RetrievalConfig] = None,
        fallback_enabled: bool = True
    ):
        """
        Initialize the two-stage retriever.
        
        Args:
            vector_store_manager: VectorStoreManager for semantic search
            data_loader: DataLoader for accessing place metadata
            config: RetrievalConfig for customizing behavior
            fallback_enabled: Whether to enable OSM fallback for failed searches
        """
        self.vector_store_manager = vector_store_manager
        self.data_loader = data_loader
        self.config = config or RetrievalConfig()
        self.fallback_enabled = fallback_enabled
        
        # Cache for place data lookup by title
        self._place_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_built = False
        
        logger.info(f"TwoStageRetriever initialized with config: "
                   f"initial_candidates={self.config.initial_candidates}, "
                   f"semantic_weight={self.config.semantic_weight}, "
                   f"fallback_enabled={self.fallback_enabled}")
    
    def _build_place_cache(self) -> None:
        """Build a cache of place data for quick lookup."""
        if self._cache_built:
            return
            
        try:
            all_places = self.data_loader.load_all_places()
            
            for place in all_places:
                # Index by both title and titleFormatted
                title = place.get('title', '').lower().strip()
                title_formatted = place.get('titleFormatted', '').lower().strip()
                
                if title:
                    self._place_cache[title] = place
                if title_formatted and title_formatted != title:
                    self._place_cache[title_formatted] = place
            
            self._cache_built = True
            logger.info(f"Built place cache with {len(self._place_cache)} entries")
            
        except Exception as e:
            logger.error(f"Error building place cache: {e}")
    
    def _get_place_data(self, document: Document) -> Dict[str, Any]:
        """
        Get place data from cache based on document content.
        
        Uses strict matching to avoid false positives (e.g., short title "gm"
        matching in unrelated content).
        
        Args:
            document: Document to find place data for
            
        Returns:
            Place data dictionary or empty dict if not found
        """
        self._build_place_cache()
        
        content = document.page_content.lower()
        
        # Method 1: Try metadata title (most reliable)
        doc_title = document.metadata.get('title', '').lower().strip()
        if doc_title and doc_title in self._place_cache:
            return self._place_cache[doc_title]
        
        # Method 2: Try to extract title from document content lines
        for line in document.page_content.split('\n'):
            if line.lower().startswith('title:') or line.lower().startswith('titleformatted:'):
                extracted_title = line.split(':', 1)[1].strip().lower()
                if extracted_title in self._place_cache:
                    return self._place_cache[extracted_title]
        
        # Method 3: Sort cache keys by length (longest first) to match specific titles first
        # This prevents short titles like "gm" from falsely matching
        sorted_titles = sorted(self._place_cache.keys(), key=len, reverse=True)
        
        for title in sorted_titles:
            # Only match titles that are substantial (>= 4 chars) to avoid false positives
            if len(title) >= 4 and title in content:
                return self._place_cache[title]
        
        # Method 4: For short titles, require exact word match (not substring)
        import re
        for title in sorted_titles:
            if len(title) < 4:
                # Use word boundary matching for short titles
                pattern = r'\b' + re.escape(title) + r'\b'
                if re.search(pattern, content):
                    return self._place_cache[title]
        
        return {}
    
    def retrieve(
        self,
        query: str,
        intent_result: Dict[str, Any],
        user_coordinates: Optional[Tuple[float, float]] = None,
        top_k: Optional[int] = None
    ) -> List[Document]:
        """
        Perform FILTER-FIRST retrieval for ALL intents.
        Semantic search is only used as an absolute last resort.
        OSM fallback is triggered when results are empty or low quality.
        
        PRIMARY APPROACH (Filter-First):
          1. Get ALL places from database
          2. Apply category filter if detected
          3. Rank based on primary intent:
             - location → rank by distance
             - popularity → rank by Bayesian score
             - price → rank by price range
             - business_hours → filter by hours
             - default → rank by popularity
          4. Return top_k results
        
        FALLBACK Chain:
          1. Semantic Search - if filter-first returns 0 results
          2. OSM Realtime - if database search is unsatisfactory
        
        Args:
            query: User's search query
            intent_result: TF-IDF intent detection results
            user_coordinates: Optional user coordinates (lat, lng)
            top_k: Number of final results (default: config.top_k)
            
        Returns:
            List of relevant documents sorted appropriately
        """
        if top_k is None:
            top_k = self.config.top_k
        
        try:
            # PRIMARY: FILTER-FIRST RETRIEVAL for ALL queries
            logger.info("Using FILTER-FIRST retrieval (semantic search is last resort)")
            results = self._filter_first_retrieve(
                query, intent_result, user_coordinates, top_k
            )
            
            # Collect scores for fallback evaluation
            scores = [doc.metadata.get('combined_score', 0.5) for doc in results] if results else []
            
            # Only use semantic search if filter-first returned nothing
            if not results:
                logger.warning("Filter-first returned no results, falling back to semantic search")
                results = self._semantic_retrieve(query, intent_result, user_coordinates, top_k)
                scores = [doc.metadata.get('combined_score', 0.5) for doc in results] if results else []
            
            # OSM FALLBACK: Check if we should supplement with OSM data
            if self.fallback_enabled and user_coordinates:
                results = self._apply_osm_fallback(
                    query, results, intent_result, user_coordinates, scores
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Error in retrieval: {e}")
            return self._fallback_retrieval(query, top_k)
    
    def _apply_osm_fallback(
        self,
        query: str,
        db_results: List[Document],
        intent_result: Dict[str, Any],
        user_coordinates: Tuple[float, float],
        scores: List[float]
    ) -> List[Document]:
        """
        Apply OSM fallback if database results are unsatisfactory.
        
        Evaluates results and triggers OSM realtime search if:
        - Results are empty
        - All scores are low confidence (<0.3)
        - Nearest result is too far (>5km)
        - Specific place name not found
        - Query is a verification query
        
        Args:
            query: Original query
            db_results: Results from database search
            intent_result: Intent classification
            user_coordinates: User location
            scores: Confidence scores for db_results
            
        Returns:
            Merged results (database + OSM if fallback triggered)
        """
        try:
            orchestrator = get_fallback_orchestrator()
            
            # Get categories from intent for targeted OSM search
            primary_category = intent_result.get('primary_category', '')
            categories = [primary_category] if primary_category else None
            
            # Let the orchestrator decide and execute fallback
            merged_result = orchestrator.search_with_fallback(
                query=query,
                db_results=db_results,
                user_coordinates=user_coordinates,
                intent_result=intent_result,
                scores=scores,
                categories=categories
            )
            
            if merged_result.fallback_used:
                logger.info(f"OSM fallback triggered: {merged_result.fallback_reason.value} - "
                           f"added {merged_result.osm_count} OSM results")
            
            return merged_result.documents
            
        except Exception as e:
            logger.warning(f"OSM fallback failed: {e}")
            return db_results  # Return original results if fallback fails
    
    def _filter_first_retrieve(
        self,
        query: str,
        intent_result: Dict[str, Any],
        user_coordinates: Optional[Tuple[float, float]],
        top_k: int
    ) -> List[Document]:
        """
        Filter-first retrieval: Filter by category, then rank by intent.
        
        This is the PRIMARY retrieval method for ALL queries.
        """
        min_results = max(3, top_k)
        
        # Get all places from cache (deduplicate by title)
        self._build_place_cache()
        seen_titles = set()
        all_places = []
        for place in self._place_cache.values():
            title = place.get('title', place.get('titleFormatted', ''))
            if title and title not in seen_titles:
                seen_titles.add(title)
                all_places.append(place)
        
        logger.info(f"Filter-first: Starting with {len(all_places)} total places")
        
        # Extract intent info
        intents = intent_result.get('intents', [])
        primary_intent = intent_result.get('primary_intent', 'general')
        primary_category = intent_result.get('primary_category', '')
        category_confidence = intent_result.get('primary_category_confidence', 0.0)
        
        has_location_intent = any(i.get('intent') == 'location' for i in intents)
        has_popularity_intent = any(i.get('intent') == 'popularity' for i in intents)
        
        # Step 1: Apply category filter if detected with reasonable confidence
        apply_category_filter = primary_category and category_confidence > 0.25
        
        if apply_category_filter:
            filtered_places = [
                p for p in all_places 
                if self._place_matches_category(p, primary_category)
            ]
            logger.info(f"Filter-first: Category '{primary_category}' filter -> {len(filtered_places)} places")
        else:
            filtered_places = all_places
            logger.info(f"Filter-first: No category filter applied")
        
        if not filtered_places:
            logger.warning(f"No places match category '{primary_category}', using all places")
            filtered_places = all_places
        
        # Step 2: Route to appropriate ranking based on primary intent
        if has_location_intent and user_coordinates:
            # LOCATION: Filter by distance, then rank
            return self._rank_by_location(
                filtered_places, user_coordinates, primary_category,
                has_popularity_intent, min_results, top_k
            )
        elif has_popularity_intent:
            # POPULARITY: Rank by Bayesian score
            return self._rank_by_popularity(
                filtered_places, primary_category, top_k
            )
        else:
            # DEFAULT: Rank by popularity (most useful default)
            return self._rank_by_popularity(
                filtered_places, primary_category, top_k
            )
    
    def _rank_by_location(
        self,
        places: List[Dict[str, Any]],
        user_coordinates: Tuple[float, float],
        category: str,
        has_popularity_intent: bool,
        min_results: int,
        top_k: int
    ) -> List[Document]:
        """Rank places by distance from user."""
        # Calculate distance for each place
        places_with_distance = []
        for place in places:
            distance = self._calculate_distance(user_coordinates, place)
            if distance is not None:
                places_with_distance.append((place, distance))
        
        logger.info(f"Location ranking: {len(places_with_distance)} places have valid coordinates")
        
        if not places_with_distance:
            return []
        
        # Sort by distance (closest first)
        places_with_distance.sort(key=lambda x: x[1])
        
        # Log closest places
        logger.info(f"Location ranking: User coords = {user_coordinates}")
        logger.info(f"Location ranking: Closest 5 places:")
        for i, (p, d) in enumerate(places_with_distance[:5]):
            title = p.get('titleFormatted', p.get('title', 'Unknown'))
            logger.info(f"  {i+1}. {title} - {d:.3f}km")
        
        # Expanding radius search: 500m -> 1km -> 2km -> 5km -> 10km
        radii = [0.5, 1.0, 2.0, 5.0, 10.0, 20.0]
        filtered_places = []
        used_radius = 0
        
        for radius in radii:
            in_radius = [(p, d) for p, d in places_with_distance if d <= radius]
            logger.info(f"Location ranking: Radius {radius}km -> {len(in_radius)} places (need {min_results})")
            
            if len(in_radius) >= min_results:
                filtered_places = in_radius
                used_radius = radius
                break
            
            filtered_places = in_radius
            used_radius = radius
        
        logger.info(f"Location ranking: FINAL - {len(filtered_places)} places within {used_radius}km")
        
        if not filtered_places:
            return []
        
        # Rank the filtered places
        scored_places = self._rank_location_results(
            filtered_places, category, has_popularity_intent
        )
        
        # Take top_k
        top_places = scored_places[:top_k]
        
        # Log final results
        for i, (place, distance, score) in enumerate(top_places[:3]):
            title = place.get('titleFormatted', place.get('title', 'Unknown'))
            rating = place.get('totalScore', 'N/A')
            reviews = place.get('reviewsCount', 'N/A')
            logger.info(f"  FINAL #{i+1}: {title} | {rating}★ ({reviews} reviews) | "
                       f"distance: {distance:.2f}km | score: {score:.3f}")
        
        return self._places_to_documents(top_places)
    
    def _rank_by_popularity(
        self,
        places: List[Dict[str, Any]],
        category: str,
        top_k: int
    ) -> List[Document]:
        """Rank places by Bayesian popularity score."""
        scored_places = []
        
        for place in places:
            # Calculate Bayesian popularity score
            pop_score = self._calculate_popularity_score(place)
            
            # Category match bonus
            cat_score = 1.0 if self._place_matches_category(place, category) else 0.7
            
            # Combined score: 80% popularity, 20% category
            final_score = 0.80 * pop_score + 0.20 * cat_score
            
            scored_places.append((place, 0.0, final_score))  # 0.0 = no distance
        
        # Sort by score (highest first)
        scored_places.sort(key=lambda x: x[2], reverse=True)
        
        # Take top_k
        top_places = scored_places[:top_k]
        
        logger.info(f"Popularity ranking: Top {len(top_places)} places by Bayesian score")
        
        # Log final results
        for i, (place, _, score) in enumerate(top_places[:3]):
            title = place.get('titleFormatted', place.get('title', 'Unknown'))
            rating = place.get('totalScore', 'N/A')
            reviews = place.get('reviewsCount', 'N/A')
            logger.info(f"  FINAL #{i+1}: {title} | {rating}★ ({reviews} reviews) | score: {score:.3f}")
        
        return self._places_to_documents_popularity(top_places)
    
    def _places_to_documents_popularity(
        self, 
        scored_places: List[Tuple[Dict[str, Any], float, float]]
    ) -> List[Document]:
        """Convert scored places to Document objects (for popularity queries)."""
        documents = []
        
        for place, _, score in scored_places:
            # Build content from place data
            content_parts = []
            for key in ['title', 'titleFormatted', 'address', 'addressFormatted',
                       'categoryName', 'totalScore', 'reviewsCount', 'businessTime',
                       'priceRange', 'description', 'phone', 'website']:
                value = place.get(key, '')
                if value:
                    content_parts.append(f"{key}: {value}")
            
            doc = Document(
                page_content='\n'.join(content_parts),
                metadata={
                    'source': 'filter_first_popularity',
                    'combined_score': score,
                    'popularity_score': self._calculate_popularity_score(place),
                    'category_score': 1.0,
                    'location_score': 0.5,  # N/A for popularity search
                    'semantic_score': 0.5   # N/A for filter-first
                }
            )
            documents.append(doc)
        
        return documents
    
    def _place_matches_category(self, place: Dict[str, Any], target_category: str) -> bool:
        """
        Check if a place matches the target category.
        Uses strict matching for categories that have similar but distinct subtypes.
        
        DEPRECATED: This method duplicates logic from CategoryMatcher.
        Consider migrating to use the shared CategoryMatcher module.
        """
        if not target_category:
            return True
        
        target_lower = target_category.lower()
        main_category = place.get('categoryName', '').lower()
        title = place.get('title', '').lower()
        
        # Gather all categories for this place
        all_categories = [main_category]
        for i in range(9):
            sub_cat = place.get(f'categories/{i}', '').lower()
            if sub_cat:
                all_categories.append(sub_cat)
        
        # Join all categories for full-text checking
        all_cats_text = ' '.join(all_categories)
        
        # === STRICT MATCHING for AÇAÍ category ===
        # Açaí shops have their own dedicated category and should NOT be conflated with cafes
        acai_terms = ['açaí', 'acai', 'açai', 'acaí', 'assai', 'asai', 'açaizeiro', 'acaizeiro']
        is_acai_search = any(term in target_lower for term in acai_terms)
        
        if is_acai_search:
            # Check if place is an actual açaí shop
            for term in acai_terms:
                if term in all_cats_text or term in title:
                    return True
            # Açaí can also be found at some restaurants (light link)
            # But only if the place explicitly mentions açaí
            for term in acai_terms:
                if term in title:
                    return True
            return False
        
        # === STRICT MATCHING for hotel category ===
        # "hotel" should NOT match "love hotel", "motel", "hostel"
        if target_lower == 'hotel':
            exclusions = ['love hotel', 'motel', 'hostel', 'capsule hotel']
            
            for excl in exclusions:
                if excl in all_cats_text:
                    return False
            
            title_formatted = place.get('titleFormatted', '').lower()
            name_text = f"{title} {title_formatted}"
            
            for excl in exclusions:
                if excl in name_text:
                    return False
            
            if 'hotel' in all_cats_text:
                return True
            if 'pousada' in all_cats_text or 'inn' in all_cats_text:
                return True
            
            return False
        
        # STRICT MATCHING for hostel category
        if target_lower == 'hostel':
            if 'hostel' in all_cats_text:
                return True
            return False
        
        # STRICT MATCHING for motel category
        if target_lower == 'motel':
            if 'motel' in all_cats_text or 'love hotel' in all_cats_text:
                return True
            return False
        
        # === STRICT MATCHING for tourist_attraction category (with exclusions) ===
        tourist_terms = [
            'tourist', 'attraction', 'turístico', 'turista', 'tourism', 'turismo',
            'museum', 'museu', 'park', 'parque', 'garden', 'jardim', 'botanical', 'botânico',
            'church', 'igreja', 'cathedral', 'catedral', 'basilica', 'basílica', 'chapel', 'capela',
            'temple', 'templo', 'monastery', 'mosteiro', 'convent', 'convento',
            'monument', 'monumento', 'statue', 'estátua', 'memorial', 'sculpture',
            'fortress', 'fortaleza', 'fort', 'forte', 'castle', 'castelo',
            'ruins', 'ruínas', 'archaeological', 'arqueológico', 'historical', 'histórico', 'heritage',
            'plaza', 'praça', 'square', 'largo', 'terreiro',
            'beach', 'praia', 'waterfront', 'orla', 'pier', 'dock', 'doca',
            'theater', 'teatro', 'opera', 'ópera', 'cultural',
            'zoo', 'zoológico', 'aquarium', 'aquário', 'nature', 'natureza',
            'island', 'ilha', 'bay', 'baía', 'port', 'porto',
            'palace', 'palácio', 'mansion', 'casarão', 'colonial'
        ]
        
        # Categories to EXCLUDE from tourist attraction results
        tourist_exclusions = [
            # Hotels and lodging
            'hotel', 'motel', 'hostel', 'pousada', 'inn', 'resort', 'lodging', 'hospedagem',
            # Bars, pubs, restaurants (NOT tourist attractions)
            'bar', 'pub', 'boteco', 'brazilian boteco', 'cocktail bar', 'wine bar',
            'restaurant', 'restaurante', 'lunch restaurant', 'steakhouse', 'churrascaria',
            'cafe', 'cafeteria', 'coffee shop', 'bakery', 'padaria',
            'açaí', 'acai', 'ice cream', 'sorveteria',
            # Shops and retail
            'shop', 'loja', 'store', 'chocolate shop', 'chocolateria', 'candy',
            'gift shop', 'souvenir', 'supermarket', 'grocery', 'boutique',
            # Sports venues
            'sports bar', 'sports pub', 'gym', 'academia', 'fitness', 'ginásio', 'ginasio',
            # Fast food
            'fast food', 'hamburger', 'pizza', 'pizzaria', 'sushi', 'lanchonete',
            'convenience store', 'gas station', 'posto',
            # Services
            'hair salon', 'salão', 'barbershop', 'clinic', 'clínica', 'pharmacy', 'farmácia',
            'bank', 'banco', 'atm', 'dentist', 'hospital',
            # Shopping malls
            'shopping center', 'shopping mall', 'mall'
        ]
        
        # Famous Belém tourist spots (always include)
        famous_spots = [
            'ver-o-peso', 'ver o peso', 'estação das docas', 'mangal das garças',
            'theatro da paz', 'teatro da paz', 'forte do presépio', 'forte do castelo',
            'basílica de nazaré', 'catedral da sé', 'museu emílio goeldi',
            'bosque rodrigues alves', 'casa das onze janelas', 'feliz lusitânia'
        ]
        
        is_tourist_search = target_lower == 'tourist_attraction' or any(
            term in target_lower for term in ['tourist', 'attraction', 'museum', 'park', 
                                               'church', 'monument', 'fortress', 'beach', 
                                               'plaza', 'historical', 'ruins']
        )
        
        if is_tourist_search:
            # FIRST: Check exclusions - bars, restaurants, hotels, etc. should NEVER be attractions
            # This takes absolute precedence - even if named after a tourist spot
            for excl in tourist_exclusions:
                if excl in all_cats_text:
                    return False  # Category is excluded, reject immediately
            
            # SECOND: Check if category indicates a true tourist attraction
            tourist_category_indicators = [
                'theater', 'teatro', 'museum', 'museu', 'park', 'parque',
                'church', 'igreja', 'cathedral', 'catedral', 'basilica', 'basílica',
                'monument', 'monumento', 'memorial', 'fort', 'forte', 'fortress',
                'palace', 'palácio', 'historical', 'histórico', 'heritage',
                'performing arts', 'cultural center', 'garden', 'jardim'
            ]
            
            for indicator in tourist_category_indicators:
                if indicator in all_cats_text:
                    return True
            
            # THIRD: Check if this is an EXACT famous tourist spot (not just substring)
            for famous in famous_spots:
                if title == famous or title.startswith(famous):
                    return True
                if famous in title and len(famous) >= len(title) * 0.7:
                    return True
            
            # FOURTH: Check title for strict tourist keywords
            for term in tourist_terms:
                if term in title:
                    return True
            return False
        
        # Standard matching for other categories
        if target_lower in all_cats_text:
            return True
        
        # Check for related terms (aliases) - açaí REMOVED from cafe
        category_aliases = {
            'cafe': ['cafe', 'café', 'coffee', 'bakery', 'padaria', 'confeitaria', 'tea', 'chá'],
            'ice_cream': ['ice cream', 'sorvete', 'sorveteria', 'gelato', 'frozen'],
            'restaurant': ['restaurant', 'restaurante', 'grill', 'steakhouse', 'pizzaria', 'sushi', 
                          'hamburger', 'lanchonete', 'churrascaria', 'buffet', 'típico', 'regional'],
            'bar': ['bar', 'pub', 'boteco', 'drinks', 'beer', 'cerveja', 'cocktail'],
        }
        
        aliases = category_aliases.get(target_lower, [])
        for alias in aliases:
            if alias in all_cats_text:
                return True
        
        return False
    
    def _rank_location_results(
        self,
        places_with_distance: List[Tuple[Dict[str, Any], float]],
        category: str,
        has_popularity_intent: bool
    ) -> List[Tuple[Dict[str, Any], float, float]]:
        """
        Rank location-filtered results.
        
        Primary sort: Distance (closest first)
        Secondary: Popularity (if popularity intent) or category match
        
        Returns: List of (place, distance, score) tuples
        """
        scored = []
        
        for place, distance in places_with_distance:
            # Base score: inverse distance (closer = higher)
            # Normalize to 0-1 range, max 10km
            distance_score = max(0, 1.0 - (distance / 10.0))
            
            # Popularity bonus (Bayesian score)
            pop_score = self._calculate_popularity_score(place)
            
            # Category match bonus
            cat_score = 1.0 if self._place_matches_category(place, category) else 0.5
            
            # Combined score - distance is ALWAYS primary
            if has_popularity_intent:
                # 60% distance, 30% popularity, 10% category
                final_score = 0.60 * distance_score + 0.30 * pop_score + 0.10 * cat_score
            else:
                # 80% distance, 10% popularity, 10% category
                final_score = 0.80 * distance_score + 0.10 * pop_score + 0.10 * cat_score
            
            scored.append((place, distance, final_score))
        
        # Sort by distance first (primary), then by score (secondary)
        scored.sort(key=lambda x: (x[1], -x[2]))
        
        return scored
    
    def _places_to_documents(
        self, 
        scored_places: List[Tuple[Dict[str, Any], float, float]]
    ) -> List[Document]:
        """Convert scored places to Document objects."""
        documents = []
        
        for place, distance, score in scored_places:
            # Build content from place data
            content_parts = []
            for key in ['title', 'titleFormatted', 'address', 'addressFormatted',
                       'categoryName', 'totalScore', 'reviewsCount', 'businessTime',
                       'priceRange', 'description', 'phone', 'website']:
                value = place.get(key, '')
                if value:
                    content_parts.append(f"{key}: {value}")
            
            content_parts.append(f"distance: {distance:.2f}km")
            
            doc = Document(
                page_content='\n'.join(content_parts),
                metadata={
                    'source': 'location_search',
                    'distance_km': distance,
                    'combined_score': score,
                    'location_score': 1.0 - (distance / 10.0),
                    'popularity_score': self._calculate_popularity_score(place),
                    'category_score': 1.0,
                    'semantic_score': 0.5  # N/A for location search
                }
            )
            documents.append(doc)
        
        return documents
    
    def _semantic_retrieve(
        self,
        query: str,
        intent_result: Dict[str, Any],
        user_coordinates: Optional[Tuple[float, float]],
        top_k: int
    ) -> List[Document]:
        """Standard semantic search with re-ranking."""
        # Stage 1: Semantic search for initial candidates
        candidates = self._stage1_semantic_search(query)
        logger.info(f"Stage 1: Retrieved {len(candidates)} semantic candidates")
        
        if not candidates:
            logger.warning("No candidates found in Stage 1")
            return []
        
        # Stage 2: Re-rank with structured filters
        scored_docs = self._stage2_rerank(
            candidates, 
            intent_result, 
            user_coordinates,
            query
        )
        logger.info(f"Stage 2: Re-ranked {len(scored_docs)} documents")
        
        # Sort by combined score and return top k
        scored_docs.sort(key=lambda x: x.combined_score, reverse=True)
        top_docs = scored_docs[:top_k]
        
        # Log top results for debugging
        if top_docs:
            logger.info(f"Top result: {self._get_doc_title(top_docs[0].document)} "
                       f"(score: {top_docs[0].combined_score:.3f})")
            for i, sd in enumerate(top_docs[:3]):
                title = sd.place_data.get('titleFormatted', sd.place_data.get('title', 'Unknown'))
                rating = sd.place_data.get('totalScore', 'N/A')
                reviews = sd.place_data.get('reviewsCount', 'N/A')
                logger.info(f"  FINAL #{i+1}: {title} | {rating}★ ({reviews} reviews) | "
                           f"combined:{sd.combined_score:.3f} "
                           f"[pop:{sd.popularity_score:.3f}, sem:{sd.semantic_score:.3f}, "
                           f"cat:{sd.category_score:.3f}, loc:{sd.location_score:.3f}]")
        
        # Return documents with enriched metadata
        return [self._enrich_document(sd) for sd in top_docs]
    
    def _stage1_semantic_search(self, query: str) -> List[Tuple[Document, float]]:
        """
        Stage 1: Pure semantic search.
        
        Args:
            query: Search query
            
        Returns:
            List of (document, similarity_score) tuples
        """
        try:
            # Use similarity_search_with_score for semantic scores
            vector_store = self.vector_store_manager.vector_store
            
            if vector_store is None:
                raise ValueError("Vector store not initialized")
            
            # Get candidates with scores
            results = vector_store.similarity_search_with_score(
                query, 
                k=self.config.initial_candidates
            )
            
            # Convert to list of tuples (document, score)
            # Note: ChromaDB returns distance, not similarity - lower is better
            # We convert to similarity score: 1 / (1 + distance)
            candidates = []
            for doc, distance in results:
                similarity = 1.0 / (1.0 + distance)
                candidates.append((doc, similarity))
            
            return candidates
            
        except Exception as e:
            logger.error(f"Stage 1 semantic search failed: {e}")
            return []
    
    def _stage2_rerank(
        self,
        candidates: List[Tuple[Document, float]],
        intent_result: Dict[str, Any],
        user_coordinates: Optional[Tuple[float, float]],
        query: str
    ) -> List[ScoredDocument]:
        """
        Stage 2: Re-rank candidates using structured filters.
        
        Args:
            candidates: List of (document, semantic_score) tuples
            intent_result: Intent detection results
            user_coordinates: User coordinates for location scoring
            query: Original query for additional context
            
        Returns:
            List of ScoredDocument objects
        """
        scored_docs = []
        
        # Extract intents
        intents = intent_result.get('intents', [])
        has_location_intent = any(i.get('intent') == 'location' for i in intents)
        has_popularity_intent = any(i.get('intent') == 'popularity' for i in intents)
        primary_category = intent_result.get('primary_category', '')
        
        # Determine max distance based on query specificity
        max_distance = self._determine_max_distance(query, has_location_intent)
        
        # Adjust weights based on intent
        weights = self._adjust_weights(has_location_intent, has_popularity_intent)
        
        for doc, semantic_score in candidates:
            # Get place data for this document
            place_data = self._get_place_data(doc)
            
            # Calculate individual scores
            location_score = self._calculate_location_score(
                place_data, user_coordinates, max_distance
            )
            category_score = self._calculate_category_score(
                place_data, primary_category
            )
            popularity_score = self._calculate_popularity_score(place_data)
            
            # Calculate combined score
            combined_score = (
                weights['semantic'] * semantic_score +
                weights['location'] * location_score +
                weights['category'] * category_score +
                weights['popularity'] * popularity_score
            )
            
            # Calculate distance for metadata
            distance_km = None
            if user_coordinates and place_data:
                distance_km = self._calculate_distance(
                    user_coordinates,
                    place_data
                )
            
            scored_doc = ScoredDocument(
                document=doc,
                semantic_score=semantic_score,
                location_score=location_score,
                category_score=category_score,
                popularity_score=popularity_score,
                combined_score=combined_score,
                distance_km=distance_km,
                place_data=place_data
            )
            
            scored_docs.append(scored_doc)
        
        return scored_docs
    
    def _determine_max_distance(self, query: str, has_location_intent: bool) -> float:
        """Determine max distance based on query specificity."""
        query_lower = query.lower()
        
        # Very close proximity terms
        close_terms = ['nearby', 'nearest', 'closest', 'próximo', 'perto', 'mais perto']
        if any(term in query_lower for term in close_terms):
            return self.config.max_distance_nearby
        
        # General location terms
        if has_location_intent:
            return self.config.max_distance_city / 2  # 5km default
        
        # No specific location intent - use full city range
        return self.config.max_distance_city
    
    def _adjust_weights(
        self, 
        has_location_intent: bool, 
        has_popularity_intent: bool
    ) -> Dict[str, float]:
        """Adjust scoring weights based on detected intents."""
        weights = {
            'semantic': self.config.semantic_weight,
            'location': self.config.location_weight,
            'category': self.config.category_weight,
            'popularity': self.config.popularity_weight
        }
        
        if has_location_intent:
            # Location is PRIMARY factor when user asks for nearby places
            # Distance should dominate the ranking
            weights['location'] = 0.55  # PRIMARY - closest places first
            weights['semantic'] = 0.20  # Some relevance consideration
            weights['category'] = 0.15  # Category match
            weights['popularity'] = 0.10  # Slight quality boost
            
        if has_popularity_intent:
            # Strongly boost popularity weight for popularity queries
            # Popularity should dominate when user asks for "best" or "good" places
            weights['popularity'] = 0.5  # Primary factor
            weights['semantic'] = 0.25   # Still consider relevance
            weights['location'] = 0.15   # Some location consideration
            weights['category'] = 0.10   # Category matching
        
        # Log weights being used for debugging
        logger.info(f"Scoring weights: loc:{weights['location']:.2f}, pop:{weights['popularity']:.2f}, "
                   f"sem:{weights['semantic']:.2f}, cat:{weights['category']:.2f}")
        
        # Ensure weights sum to 1.0
        total = sum(weights.values())
        weights = {k: v / total for k, v in weights.items()}
        
        return weights
    
    def _calculate_location_score(
        self,
        place_data: Dict[str, Any],
        user_coordinates: Optional[Tuple[float, float]],
        max_distance: float
    ) -> float:
        """
        Calculate location score based on distance from user.
        
        Args:
            place_data: Place metadata
            user_coordinates: User's coordinates
            max_distance: Maximum relevant distance in km
            
        Returns:
            Location score (0.0 to 1.0, higher = closer)
        """
        if not user_coordinates or not place_data:
            return 0.5  # Neutral score if no location data
        
        distance = self._calculate_distance(user_coordinates, place_data)
        
        if distance is None:
            return 0.5
        
        # Linear decay with distance
        # Score = 1.0 at distance 0, 0.0 at max_distance
        if distance >= max_distance:
            return 0.0
        
        score = 1.0 - (distance / max_distance)
        return max(0.0, min(1.0, score))
    
    def _calculate_distance(
        self,
        user_coords: Tuple[float, float],
        place_data: Dict[str, Any]
    ) -> Optional[float]:
        """Calculate distance in km between user and place using H3."""
        try:
            place_lat = float(place_data.get('location/lat', 0))
            place_lng = float(place_data.get('location/lng', 0))
            
            if place_lat == 0 and place_lng == 0:
                return None
            
            user_lat, user_lng = user_coords
            
            # Use haversine for accurate distance
            return self._haversine_distance(
                user_lat, user_lng, place_lat, place_lng
            )
            
        except (ValueError, TypeError):
            return None
    
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
    
    def _calculate_category_score(
        self,
        place_data: Dict[str, Any],
        target_category: str
    ) -> float:
        """
        Calculate category match score.
        
        Args:
            place_data: Place metadata
            target_category: Target category from intent
            
        Returns:
            Category score (0.0 to 1.0)
        """
        if not target_category or not place_data:
            return 0.5  # Neutral if no category filter
        
        target_lower = target_category.lower()
        
        # Check main category
        main_category = place_data.get('categoryName', '').lower()
        if target_lower in main_category:
            return 1.0
        
        # Check sub-categories
        for i in range(9):
            sub_category = place_data.get(f'categories/{i}', '').lower()
            if sub_category and target_lower in sub_category:
                return 0.8
        
        # Partial match on main category
        if any(word in main_category for word in target_lower.split()):
            return 0.5
        
        return 0.0
    
    def _calculate_popularity_score(self, place_data: Dict[str, Any]) -> float:
        """
        Calculate popularity score based on rating and reviews.
        
        Uses Bayesian lower bound method to properly penalize places with few reviews.
        A 5.0★ with 1 review will score LOWER than 4.5★ with 100 reviews.
        
        This addresses the problem where places with perfect ratings but minimal
        reviews incorrectly rank above well-established places with slightly
        lower but statistically significant ratings.
        """
        if not place_data:
            return 0.3  # Low score for missing data
        
        try:
            rating = float(place_data.get('totalScore', 0))
            review_count = int(place_data.get('reviewsCount', 0))
            
            if rating <= 0:
                return 0.2  # Very low score for no rating
            
            if review_count <= 0:
                return 0.25  # Very low score for no reviews
            
            # Use the full Bayesian ranking system with lower bound method
            # This gives a conservative estimate that accounts for uncertainty
            popularity_score = bayesian_ranker.calculate_popularity_score(
                rating=rating,
                review_count=review_count,
                method="bayesian_lower_bound"  # Most conservative, penalizes few reviews
            )
            
            # Normalize to 0-1 scale (the method returns rating on 1-5 scale)
            score = (popularity_score - 1.0) / 4.0
            
            # #region agent log - Hypothesis G: Verify Bayesian ranking is applied
            # Log popularity score calculation for debugging
            logger.info(f"Bayesian score: {place_data.get('titleFormatted', 'Unknown')[:30]} "
                        f"- {rating}★ ({review_count} reviews) -> raw:{popularity_score:.3f} norm:{score:.3f}")
            # #endregion
            
            return max(0.0, min(1.0, score))
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Error calculating popularity score: {e}")
            return 0.3
    
    def _get_doc_title(self, document: Document) -> str:
        """Extract title from document for logging."""
        # Try to find title in content
        content = document.page_content
        
        for line in content.split('\n'):
            if 'title:' in line.lower():
                return line.split(':', 1)[1].strip()[:50]
        
        return content[:50]
    
    def _enrich_document(self, scored_doc: ScoredDocument) -> Document:
        """
        Create enriched document from scored document with place_data.
        
        IMPORTANT: Uses place_data content to ensure consistency between
        scoring (which uses place_data) and LLM context (which uses page_content).
        """
        # If we have valid place_data, create document content from it
        # This ensures the LLM sees the same data that was used for scoring
        if scored_doc.place_data:
            content_parts = []
            # Add key fields from place_data
            for key in ['title', 'titleFormatted', 'address', 'addressFormatted',
                       'categoryName', 'totalScore', 'reviewsCount', 'businessTime',
                       'priceRange', 'description', 'phone', 'website']:
                value = scored_doc.place_data.get(key, '')
                if value:
                    content_parts.append(f"{key}: {value}")
            
            # Add distance if available
            if scored_doc.distance_km is not None:
                content_parts.append(f"distance: {scored_doc.distance_km:.2f}km")
            
            new_content = '\n'.join(content_parts)
        else:
            # Fallback to original document content
            new_content = scored_doc.document.page_content
            if scored_doc.distance_km is not None:
                new_content += f"\ndistance: {scored_doc.distance_km:.2f}km"
        
        # Create new document with enriched content and metadata
        enriched_doc = Document(
            page_content=new_content,
            metadata={
                **scored_doc.document.metadata,
                'combined_score': scored_doc.combined_score,
                'semantic_score': scored_doc.semantic_score,
                'location_score': scored_doc.location_score,
                'category_score': scored_doc.category_score,
                'popularity_score': scored_doc.popularity_score
            }
        )
        
        if scored_doc.distance_km is not None:
            enriched_doc.metadata['distance_km'] = scored_doc.distance_km
        
        return enriched_doc
    
    def _fallback_retrieval(self, query: str, top_k: int) -> List[Document]:
        """Fallback to basic retrieval if two-stage fails."""
        try:
            logger.warning("Using fallback retrieval")
            retriever = self.vector_store_manager.get_retriever(
                search_kwargs={"k": top_k}
            )
            return retriever.get_relevant_documents(query)
        except Exception as e:
            logger.error(f"Fallback retrieval also failed: {e}")
            return []
    
    def get_scored_results(
        self,
        query: str,
        intent_result: Dict[str, Any],
        user_coordinates: Optional[Tuple[float, float]] = None,
        top_k: Optional[int] = None
    ) -> List[ScoredDocument]:
        """
        Get full scored results for debugging/analysis.
        
        Returns ScoredDocument objects instead of plain Documents.
        """
        if top_k is None:
            top_k = self.config.top_k
            
        try:
            candidates = self._stage1_semantic_search(query)
            
            if not candidates:
                return []
            
            scored_docs = self._stage2_rerank(
                candidates, 
                intent_result, 
                user_coordinates,
                query
            )
            
            scored_docs.sort(key=lambda x: x.combined_score, reverse=True)
            
            return scored_docs[:top_k]
            
        except Exception as e:
            logger.error(f"Error getting scored results: {e}")
            return []

