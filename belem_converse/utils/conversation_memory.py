"""
Conversation Memory System for BelemConverse.

Stores up to 10 previous interactions locally on the device.
Uses JSON file for persistence.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Default memory file location
DEFAULT_MEMORY_DIR = Path(__file__).parent.parent.parent / "data" / "memory"
DEFAULT_MEMORY_FILE = DEFAULT_MEMORY_DIR / "conversation_history.json"
MAX_MEMORY_SIZE = 10  # Maximum number of interactions to store


@dataclass
class ConversationTurn:
    """Represents a single conversation turn (user question + assistant response)."""
    timestamp: str
    user_message: str
    assistant_response: str
    user_coordinates: Optional[tuple] = None
    intent: Optional[str] = None
    category: Optional[str] = None
    places_mentioned: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationTurn':
        return cls(**data)
    
    def to_context_string(self, language: str = 'en') -> str:
        """Convert to a context string for the LLM."""
        if language == 'pt':
            return f"Usuário: {self.user_message}\nAssistente: {self.assistant_response}"
        return f"User: {self.user_message}\nAssistant: {self.assistant_response}"


class ConversationMemory:
    """
    Manages conversation history with local persistence.
    
    Features:
    - Stores up to MAX_MEMORY_SIZE interactions
    - Persists to JSON file on device
    - Provides context for follow-up questions
    - Extracts mentioned places for reference
    """
    
    def __init__(self, memory_file: Optional[Path] = None):
        """
        Initialize the conversation memory.
        
        Args:
            memory_file: Path to the memory file. Uses default if not specified.
        """
        self.memory_file = memory_file or DEFAULT_MEMORY_FILE
        self.history: List[ConversationTurn] = []
        
        # Ensure directory exists
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing history
        self._load_history()
    
    def _load_history(self) -> None:
        """Load conversation history from file."""
        try:
            if self.memory_file.exists():
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.history = [
                        ConversationTurn.from_dict(turn) 
                        for turn in data.get('history', [])
                    ]
                logger.debug(f"Loaded {len(self.history)} conversation turns from memory")
        except Exception as e:
            logger.warning(f"Could not load conversation history: {e}")
            self.history = []
    
    def _save_history(self) -> None:
        """Save conversation history to file."""
        try:
            data = {
                'history': [turn.to_dict() for turn in self.history],
                'last_updated': datetime.now().isoformat()
            }
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved {len(self.history)} conversation turns to memory")
        except Exception as e:
            logger.warning(f"Could not save conversation history: {e}")
    
    def add_turn(
        self,
        user_message: str,
        assistant_response: str,
        user_coordinates: Optional[tuple] = None,
        intent: Optional[str] = None,
        category: Optional[str] = None,
        places_mentioned: Optional[List[str]] = None
    ) -> None:
        """
        Add a new conversation turn to history.
        
        Automatically removes oldest entry if exceeding MAX_MEMORY_SIZE.
        """
        turn = ConversationTurn(
            timestamp=datetime.now().isoformat(),
            user_message=user_message,
            assistant_response=assistant_response,
            user_coordinates=user_coordinates,
            intent=intent,
            category=category,
            places_mentioned=places_mentioned
        )
        
        self.history.append(turn)
        
        # Trim to max size (keep most recent)
        if len(self.history) > MAX_MEMORY_SIZE:
            self.history = self.history[-MAX_MEMORY_SIZE:]
        
        # Persist to file
        self._save_history()
    
    def get_recent_context(
        self, 
        num_turns: int = 3, 
        language: str = 'en'
    ) -> str:
        """
        Get recent conversation history as context string.
        
        Args:
            num_turns: Number of recent turns to include
            language: Language for formatting ('en' or 'pt')
            
        Returns:
            Formatted conversation history string
        """
        if not self.history:
            return ""
        
        recent = self.history[-num_turns:]
        
        if language == 'pt':
            header = "=== HISTÓRICO DE CONVERSA RECENTE ==="
        else:
            header = "=== RECENT CONVERSATION HISTORY ==="
        
        lines = [header]
        for turn in recent:
            lines.append(turn.to_context_string(language))
            lines.append("")
        
        return "\n".join(lines)
    
    def get_last_mentioned_places(self) -> List[str]:
        """Get places mentioned in the last conversation turn."""
        if self.history and self.history[-1].places_mentioned:
            return self.history[-1].places_mentioned
        return []
    
    def get_last_category(self) -> Optional[str]:
        """Get the category from the last conversation turn."""
        if self.history and self.history[-1].category:
            return self.history[-1].category
        return None
    
    def get_last_intent(self) -> Optional[str]:
        """Get the intent from the last conversation turn."""
        if self.history and self.history[-1].intent:
            return self.history[-1].intent
        return None
    
    def is_follow_up_question(self, question: str) -> bool:
        """
        Check if the question appears to be a follow-up to previous conversation.
        
        Looks for pronouns, short questions, or references to previous context.
        """
        if not self.history:
            return False
        
        question_lower = question.lower().strip()
        
        # Follow-up indicators in English
        follow_up_indicators_en = [
            'it', 'this', 'that', 'there', 'the same', 'more', 'another',
            'what about', 'how about', 'and', 'also', 'too',
            'near there', 'close to it', 'similar', 'like that',
            'the one', 'which one', 'tell me more', 'more info',
            'address', 'phone', 'hours', 'open', 'contact'
        ]
        
        # Follow-up indicators in Portuguese
        follow_up_indicators_pt = [
            'ele', 'ela', 'isso', 'este', 'esta', 'esse', 'essa',
            'lá', 'ali', 'o mesmo', 'a mesma', 'mais', 'outro', 'outra',
            'e o', 'e a', 'também', 'perto dali', 'similar', 'parecido',
            'qual', 'me fale mais', 'mais informações',
            'endereço', 'telefone', 'horário', 'aberto', 'contato'
        ]
        
        all_indicators = follow_up_indicators_en + follow_up_indicators_pt
        
        # Check for short questions (likely follow-ups)
        if len(question_lower.split()) <= 5:
            return True
        
        # Check for follow-up indicators
        for indicator in all_indicators:
            if indicator in question_lower:
                return True
        
        return False
    
    def clear_history(self) -> None:
        """Clear all conversation history."""
        self.history = []
        self._save_history()
        logger.info("Conversation history cleared")
    
    def __len__(self) -> int:
        return len(self.history)
    
    def __bool__(self) -> bool:
        return len(self.history) > 0


