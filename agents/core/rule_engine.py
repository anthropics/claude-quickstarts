"""
Rule Engine - Forward/Backward Chaining Theorem Prover

Phase 2 enhancement: Stronger reasoning core with:
- Structured predicate parsing
- Forward and backward chaining inference
- Cross-checking LLM steps against symbolic proofs
- Unification and pattern matching
"""

from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import re
from datetime import datetime
import time


class ProofStatus(Enum):
    """Status of a proof attempt."""
    PROVEN = "proven"
    DISPROVEN = "disproven"
    UNKNOWN = "unknown"
    TIMEOUT = "timeout"
    CONTRADICTION = "contradiction"


@dataclass
class Predicate:
    """A structured predicate representation."""
    name: str
    arguments: List[str]
    negated: bool = False
    
    def __str__(self) -> str:
        args = ", ".join(self.arguments)
        neg = "¬" if self.negated else ""
        return f"{neg}{self.name}({args})"
    
    def __hash__(self) -> int:
        return hash((self.name, tuple(self.arguments), self.negated))
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Predicate):
            return False
        return (self.name == other.name and 
                self.arguments == other.arguments and 
                self.negated == other.negated)
    
    def negate(self) -> "Predicate":
        """Return negation of this predicate."""
        return Predicate(self.name, self.arguments.copy(), not self.negated)
    
    def substitute(self, bindings: Dict[str, str]) -> "Predicate":
        """Apply variable bindings to create new predicate."""
        new_args = [bindings.get(arg, arg) for arg in self.arguments]
        return Predicate(self.name, new_args, self.negated)


@dataclass
class Rule:
    """An inference rule with antecedents and consequent."""
    name: str
    antecedents: List[Predicate]  # If these are true...
    consequent: Predicate  # ...then this is true
    confidence: float = 1.0
    source: str = "knowledge_base"
    
    def __str__(self) -> str:
        ants = " ∧ ".join(str(a) for a in self.antecedents)
        return f"{self.name}: {ants} → {self.consequent}"


@dataclass
class ProofStep:
    """A single step in a proof."""
    step_number: int
    predicate: Predicate
    justification: str
    rule_applied: Optional[str] = None
    bindings: Dict[str, str] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class ProofResult:
    """Result of a proof attempt."""
    status: ProofStatus
    goal: Predicate
    steps: List[ProofStep]
    confidence: float
    time_ms: float
    contradictions: List[str] = field(default_factory=list)
    
    @property
    def is_proven(self) -> bool:
        return self.status == ProofStatus.PROVEN


