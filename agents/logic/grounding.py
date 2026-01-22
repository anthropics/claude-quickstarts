"""
Symbol Grounding and Semantic Translation

Addresses the symbol grounding problem: how do we map natural language
to logical forms in a way that preserves meaning and handles edge cases?

Key challenges addressed:
1. Ambiguity: "biased" means different things in different contexts
2. Quantification: "most", "some", "all" have different logical forms
3. Modality: beliefs, obligations, causation require different logics
4. Context dependency: meaning varies with domain
"""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum


class QuantifierType(Enum):
    """Types of quantification in natural language."""
    UNIVERSAL = "all"  # ∀x
    EXISTENTIAL = "some"  # ∃x
    GENERIC = "plural"  # Birds fly (generic, not universal)
    MOST = "most"  # Most(x, P(x), Q(x)) - requires higher-order logic
    FEW = "few"  # Few(x, P(x), Q(x))


class ModalityType(Enum):
    """Types of modality that require specialized logic."""
    ALETHIC = "necessary/possible"  # □P, ◊P
    EPISTEMIC = "knows/believes"  # K_a(P), B_a(P)
    DEONTIC = "obligatory/permitted"  # O(P), P(P)
    TEMPORAL = "always/eventually"  # □P, ◊P (temporal)
    CAUSAL = "because/causes"  # P →_c Q


@dataclass
class SemanticContext:
    """
    Represents the context in which a statement is interpreted.

    Addresses the grounding problem by making context explicit.
    """
    domain: str  # e.g., "machine_learning", "ethics", "physics"
    ontology: Dict[str, Set[str]]  # Concept hierarchies
    predicates: Dict[str, str]  # Predicate definitions
    grounding_rules: Dict[str, str]  # How terms map to real-world referents

    def ground_term(self, term: str) -> Optional[str]:
        """
        Ground a term to its meaning in this context.

        Example: "biased" in ML context → "statistical correlation with protected attributes"
                 "biased" in cognitive context → "systematic deviation from rationality"
        """
        # Check for context-specific definition
        if term in self.predicates:
            return self.predicates[term]

        # Check grounding rules
        if term in self.grounding_rules:
            return self.grounding_rules[term]

        return None


@dataclass
class ParseResult:
    """
    Result of parsing natural language to logic.

    Separates successful parses from unparseable fragments.
    """
    success: bool
    logical_form: Optional[str]
    quantifier: Optional[QuantifierType]
    modality: Optional[ModalityType]
    predicates: Set[str]
    variables: Set[str]
    unparseable_fragments: List[str]  # Parts that can't be formalized
    assumptions: List[str]  # Assumptions made during parsing
    confidence: float  # How confident are we in this parse?


