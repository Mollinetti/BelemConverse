"""
Vector Database Preprocessor for TF-IDF RAG Integration.

This module has been refactored to use post-retrieval filtering via TwoStageRetriever
instead of pre-filtering which loses semantic relevance.

The new approach:
1. First perform semantic search to get candidates
2. Then apply structured filters (category, location) as re-ranking

For backward compatibility, this module can still create filtered retrievers,
but the recommended approach is to use TwoStageRetriever directly.
"""

import logging
import math
from typing import Dict, Any, List, Optional, Tuple
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class VectorDatabasePreprocessor:
    """
    Preprocessor for vector database queries.
    
    This class has been updated to support both:
    1. Legacy pre-filtering mode (for backward compatibility)
    2. New post-filtering mode via TwoStageRetriever (recommended)
    """
    
    def __init__(self, vector_store_manager, data_loader):
        """
        Initialize the preprocessor.
        
        Args:
            vector_store_manager: Vector store manager for creating retrievers
            data_loader: Data loader for accessing place data
        """
        self.vector_store_manager = vector_store_manager
        self.data_loader = data_loader
        
        # Category mapping for subcategories (e.g., ice cream → cafe)
        self.subcategory_mapping = {
            'ice_cream': 'cafe',
            'acai': 'cafe',
            'coffee': 'cafe',
            'bakery': 'cafe',
            'pizza': 'restaurant',
            'sushi': 'restaurant',
            'barbecue': 'restaurant',
            'churrascaria': 'restaurant',
        }
        
        # Enhanced category search terms for database filtering
        self.category_search_terms = {
            'cafe': [
                'cafe', 'coffee', 'ice cream', 'açaí', 'bakery', 
                'Cafe', 'Ice cream shop', 'açaí shop', 'Coffee shop',
                'Espresso bar', 'Snack bar'
            ],
            'restaurant': [
                'restaurant', 'Restaurant', 'restaurante',
                'Tapioca Restaurant', 'Breakfast restaurant', 
                'hamburger restaurant', 'lunch restaurant',
                'traditional foods restaurant', 'fast food restaurant',
                'barbecue restaurant', 'churrascaria', 'Churrascaria',
                'steakhouse', 'steak house', 'Brazilian grill',
                'pizza restaurant', 'Italian restaurant',
                'sushi restaurant', 'Japanese restaurant',
                'seafood restaurant', 'Chinese restaurant',
            ],
            'hotel': ['hotel', 'Hotel', 'love hotel', 'hostel', 'pousada'],
            'bar': ['bar', 'Bar', 'Bar & grill', 'pub', 'nightclub'],
            'shopping': ['shopping', 'mall', 'center', 'store', 'loja'],
            'tourist_attraction': [
                'museum', 'church', 'park', 'monument', 'landmark',
                'historical', 'temple', 'fortress', 'plaza', 'beach'
            ]
        }
        
        # Two-stage retriever (lazy initialization)
        self._two_stage_retriever = None
    
    def get_two_stage_retriever(self):
        """
        Get or create TwoStageRetriever instance.
        
        DEPRECATED: This method uses the legacy TwoStageRetriever.
        Consider migrating to UnifiedRetriever for the consolidated architecture.
        """
        if self._two_stage_retriever is None:
            from core.two_stage_retriever import TwoStageRetriever
            self._two_stage_retriever = TwoStageRetriever(
                self.vector_store_manager,
                self.data_loader
            )
        return self._two_stage_retriever
    
    def retrieve_with_reranking(
        self,
        query: str,
        intent_result: Dict[str, Any],
        user_coordinates: Optional[Tuple[float, float]] = None,
        top_k: int = 5
    ) -> List[Document]:
        """
        Recommended retrieval method using two-stage approach.
        
        This performs semantic search first, then applies structured
        filters as re-ranking instead of pre-filtering.
        
        Args:
            query: User's query
            intent_result: TF-IDF intent detection results
            user_coordinates: Optional user coordinates (lat, lng)
            top_k: Number of results to return
            
        Returns:
            List of relevant documents with combined ranking
        """
        try:
            retriever = self.get_two_stage_retriever()
            return retriever.retrieve(
                query=query,
                intent_result=intent_result,
                user_coordinates=user_coordinates,
                top_k=top_k
            )
        except Exception as e:
            logger.error(f"Two-stage retrieval failed: {e}")
            # Fallback to legacy method
            return self._legacy_filtered_retrieval(
                query, intent_result, user_coordinates, top_k
            )
    
    def create_filtered_retriever(
        self, 
        tfidf_result: Dict[str, Any], 
        user_coordinates: Optional[Tuple[float, float]] = None
    ) -> BaseRetriever:
        """
        Legacy method: Create a filtered retriever based on TF-IDF results.
        
        DEPRECATED: Use retrieve_with_reranking() instead for better results.
        
        This method is kept for backward compatibility but now stores
        additional metadata for post-processing.
        
        Args:
            tfidf_result: TF-IDF intent detection results
            user_coordinates: Optional user coordinates (lat, lng)
            
        Returns:
            Retriever with filtered places attached as metadata
        """
        try:
            primary_category = tfidf_result.get('primary_category', '')
            intents = tfidf_result.get('intents', [])
            has_location_intent = any(
                intent.get('intent') == 'location' for intent in intents
            )
            
            logger.info(f"Creating filtered retriever for category: '{primary_category}', "
                       f"location_intent: {has_location_intent}")
            
            # Get base retriever
            retriever = self.vector_store_manager.get_retriever()
            
            # Get filtered places for metadata
            all_places = self.data_loader.load_all_places()
            filtered_places = self._filter_places_by_category(
                all_places, primary_category
            )
            
            # Apply location filtering if needed
            if has_location_intent and user_coordinates:
                filtered_places = self._filter_places_by_location(
                    filtered_places, user_coordinates, max_distance_km=5.0
                )
            
            # Attach filtered places as metadata
            retriever._filtered_places = filtered_places
            retriever._is_filtered = True
            retriever._intent_result = tfidf_result
            retriever._user_coordinates = user_coordinates
            
            logger.info(f"Created retriever with {len(filtered_places)} filtered places")
            return retriever
            
        except Exception as e:
            logger.error(f"Error creating filtered retriever: {e}")
            return self.vector_store_manager.get_retriever()
    
    def _legacy_filtered_retrieval(
        self,
        query: str,
        intent_result: Dict[str, Any],
        user_coordinates: Optional[Tuple[float, float]],
        top_k: int
    ) -> List[Document]:
        """Legacy fallback retrieval method."""
        try:
            retriever = self.create_filtered_retriever(
                intent_result, user_coordinates
            )
            docs = retriever.get_relevant_documents(query)
            return docs[:top_k]
        except Exception as e:
            logger.error(f"Legacy retrieval failed: {e}")
            return []
    
    def _filter_places_by_category(
        self,
        places: List[Dict[str, Any]],
        category: str
    ) -> List[Dict[str, Any]]:
        """Filter places by category."""
        if not category:
            return places
        
        # Map subcategory to main category if needed
        search_category = self.subcategory_mapping.get(category, category)
        search_terms = self.category_search_terms.get(
            search_category, [category]
        )
        
        search_terms_lower = set(term.lower() for term in search_terms)
        filtered = []
        
        for place in places:
            if self._place_matches_category(place, search_terms_lower):
                filtered.append(place)
        
        logger.info(f"Category filter: {len(places)} → {len(filtered)} places")
        return filtered
    
    def _place_matches_category(
        self,
        place: Dict[str, Any],
        search_terms: set
    ) -> bool:
        """Check if place matches any search terms."""
        # Check main category
        main_category = place.get('categoryName', '').lower()
        if any(term in main_category for term in search_terms):
            return True
        
        # Check sub-categories
        for i in range(9):
            sub_cat = place.get(f'categories/{i}', '').lower()
            if sub_cat and any(term in sub_cat for term in search_terms):
                return True
        
        return False
    
    def _filter_places_by_location(
        self,
        places: List[Dict[str, Any]],
        user_coordinates: Tuple[float, float],
        max_distance_km: float = 5.0
    ) -> List[Dict[str, Any]]:
        """Filter and sort places by distance from user."""
        user_lat, user_lng = user_coordinates
        places_with_distance = []
        
        for place in places:
            try:
                place_lat = float(place.get('location/lat', 0))
                place_lng = float(place.get('location/lng', 0))
                
                if place_lat == 0 and place_lng == 0:
                    continue
                
                distance = self._haversine_distance(
                    user_lat, user_lng, place_lat, place_lng
                )
                
                if distance <= max_distance_km:
                    place_copy = place.copy()
                    place_copy['distance_km'] = distance
                    places_with_distance.append(place_copy)
                    
            except (ValueError, TypeError):
                continue
        
        # Sort by distance
        places_with_distance.sort(key=lambda x: x['distance_km'])
        
        logger.info(f"Location filter: {len(places)} → "
                   f"{len(places_with_distance)} places within {max_distance_km}km")
        
        return places_with_distance
    
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
    
    def get_places_near_location(
        self,
        coordinates: Tuple[float, float],
        category: Optional[str] = None,
        max_distance_km: float = 2.0,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Utility method to get places near a location.
        
        Args:
            coordinates: (lat, lng) coordinates
            category: Optional category filter
            max_distance_km: Maximum distance in km
            limit: Maximum number of results
            
        Returns:
            List of places sorted by distance
        """
        try:
            all_places = self.data_loader.load_all_places()
            
            # Apply category filter if specified
            if category:
                all_places = self._filter_places_by_category(all_places, category)
            
            # Apply location filter
            nearby_places = self._filter_places_by_location(
                all_places, coordinates, max_distance_km
            )
            
            return nearby_places[:limit]
            
        except Exception as e:
            logger.error(f"Error getting places near location: {e}")
            return []
