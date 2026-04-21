"""
Search Fallback Orchestrator - Manages OSM fallback when database search fails.

This module evaluates search results and decides when to invoke OSM fallback,
then merges the results intelligently while preserving source labels.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class FallbackReason(Enum):
    """Reasons for triggering OSM fallback."""
    NONE = "none"
    EMPTY_RESULTS = "empty_results"
    LOW_CONFIDENCE = "low_confidence"
    GEOGRAPHIC_GAP = "geographic_gap"
    NAME_NOT_FOUND = "name_not_found"
    VERIFICATION_QUERY = "verification_query"


@dataclass
class FallbackDecision:
    """Decision about whether to use OSM fallback."""
    should_fallback: bool
    reason: FallbackReason
    details: str = ""
    extracted_name: Optional[str] = None


@dataclass
class MergedResult:
    """Result of merging database and OSM results."""
    documents: List[Document]
    db_count: int
    osm_count: int
    fallback_used: bool
    fallback_reason: FallbackReason


class SearchFallbackOrchestrator:
    """
    Orchestrates the OSM fallback search logic.
    
    Evaluates database search results against various failure conditions
    and decides when to invoke OSM fallback, then merges results.
    """
    
    # Thresholds for fallback triggers
    LOW_CONFIDENCE_THRESHOLD = 0.3
    GEOGRAPHIC_GAP_KM = 5.0
    NAME_SIMILARITY_THRESHOLD = 0.7
    
    # Maximum OSM results to include
    MAX_OSM_RESULTS = 5
    
    def __init__(
        self,
        low_confidence_threshold: float = LOW_CONFIDENCE_THRESHOLD,
        geographic_gap_km: float = GEOGRAPHIC_GAP_KM,
        name_similarity_threshold: float = NAME_SIMILARITY_THRESHOLD,
        max_osm_results: int = MAX_OSM_RESULTS
    ):
        """
        Initialize the orchestrator.
        
        Args:
            low_confidence_threshold: Score below which results are low confidence
            geographic_gap_km: Distance in km that triggers geographic gap fallback
            name_similarity_threshold: Similarity threshold for name matching
            max_osm_results: Maximum OSM results to include in merge
        """
        self.low_confidence_threshold = low_confidence_threshold
        self.geographic_gap_km = geographic_gap_km
        self.name_similarity_threshold = name_similarity_threshold
        self.max_osm_results = max_osm_results
        
        # Lazy load the OSM searcher to avoid circular imports
        self._osm_searcher = None
    
    @property
    def osm_searcher(self):
        """Lazy load the OSM realtime searcher."""
        if self._osm_searcher is None:
            from belem_converse.ingest.osm_realtime_search import get_realtime_searcher
            self._osm_searcher = get_realtime_searcher()
        return self._osm_searcher
    
    def _extract_place_name(self, query: str) -> Optional[str]:
        """
        Extract a specific place name from the query.
        
        Looks for quoted names or patterns indicating a specific place search.
        """
        # Quoted names
        quoted = re.search(r'["\']([^"\']+)["\']', query)
        if quoted:
            return quoted.group(1).strip()
        
        # Patterns for name extraction
        patterns = [
            r'(?:called|named|chamad[ao])\s+(.+?)(?:\s+(?:is|está|still|ainda)|[?.!]|$)',
            r'(?:where is|onde fica|cadê|achar)\s+(?:the\s+|o\s+|a\s+)?(.+?)(?:\s*[?.!]|$)',
            r'(?:find|encontr[ae]|procur[ae]|buscar?)\s+(?:the\s+|o\s+|a\s+)?(.+?)(?:\s+(?:near|perto|próximo)|[?.!]|$)',
            r'(?:is|está|existe)\s+(?:the\s+|o\s+|a\s+)?(.+?)\s+(?:still|ainda|open|aberto|closed|fechado)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Filter out generic terms and short words
                generic_terms = {'restaurant', 'restaurante', 'hotel', 'cafe', 'café', 'bar', 
                                'museum', 'museu', 'park', 'parque', 'church', 'igreja'}
                if len(name) > 3 and name.lower() not in generic_terms:
                    return name
        
        return None
    
    def _is_verification_query(self, query: str, intent_result: Optional[Dict] = None) -> bool:
        """
        Check if the query is asking about a place's existence or status.
        
        Args:
            query: User query
            intent_result: Optional intent classification result
        """
        # Check intent result first
        if intent_result and intent_result.get('primary_intent') == 'verification':
            return True
        
        # Pattern-based detection
        verification_patterns = [
            r'\b(still open|ainda aberto|ainda abre|ainda funciona)\b',
            r'\b(is .+ open|está .+ aberto|.+ está aberto)\b',
            r'\b(does .+ exist|.+ existe|existe .+)\b',
            r'\b(is .+ closed|está .+ fechado|.+ fechou)\b',
            r'\b(when does .+ open|quando .+ abre)\b',
            r'\b(check if|verificar se|confirmar se)\b',
        ]
        
        query_lower = query.lower()
        for pattern in verification_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return True
        
        return False
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names."""
        try:
            from rapidfuzz import fuzz
            return fuzz.ratio(name1.lower(), name2.lower()) / 100.0
        except ImportError:
            # Fallback to simple comparison
            n1, n2 = name1.lower(), name2.lower()
            if n1 == n2:
                return 1.0
            if n1 in n2 or n2 in n1:
                return 0.8
            return 0.0
    
    def evaluate_fallback_need(
        self,
        query: str,
        db_results: List[Document],
        user_coordinates: Optional[Tuple[float, float]] = None,
        intent_result: Optional[Dict] = None,
        scores: Optional[List[float]] = None
    ) -> FallbackDecision:
        """
        Evaluate whether OSM fallback is needed.
        
        Args:
            query: User's search query
            db_results: Results from database search
            user_coordinates: User's location
            intent_result: Intent classification result
            scores: Confidence scores for db_results
            
        Returns:
            FallbackDecision indicating whether to fallback and why
        """
        # Check for empty results
        if not db_results:
            return FallbackDecision(
                should_fallback=True,
                reason=FallbackReason.EMPTY_RESULTS,
                details="No results found in database"
            )
        
        # Check for verification query
        if self._is_verification_query(query, intent_result):
            extracted_name = self._extract_place_name(query)
            return FallbackDecision(
                should_fallback=True,
                reason=FallbackReason.VERIFICATION_QUERY,
                details=f"Verification query detected for: {extracted_name or 'unknown place'}",
                extracted_name=extracted_name
            )
        
        # Check for low confidence scores
        if scores:
            max_score = max(scores) if scores else 0
            if max_score < self.low_confidence_threshold:
                return FallbackDecision(
                    should_fallback=True,
                    reason=FallbackReason.LOW_CONFIDENCE,
                    details=f"All results below confidence threshold (max: {max_score:.2f})"
                )
        
        # Check for geographic gap
        if user_coordinates:
            nearest_distance = float('inf')
            for doc in db_results:
                dist = doc.metadata.get('distance_km')
                if dist is not None and dist < nearest_distance:
                    nearest_distance = dist
            
            if nearest_distance > self.geographic_gap_km:
                return FallbackDecision(
                    should_fallback=True,
                    reason=FallbackReason.GEOGRAPHIC_GAP,
                    details=f"Nearest result is {nearest_distance:.1f}km away"
                )
        
        # Check for specific name not found
        extracted_name = self._extract_place_name(query)
        if extracted_name:
            name_found = False
            for doc in db_results:
                title = doc.metadata.get('title', '')
                if self._calculate_name_similarity(extracted_name, title) >= self.name_similarity_threshold:
                    name_found = True
                    break
            
            if not name_found:
                return FallbackDecision(
                    should_fallback=True,
                    reason=FallbackReason.NAME_NOT_FOUND,
                    details=f"Specific place '{extracted_name}' not found in results",
                    extracted_name=extracted_name
                )
        
        # No fallback needed
        return FallbackDecision(
            should_fallback=False,
            reason=FallbackReason.NONE,
            details="Database results are satisfactory"
        )
    
    def _deduplicate_results(
        self,
        db_docs: List[Document],
        osm_docs: List[Document]
    ) -> List[Document]:
        """
        Deduplicate OSM results against database results.
        
        Removes OSM documents that match database documents by name and location.
        """
        if not osm_docs:
            return []
        
        from belem_converse.ingest.place_matcher import PlaceMatcher
        
        filtered_osm = []
        for osm_doc in osm_docs:
            osm_name = osm_doc.metadata.get('title', '')
            osm_lat = osm_doc.metadata.get('location/lat', 0)
            osm_lon = osm_doc.metadata.get('location/lng', 0)
            
            is_duplicate = False
            for db_doc in db_docs:
                db_name = db_doc.metadata.get('title', '')
                db_lat = db_doc.metadata.get('location/lat', 0)
                db_lon = db_doc.metadata.get('location/lng', 0)
                
                # Check name similarity
                name_sim = self._calculate_name_similarity(osm_name, db_name)
                
                # Check distance
                try:
                    distance = PlaceMatcher.haversine_distance(
                        float(osm_lat), float(osm_lon),
                        float(db_lat), float(db_lon)
                    )
                except (ValueError, TypeError):
                    distance = float('inf')
                
                # Consider duplicate if close and similar name
                if distance < 50 and name_sim > 0.7:
                    is_duplicate = True
                    break
                # Or very similar name even if farther
                if name_sim > 0.9:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                filtered_osm.append(osm_doc)
        
        return filtered_osm
    
    def _merge_results(
        self,
        db_docs: List[Document],
        osm_docs: List[Document]
    ) -> List[Document]:
        """
        Merge database and OSM documents.
        
        Database results are ranked higher, OSM results are deduplicated
        and appended with source labels.
        """
        # Ensure all DB docs have source label
        for doc in db_docs:
            if 'data_source' not in doc.metadata:
                doc.metadata['data_source'] = 'database'
        
        # Deduplicate OSM results
        unique_osm = self._deduplicate_results(db_docs, osm_docs)
        
        # Limit OSM results
        unique_osm = unique_osm[:self.max_osm_results]
        
        # Merge: DB results first, then OSM
        merged = db_docs + unique_osm
        
        return merged
    
    def execute_fallback(
        self,
        query: str,
        db_results: List[Document],
        user_coordinates: Tuple[float, float],
        decision: FallbackDecision,
        categories: Optional[List[str]] = None
    ) -> MergedResult:
        """
        Execute the OSM fallback search and merge results.
        
        Args:
            query: User's search query
            db_results: Results from database search
            user_coordinates: User's location
            decision: Fallback decision from evaluate_fallback_need
            categories: Optional categories to search
            
        Returns:
            MergedResult with combined documents
        """
        if not decision.should_fallback:
            return MergedResult(
                documents=db_results,
                db_count=len(db_results),
                osm_count=0,
                fallback_used=False,
                fallback_reason=FallbackReason.NONE
            )
        
        logger.info(f"Executing OSM fallback: {decision.reason.value} - {decision.details}")
        
        # Perform OSM search
        osm_results = []
        
        if decision.reason == FallbackReason.NAME_NOT_FOUND and decision.extracted_name:
            # Search by specific name
            osm_results = self.osm_searcher.search_by_name(
                decision.extracted_name,
                user_coordinates,
                radius=5000
            )
        elif decision.reason == FallbackReason.VERIFICATION_QUERY and decision.extracted_name:
            # Verification query - search by name
            osm_results = self.osm_searcher.search_by_name(
                decision.extracted_name,
                user_coordinates,
                radius=10000  # Wider radius for verification
            )
        else:
            # General fallback search
            osm_results = self.osm_searcher.search(
                query,
                user_coordinates,
                categories=categories
            )
        
        # Merge results
        merged = self._merge_results(db_results, osm_results)
        
        return MergedResult(
            documents=merged,
            db_count=len(db_results),
            osm_count=len([d for d in merged if d.metadata.get('data_source') == 'osm_realtime']),
            fallback_used=True,
            fallback_reason=decision.reason
        )
    
    def search_with_fallback(
        self,
        query: str,
        db_results: List[Document],
        user_coordinates: Optional[Tuple[float, float]] = None,
        intent_result: Optional[Dict] = None,
        scores: Optional[List[float]] = None,
        categories: Optional[List[str]] = None
    ) -> MergedResult:
        """
        Complete search with automatic fallback evaluation and execution.
        
        This is the main entry point for the fallback system.
        
        Args:
            query: User's search query
            db_results: Results from database search
            user_coordinates: User's location
            intent_result: Intent classification result
            scores: Confidence scores for db_results
            categories: Categories to search in OSM fallback
            
        Returns:
            MergedResult with combined documents
        """
        # Evaluate if fallback is needed
        decision = self.evaluate_fallback_need(
            query, db_results, user_coordinates, intent_result, scores
        )
        
        if not decision.should_fallback:
            return MergedResult(
                documents=db_results,
                db_count=len(db_results),
                osm_count=0,
                fallback_used=False,
                fallback_reason=FallbackReason.NONE
            )
        
        if not user_coordinates:
            logger.warning("OSM fallback requested but no user coordinates provided")
            return MergedResult(
                documents=db_results,
                db_count=len(db_results),
                osm_count=0,
                fallback_used=False,
                fallback_reason=FallbackReason.NONE
            )
        
        # Execute fallback
        return self.execute_fallback(
            query, db_results, user_coordinates, decision, categories
        )


# Singleton instance
_orchestrator: Optional[SearchFallbackOrchestrator] = None


def get_fallback_orchestrator() -> SearchFallbackOrchestrator:
    """Get or create the singleton fallback orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SearchFallbackOrchestrator()
    return _orchestrator