class SemanticParser:
    """
    Robust semantic parser that handles the grounding problem.

    Unlike naive pattern matching, this:
    1. Tracks what can and cannot be formalized
    2. Makes parsing assumptions explicit
    3. Handles multiple types of quantification
    4. Recognizes when specialized logics are needed
    """

    def __init__(self, context: SemanticContext):
        self.context = context
        self.quantifier_patterns = {
            "all": QuantifierType.UNIVERSAL,
            "every": QuantifierType.UNIVERSAL,
            "each": QuantifierType.UNIVERSAL,
            "some": QuantifierType.EXISTENTIAL,
            "there exists": QuantifierType.EXISTENTIAL,
            "most": QuantifierType.MOST,
            "many": QuantifierType.MOST,
            "few": QuantifierType.FEW,
            # No quantifier = generic
        }

        self.modality_patterns = {
            "must": ModalityType.ALETHIC,
            "necessarily": ModalityType.ALETHIC,
            "might": ModalityType.ALETHIC,
            "possibly": ModalityType.ALETHIC,
            "believes": ModalityType.EPISTEMIC,
            "knows": ModalityType.EPISTEMIC,
            "should": ModalityType.DEONTIC,
            "ought": ModalityType.DEONTIC,
            "always": ModalityType.TEMPORAL,
            "eventually": ModalityType.TEMPORAL,
            "because": ModalityType.CAUSAL,
            "causes": ModalityType.CAUSAL,
        }

    def parse(self, statement: str) -> ParseResult:
        """
        Parse natural language statement to logical form.

        Returns ParseResult with explicit tracking of:
        - What was successfully parsed
        - What assumptions were made
        - What couldn't be formalized
        """
        statement_lower = statement.lower().strip()
        assumptions = []
        unparseable = []

        # Detect quantifier
        quantifier = self._detect_quantifier(statement_lower)

        # Detect modality
        modality = self._detect_modality(statement_lower)

        # If modality detected, check if we can handle it
        if modality and modality not in [ModalityType.ALETHIC]:
            unparseable.append(f"Modality '{modality.value}' requires specialized logic")
            return ParseResult(
                success=False,
                logical_form=None,
                quantifier=quantifier,
                modality=modality,
                predicates=set(),
                variables=set(),
                unparseable_fragments=unparseable,
                assumptions=assumptions,
                confidence=0.0
            )

        # Parse based on quantifier type
        if quantifier == QuantifierType.UNIVERSAL:
            return self._parse_universal(statement_lower, assumptions)

        elif quantifier == QuantifierType.EXISTENTIAL:
            return self._parse_existential(statement_lower, assumptions)

        elif quantifier == QuantifierType.GENERIC:
            # Generic statements are tricky - not truly universal
            assumptions.append(
                "Generic statement treated as universal (may have exceptions)"
            )
            return self._parse_generic(statement_lower, assumptions)

        elif quantifier in [QuantifierType.MOST, QuantifierType.FEW]:
            # Can't represent "most" in first-order logic
            unparseable.append(
                f"Quantifier '{quantifier.value}' requires higher-order or probabilistic logic"
            )
            return ParseResult(
                success=False,
                logical_form=None,
                quantifier=quantifier,
                modality=modality,
                predicates=set(),
                variables=set(),
                unparseable_fragments=unparseable,
                assumptions=assumptions,
                confidence=0.0
            )

        # No quantifier detected
        return self._parse_atomic(statement_lower, assumptions)

    def _detect_quantifier(self, statement: str) -> QuantifierType:
        """Detect quantifier in statement."""
        for pattern, quant_type in self.quantifier_patterns.items():
            if pattern in statement:
                return quant_type
        return QuantifierType.GENERIC  # Default

    def _detect_modality(self, statement: str) -> Optional[ModalityType]:
        """Detect modal operators in statement."""
        for pattern, mod_type in self.modality_patterns.items():
            if pattern in statement:
                return mod_type
        return None

    def _parse_universal(
        self,
        statement: str,
        assumptions: List[str]
    ) -> ParseResult:
        """
        Parse universal quantification: "All X are Y"

        Maps to: ∀x(X(x) → Y(x))
        """
        # Pattern: "all X are Y"
        if "all" in statement and "are" in statement:
            parts = statement.split("are")
            if len(parts) == 2:
                x_class = parts[0].replace("all", "").strip()
                y_class = parts[1].strip()

                # Ground predicates in context
                x_grounded = self.context.ground_term(x_class)
                y_grounded = self.context.ground_term(y_class)

                if not x_grounded:
                    assumptions.append(f"Predicate '{x_class}' not defined in context, using literal")
                if not y_grounded:
                    assumptions.append(f"Predicate '{y_class}' not defined in context, using literal")

                predicates = {x_class, y_class}
                variables = {"x"}

                logical_form = f"∀x({x_class.capitalize()}(x) → {y_class.capitalize()}(x))"

                return ParseResult(
                    success=True,
                    logical_form=logical_form,
                    quantifier=QuantifierType.UNIVERSAL,
                    modality=None,
                    predicates=predicates,
                    variables=variables,
                    unparseable_fragments=[],
                    assumptions=assumptions,
                    confidence=0.9 if (x_grounded and y_grounded) else 0.7
                )

        return ParseResult(
            success=False,
            logical_form=None,
            quantifier=QuantifierType.UNIVERSAL,
            modality=None,
            predicates=set(),
            variables=set(),
            unparseable_fragments=["Could not parse universal statement"],
            assumptions=assumptions,
            confidence=0.0
        )

    def _parse_existential(
        self,
        statement: str,
        assumptions: List[str]
    ) -> ParseResult:
        """
        Parse existential quantification: "Some X are Y"

        Maps to: ∃x(X(x) ∧ Y(x))
        """
        if "some" in statement and "are" in statement:
            parts = statement.split("are")
            if len(parts) == 2:
                x_class = parts[0].replace("some", "").strip()
                y_class = parts[1].strip()

                predicates = {x_class, y_class}
                variables = {"x"}

                logical_form = f"∃x({x_class.capitalize()}(x) ∧ {y_class.capitalize()}(x))"

                return ParseResult(
                    success=True,
                    logical_form=logical_form,
                    quantifier=QuantifierType.EXISTENTIAL,
                    modality=None,
                    predicates=predicates,
                    variables=variables,
                    unparseable_fragments=[],
                    assumptions=assumptions,
                    confidence=0.85
                )

        return ParseResult(
            success=False,
            logical_form=None,
            quantifier=QuantifierType.EXISTENTIAL,
            modality=None,
            predicates=set(),
            variables=set(),
            unparseable_fragments=["Could not parse existential statement"],
            assumptions=assumptions,
            confidence=0.0
        )

    def _parse_generic(
        self,
        statement: str,
        assumptions: List[str]
    ) -> ParseResult:
        """
        Parse generic statements: "Birds fly"

        These are NOT universal (not all birds fly).
        Represented as: Gen x(Bird(x) → Fly(x))
        But this requires generic operators not in FOL.

        We approximate as universal with caveat.
        """
        assumptions.append(
            "Generic statement may have exceptions (penguins don't fly, etc.)"
        )

        # Try to extract subject and predicate
        words = statement.split()
        if len(words) >= 2:
            subject = words[0]
            predicate = " ".join(words[1:])

            logical_form = f"Gen x({subject.capitalize()}(x) → {predicate.capitalize()}(x))"

            return ParseResult(
                success=True,
                logical_form=logical_form,
                quantifier=QuantifierType.GENERIC,
                modality=None,
                predicates={subject, predicate},
                variables={"x"},
                unparseable_fragments=[],
                assumptions=assumptions,
                confidence=0.6  # Lower confidence due to approximation
            )

        return ParseResult(
            success=False,
            logical_form=None,
            quantifier=QuantifierType.GENERIC,
            modality=None,
            predicates=set(),
            variables=set(),
            unparseable_fragments=["Could not parse generic statement"],
            assumptions=assumptions,
            confidence=0.0
        )

    def _parse_atomic(
        self,
        statement: str,
        assumptions: List[str]
    ) -> ParseResult:
        """
        Parse atomic statement: "Socrates is mortal"

        Maps to: Mortal(Socrates)
        """
        if " is " in statement:
            parts = statement.split(" is ")
            if len(parts) == 2:
                subject = parts[0].strip().capitalize()
                predicate = parts[1].strip().capitalize()

                predicates = {predicate}
                logical_form = f"{predicate}({subject})"

                return ParseResult(
                    success=True,
                    logical_form=logical_form,
                    quantifier=None,
                    modality=None,
                    predicates=predicates,
                    variables=set(),
                    unparseable_fragments=[],
                    assumptions=assumptions,
                    confidence=0.9
                )

        return ParseResult(
            success=False,
            logical_form=None,
            quantifier=None,
            modality=None,
            predicates=set(),
            variables=set(),
            unparseable_fragments=[statement],
            assumptions=assumptions,
            confidence=0.0
        )


def create_ml_context() -> SemanticContext:
    """Create semantic context for machine learning domain."""
    return SemanticContext(
        domain="machine_learning",
        ontology={
            "ml_model": {"neural_network", "decision_tree", "svm"},
            "data": {"training_data", "test_data", "biased_data"},
            "output": {"prediction", "classification", "biased_output"}
        },
        predicates={
            "biased": "exhibits statistical correlation with protected attributes beyond task relevance",
            "trained_on": "learned parameters from dataset D",
            "produces": "generates output O given input I"
        },
        grounding_rules={
            "model": "computational system with learnable parameters",
            "data": "collection of input-output pairs or feature vectors",
            "bias": "systematic deviation from population statistics"
        }
    )
