"""
Query Planner - Converts user messages into Query Plan JSON per spec/03-query-planner.md.

Integrates with intent classifier to produce structured Query Plans with:
- Language detection (EN/pt-BR) via langdetect library with keyword fallback
- Intent classification
- Slot extraction (place_type, categories, city, neighborhood, open_now, etc.)
- Sort preference logic
- Retrieval strategy selection
"""

import json
import logging
import re
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Resolved once at import time so the runtime Strategy-0 lookup in
# extract_categories doesn't pay a path-resolution cost per call. Kept
# at module scope (not inside the class) so tests can monkey-patch it.
_IMPLICIT_LEXICON_PATH = (
    Path(__file__).resolve().parents[1]
    / "classifiers"
    / "data"
    / "implicit_category_lexicon.json"
)


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
        # P1/F6 diminutives & slang typos. 'pertinho' was the most-cited gap
        # in the v2.8 diagnostic (B-S10, B-S14). 'no meu bairo' is the common
        # PT-BR misspelling of 'no meu bairro' (kept word-bounded below too).
        'aqui pertinho', 'ai pertinho', 'ali pertinho', 'por aqui pertinho',
        'pra perto', 'pra cá', 'pra ca',
        'na minha rua', 'na minha vizinhanca', 'na minha vizinhança',
        'no meu bairro', 'no meu bairo', 'no meu rolê', 'no meu role',
    ]
    _PROXIMITY_WORDS = [
        # single-word — checked with \b word boundary
        'perto', 'proximo', 'proxima', 'aqui', 'daqui', 'daki',
        'nearby', 'nearest', 'closest', 'near', 'close',
        # P1/F6 diminutives. Word-bounded so 'pertinho' won't match inside
        # spurious tokens; kept short list to avoid false positives.
        'pertinho', 'pertim', 'pertinin', 'pertico',
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

        # P1/F5 — implicit-category lexicon. Loaded lazily on first call to
        # _detect_categories_strategy0 and cached as a normalised lookup
        # structure so the per-query cost is just substring scans.
        self._implicit_lexicon_normalized: Optional[Dict[str, Dict[str, List[str]]]] = None
        self._implicit_lexicon_load_error: Optional[str] = None
        
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
    
    def _load_implicit_lexicon(self) -> Dict[str, Dict[str, List[str]]]:
        """Lazy-load the implicit-category lexicon from disk and pre-normalise
        every phrase. Cached on the instance.

        Schema after normalisation:
          ``{<lang>: {<category>: [<normalised_phrase>, ...]}}``

        Returns an empty dict if the lexicon file is missing or malformed
        (with the failure recorded on the instance for the structured log
        in :meth:`extract_categories`). Lexicon problems must NEVER
        regress category extraction — Strategy 1 and Strategy 2 still run.
        """
        if self._implicit_lexicon_normalized is not None:
            return self._implicit_lexicon_normalized

        try:
            with open(_IMPLICIT_LEXICON_PATH, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except FileNotFoundError:
            self._implicit_lexicon_load_error = "missing_file"
            self._implicit_lexicon_normalized = {}
            logger.warning(
                "Implicit-category lexicon not found at %s — Strategy 0 disabled.",
                _IMPLICIT_LEXICON_PATH,
            )
            return self._implicit_lexicon_normalized
        except (OSError, json.JSONDecodeError) as e:
            self._implicit_lexicon_load_error = f"load_error:{type(e).__name__}"
            self._implicit_lexicon_normalized = {}
            logger.error(
                "Failed to load implicit-category lexicon: %s — Strategy 0 disabled.",
                e,
                exc_info=True,
            )
            return self._implicit_lexicon_normalized

        normalised: Dict[str, Dict[str, List[str]]] = {}
        for lang_key, categories in raw.items():
            if lang_key.startswith("_") or not isinstance(categories, dict):
                continue
            normalised[lang_key] = {}
            for category, phrases in categories.items():
                if not isinstance(phrases, list):
                    continue
                normalised[lang_key][category] = [
                    self.normalize_text(p) for p in phrases if isinstance(p, str)
                ]

        self._implicit_lexicon_normalized = normalised
        return normalised

    def _detect_categories_strategy0(
        self, message_norm: str, language: Optional[str]
    ) -> Dict[str, List[str]]:
        """Strategy 0 for category extraction: look up implicit semantic
        phrases in the curated lexicon (no ML inference).

        We scan **both** the language-matched lexicon and the cross-language
        section. PT and EN phrases are disjoint enough in practice that
        cross-scanning costs nothing and helps mixed-code-switched messages
        ("near me, perto de mim, qualquer coisa").

        Returns ``{category: [matched_phrases]}`` for every category that had
        at least one phrase hit, preserving the lexicon's original phrasing
        for the instrumentation log.
        """
        lexicon = self._load_implicit_lexicon()
        if not lexicon:
            return {}

        # Try the language-matched section first, then the other(s).
        # Map "pt-BR" / "pt" to "pt-BR", everything else to "en".
        primary_key = "pt-BR" if (language or "").lower().startswith("pt") else "en"
        scan_order = [primary_key] + [k for k in lexicon.keys() if k != primary_key]

        matches: Dict[str, List[str]] = {}
        for lang_key in scan_order:
            section = lexicon.get(lang_key)
            if not section:
                continue
            for category, normalised_phrases in section.items():
                for phrase in normalised_phrases:
                    if phrase and phrase in message_norm:
                        matches.setdefault(category, []).append(phrase)
        return matches

    def _scan_category_keywords(
        self, message_norm: str
    ) -> Tuple[List[str], Dict[str, List[str]]]:
        """Strategy 1 for category extraction: scan the (normalised) message
        for any keyword across **all** category lexicons exposed by the
        classifier. Cheap; no ML inference.

        Returns ``(matched_keywords_in_order, matches_by_category)`` where
        ``matched_keywords_in_order`` preserves the user's exact phrasing and
        ``matches_by_category`` maps each category that had at least one
        keyword hit to the list of matched keywords (useful for the
        instrumentation event).
        """
        if not self.intent_classifier or not hasattr(self.intent_classifier, 'category_keywords'):
            return [], {}

        matched_in_order: List[str] = []
        matches_by_category: Dict[str, List[str]] = {}
        for cat_name, keywords in self.intent_classifier.category_keywords.items():
            for keyword in keywords:
                if self.normalize_text(keyword) in message_norm:
                    matched_in_order.append(keyword.lower())
                    matches_by_category.setdefault(cat_name, []).append(keyword.lower())
        return matched_in_order, matches_by_category

    def _predict_category_safely(
        self, message: str
    ) -> Tuple[str, Optional[str], float, List[Dict[str, Any]]]:
        """Strategy 2 for category extraction: run the classifier with
        guaranteed-safe error handling.

        Returns ``(status, primary_category, primary_confidence, high_conf_categories)``
        where ``status`` is one of ``"ok"``, ``"unavailable"``, or
        ``"error:<ExceptionType>"``. ``high_conf_categories`` lists every
        secondary prediction with confidence ≥ 0.3.
        """
        if not self.intent_classifier:
            return "unavailable", None, 0.0, []

        try:
            category_result = self.intent_classifier.predict_category(message)
            primary = category_result.get('primary_category') or None
            confidence = float(category_result.get('primary_category_confidence', 0))
            high_conf: List[Dict[str, Any]] = []
            for cat_info in category_result.get('categories', []):
                if cat_info.get('confidence', 0) >= 0.3:
                    high_conf.append({
                        'category': cat_info.get('category', ''),
                        'confidence': float(cat_info.get('confidence', 0)),
                    })
            return "ok", primary, confidence, high_conf
        except Exception as e:
            logger.error(
                f"Intent_Classifier failed for category extraction: {e}",
                extra={"query": message, "error": str(e)},
                exc_info=True,
            )
            return f"error:{type(e).__name__}", None, 0.0, []

    def extract_categories(
        self, message: str, language: Optional[str] = None
    ) -> List[str]:
        """Extract category keywords using all three strategies.

        Composes three strategies, **all always** evaluated for instrumentation:

        - **Strategy 0** (P1/F5) — implicit-category lexicon lookup. Catches
          semantic phrasings that contain no category keyword at all
          (e.g. "tô com fome" → restaurant, "preciso pernoitar" → hotel).
          Lexicon source: ``belem_converse/classifiers/data/implicit_category_lexicon.json``.
        - **Strategy 1** — scan the message for any keyword across all category
          lexicons (cheap, no ML inference). Output preserves the user's exact
          phrasing and tells us which categories the surface form touched.
        - **Strategy 2** — run the classifier to get the primary category and
          all secondary categories above the 0.3 confidence threshold.

        The returned list is the union of (a) keywords the user actually typed,
        (b) the full keyword lexicon of every Strategy-0 hit's category, and
        (c) the full keyword lexicon of every classifier-recommended category.
        Order: exact user terms first, then expanded keywords.
        Deduplicated by normalised form.

        ``language`` is used to bias which language section of the implicit
        lexicon is scanned first. Both sections are always consulted (PT and
        EN phrases are disjoint enough in practice).

        Mirrors the instrumentation pattern in :meth:`extract_proximity_intent`
        and :meth:`extract_open_now`: a structured ``category_detection`` event
        is emitted on every call carrying agreement signals that downstream
        tooling can mine to validate the classifier.
        """
        message_norm = self.normalize_text(message)

        strategy0_matches = self._detect_categories_strategy0(message_norm, language)
        strategy0_categories = set(strategy0_matches.keys())

        keyword_matches, matches_by_category = self._scan_category_keywords(message_norm)
        keyword_match_categories = set(matches_by_category.keys())

        status, primary_category, primary_confidence, high_conf_categories = (
            self._predict_category_safely(message)
        )

        detected: List[str] = list(keyword_matches)

        # Expand Strategy-0 hits into the full keyword lexicon for that
        # category so downstream retrieval gets the same vocabulary surface
        # area as a keyword hit would have produced. This is what wires the
        # implicit lexicon into the existing place_type / search machinery.
        if (
            strategy0_categories
            and self.intent_classifier
            and hasattr(self.intent_classifier, 'category_keywords')
        ):
            for cat_name in strategy0_categories:
                detected.extend(
                    kw.lower()
                    for kw in self.intent_classifier.category_keywords.get(cat_name, [])
                )

        if (
            primary_category
            and primary_confidence >= 0.3
            and self.intent_classifier
            and hasattr(self.intent_classifier, 'category_keywords')
        ):
            all_keywords_for_primary = self.intent_classifier.category_keywords.get(
                primary_category, []
            )
            detected.extend(kw.lower() for kw in all_keywords_for_primary)

        for cat_info in high_conf_categories:
            cat_name = cat_info['category']
            if cat_name and cat_name != primary_category and self.intent_classifier:
                all_keywords_for_category = self.intent_classifier.category_keywords.get(
                    cat_name, []
                )
                detected.extend(kw.lower() for kw in all_keywords_for_category)

        seen = set()
        unique_detected: List[str] = []
        for item in detected:
            normalized_item = self.normalize_text(item)
            if normalized_item not in seen:
                seen.add(normalized_item)
                unique_detected.append(item)

        # Structured instrumentation event. Mine `agree_strategy01`,
        # `agree_strategy12`, and the per-strategy contribution counts to
        # decide whether any strategy can be retired or scaled back over
        # real traffic.
        agree_strategy12: Optional[bool]
        if primary_category and keyword_match_categories:
            agree_strategy12 = primary_category in keyword_match_categories
        else:
            agree_strategy12 = None

        agree_strategy01: Optional[bool]
        if strategy0_categories and primary_category:
            agree_strategy01 = primary_category in strategy0_categories
        else:
            agree_strategy01 = None

        logger.info(
            "category_detection",
            extra={
                "query": message,
                "language": language,
                "classifier_status": status,
                "classifier_top_category": primary_category,
                "classifier_top_confidence": primary_confidence,
                "classifier_high_conf_categories": high_conf_categories,
                "keyword_match_categories": sorted(keyword_match_categories),
                "keyword_match_count": len(keyword_matches),
                "strategy0_categories": sorted(strategy0_categories),
                "strategy0_phrases": {
                    cat: phrases for cat, phrases in strategy0_matches.items()
                },
                "strategy0_lexicon_status": (
                    self._implicit_lexicon_load_error or "ok"
                ),
                "agree_strategy12": agree_strategy12,
                "agree_strategy01": agree_strategy01,
                # Backward-compat alias of agree_strategy12 (existing
                # observability dashboards consume `agree`).
                "agree": agree_strategy12,
                "result_count": len(unique_detected),
            },
        )

        return unique_detected
    
    # Phrases that explicitly mean "currently open". Multi-word, language-agnostic,
    # checked with plain substring matching on accent-stripped lowered text.
    _OPEN_NOW_PHRASES = [
        # Portuguese
        'aberto agora', 'aberta agora', 'aberto neste momento', 'aberto agora mesmo',
        'funcionando agora', 'funcionando neste momento', 'aberto 24', 'aberto 24 horas',
        'que esteja aberto', 'que estejam abertos', 'ainda aberto', 'ainda abre',
        'ainda funciona', 'aberto hoje', 'aberto no momento',
        # English
        'open now', 'currently open', 'open right now', 'open 24', 'open 24 hours',
        'still open', 'open at this time', 'open today',
        # 24-hour shorthand variants (P0/F4 — diagnostic showed bare "24h" /
        # "24 horas" missed by Strategy 1, costing 3 multi_intent failures).
        # Order matters: longer phrases first so the signal label is precise.
        'vinte e quatro horas', '24 horas', '24hrs', '24hr', '24/7', '24h',
    ]
    # Phrases that explicitly mean "currently closed". Used as a soft override
    # to suppress a Strategy-1 True when both signals appear in the same query
    # (e.g. "qual abre depois que esse fechar agora?").
    _CLOSED_NOW_PHRASES = [
        'fechado agora', 'fechado hoje', 'closed now', 'currently closed',
    ]
    # Single-word presence checks used by Strategy 2 once the classifier has
    # confirmed business_hours intent (kept here so the helper is testable in isolation).
    _OPEN_NOW_KEYWORDS = ['open', 'aberto', 'aberta', 'abertos', 'abertas', 'funcionando']
    _CLOSED_NOW_KEYWORDS = ['closed', 'fechado', 'fechada', 'fechados', 'fechadas']

    def _detect_open_now_strategy1(self, message_norm: str) -> Tuple[bool, Optional[str]]:
        """Strategy 1: direct phrase matching for currently-open intent.

        Returns ``(hit, signal)`` where ``hit`` is True only when an open-phrase
        matches AND no closed-phrase override is present in the same query.
        ``signal`` is a short label like ``"phrase:open now"`` or
        ``"closed_override:fechado agora"`` for the instrumentation log.
        """
        closed_hit = next((p for p in self._CLOSED_NOW_PHRASES if p in message_norm), None)
        if closed_hit:
            return False, f"closed_override:{closed_hit}"

        open_hit = next((p for p in self._OPEN_NOW_PHRASES if p in message_norm), None)
        if open_hit:
            return True, f"phrase:{open_hit}"

        return False, None

    def _detect_open_now_strategy2(self, message: str, message_norm: str) -> bool:
        """Strategy 2: classifier-based open_now detection.

        Returns True when ``business_hours`` appears anywhere in the
        classifier's top-K intents above the 0.3 confidence threshold AND
        open keywords are present without a closed-keyword override.

        P1/F9 — previously this checked ``primary_intent`` only. The
        diagnostic showed multi-intent queries like "açaí cremoso barato 24
        horas" land ``business_hours`` at rank 2 behind ``price``, costing
        recall. Mirrors the existing top-K logic in
        :meth:`_detect_proximity_strategy2`.

        Always swallows classifier exceptions and routes to the keyword
        fallback so callers can rely on the boolean. Logs failures with
        the structured ``extra`` payload that downstream observability tooling
        depends on.
        """
        intent_result: Dict[str, Any]

        if not self.intent_classifier:
            intent_result = self._fallback_intent_detection(
                message, "No intent_classifier available"
            )
        else:
            try:
                intent_result = self.intent_classifier.predict_intent(message)
            except Exception as e:
                logger.error(
                    f"Intent_Classifier failed for open_now extraction: {e}",
                    extra={"query": message, "error": str(e)},
                    exc_info=True,
                )
                intent_result = self._fallback_intent_detection(
                    message, f"predict_intent failed: {e}"
                )

        # Top-K membership check (P1/F9). Both primary and secondary intents
        # qualify so multi-intent queries — where business_hours often loses
        # the primary slot to price/popularity/location — still register as
        # open_now-relevant.
        business_hours_above_threshold = False
        if (
            intent_result.get('primary_intent') == 'business_hours'
            and intent_result.get('primary_confidence', 0) >= 0.3
        ):
            business_hours_above_threshold = True
        else:
            for intent_info in intent_result.get('intents', []):
                if (
                    intent_info.get('intent') == 'business_hours'
                    and intent_info.get('confidence', 0) >= 0.3
                ):
                    business_hours_above_threshold = True
                    break

        if not business_hours_above_threshold:
            return False

        has_open = any(kw in message_norm for kw in self._OPEN_NOW_KEYWORDS)
        has_closed = any(kw in message_norm for kw in self._CLOSED_NOW_KEYWORDS)
        return has_open and not has_closed

    def extract_open_now(self, message: str, language: str) -> Optional[bool]:
        """Detect whether the user wants currently-open places.

        Composes two strategies, both **always** evaluated for instrumentation:

        - **Strategy 1** — direct phrase matching, with a closed-phrase override.
        - **Strategy 2** — classifier ``business_hours`` intent + open keyword.

        Final answer is ``True`` if either strategy hits, else ``None``. We
        intentionally never return ``False`` because the legacy contract is
        tri-valued (True / unknown), and downstream filters interpret missing
        as "do not constrain" which is the safe default.

        Mirrors the instrumentation pattern in :meth:`extract_proximity_intent`:
        a structured ``open_now_detection`` event is emitted on every call so
        we can mine real traffic for keyword/classifier agreement and decide
        whether the keyword list can eventually be retired.
        """
        message_norm = self.normalize_text(message)

        strategy1_hit, strategy1_signal = self._detect_open_now_strategy1(message_norm)
        strategy2_hit = self._detect_open_now_strategy2(message, message_norm)

        final = True if (strategy1_hit or strategy2_hit) else None

        logger.info(
            "open_now_detection",
            extra={
                "query": message,
                "language": language,
                "strategy1_hit": strategy1_hit,
                "strategy1_signal": strategy1_signal,
                "strategy2_hit": strategy2_hit,
                "agree": strategy1_hit == strategy2_hit,
                "result": final,
            },
        )

        return final
    
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
    
    def _detect_proximity_strategy1(self, message_norm: str) -> Tuple[bool, Optional[str]]:
        """Strategy 1: direct phrase / keyword matching on normalised text.

        Returns (hit, signal) where ``signal`` is a short label like
        ``"phrase:near me"`` or ``"word:nearby"`` — used for the instrumentation log.
        """
        for phrase in self._PROXIMITY_PHRASES:
            if phrase in message_norm:
                return True, f"phrase:{phrase}"

        for word in self._PROXIMITY_WORDS:
            if re.search(r'\b' + re.escape(word) + r'\b', message_norm):
                return True, f"word:{word}"

        return False, None

    def _detect_proximity_strategy2(self, message: str) -> bool:
        """Strategy 2: Intent_Classifier location signal (with fallback on failure).

        Always returns a boolean. Logs classifier failures and routes to the
        keyword fallback so callers can rely on the result. Kept separate from
        :meth:`extract_proximity_intent` so it can be invoked unconditionally
        for instrumentation, not just when Strategy 1 misses.
        """
        if not self.intent_classifier:
            fallback_result = self._fallback_intent_detection(
                message, "No intent_classifier available"
            )
            return any(
                i.get('intent') == 'location'
                for i in fallback_result.get('intents', [])
            )

        try:
            intent_result = self.intent_classifier.predict_intent(message)

            if intent_result.get('primary_intent') == 'location':
                confidence = intent_result.get('primary_confidence', 0)
                if confidence >= 0.3:
                    logger.debug(f"Proximity intent detected via classifier primary (conf={confidence:.3f})")
                    return True

            for intent_info in intent_result.get('intents', []):
                if intent_info.get('intent') == 'location':
                    confidence = intent_info.get('confidence', 0)
                    if confidence >= 0.3:
                        logger.debug(f"Proximity intent detected via classifier intents (conf={confidence:.3f})")
                        return True

            return False

        except Exception as e:
            logger.error(
                f"Intent_Classifier failed for proximity intent detection: {e}",
                extra={"query": message, "error": str(e)},
                exc_info=True,
            )
            fallback_result = self._fallback_intent_detection(
                message, f"predict_intent failed: {e}"
            )
            return any(
                i.get('intent') == 'location'
                for i in fallback_result.get('intents', [])
            )

    def extract_proximity_intent(self, message: str, language: str) -> bool:
        """Detect if the user wants proximity-based filtering.

        The function composes two strategies as a logical OR:

        - **Strategy 1** — direct phrase/keyword matching on normalised text.
          Word-boundary safe so ``aqui`` does NOT match inside ``manicure``.
        - **Strategy 2** — :class:`Intent_Classifier` location signal, with a
          keyword fallback when the classifier raises or is absent.

        Both strategies are **always** evaluated, even when Strategy 1 already
        gives a definitive answer. This costs one extra inference per query but
        gives us continuous instrumentation about how often the keyword list
        and the classifier agree — i.e. the data needed to decide whether the
        keyword list can eventually be retired in favour of the classifier
        (see the post-rebase intent-detection validation work).

        The boolean returned is ``strategy1_hit OR strategy2_hit`` so the
        function stays resilient: classifier failures cannot regress proximity
        detection for queries the keyword list would have caught.
        """
        message_norm = self.normalize_text(message)

        strategy1_hit, strategy1_signal = self._detect_proximity_strategy1(message_norm)
        strategy2_hit = self._detect_proximity_strategy2(message)

        # Structured instrumentation event. Mine these to compare the two
        # strategies over real traffic before deciding to retire Strategy 1.
        logger.info(
            "proximity_intent_detection",
            extra={
                "query": message,
                "language": language,
                "strategy1_hit": strategy1_hit,
                "strategy1_signal": strategy1_signal,
                "strategy2_hit": strategy2_hit,
                "agree": strategy1_hit == strategy2_hit,
                "result": strategy1_hit or strategy2_hit,
            },
        )

        return strategy1_hit or strategy2_hit
    
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
        categories = self.extract_categories(message, language)
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
