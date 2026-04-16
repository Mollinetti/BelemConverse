"""
Enhanced RAG Agent with TF-IDF Intent Classifier Integration.

This module provides a clean, efficient RAG agent that uses:
1. TF-IDF classifier for intent detection
2. Two-stage retrieval (semantic search + structured re-ranking)
3. Optional tour planning capabilities

Pipeline: Query → TF-IDF Intent → Two-Stage Retrieval → LLM Response
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate

from utils.models import ModelManager
from data.vector_store import VectorStoreManager
from classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier
from data.vector_database_preprocessor import VectorDatabasePreprocessor
from data.data_loader import DataLoader
from utils.exceptions import RAGAgentError
from utils.bayesian_ranking import bayesian_ranker
from utils.config import (
    TRAVEL_GUIDE_PROMPT_EN, 
    TRAVEL_GUIDE_PROMPT_PT,
    UNSUPPORTED_LANGUAGE_RESPONSE
)
from utils.conversation_memory import ConversationMemory

logger = logging.getLogger(__name__)


class EnhancedRAGAgent:
    """
    Enhanced RAG Agent with TF-IDF intent classification and two-stage retrieval.
    
    Pipeline: Query → TF-IDF Intent Detection → Two-Stage Retrieval → LLM Response
    
    The two-stage retrieval approach:
    1. Stage 1: Pure semantic search for initial candidates
    2. Stage 2: Re-rank using structured filters (location, category, popularity)
    """
    
    def __init__(self, vector_store_manager: VectorStoreManager, llm_model):
        """
        Initialize the Enhanced RAG Agent.
        
        Args:
            vector_store_manager: Vector store manager for document retrieval
            llm_model: LLM model for text generation
        """
        self.vector_store_manager = vector_store_manager
        self.llm_model = llm_model
        self.data_loader = DataLoader()
        
        # Initialize core components
        self.tfidf_classifier = SimpleTFIDFIntentClassifier()
        self.db_preprocessor = VectorDatabasePreprocessor(
            vector_store_manager, self.data_loader
        )
        
        # Tour planner (lazy initialization)
        self._tour_planner = None
        
        # Initialize conversation memory (stores up to 10 interactions locally)
        self.conversation_memory = ConversationMemory()
        
        # Initialize prompt templates with conversation_history variable
        self.travel_guide_prompt_en = PromptTemplate(
            template=TRAVEL_GUIDE_PROMPT_EN,
            input_variables=["context", "question", "user_location", "conversation_history"]
        )
        self.travel_guide_prompt_pt = PromptTemplate(
            template=TRAVEL_GUIDE_PROMPT_PT,
            input_variables=["context", "question", "user_location", "conversation_history"]
        )
        
        # Performance metrics
        self.performance_metrics = {
            'total_queries': 0,
            'avg_intent_time': 0.0,
            'avg_retrieval_time': 0.0,
            'avg_llm_time': 0.0,
            'avg_total_time': 0.0
        }
        
        logger.info("Enhanced RAG Agent initialized with two-stage retrieval")
    
    def _get_tour_planner(self):
        """Lazy initialization of tour planner."""
        if self._tour_planner is None:
            try:
                from core.tour_planner import TourPlanner
                self._tour_planner = TourPlanner(self.data_loader)
                logger.info("Tour planner initialized")
            except ImportError:
                logger.warning("Tour planner not available")
                self._tour_planner = None
        return self._tour_planner
    
    @property
    def tour_planner(self):
        """Public access to tour planner."""
        return self._get_tour_planner()
    
    def query(
        self, 
        question: str, 
        user_coordinates: Optional[Tuple[float, float]] = None,
        top_k: int = 5
    ) -> str:
        """
        Process a user query using the two-stage RAG pipeline.
        
        Flow:
        1. TF-IDF Intent Detection
        2. Check for tour planning intent → route to tour planner
        3. Two-Stage Retrieval (semantic + structured re-ranking)
        4. LLM Response Generation
        
        Args:
            question: User's question
            user_coordinates: Optional user coordinates (lat, lng)
            top_k: Number of final results to return
            
        Returns:
            Formatted response string
        """
        start_time = time.time()
        
        try:
            logger.info(f"Processing query: '{question}'")
            if user_coordinates:
                logger.info(f"User coordinates: {user_coordinates}")
            
            # Step 1: TF-IDF Intent Detection
            intent_start = time.time()
            intent_result = self._detect_intent(question)
            intent_time = time.time() - intent_start
            
            logger.info(f"Intent detection completed in {intent_time:.3f}s")
            logger.info(f"Primary intent: {intent_result.get('primary_intent', 'unknown')} "
                       f"(confidence: {intent_result.get('primary_intent_confidence', 0.0):.3f})")
            logger.info(f"Primary category: {intent_result.get('primary_category', 'none')} "
                       f"(confidence: {intent_result.get('primary_category_confidence', 0.0):.3f})")
            
            # Step 2: Check for tour planning intent
            if self._is_tour_planning_query(intent_result, question):
                logger.info("Detected tour planning intent, routing to tour planner")
                return self._handle_tour_planning(
                    question, intent_result, user_coordinates
                )
            
            # Step 3: Two-Stage Retrieval
            retrieval_start = time.time()
            documents = self.db_preprocessor.retrieve_with_reranking(
                query=question,
                intent_result=intent_result,
                user_coordinates=user_coordinates,
                top_k=top_k
            )
            retrieval_time = time.time() - retrieval_start
            
            logger.info(f"Two-stage retrieval completed in {retrieval_time:.3f}s")
            logger.info(f"Retrieved {len(documents)} documents")
            
            # Step 4: LLM Response Generation
            llm_start = time.time()
            response = self._generate_response(
                question, documents, intent_result, user_coordinates, top_k
            )
            llm_time = time.time() - llm_start
            
            total_time = time.time() - start_time
            
            # Update performance metrics
            self._update_metrics(intent_time, retrieval_time, llm_time, total_time)
            
            logger.info(f"Query completed in {total_time:.3f}s")
            logger.info(f"Performance breakdown - Intent: {intent_time:.3f}s, "
                       f"Retrieval: {retrieval_time:.3f}s, LLM: {llm_time:.3f}s")
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            raise RAGAgentError(f"Failed to process query: {e}")
    
    def _detect_intent(self, question: str) -> Dict[str, Any]:
        """Detect intent using TF-IDF classifier."""
        try:
            result = self.tfidf_classifier.predict(question)
            result['original_query'] = question
            return result
        except Exception as e:
            logger.error(f"Intent detection failed: {e}")
            return {
                'primary_intent': 'unknown',
                'primary_intent_confidence': 0.0,
                'primary_category': '',
                'primary_category_confidence': 0.0,
                'intents': [],
                'categories': [],
                'original_query': question
            }
    
    def _is_tour_planning_query(
        self, 
        intent_result: Dict[str, Any], 
        question: str
    ) -> bool:
        """Check if the query is asking for tour/itinerary planning."""
        # Check if tour_planning is the PRIMARY intent with good confidence
        primary_intent = intent_result.get('primary_intent', '')
        primary_confidence = intent_result.get('primary_intent_confidence', 0.0)
        
        if primary_intent == 'tour_planning' and primary_confidence >= 0.3:
            return True
        
        # Fallback to keyword detection - require explicit tour keywords
        question_lower = question.lower()
        tour_keywords = [
            'tour', 'itinerary', 'day trip', 'plan my day', 'what to do in a day',
            'roteiro', 'passeio pelo', 'o que fazer em um dia', 'dia em belém',
            'planejar meu dia', 'one day itinerary', 'walking tour', 'food tour',
            'create an itinerary', 'plan a trip'
        ]
        
        return any(keyword in question_lower for keyword in tour_keywords)
    
    def _handle_tour_planning(
        self,
        question: str,
        intent_result: Dict[str, Any],
        user_coordinates: Optional[Tuple[float, float]]
    ) -> str:
        """Handle tour planning requests."""
        try:
            tour_planner = self._get_tour_planner()
            
            if tour_planner is None:
                # Tour planner not available, fall back to regular query
                logger.warning("Tour planner not available, using regular query")
                documents = self.db_preprocessor.retrieve_with_reranking(
                    query=question,
                    intent_result=intent_result,
                    user_coordinates=user_coordinates,
                    top_k=10
                )
                return self._generate_response(
                    question, documents, intent_result, user_coordinates, 10
                )
            
            # Parse tour parameters from question
            tour_params = self._parse_tour_parameters(question, intent_result)
            
            # Generate tour itinerary
            itinerary = tour_planner.plan_tour(
                user_coordinates=user_coordinates or (-1.4558, -48.4902),  # Default: Belém center
                duration_hours=tour_params.get('duration', 8),
                start_time=tour_params.get('start_time', '09:00'),
                categories=tour_params.get('categories'),
                num_stops=tour_params.get('num_stops', 5)
            )
            
            # Format itinerary for LLM response
            return self._generate_tour_response(question, itinerary, user_coordinates)
            
        except Exception as e:
            logger.error(f"Tour planning failed: {e}")
            # Fallback to regular response
            return "I'm sorry, I couldn't create a tour itinerary right now. Please try asking for specific places instead."
    
    def _parse_tour_parameters(
        self, 
        question: str, 
        intent_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse tour parameters from the question."""
        params = {
            'duration': 8,  # Default 8 hours
            'start_time': '09:00',
            'num_stops': 5,
            'categories': None
        }
        
        question_lower = question.lower()
        
        # Detect duration
        if 'half day' in question_lower or 'meio dia' in question_lower:
            params['duration'] = 4
            params['num_stops'] = 3
        elif 'full day' in question_lower or 'dia inteiro' in question_lower:
            params['duration'] = 10
            params['num_stops'] = 6
        
        # === AÇAÍ DETECTION (STRICT) ===
        # All possible misspellings and variations of açaí
        acai_keywords = [
            'açaí', 'acai', 'açai', 'acaí',  # Common variations
            'assai', 'asai', 'assaí', 'asaí',  # Misspellings without cedilla
            'açaizeiro', 'acaizeiro',  # Place names
            'açaí shop', 'acai shop', 'açaí place', 'acai place',
            'tomar açaí', 'tomar acai', 'comer açaí', 'comer acai',
            'tigela de açaí', 'acai bowl', 'açaí bowl'
        ]
        
        # === TOURIST ATTRACTION DETECTION (FLEXIBLE) ===
        # Comprehensive list of tourist site keywords
        tourist_keywords = [
            # General tourism
            'tourist', 'turista', 'tourism', 'turismo', 'sightseeing', 'sight seeing',
            'attraction', 'atração', 'atrações', 'ponto turístico', 'pontos turísticos',
            'conhecer', 'explore', 'explorar', 'visit', 'visitar',
            # Museums
            'museum', 'museu', 'gallery', 'galeria', 'exhibition', 'exposição',
            # Parks and nature
            'park', 'parque', 'garden', 'jardim', 'botanical', 'botânico',
            'nature', 'natureza', 'zoo', 'zoológico', 'ecological', 'ecológico',
            # Historical sites
            'historical', 'histórico', 'history', 'história', 'heritage', 'patrimônio',
            'ruins', 'ruínas', 'archaeological', 'arqueológico', 'ancient', 'antigo',
            'colonial', 'old town', 'cidade velha', 'century', 'século',
            # Religious sites
            'church', 'igreja', 'cathedral', 'catedral', 'basilica', 'basílica',
            'chapel', 'capela', 'temple', 'templo', 'monastery', 'mosteiro',
            # Monuments
            'monument', 'monumento', 'statue', 'estátua', 'memorial', 'sculpture',
            # Plazas and squares
            'plaza', 'praça', 'square', 'largo', 'terreiro',
            # Fortresses
            'fortress', 'fortaleza', 'fort', 'forte', 'castle', 'castelo',
            # Beaches and waterfront
            'beach', 'praia', 'waterfront', 'orla', 'pier', 'dock', 'doca',
            'port', 'porto', 'bay', 'baía', 'island', 'ilha',
            # Theaters and cultural venues
            'theater', 'teatro', 'opera', 'ópera', 'cultural center', 'centro cultural',
            # Famous Belém spots
            'ver-o-peso', 'ver o peso', 'estação das docas', 'mangal das garças',
            'theatro da paz', 'forte do presépio', 'forte do castelo'
        ]
        
        # Detect specific tour types - ORDER MATTERS (most specific first)
        # Açaí tour (STRICT - check first with comprehensive misspelling handling)
        if any(word in question_lower for word in acai_keywords):
            # Açaí tours should ONLY search for açaí shops, not general ice cream
            params['categories'] = ['açaí', 'acai', 'açaí shop', 'acai shop', 'açaizeiro']
            params['duration'] = 4  # Açaí tours are shorter
            params['num_stops'] = 4
            logger.info(f"Detected AÇAÍ tour from keywords in: {question_lower[:50]}...")
        # Tourist attractions (FLEXIBLE - comprehensive list)
        # BUT: check if it's a generic/vague tour request (should use default mixed instead)
        elif any(word in question_lower for word in tourist_keywords):
            # Check for GENERIC tour requests - these should use default mixed categories
            generic_patterns = [
                'plan a tour', 'plan a day', 'plan my day', 'planejar meu dia',
                'what to do in', 'o que fazer em', 'things to do', 'coisas para fazer',
                'one day in', 'um dia em', 'a day in', 'spend a day', 'passar um dia',
                'tour for me', 'roteiro para mim', 'itinerary for me'
            ]
            is_generic = any(pattern in question_lower for pattern in generic_patterns)
            
            if is_generic:
                # Generic request - let it fall through to default (tourist + restaurants)
                logger.info(f"Detected GENERIC tour request, will use default mixed categories: {question_lower[:50]}...")
            else:
                # Specific tourist attraction request
                params['categories'] = [
                    'tourist_attraction', 'museum', 'park', 'monument', 'church', 
                    'teatro', 'fortress', 'fortaleza', 'historical', 'beach', 'praia',
                    'plaza', 'praça', 'cathedral', 'memorial', 'garden', 'cultural'
                ]
                logger.info(f"Detected TOURIST ATTRACTION tour from keywords in: {question_lower[:50]}...")
        # Cultural/history tour
        elif any(word in question_lower for word in ['cultural', 'history', 'histór', 'histórico', 'heritage', 'patrimônio']):
            params['categories'] = ['tourist_attraction', 'museum', 'church', 'historical', 'monument']
        # Night/bar tour
        elif any(word in question_lower for word in ['night', 'noite', 'bar', 'drink', 'bares', 'drinks', 'boteco']):
            params['categories'] = ['bar', 'pub', 'restaurant', 'boteco']
            params['start_time'] = '18:00'
        # Traditional/regional food
        elif any(word in question_lower for word in ['tradicional', 'traditional', 'regional', 'típic', 'paraense']):
            params['categories'] = ['restaurant', 'restaurante']
        # General food tour
        elif any(word in question_lower for word in ['food', 'comida', 'gastronom', 'restaur', 'almoço', 'jantar', 'lunch', 'dinner']):
            params['categories'] = ['restaurant', 'cafe']
        # Cafe tour (NOT açaí - cafes are separate)
        elif any(word in question_lower for word in ['café', 'cafe', 'coffee', 'cafeteria']):
            params['categories'] = ['cafe', 'coffee', 'cafeteria']
        
        # === DEFAULT CHECK: Generic/vague tour requests ===
        # This handles requests like "plan a tour for me" or "what to do in Belém"
        # Check BEFORE applying intent categories to avoid overriding the default
        generic_patterns = [
            'plan a tour', 'plan a day', 'plan my day', 'planejar meu dia',
            'what to do in', 'o que fazer em', 'things to do', 'coisas para fazer',
            'one day in', 'um dia em', 'a day in', 'spend a day', 'passar um dia',
            'tour for me', 'roteiro para mim', 'itinerary for me', 'roteiro para',
            'show me around', 'me mostre', 'conhecer a cidade', 'visit the city'
        ]
        is_generic_request = any(pattern in question_lower for pattern in generic_patterns)
        
        # Get categories from intent if not specified AND not a generic request
        if params['categories'] is None and not is_generic_request:
            primary_category = intent_result.get('primary_category', '')
            if primary_category:
                # Map classifier category to tour categories
                if primary_category == 'acai':
                    params['categories'] = ['açaí', 'acai', 'açaí shop', 'acai shop']
                elif primary_category == 'tourist_attraction':
                    params['categories'] = [
                        'tourist_attraction', 'museum', 'park', 'monument', 'church',
                        'teatro', 'fortress', 'beach', 'plaza', 'cathedral'
                    ]
                else:
                    params['categories'] = [primary_category]
        
        # === DEFAULT: If still no categories specified (or it's a generic request), use mixed ===
        if params['categories'] is None:
            logger.info("Generic/vague tour request - defaulting to tourist attractions + restaurants")
            params['categories'] = [
                # Tourist attractions
                'tourist_attraction', 'museum', 'park', 'monument', 'church', 
                'teatro', 'fortress', 'historical', 'beach', 'plaza', 'cathedral',
                # Restaurants for lunch/dinner
                'restaurant', 'restaurante', 'traditional', 'regional'
            ]
            params['num_stops'] = 6  # More stops for a full day experience
        
        return params
    
    def _generate_tour_response(
        self,
        question: str,
        itinerary: Any,
        user_coordinates: Optional[Tuple[float, float]]
    ) -> str:
        """Generate LLM response for tour itinerary."""
        try:
            from utils.config import TOUR_PLANNER_PROMPT_EN, TOUR_PLANNER_PROMPT_PT
            
            # Detect language
            language = self._detect_language(question)
            
            # Format itinerary as context
            context = itinerary.to_context_string() if hasattr(itinerary, 'to_context_string') else str(itinerary)
            
            # #region agent log - Log itinerary context being passed to LLM
            import json
            _debug_log_path = "/Users/marcomollinetti/Documents/Projects/BelemConverse/.cursor/debug.log"
            try:
                import time as _time
                with open(_debug_log_path, "a") as f:
                    f.write(json.dumps({"hypothesisId": "A", "location": "enhanced_rag_agent._generate_tour_response", "message": "ITINERARY CONTEXT PASSED TO LLM", "data": {"context_length": len(context), "context_preview": context[:2000], "num_stops": len(itinerary.stops) if hasattr(itinerary, 'stops') else 0}, "timestamp": _time.time(), "sessionId": "debug-session"}) + "\n")
            except: pass
            # #endregion
            
            # Create location context
            user_location_context = self._create_location_context(user_coordinates, language)
            
            # Select prompt
            if language == 'pt':
                prompt_template = PromptTemplate(
                    template=TOUR_PLANNER_PROMPT_PT,
                    input_variables=["context", "question", "user_location"]
                )
            else:
                prompt_template = PromptTemplate(
                    template=TOUR_PLANNER_PROMPT_EN,
                    input_variables=["context", "question", "user_location"]
                )
            
            formatted_prompt = prompt_template.format(
                context=context,
                question=question,
                user_location=user_location_context
            )
            
            # #region agent log - Log full prompt being sent to LLM
            try:
                with open(_debug_log_path, "a") as f:
                    f.write(json.dumps({"hypothesisId": "B", "location": "enhanced_rag_agent._generate_tour_response", "message": "FULL PROMPT TO LLM", "data": {"prompt_length": len(formatted_prompt), "prompt_preview": formatted_prompt[:3000]}, "timestamp": _time.time(), "sessionId": "debug-session"}) + "\n")
            except: pass
            # #endregion
            
            response = self.llm_model.invoke(formatted_prompt)
            response_text = response.content
            
            # Clean any prompt leakage
            response_text = self._clean_response_leakage(response_text)
            
            return response_text
            
        except Exception as e:
            logger.error(f"Tour response generation failed: {e}")
            # Return raw itinerary if LLM fails
            return str(itinerary) if itinerary else "Unable to generate tour."
    
    def _generate_response(
        self, 
        question: str, 
        documents: List[Document], 
        intent_result: Dict[str, Any], 
        user_coordinates: Optional[Tuple[float, float]], 
        top_k: int
    ) -> str:
        """Generate the final response using the LLM with conversation memory."""
        try:
            # Detect language
            language = self._detect_language(question)
            
            # Check if language is supported
            if language not in ['en', 'pt']:
                return UNSUPPORTED_LANGUAGE_RESPONSE
            
            # Handle case when no documents found
            if not documents:
                if language == 'pt':
                    no_result_msg = "Infelizmente, não consegui encontrar a resposta agora. Por favor, tente novamente sendo mais específico."
                else:
                    no_result_msg = "Unfortunately, I could not find the answer right now. Please try again being more specific."
                
                # Still store this in memory
                self._store_interaction(
                    question=question,
                    response=no_result_msg,
                    intent_result=intent_result,
                    user_coordinates=user_coordinates,
                    places_mentioned=[]
                )
                return no_result_msg
            
            # Create context from documents
            context = self._create_context_from_documents(documents, intent_result, top_k)
            
            # Create location context from user coordinates
            user_location_context = self._create_location_context(user_coordinates, language)
            
            # Get conversation history (last 3 turns)
            conversation_history = self.conversation_memory.get_recent_context(
                num_turns=3, 
                language=language
            )
            
            # Use appropriate prompt template
            if language == 'pt':
                formatted_prompt = self.travel_guide_prompt_pt.format(
                    context=context,
                    question=question,
                    user_location=user_location_context,
                    conversation_history=conversation_history
                )
            else:
                formatted_prompt = self.travel_guide_prompt_en.format(
                    context=context,
                    question=question,
                    user_location=user_location_context,
                    conversation_history=conversation_history
                )
            
            # Generate response
            response = self.llm_model.invoke(formatted_prompt)
            response_text = response.content
            
            # Clean any prompt leakage
            response_text = self._clean_response_leakage(response_text)
            
            # Extract place names from documents for memory
            places_mentioned = self._extract_place_names(documents)
            
            # Store interaction in memory
            self._store_interaction(
                question=question,
                response=response_text,
                intent_result=intent_result,
                user_coordinates=user_coordinates,
                places_mentioned=places_mentioned
            )
            
            return response_text
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return "I'm sorry, I couldn't process your request. Please try rephrasing your question."
    
    def _clean_response_leakage(self, response: str) -> str:
        """
        Remove leaked prompt markers, context delimiters, and system instructions from LLM response.
        
        This function removes (for Llama 3.1 8B Instruct):
        - Context markers (=== AVAILABLE INFORMATION ===, etc.)
        - Location context strings (User Location:, etc.)
        - Prompt markers ([INST], <<SYS>>, etc.) - Llama 3.1 format
        - Llama 3.1 specific tokens (<|begin_of_text|>, <|eot_id|>, etc.)
        - Any content between context markers
        - Conversation history formatting markers when they appear as leakage
        
        Args:
            response: Raw LLM response text
            
        Returns:
            Cleaned response with leaked content removed
        """
        if not response:
            return response
        
        import re
        
        cleaned = response
        original_length = len(cleaned)
        
        # Remove context markers and everything between them
        context_marker_patterns = [
            r'===+\s*AVAILABLE INFORMATION\s*===+.*?===+\s*END OF INFORMATION\s*===+',
            r'===+\s*INFORMAÇÕES DISPONÍVEIS\s*===+.*?===+\s*FIM DAS INFORMAÇÕES\s*===+',
            r'===+\s*ITINERARY DATA.*?===+\s*END OF ITINERARY DATA\s*===+',
            r'===+\s*AVAILABLE INFORMATION\s*===+',
            r'===+\s*END OF INFORMATION\s*===+',
            r'===+\s*INFORMAÇÕES DISPONÍVEIS\s*===+',
            r'===+\s*FIM DAS INFORMAÇÕES\s*===+',
        ]
        
        for pattern in context_marker_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove location context blocks (entire lines containing location markers)
        lines = cleaned.split('\n')
        filtered_lines = []
        skip_until_empty = False
        
        location_markers = [
            'user location:',
            'localização do usuário:',
            'user is currently in belém',
            'o usuário está atualmente em belém',
        ]
        
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            
            # Check if this line starts a location context block
            is_location_marker = any(marker in line_lower for marker in location_markers)
            
            if is_location_marker:
                # Skip this line and continue until we hit an empty line or end
                skip_until_empty = True
                continue
            
            if skip_until_empty:
                # Skip lines until we find an empty line (end of location block)
                if not line.strip():
                    skip_until_empty = False
                    # Don't add the empty line either if it's part of the leaked block
                    continue
                else:
                    continue
            
            filtered_lines.append(line)
        
        cleaned = '\n'.join(filtered_lines)
        
        # Remove prompt markers (Llama 3.1 / Mistral format)
        prompt_markers = [
            r'\[INST\]',
            r'\[/INST\]',
            r'<<SYS>>',
            r'</SYS>>',
            r'<</SYS>>',
            # Llama 3.1 specific tokens
            r'<\|begin_of_text\|>',
            r'<\|end_of_text\|>',
            r'<\|eot_id\|>',
            r'<\|eom_id\|>',
        ]
        
        for marker in prompt_markers:
            cleaned = re.sub(marker, '', cleaned, flags=re.IGNORECASE)
        
        # Remove standalone "coordinates:" or "coordenadas:" lines that are part of location context
        # But preserve if they're part of actual place information
        lines = cleaned.split('\n')
        filtered_lines = []
        for line in lines:
            line_stripped = line.strip()
            # Only remove if it's a standalone line with just coordinates: or coordenadas:
            if re.match(r'^(coordinates?|coordenadas?):\s*[-+]?\d+\.?\d*,\s*[-+]?\d+\.?\d*$', line_stripped, re.IGNORECASE):
                continue  # Skip standalone coordinate lines (likely leakage)
            filtered_lines.append(line)
        
        cleaned = '\n'.join(filtered_lines)
        
        # Remove any remaining triple-equals markers
        cleaned = re.sub(r'===+.*?===+', '', cleaned, flags=re.DOTALL)
        
        # Clean up multiple consecutive newlines
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        
        # Trim whitespace
        cleaned = cleaned.strip()
        
        # Log if we removed significant content (for monitoring)
        if original_length > len(cleaned) + 50:  # Removed more than 50 chars
            logger.warning(f"Removed {original_length - len(cleaned)} characters of leaked content from response")
        
        return cleaned
    
    def _extract_place_names(self, documents: List[Document]) -> List[str]:
        """Extract place names from documents for memory."""
        places = []
        for doc in documents[:5]:  # Only first 5
            if hasattr(doc, 'metadata') and 'title' in doc.metadata:
                places.append(doc.metadata['title'])
            elif hasattr(doc, 'page_content'):
                # Try to extract from content
                content = doc.page_content
                if 'title:' in content.lower():
                    try:
                        start = content.lower().index('title:') + 6
                        end = content.find('\n', start)
                        if end == -1:
                            end = start + 50
                        title = content[start:end].strip()
                        if title:
                            places.append(title)
                    except:
                        pass
        return places[:5]  # Max 5 places
    
    def _store_interaction(
        self,
        question: str,
        response: str,
        intent_result: Dict[str, Any],
        user_coordinates: Optional[Tuple[float, float]],
        places_mentioned: List[str]
    ) -> None:
        """Store the interaction in conversation memory."""
        try:
            self.conversation_memory.add_turn(
                user_message=question,
                assistant_response=response,
                user_coordinates=user_coordinates,
                intent=intent_result.get('primary_intent'),
                category=intent_result.get('primary_category'),
                places_mentioned=places_mentioned
            )
            logger.debug(f"Stored interaction in memory. Total turns: {len(self.conversation_memory)}")
        except Exception as e:
            logger.warning(f"Could not store interaction in memory: {e}")
    
    def _detect_language(self, text: str) -> str:
        """Simple language detection."""
        pt_words = ['onde', 'como', 'quando', 'que', 'para', 'com', 'em', 'de', 'do', 'da', 'dos', 'das', 'qual', 'quais']
        text_lower = text.lower()
        
        pt_count = sum(1 for word in pt_words if f' {word} ' in f' {text_lower} ')
        
        return 'pt' if pt_count >= 2 else 'en'
    
    def _create_context_from_documents(
        self, 
        documents: List[Document], 
        intent_result: Dict[str, Any], 
        top_k: int
    ) -> str:
        """
        Create context string from documents with standardized formatting.
        
        Only includes: name, address, phone, hours, rating, Google Maps link.
        Omits any information not available in the data.
        """
        try:
            context_parts = []
            context_parts.append(f"Found {len(documents)} places:\n")
            
            for i, doc in enumerate(documents[:top_k], 1):
                # Parse document content
                content_lines = doc.page_content.split('\n')
                place_info = {}
                
                for line in content_lines:
                    if ':' in line:
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            key = parts[0].strip().lower()
                            value = parts[1].strip()
                            if value and value not in ['nan', 'None', '', 'null']:
                                place_info[key] = value
                
                # Build standardized place entry (using simple format, not marker-like)
                # Name (required)
                name = place_info.get('title') or place_info.get('titleformatted') or 'Unknown'
                place_lines = [f"Place {i}: {name}"]
                
                # Address (if available)
                address = place_info.get('address') or place_info.get('addressformatted')
                if address:
                    place_lines.append(f"Address: {address}")
                
                # Phone (if available)
                phone = place_info.get('phone')
                if phone:
                    place_lines.append(f"Phone: {phone}")
                
                # Business Hours (if available)
                hours = place_info.get('businesstime')
                if hours:
                    place_lines.append(f"Hours: {hours}")
                
                # Rating (if available)
                rating = place_info.get('totalscore')
                review_count = place_info.get('reviewscount')
                if rating:
                    rating_str = f"Rating: {rating}★"
                    if review_count:
                        rating_str += f" ({review_count} reviews)"
                    place_lines.append(rating_str)
                
                # Category (for context)
                category = place_info.get('categoryname')
                if category:
                    place_lines.append(f"Type: {category}")
                
                # Distance (if available from metadata)
                if 'distance_km' in doc.metadata:
                    dist = doc.metadata['distance_km']
                    if isinstance(dist, (int, float)):
                        place_lines.append(f"Distance: {dist:.2f}km from you")
                
                # Google Maps link (if place ID available)
                place_id = place_info.get('placeid')
                if place_id:
                    maps_link = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                    place_lines.append(f"Google Maps: {maps_link}")
                
                context_parts.append('\n'.join(place_lines))
                context_parts.append("")  # Empty line between places
            
            final_context = '\n'.join(context_parts)
            logger.debug(f"Context created with {len(documents)} places")
            return final_context
            
        except Exception as e:
            logger.error(f"Context creation failed: {e}")
            return f"Found {len(documents)} places. " + '\n\n'.join([doc.page_content for doc in documents[:top_k]])
    
    def _create_location_context(
        self, 
        user_coordinates: Optional[Tuple[float, float]], 
        language: str
    ) -> str:
        """Create location context string based on user coordinates."""
        try:
            if not user_coordinates:
                if language == 'pt':
                    return "O usuário não forneceu sua localização. Se ele perguntar sobre lugares 'próximos' ou 'perto de mim', informe que você precisa da localização dele."
                else:
                    return "The user has not provided their location. If they ask about 'nearby' or 'close to me' places, inform them that you need their location."
            
            lat, lng = user_coordinates
            
            # Check if coordinates are in Belém area
            belem_lat_min, belem_lat_max = -1.6, -1.3
            belem_lng_min, belem_lng_max = -48.6, -48.3
            
            is_in_belem = (belem_lat_min <= lat <= belem_lat_max and 
                          belem_lng_min <= lng <= belem_lng_max)
            
            if is_in_belem:
                if language == 'pt':
                    return f"O usuário está atualmente em Belém, Brasil. Quando ele se refere a lugares 'próximos', 'perto de mim' ou 'mais próximos', você deve considerar esta localização para recomendar lugares próximos a ele."
                else:
                    return f"The user is currently in Belém, Brazil. When they refer to 'nearby', 'close to me', or 'closest' places, you should consider this location to recommend places near them."
            else:
                if language == 'pt':
                    return f"O usuário está atualmente fora de Belém. Se ele perguntar sobre lugares próximos, você pode mencionar que as informações fornecidas são sobre lugares em Belém, Brasil."
                else:
                    return f"The user is currently outside Belém. If they ask about nearby places, you can mention that the information provided is about places in Belém, Brazil."
            
        except Exception as e:
            logger.error(f"Location context creation failed: {e}")
            if language == 'pt':
                return "Informação de localização não disponível."
            else:
                return "Location information not available."
    
    def _update_metrics(
        self, 
        intent_time: float, 
        retrieval_time: float, 
        llm_time: float, 
        total_time: float
    ):
        """Update performance metrics."""
        try:
            self.performance_metrics['total_queries'] += 1
            n = self.performance_metrics['total_queries']
            
            # Calculate running averages
            self.performance_metrics['avg_intent_time'] = (
                (self.performance_metrics['avg_intent_time'] * (n - 1) + intent_time) / n
            )
            self.performance_metrics['avg_retrieval_time'] = (
                (self.performance_metrics['avg_retrieval_time'] * (n - 1) + retrieval_time) / n
            )
            self.performance_metrics['avg_llm_time'] = (
                (self.performance_metrics['avg_llm_time'] * (n - 1) + llm_time) / n
            )
            self.performance_metrics['avg_total_time'] = (
                (self.performance_metrics['avg_total_time'] * (n - 1) + total_time) / n
            )
            
        except Exception as e:
            logger.error(f"Metrics update failed: {e}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        return self.performance_metrics.copy()
    
    def reset_performance_metrics(self):
        """Reset performance metrics."""
        self.performance_metrics = {
            'total_queries': 0,
            'avg_intent_time': 0.0,
            'avg_retrieval_time': 0.0,
            'avg_llm_time': 0.0,
            'avg_total_time': 0.0
        }
        logger.info("Performance metrics reset")
    
    # === Conversation Memory Methods ===
    
    def clear_conversation_history(self) -> None:
        """Clear all conversation history."""
        self.conversation_memory.clear_history()
        logger.info("Conversation history cleared")
    
    def get_conversation_history_length(self) -> int:
        """Get the number of stored conversation turns."""
        return len(self.conversation_memory)
    
    def is_follow_up_question(self, question: str) -> bool:
        """Check if a question is a follow-up to previous conversation."""
        return self.conversation_memory.is_follow_up_question(question)
    
    def get_last_mentioned_places(self) -> List[str]:
        """Get places mentioned in the last conversation turn."""
        return self.conversation_memory.get_last_mentioned_places()
