"""
Knowledge Base for Neuro-Symbolic Agent System

Implements a hybrid knowledge representation that bridges:
- Backend: ML-powered inference (LLM agents)
- Frontend: Formal logic system (symbolic reasoning)
"""

import json
import hashlib
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class LogicType(Enum):
    """Types of logical systems supported."""
    PROPOSITIONAL = "propositional"  # P → Q
    FIRST_ORDER = "first_order"  # ∀x(Human(x) → Mortal(x))
    MODAL = "modal"  # □P (necessarily P)
    TEMPORAL = "temporal"  # ◊P (eventually P)


class InferenceRule(Enum):
    """Formal inference rules."""
    MODUS_PONENS = "modus_ponens"  # P, P→Q ⊢ Q
    MODUS_TOLLENS = "modus_tollens"  # ¬Q, P→Q ⊢ ¬P
    HYPOTHETICAL_SYLLOGISM = "hypothetical_syllogism"  # P→Q, Q→R ⊢ P→R
    DISJUNCTIVE_SYLLOGISM = "disjunctive_syllogism"  # P∨Q, ¬P ⊢ Q
    CONJUNCTION = "conjunction"  # P, Q ⊢ P∧Q
    SIMPLIFICATION = "simplification"  # P∧Q ⊢ P
    ADDITION = "addition"  # P ⊢ P∨Q
    RESOLUTION = "resolution"  # P∨Q, ¬P∨R ⊢ Q∨R
    UNIVERSAL_INSTANTIATION = "universal_instantiation"  # ∀x P(x) ⊢ P(a)
    EXISTENTIAL_GENERALIZATION = "existential_generalization"  # P(a) ⊢ ∃x P(x)


@dataclass
class Fact:
    """Represents a validated fact in the knowledge base."""
    statement: str
    logical_form: Optional[str] = None  # Formalized representation
    confidence: float = 1.0
    source: str = "user"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    dependencies: List[str] = field(default_factory=list)  # Fact IDs this depends on

    def __hash__(self):
        return hash(self.statement)

    @property
    def fact_id(self) -> str:
        """Unique identifier for this fact."""
        return hashlib.md5(self.statement.encode()).hexdigest()[:12]


@dataclass
class ValidationResult:
    """Result of validating a claim against the knowledge base."""
    valid: bool
    confidence: float
    sources: List[str]
    reasoning_chain: List[str] = field(default_factory=list)
    inference_rules_used: List[InferenceRule] = field(default_factory=list)


@dataclass
class LogicalStatement:
    """A statement in formal logic notation."""
    natural_language: str
    formal_notation: str
    logic_type: LogicType
    variables: Set[str] = field(default_factory=set)
    predicates: Set[str] = field(default_factory=set)


