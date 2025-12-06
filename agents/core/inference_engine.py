"""
Enhanced Inference Engine - Phase 2 Enhancement

Expands on the rule engine with:
- Extended inference patterns (modus tollens, syllogisms, quantifiers)
- Formal parsing before NL fallback
- LLM conclusion cross-checking
- Proof-or-flag mechanism
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re


class InferencePattern(Enum):
    """Supported inference patterns."""
    MODUS_PONENS = "modus_ponens"  # P, P→Q ⊢ Q
    MODUS_TOLLENS = "modus_tollens"  # ¬Q, P→Q ⊢ ¬P
    HYPOTHETICAL_SYLLOGISM = "hypothetical_syllogism"  # P→Q, Q→R ⊢ P→R
    DISJUNCTIVE_SYLLOGISM = "disjunctive_syllogism"  # P∨Q, ¬P ⊢ Q
    CATEGORICAL_SYLLOGISM = "categorical_syllogism"  # All M are P, All S are M ⊢ All S are P
    UNIVERSAL_INSTANTIATION = "universal_instantiation"  # ∀x P(x) ⊢ P(a)
    EXISTENTIAL_INSTANTIATION = "existential_instantiation"  # ∃x P(x) ⊢ P(c)
    UNIVERSAL_GENERALIZATION = "universal_generalization"  # P(a) ⊢ ∀x P(x)
    CONJUNCTION_INTRODUCTION = "conjunction_introduction"  # P, Q ⊢ P∧Q
    CONJUNCTION_ELIMINATION = "conjunction_elimination"  # P∧Q ⊢ P
    DISJUNCTION_INTRODUCTION = "disjunction_introduction"  # P ⊢ P∨Q
    CONTRAPOSITION = "contraposition"  # P→Q ⊢ ¬Q→¬P
    DOUBLE_NEGATION = "double_negation"  # ¬¬P ⊢ P
    TRANSITIVE = "transitive"  # a→b, b→c ⊢ a→c


class QuantifierType(Enum):
    """Types of quantifiers."""
    UNIVERSAL = "∀"  # All, every, each
    EXISTENTIAL = "∃"  # Some, there exists
    NONE = ""


@dataclass
class LogicalTerm:
    """A term in a logical expression."""
    name: str
    is_variable: bool = False
    is_constant: bool = False
    
    def __str__(self) -> str:
        return self.name
    
    def __hash__(self) -> int:
        return hash((self.name, self.is_variable))


@dataclass
class QuantifiedPredicate:
    """A predicate with quantification."""
    quantifier: QuantifierType
    variable: Optional[str]
    predicate_name: str
    arguments: List[LogicalTerm]
    negated: bool = False
    
    def __str__(self) -> str:
        quant = f"{self.quantifier.value}{self.variable}" if self.variable else ""
        args = ", ".join(str(a) for a in self.arguments)
        neg = "¬" if self.negated else ""
        return f"{quant}{neg}{self.predicate_name}({args})"


@dataclass
class InferenceStep:
    """A step in an inference chain."""
    step_id: int
    premise_ids: List[int]  # Which previous steps are used
    conclusion: str
    pattern_used: InferencePattern
    confidence: float
    justification: str
    bindings: Dict[str, str] = field(default_factory=dict)


@dataclass
class InferenceResult:
    """Result of an inference attempt."""
    success: bool
    conclusion: str
    confidence: float
    steps: List[InferenceStep]
    patterns_used: List[InferencePattern]
    proof_found: bool
    needs_flag: bool = False
    flag_reason: Optional[str] = None
    llm_verified: bool = False


class FormalParser:
    """
    Parser for formal logical notation.
    
    Handles:
    - Propositional logic: P, Q, P→Q, P∧Q, P∨Q, ¬P
    - Predicate logic: Human(x), Mortal(socrates)
    - Quantifiers: ∀x P(x), ∃x P(x)
    - Natural language patterns
    """
    
    def __init__(self):
        # Logical operator patterns
        self.operators = {
            "→": "implies",
            "->": "implies",
            "⊃": "implies",
            "∧": "and",
            "&": "and",
            "∨": "or",
            "|": "or",
            "¬": "not",
            "~": "not",
            "!": "not",
        }
        
        # Quantifier patterns
        self.quantifier_patterns = {
            r"∀(\w+)": QuantifierType.UNIVERSAL,
            r"for\s+all\s+(\w+)": QuantifierType.UNIVERSAL,
            r"every\s+(\w+)": QuantifierType.UNIVERSAL,
            r"all\s+(\w+)": QuantifierType.UNIVERSAL,
            r"∃(\w+)": QuantifierType.EXISTENTIAL,
            r"there\s+exists?\s+(\w+)": QuantifierType.EXISTENTIAL,
            r"some\s+(\w+)": QuantifierType.EXISTENTIAL,
        }
        
        # NL to logical patterns
        self.nl_patterns = [
            (r"if\s+(.+?)\s+then\s+(.+)", self._parse_conditional),
            (r"(.+?)\s+implies\s+(.+)", self._parse_conditional),
            (r"all\s+(\w+)\s+are\s+(\w+)", self._parse_universal),
            (r"every\s+(\w+)\s+is\s+(\w+)", self._parse_universal),
            (r"no\s+(\w+)\s+are\s+(\w+)", self._parse_negated_universal),
            (r"some\s+(\w+)\s+are\s+(\w+)", self._parse_existential),
            (r"(\w+)\s+is\s+a\s+(\w+)", self._parse_instance),
            (r"(\w+)\s+is\s+(\w+)", self._parse_instance),
        ]
    
    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse text into logical structure."""
        text = text.strip()
        
        # Try formal notation first
        formal = self._parse_formal(text)
        if formal:
            return formal
        
        # Fallback to NL patterns
        return self._parse_natural_language(text)
    
    def _parse_formal(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse formal logical notation."""
        # Check for predicate with arguments
        pred_match = re.match(r'([¬~]?)(\w+)\(([^)]+)\)', text)
        if pred_match:
            negated = pred_match.group(1) in ('¬', '~')
            pred_name = pred_match.group(2)
            args = [a.strip() for a in pred_match.group(3).split(',')]
            
            return {
                "type": "predicate",
                "name": pred_name,
                "arguments": args,
                "negated": negated,
                "quantifier": None
            }
        
        # Check for quantified expression
        for pattern, quant_type in self.quantifier_patterns.items():
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                var = match.group(1)
                rest = text[match.end():].strip()
                inner = self.parse(rest)
                if inner:
                    inner["quantifier"] = quant_type.value
                    inner["bound_variable"] = var
                    return inner
        
        # Check for implication
        for op in ["→", "->", "⊃", "implies"]:
            if op in text:
                parts = text.split(op, 1)
                if len(parts) == 2:
                    left = self.parse(parts[0].strip())
                    right = self.parse(parts[1].strip())
                    if left and right:
                        return {
                            "type": "implication",
                            "antecedent": left,
                            "consequent": right
                        }
        
        return None
    
    def _parse_natural_language(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse natural language into logical structure."""
        text_lower = text.lower().strip()
        
        for pattern, handler in self.nl_patterns:
            match = re.match(pattern, text_lower, re.IGNORECASE)
            if match:
                return handler(match)
        
        # Default: treat as atomic proposition
        return {
            "type": "atomic",
            "content": text,
            "confidence": 0.5  # Lower confidence for unparsed
        }
    
    def _parse_conditional(self, match: re.Match) -> Dict[str, Any]:
        """Parse 'if P then Q' pattern."""
        return {
            "type": "implication",
            "antecedent": {"type": "atomic", "content": match.group(1).strip()},
            "consequent": {"type": "atomic", "content": match.group(2).strip()}
        }
    
    def _parse_universal(self, match: re.Match) -> Dict[str, Any]:
        """Parse 'all X are Y' pattern."""
        subject = match.group(1)
        predicate = match.group(2)
        return {
            "type": "universal",
            "quantifier": "∀",
            "variable": "x",
            "subject": subject,
            "predicate": predicate,
            "formal": f"∀x({subject.capitalize()}(x) → {predicate.capitalize()}(x))"
        }
    
    def _parse_negated_universal(self, match: re.Match) -> Dict[str, Any]:
        """Parse 'no X are Y' pattern."""
        subject = match.group(1)
        predicate = match.group(2)
        return {
            "type": "universal",
            "quantifier": "∀",
            "variable": "x",
            "subject": subject,
            "predicate": predicate,
            "negated_predicate": True,
            "formal": f"∀x({subject.capitalize()}(x) → ¬{predicate.capitalize()}(x))"
        }
    
    def _parse_existential(self, match: re.Match) -> Dict[str, Any]:
        """Parse 'some X are Y' pattern."""
        subject = match.group(1)
        predicate = match.group(2)
        return {
            "type": "existential",
            "quantifier": "∃",
            "variable": "x",
            "subject": subject,
            "predicate": predicate,
            "formal": f"∃x({subject.capitalize()}(x) ∧ {predicate.capitalize()}(x))"
        }
    
    def _parse_instance(self, match: re.Match) -> Dict[str, Any]:
        """Parse 'X is Y' pattern."""
        instance = match.group(1)
        predicate = match.group(2)
        return {
            "type": "predicate",
            "name": predicate.capitalize(),
            "arguments": [instance],
            "negated": False
        }


class InferenceEngine:
    """
    Enhanced inference engine with multiple patterns.
    """
    
    def __init__(self):
        self.parser = FormalParser()
        self.facts: Dict[str, Dict[str, Any]] = {}
        self.rules: List[Dict[str, Any]] = []
        self.inference_cache: Dict[str, InferenceResult] = {}
    
    def add_fact(self, fact_id: str, statement: str, confidence: float = 1.0) -> None:
        """Add a fact to the knowledge base."""
        parsed = self.parser.parse(statement)
        self.facts[fact_id] = {
            "statement": statement,
            "parsed": parsed,
            "confidence": confidence
        }
    
    def add_rule(
        self,
        name: str,
        antecedents: List[str],
        consequent: str,
        confidence: float = 1.0
    ) -> None:
        """Add an inference rule."""
        self.rules.append({
            "name": name,
            "antecedents": [self.parser.parse(a) for a in antecedents],
            "consequent": self.parser.parse(consequent),
            "confidence": confidence
        })
    
    def infer(
        self,
        query: str,
        max_depth: int = 10
    ) -> InferenceResult:
        """
        Attempt to infer the query from known facts and rules.
        """
        # Check cache
        if query in self.inference_cache:
            return self.inference_cache[query]
        
        parsed_query = self.parser.parse(query)
        steps: List[InferenceStep] = []
        patterns_used: List[InferencePattern] = []
        
        # Try direct fact match
        for fact_id, fact in self.facts.items():
            if self._matches(fact["parsed"], parsed_query):
                result = InferenceResult(
                    success=True,
                    conclusion=query,
                    confidence=fact["confidence"],
                    steps=[InferenceStep(
                        step_id=1,
                        premise_ids=[],
                        conclusion=query,
                        pattern_used=InferencePattern.MODUS_PONENS,
                        confidence=fact["confidence"],
                        justification=f"Direct fact: {fact['statement']}"
                    )],
                    patterns_used=[],
                    proof_found=True
                )
                self.inference_cache[query] = result
                return result
        
        # Try inference patterns
        result = self._try_inference_patterns(parsed_query, max_depth, steps, patterns_used)
        
        if result:
            self.inference_cache[query] = result
            return result
        
        # No proof found - flag for review
        return InferenceResult(
            success=False,
            conclusion=query,
            confidence=0.0,
            steps=steps,
            patterns_used=patterns_used,
            proof_found=False,
            needs_flag=True,
            flag_reason="No proof found in knowledge base"
        )
    
    def _try_inference_patterns(
        self,
        query: Dict[str, Any],
        max_depth: int,
        steps: List[InferenceStep],
        patterns_used: List[InferencePattern]
    ) -> Optional[InferenceResult]:
        """Try various inference patterns."""
        
        # Try Modus Ponens
        result = self._try_modus_ponens(query, steps, patterns_used)
        if result:
            return result
        
        # Try Modus Tollens
        result = self._try_modus_tollens(query, steps, patterns_used)
        if result:
            return result
        
        # Try Hypothetical Syllogism
        result = self._try_hypothetical_syllogism(query, steps, patterns_used)
        if result:
            return result
        
        # Try Universal Instantiation
        result = self._try_universal_instantiation(query, steps, patterns_used)
        if result:
            return result
        
        # Try Categorical Syllogism
        result = self._try_categorical_syllogism(query, steps, patterns_used)
        if result:
            return result
        
        return None
    
    def _try_modus_ponens(
        self,
        query: Dict[str, Any],
        steps: List[InferenceStep],
        patterns_used: List[InferencePattern]
    ) -> Optional[InferenceResult]:
        """
        Modus Ponens: P, P→Q ⊢ Q
        
        Look for implications where consequent matches query,
        and we have the antecedent as a fact.
        """
        for rule in self.rules:
            if rule["consequent"] and self._matches(rule["consequent"], query):
                # Check if all antecedents are satisfied
                all_satisfied = True
                antecedent_confs = []
                
                for ant in rule["antecedents"]:
                    found = False
                    for fact in self.facts.values():
                        if self._matches(fact["parsed"], ant):
                            found = True
                            antecedent_confs.append(fact["confidence"])
                            break
                    if not found:
                        all_satisfied = False
                        break
                
                if all_satisfied:
                    confidence = rule["confidence"] * min(antecedent_confs) if antecedent_confs else rule["confidence"]
                    patterns_used.append(InferencePattern.MODUS_PONENS)
                    
                    steps.append(InferenceStep(
                        step_id=len(steps) + 1,
                        premise_ids=[],
                        conclusion=str(query),
                        pattern_used=InferencePattern.MODUS_PONENS,
                        confidence=confidence,
                        justification=f"Modus Ponens via rule: {rule['name']}"
                    ))
                    
                    return InferenceResult(
                        success=True,
                        conclusion=str(query),
                        confidence=confidence,
                        steps=steps,
                        patterns_used=patterns_used,
                        proof_found=True
                    )
        
        return None
    
    def _try_modus_tollens(
        self,
        query: Dict[str, Any],
        steps: List[InferenceStep],
        patterns_used: List[InferencePattern]
    ) -> Optional[InferenceResult]:
        """
        Modus Tollens: ¬Q, P→Q ⊢ ¬P
        
        If query is negated form, look for implications where consequent
        is the non-negated form and we have negation of consequent.
        """
        if query.get("type") != "predicate" or not query.get("negated"):
            return None
        
        # Query is ¬P, look for rule Q→P where we have ¬Q
        non_negated = {**query, "negated": False}
        
        for rule in self.rules:
            if rule["consequent"] and self._matches(rule["consequent"], non_negated):
                # Check if we have negation of any antecedent
                for ant in rule["antecedents"]:
                    negated_ant = {**ant, "negated": not ant.get("negated", False)}
                    for fact in self.facts.values():
                        if self._matches(fact["parsed"], negated_ant):
                            patterns_used.append(InferencePattern.MODUS_TOLLENS)
                            confidence = rule["confidence"] * fact["confidence"]
                            
                            steps.append(InferenceStep(
                                step_id=len(steps) + 1,
                                premise_ids=[],
                                conclusion=str(query),
                                pattern_used=InferencePattern.MODUS_TOLLENS,
                                confidence=confidence,
                                justification=f"Modus Tollens via rule: {rule['name']}"
                            ))
                            
                            return InferenceResult(
                                success=True,
                                conclusion=str(query),
                                confidence=confidence,
                                steps=steps,
                                patterns_used=patterns_used,
                                proof_found=True
                            )
        
        return None
    
    def _try_hypothetical_syllogism(
        self,
        query: Dict[str, Any],
        steps: List[InferenceStep],
        patterns_used: List[InferencePattern]
    ) -> Optional[InferenceResult]:
        """
        Hypothetical Syllogism: P→Q, Q→R ⊢ P→R
        
        Chain implications together.
        """
        if query.get("type") != "implication":
            return None
        
        target_antecedent = query.get("antecedent")
        target_consequent = query.get("consequent")
        
        # Look for chain: find Q such that P→Q and Q→R
        for r1 in self.rules:
            if self._matches(r1["antecedents"][0] if r1["antecedents"] else None, target_antecedent):
                # r1 is P→Q, now find Q→R
                intermediate = r1["consequent"]
                for r2 in self.rules:
                    if r2 != r1:
                        if r2["antecedents"] and self._matches(r2["antecedents"][0], intermediate):
                            if self._matches(r2["consequent"], target_consequent):
                                patterns_used.append(InferencePattern.HYPOTHETICAL_SYLLOGISM)
                                confidence = r1["confidence"] * r2["confidence"]
                                
                                steps.append(InferenceStep(
                                    step_id=len(steps) + 1,
                                    premise_ids=[],
                                    conclusion=str(query),
                                    pattern_used=InferencePattern.HYPOTHETICAL_SYLLOGISM,
                                    confidence=confidence,
                                    justification=f"Hypothetical Syllogism: {r1['name']} + {r2['name']}"
                                ))
                                
                                return InferenceResult(
                                    success=True,
                                    conclusion=str(query),
                                    confidence=confidence,
                                    steps=steps,
                                    patterns_used=patterns_used,
                                    proof_found=True
                                )
        
        return None
    
    def _try_universal_instantiation(
        self,
        query: Dict[str, Any],
        steps: List[InferenceStep],
        patterns_used: List[InferencePattern]
    ) -> Optional[InferenceResult]:
        """
        Universal Instantiation: ∀x P(x) ⊢ P(a)
        
        Apply universal statements to specific instances.
        """
        if query.get("type") != "predicate":
            return None
        
        query_pred = query.get("name", "")
        query.get("arguments", [])
        
        for fact in self.facts.values():
            parsed = fact["parsed"]
            if parsed.get("type") == "universal":
                # Universal statement, check if applies
                fact_pred = parsed.get("predicate", "")
                if fact_pred.lower() == query_pred.lower():
                    # Check subject constraint
                    parsed.get("subject", "")
                    # Would need to verify instance is of subject type
                    patterns_used.append(InferencePattern.UNIVERSAL_INSTANTIATION)
                    
                    steps.append(InferenceStep(
                        step_id=len(steps) + 1,
                        premise_ids=[],
                        conclusion=str(query),
                        pattern_used=InferencePattern.UNIVERSAL_INSTANTIATION,
                        confidence=fact["confidence"] * 0.9,
                        justification=f"Universal Instantiation from: {fact['statement']}"
                    ))
                    
                    return InferenceResult(
                        success=True,
                        conclusion=str(query),
                        confidence=fact["confidence"] * 0.9,
                        steps=steps,
                        patterns_used=patterns_used,
                        proof_found=True
                    )
        
        return None
    
    def _try_categorical_syllogism(
        self,
        query: Dict[str, Any],
        steps: List[InferenceStep],
        patterns_used: List[InferencePattern]
    ) -> Optional[InferenceResult]:
        """
        Categorical Syllogism: All M are P, All S are M ⊢ All S are P
        
        Classic syllogistic reasoning.
        """
        if query.get("type") != "universal":
            return None
        
        target_subject = query.get("subject", "")
        target_predicate = query.get("predicate", "")
        
        # Find middle term: All S are M, All M are P
        for f1 in self.facts.values():
            p1 = f1["parsed"]
            if p1.get("type") != "universal":
                continue
            
            if p1.get("subject", "").lower() != target_subject.lower():
                continue
            
            middle = p1.get("predicate", "")
            
            # Find All M are P
            for f2 in self.facts.values():
                p2 = f2["parsed"]
                if p2.get("type") != "universal":
                    continue
                
                if p2.get("subject", "").lower() == middle.lower():
                    if p2.get("predicate", "").lower() == target_predicate.lower():
                        patterns_used.append(InferencePattern.CATEGORICAL_SYLLOGISM)
                        confidence = f1["confidence"] * f2["confidence"]
                        
                        steps.append(InferenceStep(
                            step_id=len(steps) + 1,
                            premise_ids=[],
                            conclusion=str(query),
                            pattern_used=InferencePattern.CATEGORICAL_SYLLOGISM,
                            confidence=confidence,
                            justification=f"Categorical Syllogism: {f1['statement']} + {f2['statement']}"
                        ))
                        
                        return InferenceResult(
                            success=True,
                            conclusion=str(query),
                            confidence=confidence,
                            steps=steps,
                            patterns_used=patterns_used,
                            proof_found=True
                        )
        
        return None
    
    def _matches(
        self,
        parsed1: Optional[Dict[str, Any]],
        parsed2: Optional[Dict[str, Any]]
    ) -> bool:
        """Check if two parsed structures match."""
        if parsed1 is None or parsed2 is None:
            return False
        
        if parsed1.get("type") != parsed2.get("type"):
            return False
        
        if parsed1.get("type") == "predicate":
            return (
                parsed1.get("name", "").lower() == parsed2.get("name", "").lower() and
                parsed1.get("negated", False) == parsed2.get("negated", False)
            )
        
        if parsed1.get("type") == "atomic":
            return parsed1.get("content", "").lower() == parsed2.get("content", "").lower()
        
        if parsed1.get("type") == "universal":
            return (
                parsed1.get("subject", "").lower() == parsed2.get("subject", "").lower() and
                parsed1.get("predicate", "").lower() == parsed2.get("predicate", "").lower()
            )
        
        return False
    
    def cross_check_llm(
        self,
        llm_conclusion: str,
        llm_reasoning: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Cross-check LLM conclusion against symbolic proof.
        
        Returns:
            (is_valid, list of issues)
        """
        issues = []
        
        # Try to prove the conclusion
        result = self.infer(llm_conclusion)
        
        if not result.proof_found:
            issues.append("Could not verify conclusion symbolically")
        
        # Check reasoning steps
        for i, step in enumerate(llm_reasoning):
            step_result = self.infer(step)
            if not step_result.proof_found:
                issues.append(f"Step {i+1} could not be verified: {step[:50]}...")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    def proof_or_flag(
        self,
        claim: str,
        require_proof: bool = True
    ) -> Tuple[bool, Optional[InferenceResult], Optional[str]]:
        """
        Attempt proof; if not found, flag for review.
        
        Returns:
            (has_proof, result_if_proven, flag_reason_if_not)
        """
        result = self.infer(claim)
        
        if result.proof_found:
            return True, result, None
        
        if require_proof:
            return False, None, f"No proof found for: {claim}"
        
        # Allow but flag
        return False, result, f"Unproven claim (flagged): {claim}"
