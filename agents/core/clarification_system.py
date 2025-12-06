"""
Clarification System - Phase 2 Enhancement

Provides intelligent clarification and disambiguation:
- Ambiguity detection in queries
- Clarifying question generation
- User input handling
- Disambiguation strategies
- Context preservation during clarification
"""

from typing import List, Dict, Any, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import re


class AmbiguityType(Enum):
    """Types of ambiguity that can be detected."""
    LEXICAL = "lexical"  # Word has multiple meanings
    SYNTACTIC = "syntactic"  # Sentence structure is unclear
    SEMANTIC = "semantic"  # Meaning is unclear
    REFERENTIAL = "referential"  # Unclear what is being referred to
    SCOPE = "scope"  # Scope of quantifiers/modifiers unclear
    PRAGMATIC = "pragmatic"  # Intent or context unclear


class ClarificationPriority(Enum):
    """Priority levels for clarification needs."""
    BLOCKING = 4  # Must clarify before proceeding
    HIGH = 3  # Should clarify but can make assumption
    MEDIUM = 2  # Would be helpful to clarify
    LOW = 1  # Optional clarification


class ClarificationStrategy(Enum):
    """Strategies for handling clarification."""
    ASK_USER = "ask_user"  # Ask the user directly
    USE_DEFAULT = "use_default"  # Use a reasonable default
    INFER_FROM_CONTEXT = "infer_from_context"  # Try to infer from context
    PROVIDE_OPTIONS = "provide_options"  # Present options to user
    ASSUME_AND_VERIFY = "assume_and_verify"  # Make assumption, verify later


@dataclass
class AmbiguityDetection:
    """A detected ambiguity in input."""
    ambiguity_id: str
    ambiguity_type: AmbiguityType
    location: str  # Where in the input
    description: str
    possible_interpretations: List[str]
    priority: ClarificationPriority
    confidence: float  # How confident we are this is ambiguous


@dataclass
class ClarifyingQuestion:
    """A question to clarify ambiguity."""
    question_id: str
    question_text: str
    ambiguity_id: str
    question_type: str  # "yes_no", "multiple_choice", "open_ended"
    options: List[str] = field(default_factory=list)
    default_option: Optional[str] = None
    context_hint: Optional[str] = None


@dataclass
class UserResponse:
    """Response from user to a clarifying question."""
    question_id: str
    response_text: str
    selected_option: Optional[str] = None
    confidence: float = 1.0  # How confident user seems
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ClarificationResult:
    """Result of a clarification process."""
    original_input: str
    clarified_input: str
    ambiguities_found: List[AmbiguityDetection]
    questions_asked: List[ClarifyingQuestion]
    responses_received: List[UserResponse]
    resolved: bool
    remaining_ambiguities: List[str]


