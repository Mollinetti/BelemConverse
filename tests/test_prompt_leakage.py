"""
Prompt Leakage Test Suite for BelemConverse.

Tests that LLM responses do not leak internal prompt instructions, markers,
or system messages in both Portuguese (PT) and English (EN).

Run with: python -m tests.test_prompt_leakage
"""

import sys
import os
import time
import logging
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Set
from datetime import datetime

_project_root = Path(__file__).resolve().parent.parent

_venv_python = _project_root / ".venv" / "bin" / "python"
_venv_python3 = _project_root / ".venv" / "bin" / "python3"
_using_venv = (
    hasattr(sys, "real_prefix")
    or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
    or ".venv" in sys.executable
    or "venv" in sys.executable
)

if not _using_venv and (_venv_python.exists() or _venv_python3.exists()):
    print("\nWARNING: Not using virtual environment!")
    print(f"   Current Python: {sys.executable}")
    print("   Please activate the venv first:")
    print(f"   $ cd {_project_root}")
    print("   $ source .venv/bin/activate")
    print("   $ python -m tests.test_prompt_leakage\n")

# Configure logging
LOG_FILE_PATH = Path(__file__).parent / "prompt_leakage_test_results.txt"
JSON_FILE_PATH = Path(__file__).parent / "prompt_leakage_test_results.json"

