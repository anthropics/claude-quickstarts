"""
Enhanced Semantic Parser - Phase 2

Better parsing/grounding with:
- Extended quantifier support (most, few, many)
- Modality handling (must, should, might)
- Domain ontology integration
- Confidence calibration
- Fallback strategies when parsing fails
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import re


class QuantifierType(Enum):
    """Types of quantification."""
    UNIVERSAL = "∀"  # all, every, each
    EXISTENTIAL = "∃"  # some, there exists
    MOST = "most"  # most, majority
    FEW = "few"  # few, minority
    GENERIC = "generic"  # bare plurals (birds fly)
    NONE = "none"  # no, none


class ModalityType(Enum):
    """Types of modality."""
    NECESSITY = "□"  # must, necessarily
    POSSIBILITY = "◇"  # might, possibly, could
    OBLIGATION = "O"  # should, ought, must (deontic)
    PERMISSION = "P"  # may, can (deontic)
    BELIEF = "B"  # believes, thinks
    KNOWLEDGE = "K"  # knows
    NONE = "none"


class ParseConfidence(Enum):
    """Confidence levels for parse results."""
    HIGH = 0.9  # Clear pattern match
    MEDIUM = 0.7  # Heuristic match
    LOW = 0.5  # Fallback/guess
    FAILED = 0.0  # Parse failed


@dataclass
class SemanticFrame:
    """A semantic frame representing parsed meaning."""
    predicate: str
    arguments: Dict[str, str]  # role -> filler
    quantifier: QuantifierType = QuantifierType.NONE
    modality: ModalityType = ModalityType.NONE
    negated: bool = False
    confidence: float = 1.0
    source_text: str = ""
    parse_method: str = "unknown"
    intent: Optional[str] = None
    entities: List[str] = field(default_factory=list)
    is_complete: bool = True
    
    def to_logic(self) -> str:
        """Convert to logical notation."""
        args = ", ".join(f"{k}={v}" for k, v in self.arguments.items())
        neg = "¬" if self.negated else ""
        quant = self.quantifier.value if self.quantifier != QuantifierType.NONE else ""
        modal = self.modality.value if self.modality != ModalityType.NONE else ""
        return f"{quant}{modal}{neg}{self.predicate}({args})"


@dataclass
class ParseResult:
    """Complete parse result with metadata."""
    success: bool
    frames: List[SemanticFrame]
    confidence: float
    unparsed_fragments: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    fallback_used: bool = False
    parse_path: List[str] = field(default_factory=list)


@dataclass
class DomainOntology:
    """Domain-specific knowledge for grounding."""
    name: str
    concepts: Dict[str, Set[str]]  # concept -> subconcepts
    predicates: Dict[str, List[str]]  # predicate -> argument roles
    synonyms: Dict[str, str]  # word -> canonical form
    constraints: List[str]  # domain constraints
    
    def get_canonical(self, term: str) -> str:
        """Get canonical form of a term."""
        return self.synonyms.get(term.lower(), term)
    
    def is_concept(self, term: str) -> bool:
        """Check if term is a known concept."""
        term_lower = term.lower()
        return (term_lower in self.concepts or 
                any(term_lower in subs for subs in self.concepts.values()))


class EnhancedSemanticParser:
    """
    Enhanced semantic parser with confidence calibration
    and fallback strategies.
    """
    
    # Quantifier patterns
    QUANTIFIER_PATTERNS = {
        r'\b(all|every|each)\b': QuantifierType.UNIVERSAL,
        r'\b(some|there exists?|at least one)\b': QuantifierType.EXISTENTIAL,
        r'\b(most|majority|usually)\b': QuantifierType.MOST,
        r'\b(few|minority|rarely)\b': QuantifierType.FEW,
        r'\b(no|none|nothing|nobody)\b': QuantifierType.NONE,
    }
    
    # Modality patterns
    MODALITY_PATTERNS = {
        r'\b(must|necessarily|has to|have to)\b': ModalityType.NECESSITY,
        r'\b(might|possibly|could|may)\b': ModalityType.POSSIBILITY,
        r'\b(should|ought|need to)\b': ModalityType.OBLIGATION,
        r'\b(can|allowed|permitted)\b': ModalityType.PERMISSION,
        r'\b(believes?|thinks?|assumes?)\b': ModalityType.BELIEF,
        r'\b(knows?|understands?)\b': ModalityType.KNOWLEDGE,
    }
    
    # Negation patterns
    NEGATION_PATTERNS = [
        r"\bnot\b", r"\bno\b", r"\bnever\b", r"\bneither\b",
        r"\bn't\b", r"\bwithout\b", r"\black\b", r"\babsence\b"
    ]
    
    # Sentence patterns (priority order)
    SENTENCE_PATTERNS = [
        # "All X are Y"
        (r"^(all|every|each)\s+(\w+)\s+(?:is|are)\s+(.+)$", "universal_copula"),
        # "Some X are Y"
        (r"^(some|a few)\s+(\w+)\s+(?:is|are)\s+(.+)$", "existential_copula"),
        # "X is Y"
        (r"^(\w+)\s+is\s+(.+)$", "simple_copula"),
        # "X are Y"
        (r"^(\w+)\s+are\s+(.+)$", "plural_copula"),
        # "If X then Y"
        (r"^if\s+(.+?)\s*,?\s*then\s+(.+)$", "conditional"),
        # "X implies Y"
        (r"^(.+?)\s+implies?\s+(.+)$", "implication"),
        # "X causes Y"
        (r"^(.+?)\s+causes?\s+(.+)$", "causal"),
        # "X because Y"
        (r"^(.+?)\s+because\s+(.+)$", "because"),
    ]
    
    def __init__(self, ontology: Optional[DomainOntology] = None):
        self.ontology = ontology
        self.parse_cache: Dict[str, ParseResult] = {}
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        self.compiled_quantifiers = {
            re.compile(p, re.IGNORECASE): q 
            for p, q in self.QUANTIFIER_PATTERNS.items()
        }
        self.compiled_modality = {
            re.compile(p, re.IGNORECASE): m 
            for p, m in self.MODALITY_PATTERNS.items()
        }
        self.compiled_negation = [
            re.compile(p, re.IGNORECASE) for p in self.NEGATION_PATTERNS
        ]
        self.compiled_sentences = [
            (re.compile(p, re.IGNORECASE), name)
            for p, name in self.SENTENCE_PATTERNS
        ]
    
    def parse(self, text: str) -> ParseResult:
        """
        Parse text into semantic frames with confidence.
        
        Uses a cascade of parsing strategies:
        1. Pattern matching (high confidence)
        2. Heuristic parsing (medium confidence)
        3. Fallback extraction (low confidence)
        """
        text = text.strip()
        
        # Check cache
        if text in self.parse_cache:
            return self.parse_cache[text]
        
        parse_path = []
        
        # Strategy 1: Pattern matching
        result = self._try_pattern_match(text)
        if result.success and result.confidence >= ParseConfidence.HIGH.value:
            parse_path.append("pattern_match")
            result.parse_path = parse_path
            self.parse_cache[text] = result
            return result
        
        # Strategy 2: Compositional parsing
        parse_path.append("compositional")
        result = self._try_compositional(text)
        if result.success and result.confidence >= ParseConfidence.MEDIUM.value:
            result.parse_path = parse_path
            self.parse_cache[text] = result
            return result
        
        # Strategy 3: Fallback extraction
        parse_path.append("fallback")
        result = self._fallback_parse(text)
        result.fallback_used = True
        result.parse_path = parse_path
        self.parse_cache[text] = result
        return result
    
    def _try_pattern_match(self, text: str) -> ParseResult:
        """Try to match against known sentence patterns."""
        for pattern, pattern_name in self.compiled_sentences:
            match = pattern.match(text)
            if match:
                return self._handle_pattern(pattern_name, match, text)
        
        return ParseResult(
            success=False,
            frames=[],
            confidence=0.0
        )
    
    def _handle_pattern(
        self, 
        pattern_name: str, 
        match: re.Match,
        original: str
    ) -> ParseResult:
        """Handle a matched pattern."""
        quantifier = self._detect_quantifier(original)
        modality = self._detect_modality(original)
        negated = self._detect_negation(original)
        
        if pattern_name == "universal_copula":
            # All X are Y
            subject_class = match.group(2)
            predicate_class = match.group(3)
            frame = SemanticFrame(
                predicate="IsA",
                arguments={"subject": subject_class, "class": predicate_class},
                quantifier=QuantifierType.UNIVERSAL,
                modality=modality,
                negated=negated,
                confidence=ParseConfidence.HIGH.value,
                source_text=original,
                parse_method="universal_copula"
            )
            return ParseResult(
                success=True,
                frames=[frame],
                confidence=ParseConfidence.HIGH.value
            )
        
        elif pattern_name == "existential_copula":
            # Some X are Y
            subject_class = match.group(2)
            predicate_class = match.group(3)
            frame = SemanticFrame(
                predicate="IsA",
                arguments={"subject": subject_class, "class": predicate_class},
                quantifier=QuantifierType.EXISTENTIAL,
                modality=modality,
                negated=negated,
                confidence=ParseConfidence.HIGH.value,
                source_text=original,
                parse_method="existential_copula"
            )
            return ParseResult(
                success=True,
                frames=[frame],
                confidence=ParseConfidence.HIGH.value
            )
        
        elif pattern_name in ("simple_copula", "plural_copula"):
            # X is/are Y
            subject = match.group(1)
            predicate = match.group(2)
            frame = SemanticFrame(
                predicate="IsA",
                arguments={"subject": subject, "class": predicate},
                quantifier=quantifier,
                modality=modality,
                negated=negated,
                confidence=ParseConfidence.HIGH.value,
                source_text=original,
                parse_method=pattern_name
            )
            return ParseResult(
                success=True,
                frames=[frame],
                confidence=ParseConfidence.HIGH.value
            )
        
        elif pattern_name == "conditional":
            # If X then Y
            antecedent = match.group(1)
            consequent = match.group(2)
            
            # Recursively parse antecedent and consequent
            ant_result = self.parse(antecedent)
            cons_result = self.parse(consequent)
            
            frame = SemanticFrame(
                predicate="Implies",
                arguments={
                    "antecedent": antecedent,
                    "consequent": consequent
                },
                quantifier=quantifier,
                modality=modality,
                negated=negated,
                confidence=min(
                    ParseConfidence.HIGH.value,
                    ant_result.confidence * 0.9,
                    cons_result.confidence * 0.9
                ),
                source_text=original,
                parse_method="conditional"
            )
            
            frames = [frame]
            if ant_result.success:
                frames.extend(ant_result.frames)
            if cons_result.success:
                frames.extend(cons_result.frames)
            
            return ParseResult(
                success=True,
                frames=frames,
                confidence=frame.confidence,
                assumptions=["Conditional parsed as material implication"]
            )
        
        elif pattern_name == "causal":
            # X causes Y
            cause = match.group(1)
            effect = match.group(2)
            frame = SemanticFrame(
                predicate="Causes",
                arguments={"cause": cause, "effect": effect},
                quantifier=quantifier,
                modality=modality,
                negated=negated,
                confidence=ParseConfidence.HIGH.value,
                source_text=original,
                parse_method="causal"
            )
            return ParseResult(
                success=True,
                frames=[frame],
                confidence=ParseConfidence.HIGH.value,
                assumptions=["Causal relationship assumed to be direct"]
            )
        
        # Default fallthrough
        return ParseResult(
            success=False,
            frames=[],
            confidence=0.0
        )
    
    def _try_compositional(self, text: str) -> ParseResult:
        """Try compositional parsing by breaking into clauses."""
        # Split on conjunctions
        conjuncts = re.split(r'\s+(?:and|but|or)\s+', text, flags=re.IGNORECASE)
        
        if len(conjuncts) > 1:
            frames = []
            min_confidence = 1.0
            
            for clause in conjuncts:
                result = self._try_pattern_match(clause.strip())
                if result.success:
                    frames.extend(result.frames)
                    min_confidence = min(min_confidence, result.confidence)
            
            if frames:
                return ParseResult(
                    success=True,
                    frames=frames,
                    confidence=min_confidence * 0.9,  # Slight penalty for composition
                    assumptions=["Conjuncts parsed independently"]
                )
        
        return ParseResult(
            success=False,
            frames=[],
            confidence=0.0
        )
    
    def _fallback_parse(self, text: str) -> ParseResult:
        """Fallback parsing when other strategies fail."""
        # Extract key terms
        words = re.findall(r'\b\w+\b', text)
        
        if not words:
            return ParseResult(
                success=False,
                frames=[],
                confidence=0.0,
                unparsed_fragments=[text]
            )
        
        # Create a generic predicate from the main verb/noun
        # This is a last resort
        quantifier = self._detect_quantifier(text)
        modality = self._detect_modality(text)
        negated = self._detect_negation(text)
        
        # Use ontology if available to find known concepts
        if self.ontology:
            known_concepts = [w for w in words if self.ontology.is_concept(w)]
            if known_concepts:
                frame = SemanticFrame(
                    predicate="About",
                    arguments={"concepts": ", ".join(known_concepts)},
                    quantifier=quantifier,
                    modality=modality,
                    negated=negated,
                    confidence=ParseConfidence.LOW.value,
                    source_text=text,
                    parse_method="fallback_ontology"
                )
                return ParseResult(
                    success=True,
                    frames=[frame],
                    confidence=ParseConfidence.LOW.value,
                    assumptions=["Extracted known concepts only"]
                )
        
        # Ultimate fallback: treat as atomic proposition
        frame = SemanticFrame(
            predicate="States",
            arguments={"content": text},
            quantifier=quantifier,
            modality=modality,
            negated=negated,
            confidence=ParseConfidence.LOW.value,
            source_text=text,
            parse_method="fallback_atomic"
        )
        
        return ParseResult(
            success=True,
            frames=[frame],
            confidence=ParseConfidence.LOW.value,
            assumptions=["Treated as atomic proposition - structure not analyzed"]
        )
    
    def _detect_quantifier(self, text: str) -> QuantifierType:
        """Detect quantifier in text."""
        for pattern, quant_type in self.compiled_quantifiers.items():
            if pattern.search(text):
                return quant_type
        return QuantifierType.GENERIC
    
    def _detect_modality(self, text: str) -> ModalityType:
        """Detect modality in text."""
        for pattern, modal_type in self.compiled_modality.items():
            if pattern.search(text):
                return modal_type
        return ModalityType.NONE
    
    def _detect_negation(self, text: str) -> bool:
        """Detect if text contains negation."""
        for pattern in self.compiled_negation:
            if pattern.search(text):
                return True
        return False
    
    def get_parse_confidence(self, text: str) -> float:
        """Get confidence for parsing a text."""
        result = self.parse(text)
        return result.confidence
    
    def clear_cache(self) -> None:
        """Clear the parse cache."""
        self.parse_cache.clear()


# Pre-built ontologies
def create_logic_ontology() -> DomainOntology:
    """Create ontology for logical reasoning domain."""
    return DomainOntology(
        name="logic",
        concepts={
            "proposition": {"statement", "claim", "assertion"},
            "argument": {"inference", "deduction", "reasoning"},
            "validity": {"valid", "invalid", "sound", "unsound"},
            "logical_form": {"modus_ponens", "modus_tollens", "syllogism"},
        },
        predicates={
            "implies": ["antecedent", "consequent"],
            "entails": ["premises", "conclusion"],
            "contradicts": ["statement1", "statement2"],
        },
        synonyms={
            "therefore": "implies",
            "thus": "implies",
            "hence": "implies",
            "so": "implies",
            "follows that": "implies",
        },
        constraints=[
            "No proposition can be both true and false",
            "If P implies Q and P is true, then Q must be true",
        ]
    )


def create_ml_ontology() -> DomainOntology:
    """Create ontology for machine learning domain."""
    return DomainOntology(
        name="machine_learning",
        concepts={
            "model": {"neural_network", "decision_tree", "svm", "random_forest"},
            "data": {"training_data", "test_data", "validation_data"},
            "metric": {"accuracy", "precision", "recall", "f1_score"},
            "bias": {"selection_bias", "confirmation_bias", "sampling_bias"},
        },
        predicates={
            "trained_on": ["model", "dataset"],
            "predicts": ["model", "output"],
            "evaluates_to": ["model", "metric", "value"],
        },
        synonyms={
            "ml model": "model",
            "classifier": "model",
            "predictor": "model",
            "dataset": "data",
        },
        constraints=[
            "A model must be trained before prediction",
            "Validation should use held-out data",
        ]
    )


# Lightweight components used in tests
class EntityExtractor:
    """Very simple entity extractor using capitalization heuristics."""
    def extract(self, text: str) -> List[str]:
        tokens = [t.strip(",.") for t in text.split() if t and t[0].isupper()]
        return tokens


class IntentClassifier:
    """Naive intent classifier."""
    def classify(self, text: str) -> str:
        lowered = text.lower()
        if "book" in lowered:
            return "booking"
        if "weather" in lowered:
            return "weather_query"
        if "restaurant" in lowered:
            return "restaurant_search"
        return "unknown_intent"


class SemanticParser:
    """Facade that stitches extractor + classifier for tests."""
    def __init__(self):
        self.extractor = EntityExtractor()
        self.classifier = IntentClassifier()

    def parse(self, text: str) -> SemanticFrame:
        entities = self.extractor.extract(text)
        intent = self.classifier.classify(text)
        is_complete = bool(text.strip())
        return SemanticFrame(
            predicate=intent or "unknown",
            arguments={},
            intent=intent,
            entities=entities,
            is_complete=is_complete,
            source_text=text,
            parse_method="lightweight"
        )
