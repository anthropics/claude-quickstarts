"""
Neuro-Symbolic Reasoning Agent

Combines ML-powered reasoning (LLM) with formal logic systems.
Backend: Machine learning (extended thinking, tool use)
Frontend: Logic-based knowledge system (formal reasoning, argument chains)
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .knowledge_base import (
    KnowledgeBase,
    LogicType,
    InferenceRule,
    Fact,
    LogicalStatement,
)


@dataclass
class ReasoningStep:
    """Represents one step in a logical argument chain."""
    premise: str
    inference_rule: InferenceRule
    conclusion: str
    confidence: float
    supporting_evidence: Optional[List[str]] = None
    layer_id: Optional[int] = None  # Which neural layer produced this
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class FormalArgument:
    """A complete formal logical argument."""
    premises: List[LogicalStatement]
    inference_steps: List[InferenceRule]
    conclusion: LogicalStatement
    overall_confidence: float
    cited_facts: List[str]
    notation: LogicType
    argument_structure: str  # Visual representation


class ArgumentBuilder:
    """
    Constructs formal logical arguments from ML reasoning chains.

    This is the "frontend" layer that presents neural reasoning
    as symbolic logic.
    """

    def __init__(self, logic_system: LogicType = LogicType.FIRST_ORDER):
        self.logic_system = logic_system
        self.formatter = ArgumentFormatter(logic_system)

    def build_argument(
        self,
        reasoning_chain: List[ReasoningStep]
    ) -> FormalArgument:
        """
        Convert ML reasoning chain to symbolic logic representation.

        Args:
            reasoning_chain: Steps from neural reasoning

        Returns:
            Formal logical argument
        """
        # Extract premises
        premises = [step.premise for step in reasoning_chain]
        formalized_premises = self._formalize_premises(premises)

        # Extract inference rules used
        inference_steps = [step.inference_rule for step in reasoning_chain]

        # Final conclusion
        conclusion = reasoning_chain[-1].conclusion
        formalized_conclusion = self._formalize_conclusion(conclusion)

        # Calculate overall confidence
        confidences = [step.confidence for step in reasoning_chain]
        overall_confidence = self._calculate_chain_confidence(confidences)

        # Extract cited facts
        cited_facts = []
        for step in reasoning_chain:
            if step.supporting_evidence:
                cited_facts.extend(step.supporting_evidence)

        # Build structure visualization
        structure = self._build_structure_visualization(reasoning_chain)

        return FormalArgument(
            premises=formalized_premises,
            inference_steps=inference_steps,
            conclusion=formalized_conclusion,
            overall_confidence=overall_confidence,
            cited_facts=list(set(cited_facts)),  # Deduplicate
            notation=self.logic_system,
            argument_structure=structure
        )

    def _formalize_premises(self, premises: List[str]) -> List[LogicalStatement]:
        """Convert natural language premises to logical notation."""
        formalized = []

        for premise in premises:
            logical_form = self._parse_to_predicate_logic(premise)
            formalized.append(logical_form)

        return formalized

    def _formalize_conclusion(self, conclusion: str) -> LogicalStatement:
        """Convert natural language conclusion to logical notation."""
        return self._parse_to_predicate_logic(conclusion)

    def _parse_to_predicate_logic(self, statement: str) -> LogicalStatement:
        """
        Parse natural language into predicate logic.

        Examples:
        - "All humans are mortal" → ∀x(Human(x) → Mortal(x))
        - "Socrates is human" → Human(Socrates)
        - "If it rains, the ground is wet" → Rain → Wet(ground)
        """
        variables = set()
        predicates = set()
        statement_lower = statement.lower()

        # Pattern: "All X are Y"
        if "all" in statement_lower and "are" in statement_lower:
            parts = statement_lower.split("are")
            if len(parts) == 2:
                x_class = parts[0].replace("all", "").strip()
                y_class = parts[1].strip()

                variables.add("x")
                predicates.add(x_class.capitalize())
                predicates.add(y_class.capitalize())

                formal = f"∀x({x_class.capitalize()}(x) → {y_class.capitalize()}(x))"

                return LogicalStatement(
                    natural_language=statement,
                    formal_notation=formal,
                    logic_type=self.logic_system,
                    variables=variables,
                    predicates=predicates
                )

        # Pattern: "X is Y"
        if " is " in statement_lower:
            parts = statement_lower.split(" is ")
            if len(parts) == 2:
                subject = parts[0].strip().capitalize()
                predicate = parts[1].strip().capitalize()

                predicates.add(predicate)
                formal = f"{predicate}({subject})"

                return LogicalStatement(
                    natural_language=statement,
                    formal_notation=formal,
                    logic_type=self.logic_system,
                    variables=set(),
                    predicates=predicates
                )

        # Pattern: "If P then Q"
        if "if" in statement_lower and "then" in statement_lower:
            parts = statement_lower.split("then")
            p = parts[0].replace("if", "").strip()
            q = parts[1].strip()

            formal = f"{p.capitalize()} → {q.capitalize()}"

            return LogicalStatement(
                natural_language=statement,
                formal_notation=formal,
                logic_type=self.logic_system,
                variables=set(),
                predicates={p.capitalize(), q.capitalize()}
            )

        # Default: treat as atomic proposition
        return LogicalStatement(
            natural_language=statement,
            formal_notation=f"P(\"{statement}\")",
            logic_type=self.logic_system,
            variables=set(),
            predicates={"P"}
        )

    def _calculate_chain_confidence(self, confidences: List[float]) -> float:
        """
        Calculate overall confidence for a reasoning chain.

        Uses product rule: confidence diminishes with chain length.
        """
        if not confidences:
            return 0.0

        # Product of confidences (each step reduces certainty)
        product = 1.0
        for conf in confidences:
            product *= conf

        # Apply slight boost for longer chains (more thorough)
        chain_length_factor = 1.0 + (len(confidences) * 0.02)
        adjusted = min(0.99, product * chain_length_factor)

        return adjusted

    def _build_structure_visualization(
        self,
        reasoning_chain: List[ReasoningStep]
    ) -> str:
        """Build ASCII visualization of argument structure."""
        lines = []
        lines.append("Argument Structure:")
        lines.append("=" * 60)

        for i, step in enumerate(reasoning_chain, 1):
            indent = "  " * (i - 1)
            lines.append(f"{indent}[{i}] {step.premise}")
            lines.append(f"{indent}    ↓ {step.inference_rule.value}")

        lines.append(f"{'  ' * len(reasoning_chain)}∴ {reasoning_chain[-1].conclusion}")
        lines.append("=" * 60)

        return "\n".join(lines)


class ArgumentFormatter:
    """Formats arguments in different logical notations."""

    def __init__(self, logic_system: LogicType):
        self.logic_system = logic_system

    def format_argument(self, argument: FormalArgument) -> str:
        """Format argument for display."""
        lines = []
        lines.append(f"=== FORMAL ARGUMENT ({self.logic_system.value.upper()}) ===\n")

        lines.append("PREMISES:")
        for i, premise in enumerate(argument.premises, 1):
            lines.append(f"  P{i}: {premise.formal_notation}")
            lines.append(f"      ({premise.natural_language})")

        lines.append(f"\nINFERENCE RULES: {', '.join(r.value for r in argument.inference_steps)}")

        lines.append(f"\nCONCLUSION:")
        lines.append(f"  ∴ {argument.conclusion.formal_notation}")
        lines.append(f"     ({argument.conclusion.natural_language})")

        lines.append(f"\nCONFIDENCE: {argument.overall_confidence:.1%}")

        if argument.cited_facts:
            lines.append(f"\nSOURCES: {', '.join(argument.cited_facts)}")

        lines.append(f"\n{argument.argument_structure}")

        return "\n".join(lines)


class ReasoningAgent:
    """
    Neuro-Symbolic Agent for logical reasoning.

    Backend: ML-powered extended thinking
    Frontend: Formal logic presentation
    """

    def __init__(
        self,
        name: str,
        system_prompt: str,
        logic_framework: LogicType = LogicType.FIRST_ORDER,
        reasoning_depth: int = 3,
        logic_weight: float = 0.75,
        verbose: bool = False
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.logic_framework = logic_framework
        self.reasoning_depth = reasoning_depth
        self.logic_weight = logic_weight
        self.verbose = verbose

        # Initialize components
        self.knowledge_base = KnowledgeBase(logic_system=logic_framework)
        self.argument_builder = ArgumentBuilder(logic_system=logic_framework)
        self.reasoning_chain: List[ReasoningStep] = []

    def reason(
        self,
        query: str,
        context: Optional[str] = None,
        options: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Execute extended reasoning on a query.

        Process:
        1. Decompose query into sub-problems
        2. For each sub-problem, build reasoning chain
        3. Validate against knowledge base
        4. Synthesize into formal argument
        5. Return both ML reasoning and logic representation

        Args:
            query: The question or problem
            context: Additional context
            options: Possible answers to evaluate

        Returns:
            Dict with conclusion, reasoning chain, formal argument, confidence
        """
        if self.verbose:
            print(f"\n[{self.name}] Reasoning about: {query}\n")

        # Step 1: Decompose query
        sub_problems = self._decompose(query, context)

        # Step 2: Build reasoning chain
        self.reasoning_chain = []
        for problem in sub_problems:
            step = self._reason_step(problem)
            self.reasoning_chain.append(step)

        # Step 3: Synthesize formal argument
        formal_argument = self.argument_builder.build_argument(self.reasoning_chain)

        # Step 4: Validate against knowledge base
        validation = self.knowledge_base.validate_with_contradiction_check(
            formal_argument.conclusion.natural_language
        )
        if (not validation.valid or not validation.sources) and query:
            # Fallback: validate the original query if conclusion parsing drifted
            fallback = self.knowledge_base.validate_with_contradiction_check(query)
            if fallback.valid or fallback.sources:
                validation = fallback

        # Step 5: Build result
        result = {
            "conclusion": formal_argument.conclusion.natural_language,
            "formal_conclusion": formal_argument.conclusion.formal_notation,
            "reasoning_chain": [
                {
                    "premise": step.premise,
                    "rule": step.inference_rule.value,
                    "conclusion": step.conclusion,
                    "confidence": step.confidence
                }
                for step in self.reasoning_chain
            ],
            "formal_argument": formal_argument,
            "confidence": formal_argument.overall_confidence,
            "knowledge_validation": {
                "valid": validation.valid,
                "confidence": validation.confidence,
                "sources": validation.sources,
                "reasoning_chain": validation.reasoning_chain
            },
            "knowledge_used": formal_argument.cited_facts,
            "ml_reasoning_trace": self._get_ml_trace(),
            "proved": all(step.confidence >= 0.8 for step in self.reasoning_chain)
        }

        # Step 6: Apply hallucination guard (confidence adjustment + warnings)
        guard = self._hallucination_guard(result)
        result["confidence"] = guard["adjusted_confidence"]
        result["hallucination_guard"] = guard
        result["warnings"] = guard["warnings"]

        # Evidence enforcement: fail-closed on missing validation/sources
        if not validation.valid or not validation.sources:
            result["conclusion"] = "No answer: insufficient evidence"
            result["warnings"].append(
                "Insufficient evidence to support conclusion (no sources or validation failed)."
            )
            result["confidence"] = min(result["confidence"], 0.1)
            result["verified"] = False
        else:
            # Boost slightly when well-cited and validated
            result["confidence"] = min(
                1.0, result["confidence"] * (1.05 if validation.valid else 1.0)
            )
            result["verified"] = True

        # Downstream consumers: propagate verification/warnings into formal argument
        result["formal_argument"].overall_confidence = result["confidence"]
        if result["warnings"]:
            result["formal_argument"].argument_structure += (
                f"\nWarnings: {'; '.join(result['warnings'])}"
            )
        result["formal_argument"].argument_structure += (
            "\nProof status: proved" if result["proved"] else "\nProof status: unproven/heuristic"
        )

        if self.verbose:
            self._print_result(result)

        return result

    def _decompose(self, query: str, context: Optional[str]) -> List[str]:
        """
        Decompose complex query into sub-problems.

        Uses heuristics to break down questions.
        Production would use LLM for intelligent decomposition.
        """
        # Simplified decomposition
        sub_problems = []

        # Check for compound questions (and, or)
        if " and " in query.lower():
            sub_problems = query.split(" and ")
        elif " or " in query.lower():
            sub_problems = query.split(" or ")
        else:
            sub_problems = [query]

        return [p.strip() for p in sub_problems]

    def _reason_step(self, problem: str) -> ReasoningStep:
        """
        Execute one reasoning step.

        This integrates with the extended thinking tool and knowledge base.
        """
        # Query knowledge base for relevant facts
        relevant_facts = self.knowledge_base.query(problem)

        # Determine inference rule to apply
        inference_rule = self._select_inference_rule(problem, relevant_facts)

        # Generate conclusion
        conclusion, proved = self._generate_conclusion(problem, relevant_facts, inference_rule)

        # Calculate confidence
        if relevant_facts:
            avg_fact_confidence = sum(f.confidence for f in relevant_facts) / len(relevant_facts)
            confidence = avg_fact_confidence * 0.9  # Slight reduction for inference
        else:
            confidence = 0.6  # Lower confidence without KB support

        return ReasoningStep(
            premise=problem,
            inference_rule=inference_rule,
            conclusion=conclusion,
            confidence=confidence if proved else max(confidence * 0.8, 0.1),
            supporting_evidence=[f.source for f in relevant_facts]
        )

    def _select_inference_rule(
        self,
        problem: str,
        facts: List[Fact]
    ) -> InferenceRule:
        """Select appropriate inference rule based on problem and facts."""
        problem_lower = problem.lower()

        # Heuristic rule selection
        if "all" in problem_lower and any("all" in f.statement.lower() for f in facts):
            return InferenceRule.UNIVERSAL_INSTANTIATION

        if "if" in problem_lower or any("if" in f.statement.lower() for f in facts):
            return InferenceRule.MODUS_PONENS

        if "or" in problem_lower:
            return InferenceRule.DISJUNCTIVE_SYLLOGISM

        if "and" in problem_lower:
            return InferenceRule.CONJUNCTION

        # Default
        return InferenceRule.MODUS_PONENS

    def _generate_conclusion(
        self,
        problem: str,
        facts: List[Fact],
        rule: InferenceRule
    ) -> (str, bool):
        """Generate conclusion from premises using inference rule."""
        # Simplified conclusion generation
        # Production would use LLM or formal theorem prover

        if not facts:
            return f"Cannot conclude from: {problem}", False

        # Use first relevant fact to construct conclusion
        fact = facts[0]

        if rule == InferenceRule.UNIVERSAL_INSTANTIATION:
            # Pattern: "All X are Y" + problem about specific X → "specific X is Y"
            if "all" in fact.statement.lower():
                parts = fact.statement.lower().split("are")
                if len(parts) == 2:
                    predicate = parts[1].strip()
                    # Extract subject from problem
                    words = problem.split()
                    if words:
                        subject = words[0]
                        return f"{subject} {predicate}", True

        if rule == InferenceRule.MODUS_PONENS:
            # Pattern: P, P→Q ⊢ Q
            if fact.logical_form and "→" in fact.logical_form:
                parts = fact.logical_form.split("→")
                if len(parts) == 2:
                    return parts[1].strip(), True

            statement_lower = fact.statement.lower()
            if "if" in statement_lower or "then" in statement_lower or "are" in statement_lower:
                parts = statement_lower.split("then" if "then" in statement_lower else "are")
                if len(parts) == 2:
                    return parts[1].strip(), True

        if rule == InferenceRule.MODUS_TOLLENS:
            # Pattern: ¬Q, P→Q ⊢ ¬P
            if fact.logical_form and "→" in fact.logical_form:
                parts = fact.logical_form.split("→")
                if len(parts) == 2:
                    antecedent = parts[0].strip()
                    consequent = parts[1].strip()
                    if "not" in problem.lower() or "¬" in problem:
                        return f"not {antecedent}", True

        # Default heuristic
        return f"Inferred from: {fact.statement}", False

        return f"Inferred from: {fact.statement}"

    def _get_ml_trace(self) -> str:
        """Get trace of ML reasoning process."""
        return f"Extended thinking with {len(self.reasoning_chain)} steps at depth {self.reasoning_depth}"

    def build_trace(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Structured trace for observability."""
        return {
            "query": result.get("formal_argument", {}).conclusion.natural_language if isinstance(result.get("formal_argument"), LogicalStatement) else result.get("conclusion"),
            "conclusion": result.get("conclusion"),
            "formal_conclusion": result.get("formal_conclusion"),
            "reasoning_chain": result.get("reasoning_chain"),
            "knowledge_validation": result.get("knowledge_validation"),
            "warnings": result.get("warnings"),
            "verified": result.get("verified"),
            "proved": result.get("proved", False),
            "ml_trace": result.get("ml_reasoning_trace"),
        }

    def _hallucination_guard(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mitigate hallucinations by down-weighting unvalidated outputs and flagging risks.

        Heuristics inspired by common guidance:
        - Prefer grounded, cited facts
        - Penalize low validation confidence
        - Flag missing sources
        - Highlight long/uncertain chains
        """
        warnings: List[str] = []
        adjustment = 1.0
        risk_level = "low"

        validation = result.get("knowledge_validation", {}) or {}
        knowledge_used = result.get("knowledge_used", []) or []
        chain = result.get("reasoning_chain", []) or []

        avg_chain_conf = (
            sum(step.get("confidence", 0.0) for step in chain) / len(chain)
            if chain else 0.0
        )

        if not validation.get("valid") or validation.get("confidence", 0.0) < 0.5:
            risk_level = "high"
            adjustment *= 0.7
            warnings.append("Knowledge validation failed or is low-confidence.")

        if not knowledge_used:
            if risk_level == "low":
                risk_level = "medium"
            adjustment *= 0.85
            warnings.append("No cited facts; consider verifying against trusted sources.")

        if avg_chain_conf < 0.65:
            if risk_level == "low":
                risk_level = "medium"
            adjustment *= 0.9
            warnings.append("Reasoning chain has low average confidence.")

        if len(chain) > 6:
            warnings.append("Long reasoning chain—higher chance of compounding errors.")

        adjusted_confidence = max(0.0, min(1.0, result.get("confidence", 0.0) * adjustment))

        return {
            "risk_level": risk_level,
            "warnings": warnings,
            "adjusted_confidence": adjusted_confidence,
            "validation_confidence": validation.get("confidence", 0.0),
            "knowledge_used": knowledge_used,
        }

    def _print_result(self, result: Dict[str, Any]):
        """Print reasoning result."""
        print("=" * 70)
        print(f"🧠 REASONING RESULT")
        print("=" * 70)
        print(f"\nConclusion: {result['conclusion']}")
        print(f"Formal: {result['formal_conclusion']}")
        print(f"Confidence: {result['confidence']:.1%}")
        if result.get("hallucination_guard"):
            guard = result["hallucination_guard"]
            print(f"Hallucination Risk: {guard['risk_level']}")
            if guard["warnings"]:
                print("Warnings:")
                for w in guard["warnings"]:
                    print(f"  - {w}")
        print(f"\nReasoning Chain:")
        for i, step in enumerate(result['reasoning_chain'], 1):
            print(f"  {i}. {step['premise']}")
            print(f"     → {step['rule']} → {step['conclusion']}")
        print("=" * 70)

    def add_knowledge(
        self,
        statement: str,
        source: str = "user",
        confidence: float = 1.0
    ):
        """Add knowledge to the agent's knowledge base."""
        self.knowledge_base.add_fact(statement, source, confidence)

    def get_knowledge_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base."""
        return self.knowledge_base.get_statistics()