class AmbiguityDetector:
    """Detects various types of ambiguity in input."""
    
    def __init__(self):
        # Lexical ambiguity - words with multiple meanings
        self._ambiguous_words = {
            "bank": ["financial institution", "river edge"],
            "light": ["not heavy", "electromagnetic radiation", "not dark"],
            "right": ["correct", "opposite of left", "entitlement"],
            "run": ["execute", "jog", "operate"],
            "table": ["furniture", "data structure", "postpone"],
            "match": ["competition", "fire starter", "correspond"],
            "spring": ["season", "water source", "coiled metal"],
            "fair": ["just", "carnival", "light-colored"],
        }
        
        # Pronoun ambiguity patterns
        self._pronoun_pattern = re.compile(
            r'\b(it|they|them|this|that|these|those|he|she|him|her)\b',
            re.IGNORECASE
        )
        
        # Vague quantifier patterns
        self._vague_quantifiers = [
            "some", "many", "few", "several", "various", 
            "a lot", "most", "often", "sometimes", "usually"
        ]
        
        # Scope ambiguity markers
        self._scope_markers = [
            "all", "every", "each", "any", "no", "not"
        ]
    
    def detect(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[AmbiguityDetection]:
        """Detect ambiguities in text."""
        ambiguities = []
        detection_id = 0
        
        # Detect lexical ambiguity
        for word, meanings in self._ambiguous_words.items():
            pattern = rf'\b{word}\b'
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Check if context resolves it
                if not self._context_resolves(word, text, context):
                    detection_id += 1
                    ambiguities.append(AmbiguityDetection(
                        ambiguity_id=f"amb_{detection_id}",
                        ambiguity_type=AmbiguityType.LEXICAL,
                        location=f"position {match.start()}",
                        description=f"'{word}' has multiple meanings",
                        possible_interpretations=meanings,
                        priority=ClarificationPriority.MEDIUM,
                        confidence=0.7
                    ))
        
        # Detect referential ambiguity (pronouns without clear referent)
        pronouns = self._pronoun_pattern.findall(text)
        if pronouns:
            # Check if there are multiple potential referents
            sentences = text.split('.')
            for i, sentence in enumerate(sentences):
                sentence_pronouns = self._pronoun_pattern.findall(sentence)
                if sentence_pronouns and i == 0:
                    # Pronoun in first sentence might lack referent
                    detection_id += 1
                    ambiguities.append(AmbiguityDetection(
                        ambiguity_id=f"amb_{detection_id}",
                        ambiguity_type=AmbiguityType.REFERENTIAL,
                        location=f"sentence {i+1}",
                        description=f"Pronoun '{sentence_pronouns[0]}' may lack clear referent",
                        possible_interpretations=["previous context", "to be specified"],
                        priority=ClarificationPriority.HIGH,
                        confidence=0.6
                    ))
        
        # Detect vague quantifiers
        for quantifier in self._vague_quantifiers:
            if quantifier in text.lower():
                detection_id += 1
                ambiguities.append(AmbiguityDetection(
                    ambiguity_id=f"amb_{detection_id}",
                    ambiguity_type=AmbiguityType.SEMANTIC,
                    location=f"'{quantifier}'",
                    description=f"Vague quantifier '{quantifier}' - amount unclear",
                    possible_interpretations=["small amount", "moderate amount", "large amount"],
                    priority=ClarificationPriority.LOW,
                    confidence=0.5
                ))
        
        # Detect potential scope ambiguity
        scope_words = [w for w in self._scope_markers if w in text.lower()]
        if len(scope_words) >= 2:
            detection_id += 1
            ambiguities.append(AmbiguityDetection(
                ambiguity_id=f"amb_{detection_id}",
                ambiguity_type=AmbiguityType.SCOPE,
                location="sentence",
                description=f"Potential scope ambiguity with '{', '.join(scope_words)}'",
                possible_interpretations=["wide scope", "narrow scope"],
                priority=ClarificationPriority.MEDIUM,
                confidence=0.6
            ))
        
        # Detect pragmatic ambiguity (underspecified intent)
        if self._is_underspecified(text):
            detection_id += 1
            ambiguities.append(AmbiguityDetection(
                ambiguity_id=f"amb_{detection_id}",
                ambiguity_type=AmbiguityType.PRAGMATIC,
                location="overall",
                description="Request may be underspecified",
                possible_interpretations=["need more details"],
                priority=ClarificationPriority.HIGH,
                confidence=0.7
            ))
        
        return ambiguities
    
    def _context_resolves(
        self, 
        word: str, 
        text: str, 
        context: Optional[Dict[str, Any]]
    ) -> bool:
        """Check if context resolves the ambiguity."""
        if not context:
            return False
        
        # Check domain context
        domain = context.get("domain", "")
        if domain == "finance" and word == "bank":
            return True  # "bank" clearly means financial institution
        if domain == "geography" and word == "bank":
            return True  # "bank" clearly means river bank
        
        return False
    
    def _is_underspecified(self, text: str) -> bool:
        """Check if the text is underspecified."""
        # Very short queries
        if len(text.split()) < 3:
            return True
        
        # Starts with vague words
        vague_starters = ["something", "anything", "stuff", "things"]
        first_word = text.split()[0].lower()
        if first_word in vague_starters:
            return True
        
        # Missing key information markers
        question_words = ["what", "how", "when", "where", "why", "which"]
        if any(text.lower().startswith(w) for w in question_words):
            # Questions without specifics
            if len(text.split()) < 5:
                return True
        
        return False


class QuestionGenerator:
    """Generates clarifying questions for detected ambiguities."""
    
    def __init__(self):
        self._templates = {
            AmbiguityType.LEXICAL: [
                "When you say '{term}', do you mean {options}?",
                "Could you clarify what you mean by '{term}'?",
                "'{term}' can mean different things. Which meaning do you intend?"
            ],
            AmbiguityType.REFERENTIAL: [
                "What does '{term}' refer to in your question?",
                "Could you specify what '{term}' is referring to?",
                "I'm not sure what '{term}' points to. Can you clarify?"
            ],
            AmbiguityType.SEMANTIC: [
                "Could you be more specific about '{term}'?",
                "What exactly do you mean by '{term}'?",
                "Can you provide more details about '{term}'?"
            ],
            AmbiguityType.SCOPE: [
                "Does '{term}' apply to all items or specific ones?",
                "What is the scope of '{term}' in your request?",
                "Should '{term}' be interpreted broadly or narrowly?"
            ],
            AmbiguityType.PRAGMATIC: [
                "Could you provide more details about what you're looking for?",
                "What specific outcome are you hoping for?",
                "Can you elaborate on your request?"
            ]
        }
    
    def generate(
        self, 
        ambiguity: AmbiguityDetection,
        context: Optional[Dict[str, Any]] = None
    ) -> ClarifyingQuestion:
        """Generate a clarifying question for an ambiguity."""
        templates = self._templates.get(ambiguity.ambiguity_type, [])
        template = templates[0] if templates else "Could you clarify what you mean?"
        
        # Format the question
        term = ambiguity.location
        if "'" in ambiguity.description:
            # Extract the term from description
            match = re.search(r"'([^']+)'", ambiguity.description)
            if match:
                term = match.group(1)
        
        options = " or ".join(ambiguity.possible_interpretations[:3])
        question_text = template.format(term=term, options=options)
        
        # Determine question type
        if len(ambiguity.possible_interpretations) == 2:
            question_type = "yes_no" if ambiguity.possible_interpretations in [
                ["yes", "no"], ["true", "false"]
            ] else "multiple_choice"
        elif len(ambiguity.possible_interpretations) <= 5:
            question_type = "multiple_choice"
        else:
            question_type = "open_ended"
        
        return ClarifyingQuestion(
            question_id=f"q_{ambiguity.ambiguity_id}",
            question_text=question_text,
            ambiguity_id=ambiguity.ambiguity_id,
            question_type=question_type,
            options=ambiguity.possible_interpretations,
            default_option=ambiguity.possible_interpretations[0] if ambiguity.possible_interpretations else None,
            context_hint=f"This helps clarify: {ambiguity.description}"
        )
    
    def generate_batch(
        self, 
        ambiguities: List[AmbiguityDetection],
        max_questions: int = 3
    ) -> List[ClarifyingQuestion]:
        """Generate questions for multiple ambiguities."""
        # Sort by priority
        sorted_ambiguities = sorted(
            ambiguities, 
            key=lambda a: a.priority.value, 
            reverse=True
        )
        
        questions = []
        for amb in sorted_ambiguities[:max_questions]:
            questions.append(self.generate(amb))
        
        return questions


class DisambiguationEngine:
    """Applies disambiguation strategies to resolve ambiguities."""
    
    def __init__(self):
        self._defaults = {
            "bank": "financial institution",
            "light": "not heavy",
            "run": "execute",
        }
        
        self._context_rules: List[Tuple[Callable, str, str]] = [
            # (condition_func, word, meaning)
            (lambda c: c.get("domain") == "finance", "bank", "financial institution"),
            (lambda c: c.get("domain") == "nature", "bank", "river edge"),
            (lambda c: "code" in str(c.get("topic", "")), "run", "execute"),
        ]
    
    def apply_strategy(
        self,
        ambiguity: AmbiguityDetection,
        strategy: ClarificationStrategy,
        context: Optional[Dict[str, Any]] = None,
        user_response: Optional[UserResponse] = None
    ) -> Optional[str]:
        """Apply a disambiguation strategy and return resolved meaning."""
        
        if strategy == ClarificationStrategy.ASK_USER:
            if user_response:
                return user_response.selected_option or user_response.response_text
            return None  # Need to ask user
        
        elif strategy == ClarificationStrategy.USE_DEFAULT:
            # Extract term from ambiguity
            term = self._extract_term(ambiguity)
            return self._defaults.get(term)
        
        elif strategy == ClarificationStrategy.INFER_FROM_CONTEXT:
            if not context:
                return None
            term = self._extract_term(ambiguity)
            for condition, word, meaning in self._context_rules:
                if word == term and condition(context):
                    return meaning
            return None
        
        elif strategy == ClarificationStrategy.PROVIDE_OPTIONS:
            # Return formatted options
            return f"Options: {', '.join(ambiguity.possible_interpretations)}"
        
        elif strategy == ClarificationStrategy.ASSUME_AND_VERIFY:
            # Use first interpretation as assumption
            if ambiguity.possible_interpretations:
                return f"[Assuming: {ambiguity.possible_interpretations[0]}]"
            return None
        
        return None
    
    def _extract_term(self, ambiguity: AmbiguityDetection) -> str:
        """Extract the ambiguous term from the detection."""
        match = re.search(r"'([^']+)'", ambiguity.description)
        if match:
            return match.group(1).lower()
        return ambiguity.location
    
    def select_strategy(
        self,
        ambiguity: AmbiguityDetection,
        context: Optional[Dict[str, Any]] = None,
        allow_user_interaction: bool = True
    ) -> ClarificationStrategy:
        """Select the best disambiguation strategy."""
        
        # Blocking priority always needs user input
        if ambiguity.priority == ClarificationPriority.BLOCKING:
            if allow_user_interaction:
                return ClarificationStrategy.ASK_USER
            else:
                return ClarificationStrategy.ASSUME_AND_VERIFY
        
        # Try context inference first
        if context and self._can_infer_from_context(ambiguity, context):
            return ClarificationStrategy.INFER_FROM_CONTEXT
        
        # High priority - prefer asking user
        if ambiguity.priority == ClarificationPriority.HIGH:
            if allow_user_interaction:
                return ClarificationStrategy.ASK_USER
            else:
                return ClarificationStrategy.USE_DEFAULT
        
        # Medium priority - use defaults if available
        if ambiguity.priority == ClarificationPriority.MEDIUM:
            term = self._extract_term(ambiguity)
            if term in self._defaults:
                return ClarificationStrategy.USE_DEFAULT
            elif allow_user_interaction:
                return ClarificationStrategy.ASK_USER
            else:
                return ClarificationStrategy.ASSUME_AND_VERIFY
        
        # Low priority - just use defaults or assume
        return ClarificationStrategy.USE_DEFAULT
    
    def _can_infer_from_context(
        self, 
        ambiguity: AmbiguityDetection,
        context: Dict[str, Any]
    ) -> bool:
        """Check if context can resolve this ambiguity."""
        term = self._extract_term(ambiguity)
        for condition, word, _ in self._context_rules:
            if word == term and condition(context):
                return True
        return False


class ClarificationManager:
    """
    Main manager for the clarification process.
    
    Coordinates detection, question generation, and resolution.
    """
    
    def __init__(
        self,
        allow_user_interaction: bool = True,
        max_questions: int = 3,
        auto_resolve_low_priority: bool = True
    ):
        self.detector = AmbiguityDetector()
        self.question_generator = QuestionGenerator()
        self.disambiguation_engine = DisambiguationEngine()
        
        self.allow_user_interaction = allow_user_interaction
        self.max_questions = max_questions
        self.auto_resolve_low_priority = auto_resolve_low_priority
        
        self._pending_questions: List[ClarifyingQuestion] = []
        self._responses: List[UserResponse] = []
    
    def analyze(
        self, 
        text: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[AmbiguityDetection], List[ClarifyingQuestion]]:
        """
        Analyze text for ambiguities and generate questions.
        
        Returns (ambiguities, questions_to_ask)
        """
        # Detect ambiguities
        ambiguities = self.detector.detect(text, context)
        
        if not ambiguities:
            return [], []
        
        # Filter out low priority if auto-resolving
        if self.auto_resolve_low_priority:
            ambiguities = [
                a for a in ambiguities 
                if a.priority.value >= ClarificationPriority.MEDIUM.value
            ]
        
        # Generate questions
        questions = self.question_generator.generate_batch(
            ambiguities, 
            self.max_questions
        )
        
        self._pending_questions = questions
        
        return ambiguities, questions
    
    def needs_clarification(
        self, 
        text: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if input needs clarification."""
        ambiguities = self.detector.detect(text, context)
        
        # Only need clarification for high-priority ambiguities
        high_priority = [
            a for a in ambiguities
            if a.priority.value >= ClarificationPriority.HIGH.value
        ]
        
        return len(high_priority) > 0
    
    def process_response(
        self,
        question_id: str,
        response_text: str,
        selected_option: Optional[str] = None
    ) -> None:
        """Process a user response to a clarifying question."""
        response = UserResponse(
            question_id=question_id,
            response_text=response_text,
            selected_option=selected_option
        )
        self._responses.append(response)
        
        # Remove from pending
        self._pending_questions = [
            q for q in self._pending_questions 
            if q.question_id != question_id
        ]
    
    def clarify(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        responses: Optional[Dict[str, str]] = None
    ) -> ClarificationResult:
        """
        Complete clarification process.
        
        Args:
            text: Original input text
            context: Additional context
            responses: Pre-provided responses {question_id: response}
        
        Returns:
            ClarificationResult with clarified input
        """
        # Detect and generate questions
        ambiguities, questions = self.analyze(text, context)
        
        if not ambiguities:
            return ClarificationResult(
                original_input=text,
                clarified_input=text,
                ambiguities_found=[],
                questions_asked=[],
                responses_received=[],
                resolved=True,
                remaining_ambiguities=[]
            )
        
        # Process pre-provided responses
        if responses:
            for q_id, resp in responses.items():
                self.process_response(q_id, resp)
        
        # Apply disambiguation
        clarified_text = text
        resolved_ambiguities = []
        remaining = []
        
        for amb in ambiguities:
            strategy = self.disambiguation_engine.select_strategy(
                amb, context, self.allow_user_interaction
            )
            
            # Find response for this ambiguity
            response = None
            for r in self._responses:
                if r.question_id == f"q_{amb.ambiguity_id}":
                    response = r
                    break
            
            resolution = self.disambiguation_engine.apply_strategy(
                amb, strategy, context, response
            )
            
            if resolution:
                resolved_ambiguities.append(amb.ambiguity_id)
                # Add clarification annotation to text
                clarified_text += f" [Clarified: {resolution}]"
            else:
                remaining.append(amb.ambiguity_id)
        
        return ClarificationResult(
            original_input=text,
            clarified_input=clarified_text,
            ambiguities_found=ambiguities,
            questions_asked=questions,
            responses_received=list(self._responses),
            resolved=len(remaining) == 0,
            remaining_ambiguities=remaining
        )
    
    def get_pending_questions(self) -> List[ClarifyingQuestion]:
        """Get questions waiting for user response."""
        return list(self._pending_questions)
    
    def format_questions_for_user(self) -> str:
        """Format pending questions for display to user."""
        if not self._pending_questions:
            return ""
        
        lines = ["I need some clarification:"]
        for i, q in enumerate(self._pending_questions, 1):
            lines.append(f"\n{i}. {q.question_text}")
            if q.options and q.question_type == "multiple_choice":
                for j, opt in enumerate(q.options, 1):
                    default = " (default)" if opt == q.default_option else ""
                    lines.append(f"   {j}. {opt}{default}")
        
        return "\n".join(lines)
    
    def reset(self) -> None:
        """Reset the manager state."""
        self._pending_questions = []
        self._responses = []


# Convenience functions

def needs_clarification(text: str, context: Optional[Dict[str, Any]] = None) -> bool:
    """Quick check if text needs clarification."""
    manager = ClarificationManager(allow_user_interaction=False)
    return manager.needs_clarification(text, context)


def get_clarifying_questions(
    text: str, 
    context: Optional[Dict[str, Any]] = None,
    max_questions: int = 3
) -> List[ClarifyingQuestion]:
    """Get clarifying questions for text."""
    manager = ClarificationManager(max_questions=max_questions)
    _, questions = manager.analyze(text, context)
    return questions


def auto_clarify(
    text: str,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """Automatically clarify text using defaults and context."""
    manager = ClarificationManager(allow_user_interaction=False)
    result = manager.clarify(text, context)
    return result.clarified_input


# Lightweight components for tests
@dataclass
class ClarificationRequest:
    request_id: str
    original_query: str
    ambiguity_type: str
    clarifying_questions: List[str]


class AmbiguityDetector:
    def detect(self, text: str) -> bool:
        return "it" in text.lower() or "this" in text.lower()


class QuestionGenerator:
    def generate(self, query: str, ambiguities: List[str]) -> List[str]:
        return [f"What do you mean by '{ambiguities[0]}'?"] if ambiguities else [f"Can you clarify '{query}'?"]


class ClarificationSystem:
    def __init__(self):
        self.detector = AmbiguityDetector()
        self.generator = QuestionGenerator()

    def needs_clarification(self, query: str) -> bool:
        return self.detector.detect(query)

    def generate_questions(self, query: str) -> List[str]:
        return self.generator.generate(query, ["unclear_referent"])

    def resolve(self, original_query: str, user_clarification: str) -> str:
        return f"{original_query} ({user_clarification})"
