"""
Query Planner - Converts user messages into Query Plan JSON per spec/03-query-planner.md.

Integrates with intent classifier to produce structured Query Plans with:
- Language detection (EN/pt-BR) via langdetect library with keyword fallback
- Intent classification
- Slot extraction (place_type, categories, city, neighborhood, open_now, etc.)
- Sort preference logic
- Retrieval strategy selection
"""

import logging
import re
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class QueryPlan:
    """Query Plan structure per spec"""
    language: str  # "en" | "pt-BR"
    intent: str  # "find_places" | "place_details" | "compare_places" | "smalltalk" | "help" | "tour_planning"
    slots: Dict[str, Any]
    retrieval_strategy: str  # "structured_only" | "structured_then_lexical" | "structured_then_vector_fallback"
    debug: Dict[str, Any]


class QueryPlanner:
    """Query Planner that outputs Query Plan JSON per spec"""
    
    # Unambiguous PT-BR words used as keyword fallback when langdetect is unavailable
    # or returns low confidence. These words do not exist in English.
    _PT_BR_KEYWORDS = {
        # Pronouns / articles
        'pra', 'num', 'numa', 'nuns', 'numas', 'uns', 'umas',
        # Verbs
        'quero', 'preciso', 'busco', 'procuro', 'bora', 'vou', 'tem', 'temos',
        'fica', 'ficam', 'funciona', 'funcionam', 'aberto', 'aberta', 'fechado',
        # Adverbs / prepositions
        'perto', 'aqui', 'daqui', 'agora', 'hoje', 'amanha', 'ontem',
        'junto', 'tudo', 'nada', 'muito', 'pouco', 'mais', 'menos',
        # Common nouns (unambiguous)
        'lugar', 'lugares', 'restaurante', 'restaurantes', 'lanchonete',
        'padaria', 'sorveteria', 'churrascaria', 'pizzaria', 'hamburgueria',
        'farmacia', 'farmácia', 'clinica', 'clínica', 'academia', 'barbearia',
        'salao', 'salão', 'petshop', 'veterinario', 'veterinário',
        'balada', 'boate', 'brinquedoteca', 'parquinho', 'quadra',
        'oficina', 'mecanica', 'mecânica', 'borracharia', 'funilaria',
        'manicure', 'pedicure', 'cabeleireiro', 'maquiagem', 'depilacao',
        'almoco', 'almoço', 'jantar', 'manha', 'manhã', 'noite',
        'barato', 'caro', 'preço', 'preco', 'nota', 'avaliacao', 'avaliação',
        'aberto', 'fechado', 'horario', 'horário', 'funcionamento',
        'entrega', 'delivery', 'cardapio', 'cardápio',
        # Connectors
        'ou', 'mas', 'porque', 'quando', 'onde', 'como', 'qual', 'quais',
        # Slang / colloquial
        'massa', 'gelada', 'tira', 'gosto', 'tipo', 'sabe', 'cara',
    }

    # Unambiguous proximity keywords used as Strategy 1 (direct match, word-boundary safe).
    # Multi-word phrases are checked first (longest match wins).
    # Single-word terms use \b word-boundary regex to avoid substring false positives
    # (e.g. 'aqui' must not match inside 'manicure').
    _PROXIMITY_PHRASES = [
        # multi-word — checked with plain `in` after normalization
        'perto de mim', 'perto daqui', 'perto daki', 'aqui perto', 'ai perto',
        'ali perto', 'por aqui', 'por perto', 'perto de casa', 'perto da', 'perto do',
        'na minha regiao', 'na minha area', 'near me', 'around here', 'close to me',
        'walking distance',
    ]
    _PROXIMITY_WORDS = [
        # single-word — checked with \b word boundary
        'perto', 'proximo', 'proxima', 'aqui', 'daqui', 'daki',
        'nearby', 'nearest', 'closest', 'near', 'close',
    ]

    def __init__(self, intent_classifier=None):
        """
        Initialize Query Planner.

        Args:
            intent_classifier: Optional intent classifier instance (required for intent detection)
        """
        self.intent_classifier = intent_classifier
        if not intent_classifier:
            logger.warning("QueryPlanner initialized without intent_classifier - will use minimal fallback")
        
        # Try to import langdetect once at init time so we know if it's available
        self._langdetect_available = False
        try:
            from langdetect import detect, LangDetectException  # noqa: F401
            self._langdetect_available = True
            logger.debug("langdetect library available for language detection")
        except ImportError:
            logger.warning("langdetect not installed — falling back to keyword-based language detection. "
                           "Install with: pip install langdetect")
    
    def _fallback_intent_detection(self, message: str, error_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Minimal fallback intent detection when Intent_Classifier is unavailable.
        
        This is a last resort and should rarely be used. Logs explicitly when invoked.
        
        Args:
            message: User message to analyze
            error_context: Optional error context explaining why fallback is being used
        
        Returns:
            Dict with minimal intent/category information, all confidence scores set to 0.0
        """
        log_msg = f"FALLBACK MODE: Using minimal keyword-based intent detection for message: '{message}'"
        if error_context:
            log_msg += f" | Reason: {error_context}"
        logger.warning(log_msg)
        
        message_lower = self.normalize_text(message)
        
        # Minimal keyword-based detection
        detected_intents = []
        
        # Check for proximity keywords
        proximity_keywords = ['near', 'nearby', 'close', 'closest', 'perto', 'próximo']
        if any(kw in message_lower for kw in proximity_keywords):
            detected_intents.append('location')
        
        # Check for popularity keywords
        popularity_keywords = ['best', 'top', 'popular', 'melhor', 'popular']
        if any(kw in message_lower for kw in popularity_keywords):
            detected_intents.append('popularity')
        
        # Check for business hours keywords
        hours_keywords = ['open', 'hours', 'aberto', 'horário']
        if any(kw in message_lower for kw in hours_keywords):
            detected_intents.append('business_hours')
        
        # Check for price keywords
        price_keywords = ['cheap', 'price', 'barato', 'preço']
        if any(kw in message_lower for kw in price_keywords):
            detected_intents.append('price')
        
        # Minimal category detection
        detected_category = 'restaurant'  # Default fallback
        if 'bar' in message_lower or 'pub' in message_lower:
            detected_category = 'bar'
        elif 'hotel' in message_lower or 'motel' in message_lower:
            detected_category = 'hotel'
        elif 'park' in message_lower or 'parque' in message_lower:
            detected_category = 'tourist_attraction'
        
        return {
            'intents': [{'intent': intent, 'confidence': 0.0} for intent in detected_intents],
            'primary_intent': detected_intents[0] if detected_intents else 'unknown',
            'primary_confidence': 0.0,
            'categories': [{'category': detected_category, 'confidence': 0.0}],
            'primary_category': detected_category,
            'primary_category_confidence': 0.0,
            'fallback_mode': True
        }
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for matching (lowercase, remove accents)"""
        import unicodedata
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        return text.lower().strip()
    
    def detect_language(self, message: str, explicit_language: Optional[str] = None) -> str:
        """
        Detect language from message or use explicit language.

        Strategy (in order):
        1. Honour explicit_language if provided by the client.
        2. Try langdetect library (fast, accurate, handles typos/slang well).
        3. Fall back to keyword matching against _PT_BR_KEYWORDS.

        Args:
            message: User message
            explicit_language: Explicit language from client (en/pt-BR)

        Returns:
            "en" or "pt-BR"
        """
        if explicit_language:
            if explicit_language.lower() in ['pt', 'pt-br', 'pt_br']:
                return 'pt-BR'
            return 'en'

        # --- Strategy 2: langdetect ---
        if self._langdetect_available and len(message.strip()) >= 5:
            try:
                from langdetect import detect, LangDetectException
                lang_code = detect(message)
                # langdetect returns 'pt' for Portuguese (both PT and BR)
                if lang_code == 'pt':
                    logger.debug(f"langdetect detected pt-BR for: '{message[:40]}'")
                    return 'pt-BR'
                # If langdetect is confident it's something else, trust it
                logger.debug(f"langdetect detected '{lang_code}' for: '{message[:40]}'")
                # Still run keyword check below as a safety net for short/ambiguous queries
            except Exception as e:
                logger.debug(f"langdetect failed ({e}), falling back to keyword detection")

        # --- Strategy 3: keyword fallback ---
        message_lower = self.normalize_text(message)
        words = set(re.findall(r'\b\w+\b', message_lower))
        if words & self._PT_BR_KEYWORDS:
            logger.debug(f"PT-BR detected via keyword fallback for: '{message[:40]}'")
            return 'pt-BR'

        return 'en'
    
    def classify_intent(self, message: str) -> str:
        """
        Classify high-level intent from message.
        
        This method handles application-level routing intents. For retrieval-related
        intents (location, popularity, price, etc.), use Intent_Classifier directly.
        
        Returns:
            "find_places" | "place_details" | "compare_places" | "smalltalk" | "help" | "tour_planning"
        """
        message_lower = self.normalize_text(message)
        
        # Check for tour planning intent using Intent_Classifier
        if self.intent_classifier:
            try:
                intent_result = self.intent_classifier.predict_intent(message)
                if intent_result.get('primary_intent') == 'tour_planning' and intent_result.get('primary_intent_confidence', 0) >= 0.3:
                    return 'tour_planning'
            except Exception as e:
                logger.warning(f"Intent_Classifier failed for tour_planning detection: {e}")
                # Fall through to keyword-based fallback below
        
        # Fallback: Check for tour planning keywords if classifier unavailable
        tour_keywords_en = ['plan', 'itinerary', 'tour', 'day trip', 'trip plan', 'schedule', 'route']
        tour_keywords_pt = ['roteiro', 'passeio', 'planejar', 'itinerario', 'viagem', 'programar', 'programacao', 'rota']
        
        if any(word in message_lower for word in tour_keywords_en + tour_keywords_pt):
            logger.info("Tour planning detected via fallback keywords")
            return 'tour_planning'
        
        # Check for other application-level intents (not handled by Intent_Classifier)
        if any(word in message_lower for word in ['compare', 'comparar', 'diferença', 'difference']):
            return 'compare_places'
        
        if any(word in message_lower for word in ['help', 'ajuda', 'como', 'how']):
            return 'help'
        
        if any(word in message_lower for word in ['hello', 'hi', 'olá', 'oi', 'thanks', 'obrigado']):
            return 'smalltalk'
        
        # Check for place details (specific place name or placeId)
        # This is a simple heuristic - could be enhanced
        if any(word in message_lower for word in ['what is', 'tell me about', 'informações', 'detalhes']):
            return 'place_details'
        
        # Default to find_places
        return 'find_places'
    
    def extract_place_types(self, message: str, language: str) -> List[str]:
        """
        Extract place_type from message using Intent_Classifier.
        
        Delegates to Intent_Classifier for category detection, then maps to place_types.
        """
        if not self.intent_classifier:
            logger.warning("No intent_classifier available for place_type extraction, using fallback")
            fallback_result = self._fallback_intent_detection(message, "No intent_classifier available")
            primary_category = fallback_result.get('primary_category', 'restaurant')
        else:
            try:
                category_result = self.intent_classifier.predict_category(message)
                primary_category = category_result.get('primary_category', '')
            except Exception as e:
                logger.error(f"Intent_Classifier failed for place_type extraction: {e}", 
                           extra={"query": message, "error": str(e)}, exc_info=True)
                fallback_result = self._fallback_intent_detection(message, f"predict_category failed: {e}")
                primary_category = fallback_result.get('primary_category', 'restaurant')
        
        # Map TFIDF categories to place_types
        category_to_place_type = {
            'restaurant': 'restaurant',
            'bar': 'bar',
            'tourist_attraction': 'park',  # Parks are often tourist attractions
            'acai': 'restaurant',  # Açaí shops are restaurants
            'cafe': 'restaurant',  # Cafes are restaurants
            'hotel': 'other',
            'shopping': 'other',
            'entertainment': 'other',
            'ice_cream': 'restaurant'
        }
        
        place_type = category_to_place_type.get(primary_category)
        if place_type:
            logger.debug(f"Extracted place_type '{place_type}' from category '{primary_category}'")
            return [place_type]
        
        logger.debug(f"No place_type mapping for category '{primary_category}'")
        return []
    
    def extract_categories(self, message: str) -> List[str]:
        """
        Extract category keywords using ALL keywords from the TF-IDF classifier.
        
        This function:
        1. Uses the classifier to detect categories
        2. Extracts exact keywords from the message that match classifier keywords
        3. Adds ALL keywords from detected categories (not just a subset)
        """
        detected = []
        message_lower = self.normalize_text(message)
        
        # Use TFIDF classifier if available
        if self.intent_classifier:
            try:
                category_result = self.intent_classifier.predict_category(message)
                primary_category = category_result.get('primary_category', '')
                categories = category_result.get('categories', [])
                
                # Get ALL keywords from the classifier dynamically
                all_classifier_keywords = {}
                if hasattr(self.intent_classifier, 'category_keywords'):
                    all_classifier_keywords = self.intent_classifier.category_keywords
                else:
                    logger.warning("Classifier does not have category_keywords attribute")
                    all_classifier_keywords = {}
                
                # Track which categories we've already processed
                processed_categories = set()
                
                # Step 1: Extract exact keywords from message that match classifier keywords
                # This captures the exact terms the user typed (e.g., "sorveteria", "churrascaria")
                matched_keywords_from_message = []
                for cat_name, keywords in all_classifier_keywords.items():
                    for keyword in keywords:
                        normalized_keyword = self.normalize_text(keyword)
                        # Check if keyword appears in message (substring match)
                        if normalized_keyword in message_lower:
                            # Add the exact keyword the user used (preserve original case from classifier)
                            matched_keywords_from_message.append(keyword.lower())
                            # Mark this category as detected
                            processed_categories.add(cat_name)
                
                # Add exact matched keywords first (preserves user's original terms)
                detected.extend(matched_keywords_from_message)
                
                # Step 2: Add ALL keywords from primary category if detected with good confidence
                if primary_category and category_result.get('primary_category_confidence', 0) >= 0.3:
                    if primary_category in all_classifier_keywords:
                        # Get ALL keywords for this category from the classifier
                        all_keywords_for_category = all_classifier_keywords[primary_category]
                        detected.extend([kw.lower() for kw in all_keywords_for_category])
                        processed_categories.add(primary_category)
                        logger.debug(f"Added ALL {len(all_keywords_for_category)} keywords from primary category: {primary_category}")
                
                # Step 3: Add ALL keywords from other high-confidence categories
                for cat_info in categories:
                    cat_name = cat_info.get('category', '')
                    confidence = cat_info.get('confidence', 0)
                    if confidence >= 0.3 and cat_name != primary_category:
                        if cat_name in all_classifier_keywords:
                            # Get ALL keywords for this category from the classifier
                            all_keywords_for_category = all_classifier_keywords[cat_name]
                            detected.extend([kw.lower() for kw in all_keywords_for_category])
                            processed_categories.add(cat_name)
                            logger.debug(f"Added ALL {len(all_keywords_for_category)} keywords from category: {cat_name}")
                
                # Remove duplicates while preserving order (exact user terms first)
                seen = set()
                unique_detected = []
                for item in detected:
                    normalized_item = self.normalize_text(item)
                    if normalized_item not in seen:
                        seen.add(normalized_item)
                        unique_detected.append(item)
                
                if unique_detected:
                    logger.info(f"Extracted {len(unique_detected)} category keywords via classifier: {unique_detected[:10]}..." 
                              if len(unique_detected) > 10 else f"Extracted categories via classifier: {unique_detected}")
                    return unique_detected
                    
            except Exception as e:
                logger.error(f"Intent_Classifier failed for category extraction: {e}", 
                           extra={"query": message, "error": str(e)}, exc_info=True)
        
        # Fallback: keyword-only scan across ALL category domains in the classifier.
        # This runs when the ML prediction path raised an exception or returned nothing.
        # It covers all 16+ category domains including the new ones (health, beauty, etc.)
        if self.intent_classifier and hasattr(self.intent_classifier, 'category_keywords'):
            all_classifier_keywords = self.intent_classifier.category_keywords
            detected = []
            for cat_name, keywords in all_classifier_keywords.items():
                for keyword in keywords:
                    normalized_keyword = self.normalize_text(keyword)
                    if normalized_keyword in message_lower:
                        detected.append(keyword.lower())

            seen = set()
            unique_detected = []
            for item in detected:
                normalized_item = self.normalize_text(item)
                if normalized_item not in seen:
                    seen.add(normalized_item)
                    unique_detected.append(item)

            if unique_detected:
                logger.info(f"Extracted categories via keyword-only fallback: {unique_detected}")
                return unique_detected
        
        # No categories detected - Intent_Classifier is the single source of truth
        # If classifier is unavailable or has no keywords, return empty list
        logger.info("No categories extracted - Intent_Classifier unavailable or no matching keywords")
        return []
    
    def extract_open_now(self, message: str, language: str) -> Optional[bool]:
        """
        Extract open_now slot.

        Strategy:
        1. Direct phrase matching (independent of primary intent) — catches cases where
           the classifier's primary intent is something else (e.g. popularity) but the
           user also said "aberto agora".
        2. Intent-classifier business_hours intent as a secondary signal.

        Returns True only when the user is asking for currently-open places.
        Returns None when no open/closed signal is found.
        """
        message_lower = self.normalize_text(message)

        # --- Strategy 1: direct phrase matching (language-agnostic) ---
        open_now_phrases = [
            # Portuguese
            'aberto agora', 'aberta agora', 'aberto neste momento', 'aberto agora mesmo',
            'funcionando agora', 'funcionando neste momento', 'aberto 24', 'aberto 24 horas',
            'que esteja aberto', 'que estejam abertos', 'ainda aberto', 'ainda abre',
            'ainda funciona', 'aberto hoje', 'aberto no momento',
            # English
            'open now', 'currently open', 'open right now', 'open 24', 'open 24 hours',
            'still open', 'open at this time', 'open today',
        ]
        closed_phrases = [
            'fechado agora', 'fechado hoje', 'closed now', 'currently closed',
        ]

        if any(p in message_lower for p in open_now_phrases):
            if not any(p in message_lower for p in closed_phrases):
                logger.debug("open_now=True detected via direct phrase match")
                return True

        # --- Strategy 2: intent classifier business_hours signal ---
        if not self.intent_classifier:
            fallback_result = self._fallback_intent_detection(message, "No intent_classifier available")
            primary_intent = fallback_result.get('primary_intent', '')
        else:
            try:
                intent_result = self.intent_classifier.predict_intent(message)
                primary_intent = intent_result.get('primary_intent', '')
            except Exception as e:
                logger.error(f"Intent_Classifier failed for open_now extraction: {e}",
                             extra={"query": message, "error": str(e)}, exc_info=True)
                fallback_result = self._fallback_intent_detection(message, f"predict_intent failed: {e}")
                primary_intent = fallback_result.get('primary_intent', '')

        if primary_intent == 'business_hours':
            open_keywords = ['open', 'aberto', 'aberta', 'abertos', 'abertas', 'funcionando']
            closed_keywords = ['closed', 'fechado', 'fechada', 'fechados', 'fechadas']
            has_open = any(kw in message_lower for kw in open_keywords)
            has_closed = any(kw in message_lower for kw in closed_keywords)
            if has_open and not has_closed:
                logger.debug("open_now=True detected via Intent_Classifier business_hours intent")
                return True

        return None
    
    def extract_price_max(self, message: str, language: str) -> Optional[float]:
        """Extract price_max from message."""
        message_lower = self.normalize_text(message)

        # Explicit numeric price patterns
        price_patterns = [
            r'price\s*[<<=]\s*(\d+)',
            r'preco\s*[<<=]\s*(\d+)',
            r'\$\s*(\d+)',
            r'ate\s*(\d+)',
        ]
        for pattern in price_patterns:
            match = re.search(pattern, message_lower)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    pass

        # Qualitative cheap keywords — Portuguese (extended) + English
        cheap_keywords_pt = [
            'barato', 'baratos', 'barata', 'baratas',
            'economico', 'econômico', 'economica', 'econômica',
            'em conta', 'bom preco', 'bom preço', 'preco bom', 'preço bom',
            'acessivel', 'acessível', 'custo beneficio', 'custo-benefício',
            'nao muito caro', 'não muito caro', 'preco baixo', 'preço baixo',
        ]
        cheap_keywords_en = ['cheap', 'inexpensive', 'affordable', 'budget', 'low cost', 'low-cost']

        if any(kw in message_lower for kw in cheap_keywords_pt + cheap_keywords_en):
            return 2.0

        # Expensive / luxury keywords map to price_max = 4 (no upper cap needed, but signals premium)
        luxury_keywords_pt = ['caro', 'luxo', 'luxuoso', 'premium', 'sofisticado', 'requintado']
        luxury_keywords_en = ['expensive', 'luxury', 'upscale', 'fine dining', 'high-end']
        if any(kw in message_lower for kw in luxury_keywords_pt + luxury_keywords_en):
            return 4.0

        return None
    
    def extract_min_rating(self, message: str, language: str) -> Optional[float]:
        """Extract min_rating from message.

        Handles:
        - Numeric patterns: "4.5+", "rating >= 4", "nota >= 4"
        - Portuguese natural language: "nota acima de 4", "acima de 4 estrelas"
        - Qualitative terms: "altamente avaliado", "bem avaliado", "excelente"
        """
        message_lower = self.normalize_text(message)

        # --- Numeric patterns ---
        rating_patterns = [
            r'(\d+\.?\d*)\s*\+',                          # "4.5+"
            r'rating\s*[>>=]+\s*(\d+\.?\d*)',             # "rating >= 4"
            r'nota\s*[>>=]+\s*(\d+\.?\d*)',               # "nota >= 4"
            r'nota\s+acima\s+de\s+(\d+\.?\d*)',           # "nota acima de 4"
            r'acima\s+de\s+(\d+\.?\d*)\s*estrela',        # "acima de 4 estrelas"
            r'pelo\s+menos\s+(\d+\.?\d*)\s*estrela',      # "pelo menos 4 estrelas"
            r'minimo\s+de\s+(\d+\.?\d*)',                  # "mínimo de 4"
            r'no\s+minimo\s+(\d+\.?\d*)',                  # "no mínimo 4"
            r'(\d+\.?\d*)\s*estrelas?\s+ou\s+mais',       # "4 estrelas ou mais"
            r'score\s*[>>=]+\s*(\d+\.?\d*)',               # "score >= 4"
        ]
        for pattern in rating_patterns:
            match = re.search(pattern, message_lower)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    pass

        # --- Qualitative terms → numeric thresholds ---
        qualitative_map = {
            # Portuguese
            'altamente avaliado': 4.5, 'altamente avaliados': 4.5,
            'muito bem avaliado': 4.5, 'muito bem avaliados': 4.5,
            'bem avaliado': 4.0, 'bem avaliados': 4.0,
            'excelente': 4.5, 'excelentes': 4.5,
            'otimo': 4.0, 'ótimo': 4.0, 'otimos': 4.0, 'ótimos': 4.0,
            'muito bom': 4.0, 'muito boa': 4.0, 'muito bons': 4.0,
            'top avaliado': 4.5, 'melhor avaliado': 4.5,
            # English
            'highly rated': 4.5, 'top rated': 4.5, 'best rated': 4.5,
            'well rated': 4.0, 'great': 4.0, 'excellent': 4.5,
        }
        for phrase, threshold in qualitative_map.items():
            if phrase in message_lower:
                logger.debug(f"min_rating={threshold} inferred from qualitative term '{phrase}'")
                return threshold

        return None
    
    def extract_min_reviews(self, message: str) -> Optional[int]:
        """Extract min_reviews from message"""
        # Look for review count patterns
        review_patterns = [
            r'(\d+)\s*reviews',
            r'(\d+)\s*avaliações',
            r'at least\s*(\d+)\s*reviews'
        ]
        
        message_lower = self.normalize_text(message)
        for pattern in review_patterns:
            match = re.search(pattern, message_lower)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    pass
        
        return None
    
    def extract_proximity_intent(self, message: str, language: str) -> bool:
        """
        Detect if user wants proximity-based filtering.

        Strategy 1 — Direct keyword/phrase matching (word-boundary safe, language-agnostic).
            Runs first and is independent of classifier confidence.  Uses word-boundary
            regex for single-word terms so 'aqui' does NOT match inside 'manicure'.

        Strategy 2 — Intent_Classifier location intent signal.
            Used as a secondary check when Strategy 1 finds nothing.  Threshold is
            deliberately kept at 0.25 (instead of 0.3) because multi-intent queries
            (e.g. open_now + proximity + category) split probability across several
            intents and location rarely wins outright even when a proximity word is
            clearly present.

        Returns True only when proximity intent is explicitly detected.
        """
        message_norm = self.normalize_text(message)

        # --- Strategy 1: direct phrase / keyword matching ---
        # Check multi-word phrases first (plain substring on normalised text)
        for phrase in self._PROXIMITY_PHRASES:
            if phrase in message_norm:
                logger.debug(f"Proximity intent detected via phrase match: '{phrase}'")
                return True

        # Check single words with word-boundary to avoid substring false positives
        for word in self._PROXIMITY_WORDS:
            if re.search(r'\b' + re.escape(word) + r'\b', message_norm):
                logger.debug(f"Proximity intent detected via word match: '{word}'")
                return True

        # --- Strategy 2: Intent_Classifier location signal ---
        if not self.intent_classifier:
            fallback_result = self._fallback_intent_detection(message, "No intent_classifier available")
            intents = fallback_result.get('intents', [])
            for intent_info in intents:
                if intent_info.get('intent') == 'location':
                    logger.debug("Proximity intent detected via fallback classifier")
                    return True
            return False

        try:
            intent_result = self.intent_classifier.predict_intent(message)

            # Check primary intent first
            if intent_result.get('primary_intent') == 'location':
                confidence = intent_result.get('primary_confidence', 0)
                if confidence >= 0.3:
                    logger.debug(f"Proximity intent detected via classifier primary (conf={confidence:.3f})")
                    return True

            # Check all returned intents — location may not be primary in multi-intent queries
            for intent_info in intent_result.get('intents', []):
                if intent_info.get('intent') == 'location':
                    confidence = intent_info.get('confidence', 0)
                    if confidence >= 0.3:
                        logger.debug(f"Proximity intent detected via classifier intents (conf={confidence:.3f})")
                        return True

            logger.debug("Strategy 2 (classifier): no location intent above threshold — proximity=False")
            return False

        except Exception as e:
            logger.error(f"Intent_Classifier failed for proximity intent detection: {e}",
                         extra={"query": message, "error": str(e)}, exc_info=True)
            fallback_result = self._fallback_intent_detection(message, f"predict_intent failed: {e}")
            for intent_info in fallback_result.get('intents', []):
                if intent_info.get('intent') == 'location':
                    logger.debug("Proximity intent detected via exception fallback")
                    return True
            return False
    
    def extract_location_slots(self, message: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract city and neighborhood from message"""
        # Simple extraction - could be enhanced with NER
        # For PoC, only extract if explicitly mentioned
        message_lower = self.normalize_text(message)
        
        city = None
        neighborhood = None
        
        # Common city/neighborhood patterns
        # This is a simplified version - real implementation would use NER
        if 'in ' in message_lower or 'em ' in message_lower:
            # Could extract city/neighborhood here
            pass
        
        return city, neighborhood
    
    def determine_sort_preference(
        self,
        message: str,
        language: str,
        user_location: Optional[Dict[str, float]],
        proximity_intent_detected: bool = False
    ) -> str:
        """
        Determine sort_preference based on Intent_Classifier results.
        
        Precedence:
        1. If proximity intent detected + user_location → distance
        2. Else if "popularity" intent → popularity
        3. Else if "best/top rated" (popularity with high rating keywords) → rating
        4. Else → best_match
        
        IMPORTANT: Only use distance sorting if proximity intent is explicitly detected.
        Do NOT assume distance sorting just because user_location is available.
        """
        # Check distance intent - only use distance sorting if proximity intent was detected
        if proximity_intent_detected and user_location:
            logger.debug("Sort preference: distance (proximity intent detected)")
            return 'distance'
        
        if not self.intent_classifier:
            logger.debug("Sort preference: best_match (no intent_classifier)")
            return 'best_match'
        
        try:
            intent_result = self.intent_classifier.predict_intent(message)
            primary_intent = intent_result.get('primary_intent', '')
            confidence = intent_result.get('primary_confidence', 0)
            
            # Check for popularity intent
            if primary_intent == 'popularity' and confidence >= 0.3:
                logger.debug(f"Sort preference: popularity (confidence: {confidence:.3f})")
                return 'popularity'
            
            # Check for rating intent (best/top rated)
            # This is a special case of popularity with rating keywords
            message_lower = self.normalize_text(message)
            rating_keywords = ['best', 'top', 'melhor', 'rating', 'rated', 'nota', 'avaliado']
            if primary_intent == 'popularity' and any(kw in message_lower for kw in rating_keywords):
                logger.debug(f"Sort preference: rating (popularity intent with rating keywords)")
                return 'rating'
            
            # Default to best_match
            logger.debug("Sort preference: best_match (default)")
            return 'best_match'
            
        except Exception as e:
            logger.error(f"Intent_Classifier failed for sort preference determination: {e}", 
                       extra={"query": message, "error": str(e)}, exc_info=True)
            # Fallback to best_match on error
            logger.debug("Sort preference: best_match (fallback due to error)")
            return 'best_match'
    
    def determine_retrieval_strategy(self, message: str, user_location: Optional[Dict[str, float]]) -> str:
        """
        Determine retrieval strategy based on design principles.
        
        Default: structured_then_lexical (filter-first approach)
        OSM fallback is enabled when user_location is available.
        
        Note: Vector fallback and vibe keywords have been removed per unified design.
        """
        # Always use structured_then_lexical as the primary strategy (filter-first)
        # This aligns with the unified design's filter-first philosophy
        logger.debug("Retrieval strategy: structured_then_lexical (filter-first)")
        return 'structured_then_lexical'
    
    def extract_keywords(self, message: str) -> List[str]:
        """Extract keywords from message (non-structured terms)"""
        # Simple keyword extraction - could be enhanced
        # Remove common stop words and extract meaningful terms
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                     'of', 'with', 'by', 'o', 'a', 'os', 'as', 'de', 'da', 'do', 'das', 'dos',
                     'em', 'para', 'com', 'por'}
        
        words = re.findall(r'\b\w+\b', message.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        return keywords[:10]  # Limit to 10 keywords
    
    def create_query_plan(
        self,
        message: str,
        user_location: Optional[Dict[str, float]] = None,
        explicit_language: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> QueryPlan:
        """
        Create Query Plan from user message.
        
        Delegates all intent detection to Intent_Classifier per unified design.
        
        Args:
            message: User message
            user_location: Optional user location dict with 'lat' and 'lng'
            explicit_language: Optional explicit language (en/pt-BR)
            filters: Optional explicit filters from client
            
        Returns:
            QueryPlan object
        """
        logger.info(f"Creating query plan for message: '{message[:50]}...'")
        
        # Detect language
        language = self.detect_language(message, explicit_language)
        logger.debug(f"Detected language: {language}")
        
        # Classify intent
        intent = self.classify_intent(message)
        logger.debug(f"Classified intent: {intent}")
        
        # Extract slots using Intent_Classifier
        place_types = self.extract_place_types(message, language)
        categories = self.extract_categories(message)
        city, neighborhood = self.extract_location_slots(message)
        open_now = self.extract_open_now(message, language)
        price_max = self.extract_price_max(message, language)
        min_rating = self.extract_min_rating(message, language)
        min_reviews = self.extract_min_reviews(message)
        keywords = self.extract_keywords(message)
        
        logger.debug(f"Extracted slots - place_types: {place_types}, categories: {len(categories) if categories else 0}, "
                    f"open_now: {open_now}, price_max: {price_max}")
        
        # Detect proximity intent - only filter by proximity if user explicitly mentioned it
        proximity_intent_detected = self.extract_proximity_intent(message, language)
        logger.debug(f"Proximity intent detected: {proximity_intent_detected}")
        
        # Only use user_location for filtering if proximity intent is detected
        # If user hasn't mentioned proximity, set user_location to None for filtering
        effective_user_location = user_location if proximity_intent_detected else None
        
        sort_preference = self.determine_sort_preference(
            message, language, effective_user_location, proximity_intent_detected
        )
        retrieval_strategy = self.determine_retrieval_strategy(message, user_location)
        
        logger.debug(f"Sort preference: {sort_preference}, Retrieval strategy: {retrieval_strategy}")
        
        # Override with explicit filters if provided
        if filters:
            if 'placeType' in filters:
                place_types = filters['placeType'] or place_types
            if 'city' in filters:
                city = filters['city'] or city
            if 'neighborhood' in filters:
                neighborhood = filters['neighborhood'] or neighborhood
            if 'openNow' in filters:
                open_now = filters['openNow'] if filters['openNow'] is not None else open_now
            if 'priceMax' in filters:
                price_max = filters['priceMax'] if filters['priceMax'] is not None else price_max
            if 'minRating' in filters:
                min_rating = filters['minRating'] if filters['minRating'] is not None else min_rating
            if 'minReviews' in filters:
                min_reviews = filters['minReviews'] if filters['minReviews'] is not None else min_reviews
        
        # Build slots dict
        slots = {
            'place_type': place_types if place_types else None,
            'categories': categories if categories else None,
            'city': city,
            'neighborhood': neighborhood,
            'open_now': open_now,
            'price_max': price_max,
            'min_rating': min_rating,
            'min_reviews': min_reviews,
            'user_location': effective_user_location,  # Only set if proximity intent detected
            'proximity_intent_detected': proximity_intent_detected,  # Track if proximity intent was detected
            'radius_strategy': 'auto_escalate_0.5_1_2_km' if proximity_intent_detected else None,
            'keywords': keywords if keywords else None,
            'sort_preference': sort_preference
        }
        
        # Build detected signals for debug
        detected_signals = []
        if place_types:
            detected_signals.append(f"place_type={place_types}")
        if open_now:
            detected_signals.append("open_now=true")
        if price_max:
            detected_signals.append(f"price_max={price_max}")
        if min_rating:
            detected_signals.append(f"min_rating={min_rating}")
        if sort_preference != 'best_match':
            detected_signals.append(f"sort={sort_preference}")
        
        debug = {
            'detected_signals': detected_signals
        }
        
        return QueryPlan(
            language=language,
            intent=intent,
            slots=slots,
            retrieval_strategy=retrieval_strategy,
            debug=debug
        )
    
    def plan_to_dict(self, plan: QueryPlan) -> Dict[str, Any]:
        """Convert QueryPlan to dictionary (JSON-serializable)"""
        return {
            'language': plan.language,
            'intent': plan.intent,
            'slots': {k: v for k, v in plan.slots.items() if v is not None},
            'retrieval_strategy': plan.retrieval_strategy,
            'debug': plan.debug
        }