class PredicateParser:
    """Parse natural language and logical notation into predicates."""
    
    # Patterns for parsing
    PREDICATE_PATTERN = re.compile(r'(\w+)\s*\(\s*([^)]+)\s*\)')
    NEGATION_PATTERNS = ["not", "no", "isn't", "aren't", "doesn't", "don't", "¬"]
    QUANTIFIER_PATTERNS = {
        "all": "∀",
        "every": "∀",
        "each": "∀",
        "some": "∃",
        "there exists": "∃",
        "any": "∀"
    }
    
    def parse(self, statement: str) -> Optional[Predicate]:
        """Parse a statement into a predicate."""
        statement = statement.strip()

        negated_prefix = False
        if statement.startswith("¬"):
            negated_prefix = True
            statement = statement[1:]
        
        # Check for explicit predicate notation: Name(arg1, arg2)
        match = self.PREDICATE_PATTERN.match(statement)
        if match:
            name = match.group(1)
            args = [a.strip() for a in match.group(2).split(",")]
            negated = negated_prefix or any(neg in statement.lower() for neg in self.NEGATION_PATTERNS)
            return Predicate(name, args, negated)
        
        # Parse natural language patterns
        return self._parse_natural_language(statement)

    def parse_natural_language(self, statement: str) -> Optional[Predicate]:
        """Public wrapper for natural language parsing."""
        return self._parse_natural_language(statement)
    
    def _parse_natural_language(self, statement: str) -> Optional[Predicate]:
        """Parse natural language into predicate form."""
        lower = statement.lower()
        negated = any(neg in lower for neg in self.NEGATION_PATTERNS[:6])
        
        # Pattern: "X is Y" -> IsY(X) or Y(X)
        if " is " in lower:
            parts = statement.split(" is ", 1)
            if len(parts) == 2:
                subject = self._extract_subject(parts[0])
                predicate_name = self._to_predicate_name(parts[1])
                return Predicate(predicate_name, [subject], negated)
        
        # Pattern: "X are Y" -> AreY(X) for plurals
        if " are " in lower:
            parts = statement.split(" are ", 1)
            if len(parts) == 2:
                subject = self._extract_subject(parts[0])
                predicate_name = self._to_predicate_name(parts[1])
                return Predicate(predicate_name, [subject], negated)
        
        # Pattern: "All X are Y" -> ∀x(X(x) → Y(x))
        for quant, symbol in self.QUANTIFIER_PATTERNS.items():
            if lower.startswith(quant + " "):
                return self._parse_quantified(statement, quant, symbol)
        
        # Default: treat as atomic proposition
        name = self._to_predicate_name(statement)
        return Predicate(name, [], negated)
    
    def _parse_quantified(self, statement: str, quant: str, symbol: str) -> Optional[Predicate]:
        """Parse quantified statement."""
        # Remove quantifier
        rest = statement[len(quant):].strip()
        
        if " are " in rest.lower():
            parts = rest.split(" are ", 1)
            if len(parts) == 2:
                subject_class = self._to_predicate_name(parts[0])
                predicate_class = self._to_predicate_name(parts[1])
                # Return as implication predicate
                return Predicate("Implies", [subject_class, predicate_class])
        
        return None
    
    def _extract_subject(self, text: str) -> str:
        """Extract subject from text, removing articles."""
        articles = ["the", "a", "an", "all", "some", "every"]
        words = text.strip().split()
        words = [w for w in words if w.lower() not in articles]
        return "_".join(words) if words else "unknown"
    
    def _to_predicate_name(self, text: str) -> str:
        """Convert text to valid predicate name."""
        # Remove articles and punctuation
        text = re.sub(r'[^\w\s]', '', text)
        articles = ["the", "a", "an", "is", "are", "not", "no"]
        words = [w for w in text.strip().split() if w.lower() not in articles]
        if not words:
            return "Unknown"
        # CamelCase the predicate name
        return "".join(w.capitalize() for w in words)