class KnowledgeBase:
    """
    Hybrid knowledge base combining symbolic and neural reasoning.

    Backend: Stores facts, rules, and ontologies
    Frontend: Provides logical inference and validation
    """

    def __init__(self, logic_system: LogicType = LogicType.FIRST_ORDER):
        self.logic_system = logic_system
        self.facts: Dict[str, Fact] = {}
        self.rules: List[Dict[str, Any]] = []
        self.ontology: Dict[str, Set[str]] = {}  # Concept relationships
        self.inference_cache: Dict[str, ValidationResult] = {}

    def add_fact(
        self,
        statement: str,
        source: str = "agent",
        confidence: float = 1.0,
        logical_form: Optional[str] = None
    ) -> str:
        """
        Add a validated fact to the knowledge base.

        Args:
            statement: Natural language statement
            source: Where this fact came from
            confidence: Confidence score (0-1)
            logical_form: Optional formal logic representation

        Returns:
            Fact ID
        """
        fact = Fact(
            statement=statement,
            logical_form=logical_form or self._parse_to_logic(statement),
            confidence=confidence,
            source=source
        )

        self.facts[fact.fact_id] = fact
        return fact.fact_id

    def query(self, question: str) -> List[Fact]:
        """
        Query the knowledge base using natural language.

        Args:
            question: Natural language query

        Returns:
            List of relevant facts
        """
        # Convert question to logical form
        logical_query = self._parse_to_logic(question)

        # Execute forward chaining inference
        results = self._forward_chain(logical_query)

        return results

    def detect_contradictions(self) -> List[str]:
        """
        Detect explicit contradictions among stored facts.

        This is a lightweight check that looks for direct negations
        (e.g., "X is Y" vs "X is not Y") and conflicting implications.
        """
        contradictions = []

        facts_list = list(self.facts.values())
        for i, fact_a in enumerate(facts_list):
            for fact_b in facts_list[i + 1:]:
                if self._are_contradictory(fact_a.statement, fact_b.statement):
                    contradictions.append(
                        f"Contradiction between '{fact_a.statement}' and '{fact_b.statement}'"
                    )
        return contradictions

    def validate(self, claim: str, use_ml: bool = True) -> ValidationResult:
        """
        Validate a claim against the knowledge base.

        Strategy:
        1. Check if directly stated in KB (exact match)
        2. Try logical inference from existing facts
        3. Use ML agent to research via tools (if use_ml=True)

        Args:
            claim: Statement to validate
            use_ml: Whether to use ML agent for research

        Returns:
            ValidationResult with confidence and sources
        """
        # Check cache
        cache_key = hashlib.md5(claim.encode()).hexdigest()
        if cache_key in self.inference_cache:
            return self.inference_cache[cache_key]

        # Step 1: Direct match
        for fact_id, fact in self.facts.items():
            if self._statements_match(claim, fact.statement):
                result = ValidationResult(
                    valid=True,
                    confidence=fact.confidence,
                    sources=[fact.source],
                    reasoning_chain=[f"Direct match: {fact.statement}"]
                )
                self.inference_cache[cache_key] = result
                return result

        # Step 2: Logical inference
        inferred = self._infer(claim)
        if inferred:
            self.inference_cache[cache_key] = inferred
            return inferred

        # Step 3: ML-based research (would call agent tools)
        if use_ml:
            researched = self._research_claim(claim)
            self.inference_cache[cache_key] = researched
            return researched

        # Could not validate
        return ValidationResult(
            valid=False,
            confidence=0.0,
            sources=[],
            reasoning_chain=["No evidence found"]
        )

    def validate_with_contradiction_check(self, claim: str, use_ml: bool = True) -> ValidationResult:
        """
        Validate a claim and surface contradictions in the KB.
        """
        base = self.validate(claim, use_ml=use_ml)
        contradictions = self.detect_contradictions()
        if contradictions:
            base.reasoning_chain.extend(contradictions)
            base.confidence *= 0.7
        return base

    def add_inference_rule(
        self,
        name: str,
        premises: List[str],
        conclusion: str,
        rule_type: InferenceRule
    ):
        """Add a custom inference rule to the knowledge base."""
        self.rules.append({
            "name": name,
            "premises": premises,
            "conclusion": conclusion,
            "type": rule_type
        })

    def add_to_ontology(self, concept: str, related_concepts: List[str]):
        """Add concept relationships to the ontology."""
        if concept not in self.ontology:
            self.ontology[concept] = set()
        self.ontology[concept].update(related_concepts)

    def get_related_concepts(self, concept: str) -> Set[str]:
        """Get all concepts related to a given concept."""
        return self.ontology.get(concept, set())

    def _parse_to_logic(self, statement: str) -> str:
        """
        Convert natural language to formal logic notation.

        This is a simplified implementation. Production would use:
        - NLP parsing (dependency trees, semantic roles)
        - Logic synthesis (variable binding, predicate extraction)
        - Normalization (standard form conversion)
        """
        # Simplified logic parsing
        statement_lower = statement.lower()

        # Pattern: "All X are Y" → ∀x(X(x) → Y(x))
        if "all" in statement_lower and "are" in statement_lower:
            parts = statement_lower.split("are")
            if len(parts) == 2:
                subject = parts[0].replace("all", "").strip()
                predicate = parts[1].strip()
                return f"∀x({subject.capitalize()}(x) → {predicate.capitalize()}(x))"

        # Pattern: "X is Y" → Y(X)
        if " is " in statement_lower:
            parts = statement_lower.split(" is ")
            if len(parts) == 2:
                subject = parts[0].strip()
                predicate = parts[1].strip()
                return f"{predicate.capitalize()}({subject.capitalize()})"

        # Pattern: "If X then Y" → X → Y
        if "if" in statement_lower and "then" in statement_lower:
            parts = statement_lower.split("then")
            antecedent = parts[0].replace("if", "").strip()
            consequent = parts[1].strip()
            return f"({antecedent}) → ({consequent})"

        # Default: wrap in proposition
        return f"P({statement})"

    def _statements_match(self, s1: str, s2: str) -> bool:
        """Check if two statements are semantically equivalent."""
        # Simplified: exact match after normalization
        return s1.lower().strip() == s2.lower().strip()

    def _are_contradictory(self, s1: str, s2: str) -> bool:
        """
        Naive contradiction check: detect simple negations and opposite claims.

        Examples:
        - "X is Y" vs "X is not Y"
        - "All X are Y" vs "Some X are not Y"
        """
        a = s1.lower().strip()
        b = s2.lower().strip()

        if a == b:
            return False

        neg_markers = [" not ", " no ", "never ", "cannot ", "can't "]

        def normalize(sentence: str) -> str:
            return sentence.replace("all ", "").replace("some ", "").strip()

        normalized_a = normalize(a)
        normalized_b = normalize(b)

        # Direct negation pattern
        for marker in neg_markers:
            if marker in normalized_a and normalized_a.replace(marker, " ") == normalized_b:
                return True
            if marker in normalized_b and normalized_b.replace(marker, " ") == normalized_a:
                return True

        # Simple contradictory forms
        if " are " in normalized_a and " are " in normalized_b:
            left = normalized_a.split(" are ")
            right = normalized_b.split(" are ")
            if len(left) == 2 and len(right) == 2 and left[0] == right[0] and left[1] != right[1]:
                return True

        return False

    def _forward_chain(self, query: str) -> List[Fact]:
        """
        Forward chaining inference from facts.

        Start with known facts, apply rules to derive new facts
        until query is satisfied or no more rules apply.
        """
        results = []

        # Start with facts matching the query pattern
        for fact_id, fact in self.facts.items():
            if query.lower() in fact.statement.lower():
                results.append(fact)

        # Apply inference rules
        for rule in self.rules:
            # Check if all premises are satisfied
            premises_satisfied = all(
                any(p.lower() in f.statement.lower() for f in self.facts.values())
                for p in rule["premises"]
            )

            if premises_satisfied:
                # Add conclusion if it matches query
                if query.lower() in rule["conclusion"].lower():
                    derived_fact = Fact(
                        statement=rule["conclusion"],
                        source=f"inferred_via_{rule['name']}",
                        confidence=0.9
                    )
                    results.append(derived_fact)

        return results

    def _infer(self, claim: str) -> Optional[ValidationResult]:
        """
        Try to infer the claim using logical inference rules.

        Implements common inference patterns:
        - Modus Ponens: P, P→Q ⊢ Q
        - Universal Instantiation: ∀x P(x) ⊢ P(a)
        - Transitive property: a→b, b→c ⊢ a→c
        """
        claim_lower = claim.lower()
        reasoning_chain = []

        # Try Modus Ponens
        for fact in self.facts.values():
            # Look for implication: "If X then Y" or "All X are Y"
            if "→" in fact.logical_form or "if" in fact.statement.lower():
                # Check if we have the antecedent
                parts = fact.statement.lower().split("then" if "then" in fact.statement.lower() else "are")
                if len(parts) == 2:
                    antecedent = parts[0].replace("if", "").replace("all", "").strip()
                    consequent = parts[1].strip()

                    # Check if claim matches consequent
                    if consequent in claim_lower:
                        # Look for antecedent in facts
                        for f2 in self.facts.values():
                            if antecedent in f2.statement.lower():
                                reasoning_chain.append(f"Premise 1: {f2.statement}")
                                reasoning_chain.append(f"Premise 2: {fact.statement}")
                                reasoning_chain.append(f"Applied: Modus Ponens")
                                reasoning_chain.append(f"Conclusion: {claim}")

                                return ValidationResult(
                                    valid=True,
                                    confidence=min(fact.confidence, f2.confidence) * 0.95,
                                    sources=[fact.source, f2.source],
                                    reasoning_chain=reasoning_chain,
                                    inference_rules_used=[InferenceRule.MODUS_PONENS]
                                )

        # Try Universal Instantiation
        for fact in self.facts.values():
            if "∀" in fact.logical_form or "all" in fact.statement.lower():
                # Pattern: "All X are Y" + "Alice is X" → "Alice is Y"
                parts = fact.statement.lower().split("are")
                if len(parts) == 2:
                    category = parts[0].replace("all", "").strip()
                    property = parts[1].strip()

                    # Check if claim is about a specific instance
                    claim_words = claim_lower.split()
                    if category in claim_lower and property in claim_lower:
                        reasoning_chain.append(f"Universal rule: {fact.statement}")
                        reasoning_chain.append(f"Applied: Universal Instantiation")
                        reasoning_chain.append(f"Conclusion: {claim}")

                        return ValidationResult(
                            valid=True,
                            confidence=fact.confidence * 0.9,
                            sources=[fact.source],
                            reasoning_chain=reasoning_chain,
                            inference_rules_used=[InferenceRule.UNIVERSAL_INSTANTIATION]
                        )

        return None

    def _research_claim(self, claim: str) -> ValidationResult:
        """
        Use ML agent to research a claim.

        This would integrate with the Agent class to:
        1. Search external sources
        2. Evaluate evidence
        3. Synthesize findings

        For now, returns a placeholder.
        """
        # Placeholder for ML-based research
        return ValidationResult(
            valid=False,
            confidence=0.0,
            sources=["ml_research_needed"],
            reasoning_chain=["ML research not implemented in this demo"]
        )

    def export_to_prolog(self) -> str:
        """Export knowledge base to Prolog format."""
        lines = []
        lines.append("% Knowledge Base Export")
        lines.append("% Generated: " + datetime.now().isoformat())
        lines.append("")

        for fact in self.facts.values():
            # Convert to Prolog fact
            prolog_fact = self._to_prolog_fact(fact)
            lines.append(prolog_fact)

        return "\n".join(lines)

    def _to_prolog_fact(self, fact: Fact) -> str:
        """Convert a fact to Prolog syntax."""
        # Simplified conversion
        statement = fact.statement.lower().replace(" ", "_")
        return f"fact('{statement}', {fact.confidence})."

    def get_statistics(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        return {
            "total_facts": len(self.facts),
            "total_rules": len(self.rules),
            "ontology_concepts": len(self.ontology),
            "logic_system": self.logic_system.value,
            "cache_size": len(self.inference_cache),
            "avg_confidence": sum(f.confidence for f in self.facts.values()) / len(self.facts) if self.facts else 0
        }