# Create file handler
file_handler = logging.FileHandler(LOG_FILE_PATH, mode='w', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Configure root logger
logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
logger = logging.getLogger(__name__)


# Test coordinates
USER_HOME_COORDS = (-1.4695, -48.4665)  # Belém location
TOURIST_CENTER_COORDS = (-1.4558, -48.4902)  # Near Ver-o-Peso


class LeakageDetector:
    """Detects prompt leakage in LLM responses."""
    
    def __init__(self):
        """Initialize leakage patterns."""
        # Prompt markers (Llama 3.1 format - compatible with Mistral)
        # Llama 3.1 uses [INST] and <<SYS>> tags similar to Mistral
        self.prompt_markers = {
            '[INST]', '[/INST]', '<<SYS>>', '</SYS>>', '<</SYS>>',
            '[inst]', '[/inst]', '<<sys>>', '</sys>>', '<</sys>>',
            # Llama 3.1 specific tokens
            '<|begin_of_text|>', '<|end_of_text|>', '<|eot_id|>', '<|eom_id|>'
        }
        
        # System instructions (English)
        self.system_instructions_en = {
            'CRITICAL RULES',
            'RESPONSE FORMAT',
            'FOLLOW-UP',
            'Do NOT include',
            'ALWAYS respond in English only',
            'Use ONLY the information provided',
            'NEVER invent or make up',
            'If information is not available',
            'simply omit it',
            'do NOT guess or fabricate',
            'You are a friendly and experienced travel guide',
            'Help users discover local attractions',
            'You are an expert travel itinerary planner',
            'WARNING: Any place name',
            'you are hallucinating',
            'violating your instructions',
            'Copy the place names',
            'EXACTLY as provided'
        }
        
        # System instructions (Portuguese)
        self.system_instructions_pt = {
            'REGRAS CRÍTICAS',
            'FORMATO DA RESPOSTA',
            'ACOMPANHAMENTO',
            'NÃO inclua',
            'SEMPRE responda em Português Brasileiro apenas',
            'Use APENAS as informações fornecidas',
            'NUNCA invente ou crie',
            'Se a informação não estiver disponível',
            'simplesmente omita',
            'NÃO adivinhe ou fabrique',
            'Você é um guia turístico',
            'Ajude os usuários a descobrir',
            'Você é um especialista em planejamento de roteiros',
            'AVISO: Qualquer nome de lugar',
            'você está alucinando',
            'violando suas instruções',
            'Copie os nomes dos lugares',
            'EXATAMENTE como fornecido'
        }
        
        # Context markers
        self.context_markers = {
            '=== AVAILABLE INFORMATION ===',
            '=== END OF INFORMATION ===',
            '=== INFORMAÇÕES DISPONÍVEIS ===',
            '=== FIM DAS INFORMAÇÕES ===',
            '--- PLACE',
            '--- Place',
            '=== ITINERARY DATA',
            '=== END OF ITINERARY DATA',
            'ITINERARY DATA (USE ONLY THIS DATA',
            'DO NOT INVENT ANYTHING ELSE',
            'Present ONLY the stops listed above'
        }
        
        # Location context strings
        self.location_markers = {
            'USER LOCATION:',
            'LOCALIZAÇÃO DO USUÁRIO:',
            'User is currently in Belém',
            'O usuário está atualmente em Belém',
            'coordinates:',
            'coordenadas:'
        }
        
        # Conversation history markers (when part of formatting)
        self.conversation_markers = {
            'User:',
            'Usuário:',
            'Assistant:',
            'Assistente:'
        }
        
        # Internal instruction phrases
        self.internal_phrases_en = {
            'NEVER invent or make up information',
            'do NOT guess or fabricate',
            'If information is not available, simply omit it',
            'After answering, ask a helpful follow-up question',
            'Would you like more details about this place',
            'Should I find similar places nearby',
            'Do you need directions or the Google Maps link'
        }
        
        self.internal_phrases_pt = {
            'NUNCA invente ou crie informações',
            'NÃO adivinhe ou fabrique',
            'Se a informação não estiver disponível, simplesmente omita',
            'Após responder, faça uma pergunta de acompanhamento útil',
            'Gostaria de mais detalhes sobre este lugar',
            'Quer que eu encontre lugares similares por perto',
            'Precisa de direções ou do link do Google Maps'
        }
        
        # Compile all patterns for case-insensitive matching
        self.all_patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> List[re.Pattern]:
        """Compile all patterns into regex for case-insensitive matching."""
        patterns = []
        
        # Add all pattern sets
        all_strings = (
            self.prompt_markers |
            self.system_instructions_en |
            self.system_instructions_pt |
            self.context_markers |
            self.location_markers |
            self.conversation_markers |
            self.internal_phrases_en |
            self.internal_phrases_pt
        )
        
        for pattern_str in all_strings:
            # Escape special regex characters and create case-insensitive pattern
            escaped = re.escape(pattern_str)
            patterns.append(re.compile(escaped, re.IGNORECASE))
        
        return patterns
    
    def detect_leakage(self, response: str) -> Dict[str, Any]:
        """
        Detect prompt leakage in a response.
        
        Args:
            response: The LLM response text to check
            
        Returns:
            Dictionary with leakage detection results:
            {
                'has_leakage': bool,
                'leaked_patterns': List[str],
                'leakage_count': int,
                'leakage_details': List[Dict]  # Line number and context
            }
        """
        if not response:
            return {
                'has_leakage': False,
                'leaked_patterns': [],
                'leakage_count': 0,
                'leakage_details': []
            }
        
        leaked_patterns = set()
        leakage_details = []
        lines = response.split('\n')
        
        # Check each line for leakage patterns
        for line_num, line in enumerate(lines, 1):
            for pattern in self.all_patterns:
                matches = pattern.finditer(line)
                for match in matches:
                    matched_text = match.group()
                    leaked_patterns.add(matched_text)
                    
                    # Get context (surrounding text)
                    start = max(0, match.start() - 30)
                    end = min(len(line), match.end() + 30)
                    context = line[start:end].strip()
                    
                    leakage_details.append({
                        'line': line_num,
                        'pattern': matched_text,
                        'context': context,
                        'full_line': line.strip()
                    })
        
        # Filter out false positives (patterns that might appear naturally)
        filtered_patterns = self._filter_false_positives(leaked_patterns, response)
        filtered_details = [
            detail for detail in leakage_details
            if detail['pattern'] in filtered_patterns
        ]
        
        return {
            'has_leakage': len(filtered_patterns) > 0,
            'leaked_patterns': sorted(list(filtered_patterns)),
            'leakage_count': len(filtered_patterns),
            'leakage_details': filtered_details
        }
    
    def _filter_false_positives(self, patterns: Set[str], response: str) -> Set[str]:
        """
        Filter out false positives where patterns might appear naturally.
        
        For example, "format" might appear in user questions, or "user" might
        be part of "restaurant" or other words.
        """
        filtered = set()
        response_lower = response.lower()
        lines = response.split('\n')
        
        for pattern in patterns:
            pattern_lower = pattern.lower()
            
            # Special handling for "--- PLACE" pattern
            # Only flag if it appears as a standalone marker, not as "--- PLACE 1 ---" (which is LLM formatting)
            if pattern_lower == '--- place':
                # Check if it appears as standalone or with numbers
                is_standalone_marker = False
                for line in lines:
                    line_lower = line.lower().strip()
                    # Match "--- PLACE" or "--- PLACE ---" but not "--- PLACE 1 ---"
                    if line_lower == '--- place' or line_lower == '--- place ---':
                        is_standalone_marker = True
                        break
                    # If it's "--- PLACE 1 ---" or similar, it's likely LLM formatting, not leakage
                    if '--- place' in line_lower and any(char.isdigit() for char in line_lower):
                        # This is likely LLM's own formatting, not leakage
                        continue
                
                if is_standalone_marker:
                    filtered.add(pattern)
                # Otherwise, skip it (it's LLM formatting, not leakage)
                continue
            
            # Check for common false positives
            false_positives = [
                ('format', 'information'),  # "format" in "information"
                ('user', 'restaurant'),     # "user" in "restaurant"
                ('user', 'museum'),         # "user" in "museum"
                ('assistant', 'restaurant'), # "assistant" in "restaurant"
            ]
            
            is_false_positive = False
            for fp_pattern, fp_context in false_positives:
                if fp_pattern in pattern_lower:
                    # Check if it's part of a larger word
                    pattern_idx = response_lower.find(pattern_lower)
                    if pattern_idx != -1:
                        # Check surrounding characters
                        before = response_lower[max(0, pattern_idx - 1)]
                        after_idx = pattern_idx + len(pattern_lower)
                        after = response_lower[min(len(response_lower) - 1, after_idx)]
                        
                        # If surrounded by letters, it's likely part of a word
                        if (before.isalpha() or after.isalpha()) and fp_context in response_lower:
                            is_false_positive = True
                            break
            
            if not is_false_positive:
                filtered.add(pattern)
        
        return filtered


class PromptLeakageTestSuite:
    """Test suite for prompt leakage detection."""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.agent = None
        self.detector = LeakageDetector()
        self.test_cases = self._define_test_cases()
    
    def _define_test_cases(self) -> List[Dict[str, Any]]:
        """Define test cases covering various query types."""
        return [
            # Regular Queries - English
            {
                'query': 'Where can I find good restaurants in Belém?',
                'language': 'en',
                'query_type': 'regular',
                'coordinates': USER_HOME_COORDS,
                'description': 'Simple place search (EN)'
            },
            {
                'query': 'What are the best hotels near me?',
                'language': 'en',
                'query_type': 'regular',
                'coordinates': USER_HOME_COORDS,
                'description': 'Location-based query (EN)'
            },
            {
                'query': 'Show me museums in Belém',
                'language': 'en',
                'query_type': 'regular',
                'coordinates': TOURIST_CENTER_COORDS,
                'description': 'Category-specific query (EN)'
            },
            {
                'query': 'Tell me more about the first one',
                'language': 'en',
                'query_type': 'follow-up',
                'coordinates': USER_HOME_COORDS,
                'description': 'Follow-up query (EN)'
            },
            
            # Regular Queries - Portuguese
            {
                'query': 'Onde posso encontrar bons restaurantes em Belém?',
                'language': 'pt',
                'query_type': 'regular',
                'coordinates': USER_HOME_COORDS,
                'description': 'Simple place search (PT)'
            },
            {
                'query': 'Quais são os melhores hotéis perto de mim?',
                'language': 'pt',
                'query_type': 'regular',
                'coordinates': USER_HOME_COORDS,
                'description': 'Location-based query (PT)'
            },
            {
                'query': 'Mostre-me museus em Belém',
                'language': 'pt',
                'query_type': 'regular',
                'coordinates': TOURIST_CENTER_COORDS,
                'description': 'Category-specific query (PT)'
            },
            {
                'query': 'Me conte mais sobre o primeiro',
                'language': 'pt',
                'query_type': 'follow-up',
                'coordinates': USER_HOME_COORDS,
                'description': 'Follow-up query (PT)'
            },
            
            # Tour Planning Queries - English
            {
                'query': 'Plan a tour for me in Belém',
                'language': 'en',
                'query_type': 'tour_planning',
                'coordinates': USER_HOME_COORDS,
                'description': 'Generic tour request (EN)'
            },
            {
                'query': 'I want to visit açaí places and tourist attractions',
                'language': 'en',
                'query_type': 'tour_planning',
                'coordinates': TOURIST_CENTER_COORDS,
                'description': 'Specific tour request (EN)'
            },
            {
                'query': 'Plan a half-day tour starting at 10am',
                'language': 'en',
                'query_type': 'tour_planning',
                'coordinates': USER_HOME_COORDS,
                'description': 'Time-specific tour (EN)'
            },
            
            # Tour Planning Queries - Portuguese
            {
                'query': 'Planeje um passeio para mim em Belém',
                'language': 'pt',
                'query_type': 'tour_planning',
                'coordinates': USER_HOME_COORDS,
                'description': 'Generic tour request (PT)'
            },
            {
                'query': 'Quero visitar lugares de açaí e atrações turísticas',
                'language': 'pt',
                'query_type': 'tour_planning',
                'coordinates': TOURIST_CENTER_COORDS,
                'description': 'Specific tour request (PT)'
            },
            {
                'query': 'Planeje um passeio de meio dia começando às 10h',
                'language': 'pt',
                'query_type': 'tour_planning',
                'coordinates': USER_HOME_COORDS,
                'description': 'Time-specific tour (PT)'
            },
            
            # Edge Cases
            {
                'query': 'Find me a place that does not exist in Belém',
                'language': 'en',
                'query_type': 'edge_case',
                'coordinates': USER_HOME_COORDS,
                'description': 'Empty context query (EN)'
            },
            {
                'query': 'Encontre um lugar que não existe em Belém',
                'language': 'pt',
                'query_type': 'edge_case',
                'coordinates': USER_HOME_COORDS,
                'description': 'Empty context query (PT)'
            },
        ]
    
    def initialize(self) -> bool:
        """Initialize the RAG agent."""
        # #region agent log
        try:
            import json as _json
            import time as _time
            _log_path = "/Users/marcomollinetti/Documents/Projects/BelemConverse/.cursor/debug.log"
            with open(_log_path, "a") as _f:
                _f.write(_json.dumps({"id": f"log_{int(_time.time())}_init_start", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:initialize", "message": "Initialize start", "data": {}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}) + "\n")
        except: pass
        # #endregion
        
        logger.info("Initializing RAG agent for prompt leakage tests...")
        
        try:
            # #region agent log
            try:
                with open(_log_path, "a") as _f:
                    _f.write(_json.dumps({"id": f"log_{int(_time.time())}_before_imports", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:initialize", "message": "Before imports", "data": {}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}) + "\n")
            except: pass
            # #endregion
            
            from belem_converse.ingest.vector_store import VectorStoreManager
            from belem_converse.utils.models import ModelManager
            from belem_converse.core.enhanced_rag_agent import EnhancedRAGAgent
            
            # #region agent log
            try:
                with open(_log_path, "a") as _f:
                    _f.write(_json.dumps({"id": f"log_{int(_time.time())}_after_imports", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:initialize", "message": "After imports", "data": {}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}) + "\n")
            except: pass
            # #endregion
            
            # Initialize vector store
            logger.info("Loading vector store...")
            # #region agent log
            try:
                with open(_log_path, "a") as _f:
                    _f.write(_json.dumps({"id": f"log_{int(_time.time())}_before_vs", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:initialize", "message": "Before VectorStoreManager", "data": {}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}) + "\n")
            except: pass
            # #endregion
            
            vector_store_manager = VectorStoreManager()
            
            # #region agent log
            try:
                with open(_log_path, "a") as _f:
                    _f.write(_json.dumps({"id": f"log_{int(_time.time())}_after_vs", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:initialize", "message": "After VectorStoreManager", "data": {}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}) + "\n")
            except: pass
            # #endregion
            
            # Initialize LLM model
            logger.info("Loading LLM model...")
            # #region agent log
            try:
                with open(_log_path, "a") as _f:
                    _f.write(_json.dumps({"id": f"log_{int(_time.time())}_before_llm", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:initialize", "message": "Before ModelManager.get_llm", "data": {}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}) + "\n")
            except: pass
            # #endregion
            
            llm_model = ModelManager.get_llm()
            
            # #region agent log
            try:
                with open(_log_path, "a") as _f:
                    _f.write(_json.dumps({"id": f"log_{int(_time.time())}_after_llm", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:initialize", "message": "After ModelManager.get_llm", "data": {"llm_model_type": type(llm_model).__name__}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}) + "\n")
            except: pass
            # #endregion
            
            # Initialize RAG Agent
            logger.info("Setting up Enhanced RAG Agent...")
            # #region agent log
            try:
                with open(_log_path, "a") as _f:
                    _f.write(_json.dumps({"id": f"log_{int(_time.time())}_before_agent", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:initialize", "message": "Before EnhancedRAGAgent", "data": {}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}) + "\n")
            except: pass
            # #endregion
            
            self.agent = EnhancedRAGAgent(
                vector_store_manager=vector_store_manager,
                llm_model=llm_model
            )
            
            # #region agent log
            try:
                with open(_log_path, "a") as _f:
                    _f.write(_json.dumps({"id": f"log_{int(_time.time())}_after_agent", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:initialize", "message": "After EnhancedRAGAgent", "data": {"agent_created": self.agent is not None}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}) + "\n")
            except: pass
            # #endregion
            
            logger.info("Initialization complete!")
            return True
            
        except ImportError as e:
            # #region agent log
            try:
                import traceback as _tb
                with open(_log_path, "a") as _f:
                    _f.write(_json.dumps({"id": f"log_{int(_time.time())}_init_import_error", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:initialize", "message": "ImportError in initialize", "data": {"exception_type": type(e).__name__, "exception_msg": str(e)}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}) + "\n")
            except: pass
            # #endregion
            missing_module = str(e).replace("No module named ", "").strip("'\"")
            logger.error(f"Failed to initialize: Missing dependency '{missing_module}'")
            logger.error(f"Please install dependencies: pip install -r requirements.txt")
            print(f"\n❌ ERROR: Missing dependency '{missing_module}'")
            print(f"   Please run: pip install -r requirements.txt\n")
            import traceback
            logger.error(traceback.format_exc())
            return False
        except Exception as e:
            # #region agent log
            try:
                import traceback as _tb
                with open(_log_path, "a") as _f:
                    _f.write(_json.dumps({"id": f"log_{int(_time.time())}_init_exception", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:initialize", "message": "Exception in initialize", "data": {"exception_type": type(e).__name__, "exception_msg": str(e), "traceback": _tb.format_exc()}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}) + "\n")
            except: pass
            # #endregion
            logger.error(f"Failed to initialize: {e}")
            print(f"\n❌ ERROR: {e}\n")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def run_test(self, test_num: int, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Run a single prompt leakage test."""
        query = test_case['query']
        description = test_case['description']
        coordinates = test_case.get('coordinates')
        
        logger.info(f"\n{'='*70}")
        logger.info(f"TEST {test_num}: {description}")
        logger.info(f"Query: '{query}'")
        logger.info(f"Language: {test_case['language'].upper()}")
        logger.info(f"Type: {test_case['query_type']}")
        logger.info(f"{'='*70}")
        
        result = {
            'test_num': test_num,
            'description': description,
            'query': query,
            'language': test_case['language'],
            'query_type': test_case['query_type'],
            'coordinates': coordinates,
            'response': None,
            'leakage_result': None,
            'passed': False,
            'error': None,
            'response_time': 0
        }
        
        start_time = time.time()
        
        try:
            # Query the agent
            response = self.agent.query(
                question=query,
                user_coordinates=coordinates
            )
            
            result['response'] = response
            result['response_time'] = time.time() - start_time
            
            # Detect leakage
            leakage_result = self.detector.detect_leakage(response)
            result['leakage_result'] = leakage_result
            result['passed'] = not leakage_result['has_leakage']
            
            # Log results
            if leakage_result['has_leakage']:
                logger.warning(f"\n⚠️  LEAKAGE DETECTED in Test {test_num}!")
                logger.warning(f"Leaked patterns ({leakage_result['leakage_count']}):")
                for pattern in leakage_result['leaked_patterns']:
                    logger.warning(f"  - {pattern}")
                
                logger.warning("\nLeakage details:")
                for detail in leakage_result['leakage_details']:
                    logger.warning(f"  Line {detail['line']}: {detail['pattern']}")
                    logger.warning(f"    Context: ...{detail['context']}...")
                    logger.warning(f"    Full line: {detail['full_line']}")
            else:
                logger.info(f"✓ No leakage detected")
            
            logger.info(f"\nResponse preview (first 200 chars):")
            logger.info(f"{response[:200]}...")
            
        except Exception as e:
            result['error'] = str(e)
            result['response_time'] = time.time() - start_time
            logger.error(f"Test {test_num} failed with error: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        logger.info(f"\nTest {test_num} completed in {result['response_time']:.2f}s")
        logger.info(f"Result: {'✓ PASSED' if result['passed'] else '✗ FAILED'}")
        
        return result
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all test cases."""
        # #region agent log
        try:
            import json as _json
            import time as _time
            _log_path = "/Users/marcomollinetti/Documents/Projects/BelemConverse/.cursor/debug.log"
            with open(_log_path, "a") as _f:
                _f.write(_json.dumps({"id": f"log_{int(_time.time())}_run_all_start", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:run_all_tests", "message": "run_all_tests start", "data": {"test_cases_count": len(self.test_cases), "agent_exists": self.agent is not None}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "E"}) + "\n")
        except: pass
        # #endregion
        
        # Optional limit for quick run (e.g. PROMPT_LEAKAGE_MAX_TESTS=1)
        _max = os.environ.get("PROMPT_LEAKAGE_MAX_TESTS")
        tests_to_run = self.test_cases
        if _max is not None:
            try:
                n = int(_max)
                if n > 0:
                    tests_to_run = self.test_cases[:n]
                    logger.info(f"Quick mode: running first {n} of {len(self.test_cases)} tests (set PROMPT_LEAKAGE_MAX_TESTS to run more or unset for all)")
            except ValueError:
                pass
        
        logger.info("\n" + "="*70)
        logger.info("PROMPT LEAKAGE TEST SUITE")
        logger.info("="*70)
        logger.info(f"Total test cases: {len(tests_to_run)}" + (f" (of {len(self.test_cases)})" if tests_to_run is not self.test_cases else ""))
        logger.info(f"Detector patterns: {len(self.detector.all_patterns)}")
        logger.info("="*70)
        
        if not self.agent:
            logger.error("Agent not initialized. Call initialize() first.")
            # #region agent log
            try:
                with open(_log_path, "a") as _f:
                    _f.write(_json.dumps({"id": f"log_{int(_time.time())}_no_agent", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:run_all_tests", "message": "Agent not initialized", "data": {}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "E"}) + "\n")
            except: pass
            # #endregion
            return {'error': 'Agent not initialized'}
        
        # #region agent log
        try:
            with open(_log_path, "a") as _f:
                _f.write(_json.dumps({"id": f"log_{int(_time.time())}_before_loop", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:run_all_tests", "message": "Before test loop", "data": {"test_cases_count": len(self.test_cases)}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "E"}) + "\n")
        except: pass
        # #endregion
        
        # Run all tests (or subset in quick mode)
        for i, test_case in enumerate(tests_to_run, 1):
            # #region agent log
            try:
                with open(_log_path, "a") as _f:
                    _f.write(_json.dumps({"id": f"log_{int(_time.time())}_test_start", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:run_all_tests", "message": "Starting test", "data": {"test_num": i, "query": test_case.get('query', '')[:50]}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "E"}) + "\n")
            except: pass
            # #endregion
            result = self.run_test(i, test_case)
            self.results.append(result)
            # #region agent log
            try:
                with open(_log_path, "a") as _f:
                    _f.write(_json.dumps({"id": f"log_{int(_time.time())}_test_end", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:run_all_tests", "message": "Test completed", "data": {"test_num": i, "passed": result.get('passed', False), "has_error": result.get('error') is not None}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "E"}) + "\n")
            except: pass
            # #endregion
        
        # #region agent log
        try:
            with open(_log_path, "a") as _f:
                _f.write(_json.dumps({"id": f"log_{int(_time.time())}_before_summary_gen", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:run_all_tests", "message": "Before _generate_summary", "data": {"results_count": len(self.results)}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "E"}) + "\n")
        except: pass
        # #endregion
        
        # Generate summary
        summary = self._generate_summary()
        
        # #region agent log
        try:
            with open(_log_path, "a") as _f:
                _f.write(_json.dumps({"id": f"log_{int(_time.time())}_after_summary_gen", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:run_all_tests", "message": "After _generate_summary", "data": {"summary_type": type(summary).__name__, "summary_keys": list(summary.keys()) if isinstance(summary, dict) else None}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "E"}) + "\n")
        except: pass
        # #endregion
        
        return summary
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate test summary statistics."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r['passed'])
        failed = total - passed
        
        # Group by language
        en_tests = [r for r in self.results if r['language'] == 'en']
        pt_tests = [r for r in self.results if r['language'] == 'pt']
        
        en_passed = sum(1 for r in en_tests if r['passed'])
        pt_passed = sum(1 for r in pt_tests if r['passed'])
        
        # Group by query type
        by_type = {}
        for result in self.results:
            qtype = result['query_type']
            if qtype not in by_type:
                by_type[qtype] = {'total': 0, 'passed': 0}
            by_type[qtype]['total'] += 1
            if result['passed']:
                by_type[qtype]['passed'] += 1
        
        # Calculate leakage statistics
        total_leakage_count = sum(
            r['leakage_result']['leakage_count'] 
            for r in self.results 
            if r['leakage_result']
        )
        
        summary = {
            'total_tests': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': (passed / total * 100) if total > 0 else 0,
            'total_leakage_count': total_leakage_count,
            'by_language': {
                'en': {'total': len(en_tests), 'passed': en_passed},
                'pt': {'total': len(pt_tests), 'passed': pt_passed}
            },
            'by_query_type': by_type,
            'timestamp': datetime.now().isoformat()
        }
        
        return summary
    
    def save_reports(self):
        """Save test results to JSON and text files."""
        # Save JSON report
        json_data = {
            'summary': self._generate_summary(),
            'results': self.results
        }
        
        with open(JSON_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\nJSON report saved to: {JSON_FILE_PATH}")
        
        # Save detailed text report
        with open(LOG_FILE_PATH, 'a', encoding='utf-8') as f:
            f.write("\n" + "="*70 + "\n")
            f.write("PROMPT LEAKAGE TEST SUMMARY\n")
            f.write("="*70 + "\n\n")
            
            summary = self._generate_summary()
            f.write(f"Total Tests: {summary['total_tests']}\n")
            f.write(f"Passed: {summary['passed']}\n")
            f.write(f"Failed: {summary['failed']}\n")
            f.write(f"Pass Rate: {summary['pass_rate']:.1f}%\n")
            f.write(f"Total Leakage Count: {summary['total_leakage_count']}\n\n")
            
            f.write("By Language:\n")
            for lang, stats in summary['by_language'].items():
                f.write(f"  {lang.upper()}: {stats['passed']}/{stats['total']} passed\n")
            
            f.write("\nBy Query Type:\n")
            for qtype, stats in summary['by_query_type'].items():
                f.write(f"  {qtype}: {stats['passed']}/{stats['total']} passed\n")
            
            f.write("\n" + "="*70 + "\n")
            f.write("DETAILED RESULTS\n")
            f.write("="*70 + "\n\n")
            
            for result in self.results:
                f.write(f"\nTest {result['test_num']}: {result['description']}\n")
                f.write(f"Query: {result['query']}\n")
                f.write(f"Status: {'PASSED' if result['passed'] else 'FAILED'}\n")
                
                if result['leakage_result'] and result['leakage_result']['has_leakage']:
                    f.write(f"Leakage Count: {result['leakage_result']['leakage_count']}\n")
                    f.write(f"Leaked Patterns: {', '.join(result['leakage_result']['leaked_patterns'])}\n")
                
                if result['error']:
                    f.write(f"Error: {result['error']}\n")
                
                f.write("-" * 70 + "\n")
        
        logger.info(f"Text report saved to: {LOG_FILE_PATH}")


def main():
    """Main execution function."""
    # #region agent log
    try:
        import json as _json
        import time as _time
        _log_path = "/Users/marcomollinetti/Documents/Projects/BelemConverse/.cursor/debug.log"
        with open(_log_path, "a") as _f:
            _f.write(_json.dumps({"id": f"log_{int(_time.time())}_main_entry", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:main", "message": "Main function entry", "data": {}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}) + "\n")
    except: pass
    # #endregion
    
    try:
        # #region agent log
        try:
            with open(_log_path, "a") as _f:
                _f.write(_json.dumps({"id": f"log_{int(_time.time())}_suite_init", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:main", "message": "Creating PromptLeakageTestSuite", "data": {}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "B"}) + "\n")
        except: pass
        # #endregion
        
        suite = PromptLeakageTestSuite()
        
        # #region agent log
        try:
            with open(_log_path, "a") as _f:
                _f.write(_json.dumps({"id": f"log_{int(_time.time())}_before_init", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:main", "message": "Before initialize() call", "data": {"suite_created": True}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}) + "\n")
        except: pass
        # #endregion
        
        # Initialize
        init_result = suite.initialize()
        
        # #region agent log
        try:
            with open(_log_path, "a") as _f:
                _f.write(_json.dumps({"id": f"log_{int(_time.time())}_after_init", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:main", "message": "After initialize() call", "data": {"init_result": init_result, "agent_exists": suite.agent is not None}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}) + "\n")
        except: pass
        # #endregion
        
        if not init_result:
            logger.error("Failed to initialize test suite. Exiting.")
            print("\n❌ Test suite initialization failed. Check logs above for details.\n")
            # #region agent log
            try:
                with open(_log_path, "a") as _f:
                    _f.write(_json.dumps({"id": f"log_{int(_time.time())}_init_failed", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:main", "message": "Initialization failed", "data": {}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}) + "\n")
            except: pass
            # #endregion
            return 1
        
        # #region agent log
        try:
            with open(_log_path, "a") as _f:
                _f.write(_json.dumps({"id": f"log_{int(_time.time())}_before_run", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:main", "message": "Before run_all_tests() call", "data": {"test_cases_count": len(suite.test_cases)}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "E"}) + "\n")
        except: pass
        # #endregion
        
        # Run all tests
        summary = suite.run_all_tests()
        
        # #region agent log
        try:
            with open(_log_path, "a") as _f:
                _f.write(_json.dumps({"id": f"log_{int(_time.time())}_after_run", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:main", "message": "After run_all_tests() call", "data": {"summary_type": type(summary).__name__, "summary_keys": list(summary.keys()) if isinstance(summary, dict) else None, "has_error": "error" in summary if isinstance(summary, dict) else False}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "E"}) + "\n")
        except: pass
        # #endregion
        
        if not summary or (isinstance(summary, dict) and 'error' in summary):
            logger.error(f"Test execution failed: {summary}")
            # #region agent log
            try:
                with open(_log_path, "a") as _f:
                    _f.write(_json.dumps({"id": f"log_{int(_time.time())}_run_failed", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:main", "message": "run_all_tests failed", "data": {"summary": str(summary)}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "F"}) + "\n")
            except: pass
            # #endregion
            return 1
        
        # #region agent log
        try:
            with open(_log_path, "a") as _f:
                _f.write(_json.dumps({"id": f"log_{int(_time.time())}_before_save", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:main", "message": "Before save_reports() call", "data": {"results_count": len(suite.results)}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "G"}) + "\n")
        except: pass
        # #endregion
        
        # Save reports
        suite.save_reports()
        
        # #region agent log
        try:
            with open(_log_path, "a") as _f:
                _f.write(_json.dumps({"id": f"log_{int(_time.time())}_before_summary", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:main", "message": "Before summary print", "data": {"summary_keys": list(summary.keys()) if isinstance(summary, dict) else None}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "H"}) + "\n")
        except: pass
        # #endregion
        
        # Print summary
        logger.info("\n" + "="*70)
        logger.info("TEST SUMMARY")
        logger.info("="*70)
        logger.info(f"Total Tests: {summary['total_tests']}")
        logger.info(f"Passed: {summary['passed']}")
        logger.info(f"Failed: {summary['failed']}")
        logger.info(f"Pass Rate: {summary['pass_rate']:.1f}%")
        logger.info(f"Total Leakage Count: {summary['total_leakage_count']}")
        
        logger.info("\nBy Language:")
        for lang, stats in summary['by_language'].items():
            logger.info(f"  {lang.upper()}: {stats['passed']}/{stats['total']} passed")
        
        logger.info("\nBy Query Type:")
        for qtype, stats in summary['by_query_type'].items():
            logger.info(f"  {qtype}: {stats['passed']}/{stats['total']} passed")
        
        logger.info("="*70)
        
        # #region agent log
        try:
            with open(_log_path, "a") as _f:
                _f.write(_json.dumps({"id": f"log_{int(_time.time())}_main_exit", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:main", "message": "Main function exit", "data": {"exit_code": 0 if summary['failed'] == 0 else 1}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}) + "\n")
        except: pass
        # #endregion
        
        # Return exit code (0 if all passed, 1 if any failed)
        return 0 if summary['failed'] == 0 else 1
        
    except Exception as e:
        # #region agent log
        try:
            import traceback as _tb
            with open(_log_path, "a") as _f:
                _f.write(_json.dumps({"id": f"log_{int(_time.time())}_main_exception", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:main", "message": "Exception in main", "data": {"exception_type": type(e).__name__, "exception_msg": str(e), "traceback": _tb.format_exc()}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "Z"}) + "\n")
        except: pass
        # #endregion
        logger.error(f"Fatal error in main: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == '__main__':
    # #region agent log
    try:
        import json as _json
        import time as _time
        _log_path = "/Users/marcomollinetti/Documents/Projects/BelemConverse/.cursor/debug.log"
        with open(_log_path, "a") as _f:
            _f.write(_json.dumps({"id": f"log_{int(_time.time())}_script_start", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:__main__", "message": "Script started", "data": {"sys_executable": sys.executable, "using_venv": _using_venv, "sys_path": str(sys.path[:3])}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}) + "\n")
    except Exception as _e:
        print(f"Debug log init failed: {_e}")
    # #endregion
    
    try:
        exit_code = main()
        # #region agent log
        try:
            with open(_log_path, "a") as _f:
                _f.write(_json.dumps({"id": f"log_{int(_time.time())}_script_exit", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:__main__", "message": "Script exiting", "data": {"exit_code": exit_code}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}) + "\n")
        except: pass
        # #endregion
        sys.exit(exit_code)
    except Exception as e:
        # #region agent log
        try:
            import traceback as _tb
            with open(_log_path, "a") as _f:
                _f.write(_json.dumps({"id": f"log_{int(_time.time())}_script_exception", "timestamp": int(_time.time() * 1000), "location": "test_prompt_leakage.py:__main__", "message": "Exception in __main__", "data": {"exception_type": type(e).__name__, "exception_msg": str(e), "traceback": _tb.format_exc()}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "Z"}) + "\n")
        except: pass
        # #endregion
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