class RuleEngine:
    """
    Forward and backward chaining inference engine.
    
    Provides deterministic symbolic reasoning that can
    cross-check LLM outputs.
    """
    
    def __init__(self, max_depth: int = 10, timeout_ms: float = 5000):
        self.facts: Set[Predicate] = set()
        self.rules: List[Rule] = []
        self.parser = PredicateParser()
        self.max_depth = max_depth
        self.timeout_ms = timeout_ms
        self.inference_trace: List[ProofStep] = []
        # Lightweight chainers for tests
        self.forward_chainer = ForwardChainer(self.facts, self.rules)
        self.backward_chainer = BackwardChainer(self.facts, self.rules, self.max_depth)
    
    def add_fact(self, fact: Predicate) -> None:
        """Add a fact to the knowledge base."""
        if isinstance(fact, str):
            parsed = self.parser.parse(fact)
            if parsed:
                self.facts.add(parsed)
        else:
            self.facts.add(fact)
    
    def add_fact_from_text(self, statement: str) -> Optional[Predicate]:
        """Parse and add a fact from natural language."""
        pred = self.parser.parse(statement)
        if pred:
            self.add_fact(pred)
        return pred
    
    def add_rule(self, rule: Rule) -> None:
        """Add an inference rule."""
        if isinstance(rule, str):
            parsed = self._parse_rule_text(rule)
            if parsed:
                self.rules.append(parsed)
        else:
            self.rules.append(rule)
    
    def add_rule_from_implication(
        self, 
        name: str,
        if_predicates: List[str], 
        then_predicate: str,
        confidence: float = 1.0
    ) -> Optional[Rule]:
        """Create and add a rule from natural language."""
        antecedents = []
        for pred_text in if_predicates:
            pred = self.parser.parse(pred_text)
            if pred:
                antecedents.append(pred)
        
        consequent = self.parser.parse(then_predicate)
        if consequent and antecedents:
            rule = Rule(name, antecedents, consequent, confidence)
            self.add_rule(rule)
            return rule
        return None
    
    def _parse_rule_text(self, text: str) -> Optional[Rule]:
        """Parse 'P -> Q' style text into a Rule."""
        arrow = "->" if "->" in text else "→" if "→" in text else None
        if not arrow:
            return None
        parts = text.split(arrow)
        if len(parts) != 2:
            return None
        antecedent_part, consequent_part = parts
        antecedent_texts = [p.strip() for p in antecedent_part.split(",") if p.strip()]
        antecedents = []
        for a in antecedent_texts:
            pred = self.parser.parse(a)
            if pred:
                antecedents.append(pred)
        consequent = self.parser.parse(consequent_part.strip())
        if antecedents and consequent:
            return Rule(name=text.strip(), antecedents=antecedents, consequent=consequent)
        return None

    def prove(self, goal: str) -> ProofResult:
        """Prove a goal expressed as text."""
        pred = self.parser.parse(goal) if isinstance(goal, str) else goal
        if not pred:
            return ProofResult(ProofStatus.UNKNOWN, Predicate("Unknown", []), [], 0.0, 0.0)
        return self.backward_chainer.prove(pred)

    def check_contradictions(self) -> List[Predicate]:
        """Detect direct contradictions in facts."""
        contradictions = []
        for fact in list(self.facts):
            negated = fact.negate()
            if negated in self.facts:
                contradictions.append(fact)
        return contradictions
    
    def forward_chain(self, max_iterations: int = 100) -> List[Predicate]:
        """
        Forward chaining inference.
        
        Derives all possible conclusions from current facts and rules.
        Returns list of newly derived facts.
        """
        derived = []
        iterations = 0
        
        while iterations < max_iterations:
            new_facts = []
            
            for rule in self.rules:
                # Try to match all antecedents
                bindings = self._match_antecedents(rule.antecedents, {})
                
                for binding in bindings:
                    # Apply bindings to consequent
                    new_fact = rule.consequent.substitute(binding)
                    
                    if new_fact not in self.facts and new_fact not in new_facts:
                        new_facts.append(new_fact)
                        self.inference_trace.append(ProofStep(
                            step_number=len(self.inference_trace) + 1,
                            predicate=new_fact,
                            justification="Derived by forward chaining",
                            rule_applied=rule.name,
                            bindings=binding,
                            confidence=rule.confidence
                        ))
            
            if not new_facts:
                break
            
            for fact in new_facts:
                self.facts.add(fact)
                derived.append(fact)
            
            iterations += 1
        
        return derived
    
    def backward_chain(self, goal: Predicate, depth: int = 0) -> ProofResult:
        """
        Backward chaining inference (goal-directed).
        
        Attempts to prove a goal by finding supporting facts and rules.
        """
        start_time = datetime.now()
        steps = []
        
        # Check depth limit
        if depth > self.max_depth:
            return ProofResult(
                status=ProofStatus.UNKNOWN,
                goal=goal,
                steps=steps,
                confidence=0.0,
                time_ms=0
            )
        
        # Check if goal is a known fact
        if goal in self.facts:
            steps.append(ProofStep(
                step_number=1,
                predicate=goal,
                justification="Known fact",
                confidence=1.0
            ))
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return ProofResult(
                status=ProofStatus.PROVEN,
                goal=goal,
                steps=steps,
                confidence=1.0,
                time_ms=elapsed
            )
        
        # Check for contradiction
        if goal.negate() in self.facts:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return ProofResult(
                status=ProofStatus.DISPROVEN,
                goal=goal,
                steps=steps,
                confidence=1.0,
                time_ms=elapsed,
                contradictions=[f"Negation of {goal} is a known fact"]
            )
        
        # Try to prove via rules
        for rule in self.rules:
            bindings = self._unify(goal, rule.consequent)
            
            if bindings is not None:
                # Try to prove all antecedents
                all_proven = True
                antecedent_steps = []
                combined_confidence = rule.confidence
                
                for ant in rule.antecedents:
                    sub_ant = ant.substitute(bindings)
                    sub_result = self.backward_chain(sub_ant, depth + 1)
                    
                    if not sub_result.is_proven:
                        all_proven = False
                        break
                    
                    antecedent_steps.extend(sub_result.steps)
                    combined_confidence *= sub_result.confidence
                
                if all_proven:
                    steps.extend(antecedent_steps)
                    steps.append(ProofStep(
                        step_number=len(steps) + 1,
                        predicate=goal,
                        justification=f"Derived via {rule.name}",
                        rule_applied=rule.name,
                        bindings=bindings,
                        confidence=combined_confidence
                    ))
                    
                    elapsed = (datetime.now() - start_time).total_seconds() * 1000
                    return ProofResult(
                        status=ProofStatus.PROVEN,
                        goal=goal,
                        steps=steps,
                        confidence=combined_confidence,
                        time_ms=elapsed
                    )
        
        # Could not prove
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        return ProofResult(
            status=ProofStatus.UNKNOWN,
            goal=goal,
            steps=steps,
            confidence=0.0,
            time_ms=elapsed
        )
    
    def verify_llm_step(
        self,
        premise: str,
        conclusion: str,
        claimed_rule: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cross-check an LLM reasoning step against symbolic proof.
        
        Returns verification result with confidence and any discrepancies.
        """
        premise_pred = self.parser.parse(premise)
        conclusion_pred = self.parser.parse(conclusion)
        
        if not premise_pred or not conclusion_pred:
            return {
                "verified": False,
                "reason": "Could not parse premise or conclusion",
                "confidence": 0.0,
                "symbolic_support": False
            }
        
        # Temporarily add premise as fact
        original_facts = self.facts.copy()
        self.add_fact(premise_pred)
        
        # Try to prove conclusion
        proof = self.backward_chain(conclusion_pred)
        
        # Restore original facts
        self.facts = original_facts
        
        result = {
            "verified": proof.is_proven,
            "confidence": proof.confidence,
            "symbolic_support": proof.is_proven,
            "proof_steps": len(proof.steps),
            "time_ms": proof.time_ms
        }
        
        if proof.status == ProofStatus.DISPROVEN:
            result["reason"] = "Symbolic proof found contradiction"
            result["contradictions"] = proof.contradictions
        elif proof.status == ProofStatus.UNKNOWN:
            result["reason"] = "Could not verify symbolically (may still be valid)"
        else:
            result["reason"] = "Symbolically verified"
            result["proof_trace"] = [str(s.predicate) for s in proof.steps]
        
        return result
    
    def check_consistency(self) -> List[str]:
        """Check for contradictions in the knowledge base."""
        contradictions = []
        
        for fact in self.facts:
            negation = fact.negate()
            if negation in self.facts:
                contradictions.append(
                    f"Contradiction: {fact} and {negation} both asserted"
                )
        
        return contradictions
    
    def _match_antecedents(
        self,
        antecedents: List[Predicate],
        bindings: Dict[str, str]
    ) -> List[Dict[str, str]]:
        """Find all binding combinations that satisfy antecedents."""
        if not antecedents:
            return [bindings]
        
        results = []
        first = antecedents[0]
        rest = antecedents[1:]
        
        for fact in self.facts:
            new_bindings = self._unify(first.substitute(bindings), fact)
            if new_bindings is not None:
                combined = {**bindings, **new_bindings}
                results.extend(self._match_antecedents(rest, combined))
        
        return results
    
    def _unify(
        self,
        p1: Predicate,
        p2: Predicate
    ) -> Optional[Dict[str, str]]:
        """
        Attempt to unify two predicates.
        
        Returns variable bindings if successful, None otherwise.
        """
        if p1.name != p2.name:
            return None
        if p1.negated != p2.negated:
            return None
        if len(p1.arguments) != len(p2.arguments):
            return None
        
        bindings = {}
        for a1, a2 in zip(p1.arguments, p2.arguments):
            # Variable starts with uppercase or is a placeholder
            is_var1 = a1[0].isupper() or a1.startswith("?")
            is_var2 = a2[0].isupper() or a2.startswith("?")
            
            if is_var1 and is_var2:
                # Both variables - bind first to second
                bindings[a1] = a2
            elif is_var1:
                # First is variable - bind to second
                bindings[a1] = a2
            elif is_var2:
                # Second is variable - bind to first
                bindings[a2] = a1
            elif a1.lower() != a2.lower():
                # Constants don't match
                return None
        
        return bindings
    
    def get_proof_trace(self) -> str:
        """Get formatted proof trace."""
        lines = ["Inference Trace:", "=" * 50]
        for step in self.inference_trace:
            lines.append(
                f"{step.step_number}. {step.predicate} "
                f"[{step.justification}]"
            )
        return "\n".join(lines)
    
    def clear_trace(self) -> None:
        """Clear the inference trace."""
        self.inference_trace = []


# -----------------------------------------------------------------------------
# Lightweight components to satisfy unit tests (unification & simple chaining)
# -----------------------------------------------------------------------------


class Unifier:
    """Basic first-order unification for predicates."""

    @staticmethod
    def _is_var(token: str) -> bool:
        return token and token[0].isupper()

    def unify(self, p1: Predicate, p2: Predicate) -> Optional[Dict[str, str]]:
        if p1.name != p2.name or len(p1.arguments) != len(p2.arguments):
            return None
        bindings: Dict[str, str] = {}
        for a1, a2 in zip(p1.arguments, p2.arguments):
            if self._is_var(a1) and self._is_var(a2):
                bindings.setdefault(a1, a2)
                bindings.setdefault(a2, a1)
            elif self._is_var(a1):
                if a1 in bindings and bindings[a1] != a2:
                    return None
                bindings[a1] = a2
            elif self._is_var(a2):
                if a2 in bindings and bindings[a2] != a1:
                    return None
                bindings[a2] = a1
            else:
                if a1 != a2:
                    return None
        return bindings


class ForwardChainer:
    """Minimal forward chainer for tests."""
    def __init__(self, facts: Optional[Set[Predicate]] = None, rules: Optional[List[Rule]] = None):
        self.facts: Set[Predicate] = facts if facts is not None else set()
        self.rules: List[Rule] = rules if rules is not None else []
        self.unifier = Unifier()

    def add_fact(self, fact: Predicate) -> None:
        self.facts.add(fact)

    def add_rule(self, rule: Rule) -> None:
        self.rules.append(rule)

    def infer(self) -> None:
        added = True
        while added:
            added = False
            for rule in list(self.rules):
                bindings_list = self._match_antecedents(rule.antecedents)
                for bindings in bindings_list:
                    new_fact = rule.consequent.substitute(bindings)
                    if new_fact not in self.facts:
                        self.facts.add(new_fact)
                        added = True

    def _match_antecedents(self, antecedents: List[Predicate]) -> List[Dict[str, str]]:
        if not antecedents:
            return [{}]
        first, *rest = antecedents
        matches: List[Dict[str, str]] = []
        for fact in self.facts:
            b = self.unifier.unify(first, fact)
            if b is None:
                continue
            if rest:
                for sub_b in self._match_antecedents([a.substitute(b) for a in rest]):
                    merged = {**b, **sub_b}
                    matches.append(merged)
            else:
                matches.append(b)
        return matches


class BackwardChainer:
    """Minimal backward chainer for tests."""
    def __init__(self, facts: Optional[Set[Predicate]] = None, rules: Optional[List[Rule]] = None, max_depth: int = 5):
        self.facts = facts if facts is not None else set()
        self.rules = rules if rules is not None else []
        self.unifier = Unifier()
        self.max_depth = max_depth

    def add_fact(self, fact: Predicate) -> None:
        self.facts.add(fact)

    def add_rule(self, rule: Rule) -> None:
        self.rules.append(rule)

    def prove(self, goal: Predicate, depth: int = 0) -> ProofResult:
        start = time.time()
        if depth > self.max_depth:
            return ProofResult(ProofStatus.TIMEOUT, goal, [], 0.0, (time.time() - start) * 1000)

        if goal in self.facts:
            return ProofResult(ProofStatus.PROVEN, goal, [ProofStep(1, goal, "Given fact")], 1.0, (time.time() - start) * 1000)

        for rule in self.rules:
            b = self.unifier.unify(rule.consequent, goal)
            if b is None:
                continue
            local_steps: List[ProofStep] = []
            success = True
            step_counter = 1
            for ant in rule.antecedents:
                sub_goal = ant.substitute(b)
                result = self.prove(sub_goal, depth + 1)
                local_steps.extend(result.steps)
                step_counter += len(result.steps)
                if result.status != ProofStatus.PROVEN:
                    success = False
                    break
            if success:
                local_steps.append(ProofStep(step_counter, goal, "By rule", rule_applied=rule.name, bindings=b))
                return ProofResult(ProofStatus.PROVEN, goal, local_steps, 1.0, (time.time() - start) * 1000)

        return ProofResult(ProofStatus.UNKNOWN, goal, [], 0.0, (time.time() - start) * 1000)
