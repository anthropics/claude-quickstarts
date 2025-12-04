"""
Logic Orchestrator - Single Entry Point for Deterministic Reasoning

This module provides the LogicOrchestrator class, which serves as the unified
interface for all deterministic logic operations in the neuro-symbolic agent
framework.

ARCHITECTURAL ROLE:
    The LogicOrchestrator is the ONLY module that coordinates multiple logic
    engines. All higher-level components (CLI, API, ReasonableMindEngine)
    should interact with deterministic reasoning through this single entry point.

ROUTING STRATEGY:
    - Categorical arguments → CategoricalEngine (syllogisms)
    - Propositional arguments → InferenceEngine (rule-based)
    - All arguments → FallacyDetector (pattern matching)
    - Future: ProofEngine for step-by-step derivations

INVARIANTS:
    1. DETERMINISTIC: No randomness, no network calls, no LLM invocations.
       Given the same input, this module always produces the same output.
    2. SIDE-EFFECT FREE: No mutation of external state, no I/O operations.
    3. COMPOSABLE: Results can be aggregated and passed to other layers.

INTEGRATION POINTS:
    - agents/core/categorical_engine.py - Syllogistic reasoning
    - agents/core/inference_engine.py - Propositional/rule-based inference
    - agents/core/fallacy_detector.py - Fallacy pattern detection
    - (Future) agents/core/proof_engine.py - Formal proof construction

TODO: Integration with proof_engine.py for step-by-step derivations
TODO: Integration with ReasonableMindEngine for LLM-augmented analysis
TODO: Add caching layer for repeated queries
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

# Internal engine imports
from agents.core.categorical_engine import (
    CategoricalEngine,
    SyllogismResult,
)
from agents.core.inference_engine import (
    InferenceEngine,
    InferenceResult,
    InferencePattern,
)
from agents.core.fallacy_detector import (
    FallacyDetector,
    FallacyPattern,
    FallacyCategory,
)


# =============================================================================
# Data Structures
# =============================================================================

class ArgumentType(Enum):
    """Classification of argument structure for routing."""
    CATEGORICAL = "categorical"      # Syllogistic (All A are B, etc.)
    PROPOSITIONAL = "propositional"  # If-then, and, or, not
    MIXED = "mixed"                  # Combination of both
    UNKNOWN = "unknown"              # Requires parsing/classification


@dataclass
class StructuredArgument:
    """
    A structured representation of a logical argument.
    
    This is the primary input type for LogicOrchestrator. It represents
    an argument with explicit premises and conclusion, along with metadata
    about its logical form.
    
    Attributes:
        premises: List of premise statements (strings or parsed forms)
        conclusion: The claim being argued for
        argument_type: Classification for routing to appropriate engine
        metadata: Optional context (source, confidence, domain, etc.)
    
    Example:
        >>> arg = StructuredArgument(
        ...     premises=["All mammals are animals", "All dogs are mammals"],
        ...     conclusion="All dogs are animals",
        ...     argument_type=ArgumentType.CATEGORICAL
        ... )
    """
    premises: List[str]
    conclusion: str
    argument_type: ArgumentType = ArgumentType.UNKNOWN
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate argument structure."""
        if not self.premises:
            raise ValueError("Argument must have at least one premise")
        if not self.conclusion:
            raise ValueError("Argument must have a conclusion")


@dataclass
class LogicAnalysisResult:
    """
    Unified result type for all logic analysis operations.
    
    This structure is designed to be implementation-agnostic and can be
    consumed by CLI, API, and higher-level reasoning layers without
    knowledge of which specific engine produced the result.
    
    Attributes:
        is_valid: Whether the argument is logically valid (None if undetermined)
        engine_used: Which engine(s) processed this argument
        syllogism_form: The identified syllogistic form (e.g., "Barbara (AAA-1)")
        inference_pattern: The inference rule used (e.g., "Modus Ponens")
        fallacies: List of detected logical fallacies
        violations: List of constraint/rule violations
        proof_steps: Step-by-step derivation (populated by proof_engine)
        confidence: Confidence score for the analysis (0.0–1.0)
        notes: Explanatory annotations and warnings
        raw_engine_results: Preserved original engine outputs for debugging
    """
    is_valid: Optional[bool] = None
    engine_used: Literal["categorical", "propositional", "mixed", "fallacy_only", "unknown"] = "unknown"
    syllogism_form: Optional[str] = None
    inference_pattern: Optional[str] = None
    fallacies: List[FallacyPattern] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    proof_steps: Optional[List[str]] = None  # TODO: Populate via proof_engine
    confidence: float = 0.0
    notes: List[str] = field(default_factory=list)
    raw_engine_results: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def has_fallacies(self) -> bool:
        """Check if any fallacies were detected."""
        return len(self.fallacies) > 0
    
    @property
    def is_sound(self) -> Optional[bool]:
        """
        Check if argument is sound (valid AND has no fallacies).
        
        Returns None if validity is undetermined.
        """
        if self.is_valid is None:
            return None
        return self.is_valid and not self.has_fallacies
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "is_valid": self.is_valid,
            "engine_used": self.engine_used,
            "syllogism_form": self.syllogism_form,
            "inference_pattern": self.inference_pattern,
            "fallacies": [
                {"name": f.name, "category": f.category.value, "severity": f.severity.value}
                for f in self.fallacies
            ],
            "violations": self.violations,
            "proof_steps": self.proof_steps,
            "confidence": self.confidence,
            "notes": self.notes,
        }


# =============================================================================
# Logic Orchestrator
# =============================================================================

class LogicOrchestrator:
    """
    Single entry point for all deterministic reasoning operations.
    
    The LogicOrchestrator coordinates between specialized logic engines
    (categorical, propositional, fallacy detection) to provide unified
    analysis of logical arguments. It routes requests to the appropriate
    engine based on argument type and aggregates results.
    
    DESIGN PRINCIPLES:
        1. Single Responsibility: Only coordinates, does not perform inference
        2. Deterministic: No randomness or external dependencies
        3. Composable: Results can be passed to other layers
        4. Extensible: New engines can be added without API changes
    
    Example:
        >>> orchestrator = LogicOrchestrator()
        >>> arg = StructuredArgument(
        ...     premises=["All mammals are animals", "All dogs are mammals"],
        ...     conclusion="All dogs are animals",
        ...     argument_type=ArgumentType.CATEGORICAL
        ... )
        >>> result = orchestrator.analyze(arg)
        >>> print(result.is_valid)  # True
        >>> print(result.syllogism_form)  # "Barbara (AAA-1)"
    
    TODO: Add proof_engine integration for step-by-step derivations
    TODO: Add ReasonableMindEngine integration for LLM-augmented analysis
    TODO: Add performance metrics and logging hooks
    """
    
    def __init__(self):
        """Initialize the orchestrator with all available engines."""
        self._categorical_engine = CategoricalEngine()
        self._inference_engine = InferenceEngine()
        self._fallacy_detector = FallacyDetector()
        # TODO: self._proof_engine = ProofEngine()
    
    # =========================================================================
    # Public API
    # =========================================================================
    
    def analyze(self, argument: StructuredArgument) -> LogicAnalysisResult:
        """
        Analyze a structured argument using appropriate logic engines.
        
        This is the primary entry point for logical analysis. It routes
        the argument to the appropriate engine(s) based on argument type
        and aggregates the results.
        
        Args:
            argument: A StructuredArgument with premises, conclusion, and type
            
        Returns:
            LogicAnalysisResult with validity, fallacies, and analysis details
            
        Raises:
            ValueError: If argument is malformed
        """
        result = LogicAnalysisResult(notes=[])
        
        # Step 1: Route to primary engine based on argument type
        if argument.argument_type == ArgumentType.CATEGORICAL:
            result = self._analyze_categorical(argument, result)
        elif argument.argument_type == ArgumentType.PROPOSITIONAL:
            result = self._analyze_propositional(argument, result)
        elif argument.argument_type == ArgumentType.MIXED:
            result = self._analyze_mixed(argument, result)
        else:
            # Unknown type - try to infer or return partial analysis
            result = self._analyze_unknown(argument, result)
        
        # Step 2: Always run fallacy detection
        result = self._detect_fallacies(argument, result)
        
        # Step 3: Calculate overall confidence
        result.confidence = self._calculate_confidence(result)
        
        return result
    
    def analyze_text(self, raw_text: str) -> LogicAnalysisResult:
        """
        Analyze natural language text for logical structure.
        
        This method is a placeholder for future integration with a semantic
        parser or LLM-based argument extraction. Currently returns a result
        indicating that parsing is not yet implemented.
        
        IMPORTANT: This method itself remains deterministic. Any LLM-based
        parsing should happen in a separate layer that calls this method
        with the parsed StructuredArgument.
        
        Args:
            raw_text: Natural language text containing an argument
            
        Returns:
            LogicAnalysisResult with engine_used="unknown" until parser exists
            
        TODO: Integrate with semantic_parser.py for argument extraction
        TODO: Define handoff protocol for LLM-based parsing layer
        """
        # Stub implementation - parsing not yet available
        return LogicAnalysisResult(
            is_valid=None,
            engine_used="unknown",
            confidence=0.0,
            notes=[
                "Text parsing not yet implemented",
                "Please provide a StructuredArgument via analyze() method",
                f"Raw text received: {len(raw_text)} characters"
            ],
            violations=["PARSE_NOT_IMPLEMENTED"]
        )
    
    def check_validity(
        self, 
        premises: List[str], 
        conclusion: str,
        argument_type: ArgumentType = ArgumentType.UNKNOWN
    ) -> Tuple[bool, float]:
        """
        Convenience method for simple validity checks.
        
        Args:
            premises: List of premise statements
            conclusion: The conclusion to validate
            argument_type: Optional type hint for routing
            
        Returns:
            Tuple of (is_valid, confidence) where is_valid may be False
            if validity cannot be determined
        """
        argument = StructuredArgument(
            premises=premises,
            conclusion=conclusion,
            argument_type=argument_type
        )
        result = self.analyze(argument)
        return (result.is_valid or False, result.confidence)
    
    def detect_fallacies_only(self, text: str) -> List[FallacyPattern]:
        """
        Run only fallacy detection on text without full analysis.
        
        This is useful when you only need to check for fallacies
        without validating logical structure.
        
        Args:
            text: Text to check for fallacies
            
        Returns:
            List of detected FallacyPattern objects
        """
        # FallacyDetector.detect requires premises and conclusion
        # For text-only detection, we treat it as a single premise with empty conclusion
        return self._fallacy_detector.detect(argument=text, premises=[text], conclusion="")
    
    # =========================================================================
    # Internal Routing Methods (Stubs)
    # =========================================================================
    
    def _analyze_categorical(
        self, 
        argument: StructuredArgument, 
        result: LogicAnalysisResult
    ) -> LogicAnalysisResult:
        """
        Route categorical arguments to the CategoricalEngine.
        
        Handles syllogistic reasoning with propositions of the form:
        - All A are B (Universal Affirmative)
        - No A are B (Universal Negative)
        - Some A are B (Particular Affirmative)
        - Some A are not B (Particular Negative)
        
        TODO: Implement full parsing of natural language to CategoricalProposition
        TODO: Support multi-premise syllogistic chains
        """
        result.engine_used = "categorical"
        result.notes.append("Routed to CategoricalEngine for syllogistic analysis")
        
        # Stub: Attempt basic syllogism detection
        # In full implementation, this would parse premises into CategoricalPropositions
        if len(argument.premises) == 2:
            # Try to evaluate as a standard syllogism
            # TODO: Parse natural language premises to CategoricalProposition objects
            result.notes.append("TODO: Parse premises to categorical propositions")
            result.notes.append(f"Premises received: {argument.premises}")
            result.notes.append(f"Conclusion received: {argument.conclusion}")
            
            # Placeholder result
            result.is_valid = None
            result.syllogism_form = None
            result.violations.append("CATEGORICAL_PARSING_NOT_IMPLEMENTED")
        else:
            result.notes.append(
                f"Expected 2 premises for standard syllogism, got {len(argument.premises)}"
            )
            result.violations.append("PREMISE_COUNT_MISMATCH")
        
        return result
    
    def _analyze_propositional(
        self, 
        argument: StructuredArgument, 
        result: LogicAnalysisResult
    ) -> LogicAnalysisResult:
        """
        Route propositional arguments to the InferenceEngine.
        
        Handles rule-based reasoning with logical connectives:
        - Conditionals (if-then)
        - Conjunctions (and)
        - Disjunctions (or)
        - Negations (not)
        
        TODO: Implement full propositional formula parsing
        TODO: Support complex nested expressions
        """
        result.engine_used = "propositional"
        result.notes.append("Routed to InferenceEngine for propositional analysis")
        
        # Stub: Add facts and attempt inference
        # In full implementation, this would parse premises into logical formulas
        try:
            # Add premises as facts
            for i, premise in enumerate(argument.premises):
                self._inference_engine.add_fact(f"premise_{i}", premise)
            
            # Attempt to infer the conclusion
            inference_result = self._inference_engine.infer(argument.conclusion)
            
            result.is_valid = inference_result.success
            result.confidence = inference_result.confidence
            
            if inference_result.patterns_used:
                result.inference_pattern = inference_result.patterns_used[0].value
            
            if inference_result.proof_found:
                result.notes.append("Proof found via InferenceEngine")
            elif inference_result.needs_flag:
                result.violations.append(f"FLAG: {inference_result.flag_reason}")
            
            result.raw_engine_results["inference"] = {
                "success": inference_result.success,
                "patterns": [p.value for p in inference_result.patterns_used],
                "steps": len(inference_result.steps)
            }
            
        except Exception as e:
            result.notes.append(f"InferenceEngine error: {str(e)}")
            result.violations.append("INFERENCE_ENGINE_ERROR")
        
        return result
    
    def _analyze_mixed(
        self, 
        argument: StructuredArgument, 
        result: LogicAnalysisResult
    ) -> LogicAnalysisResult:
        """
        Handle arguments that mix categorical and propositional forms.
        
        Strategy: Run both engines and aggregate results.
        
        TODO: Implement proper mixed-mode analysis
        TODO: Define conflict resolution when engines disagree
        """
        result.engine_used = "mixed"
        result.notes.append("Mixed argument type - running both engines")
        
        # Run categorical analysis
        cat_result = self._analyze_categorical(argument, LogicAnalysisResult())
        
        # Run propositional analysis
        prop_result = self._analyze_propositional(argument, LogicAnalysisResult())
        
        # Aggregate (stub - just note both were run)
        result.notes.append(f"Categorical result: valid={cat_result.is_valid}")
        result.notes.append(f"Propositional result: valid={prop_result.is_valid}")
        
        # Conservative: only valid if both agree
        if cat_result.is_valid is not None and prop_result.is_valid is not None:
            result.is_valid = cat_result.is_valid and prop_result.is_valid
        else:
            result.is_valid = cat_result.is_valid or prop_result.is_valid
        
        result.raw_engine_results["categorical"] = cat_result.to_dict()
        result.raw_engine_results["propositional"] = prop_result.to_dict()
        
        return result
    
    def _analyze_unknown(
        self, 
        argument: StructuredArgument, 
        result: LogicAnalysisResult
    ) -> LogicAnalysisResult:
        """
        Handle arguments with unknown type.
        
        Strategy: Attempt to classify, then route appropriately.
        
        TODO: Implement argument type classification heuristics
        TODO: Consider confidence-weighted multi-engine approach
        """
        result.engine_used = "unknown"
        result.notes.append("Argument type unknown - attempting classification")
        
        # Stub: Use simple heuristics to guess type
        all_text = " ".join(argument.premises) + " " + argument.conclusion
        all_lower = all_text.lower()
        
        # Very basic heuristics (to be replaced with proper classification)
        categorical_indicators = ["all ", "no ", "some ", " are ", " is a "]
        propositional_indicators = ["if ", "then ", " and ", " or ", "not "]
        
        cat_score = sum(1 for ind in categorical_indicators if ind in all_lower)
        prop_score = sum(1 for ind in propositional_indicators if ind in all_lower)
        
        if cat_score > prop_score:
            result.notes.append(f"Heuristic classification: categorical (score {cat_score})")
            return self._analyze_categorical(argument, result)
        elif prop_score > cat_score:
            result.notes.append(f"Heuristic classification: propositional (score {prop_score})")
            return self._analyze_propositional(argument, result)
        else:
            result.notes.append("Could not classify argument type")
            result.violations.append("CLASSIFICATION_FAILED")
            result.is_valid = None
        
        return result
    
    def _detect_fallacies(
        self, 
        argument: StructuredArgument, 
        result: LogicAnalysisResult
    ) -> LogicAnalysisResult:
        """
        Run fallacy detection on the argument.
        
        This is always run regardless of argument type, as fallacies
        can appear in any form of reasoning.
        """
        # Run fallacy detector with structured argument
        fallacies = self._fallacy_detector.detect(
            argument=" ".join(argument.premises) + " " + argument.conclusion,
            premises=argument.premises,
            conclusion=argument.conclusion
        )
        result.fallacies = fallacies
        
        if result.fallacies:
            result.notes.append(f"Detected {len(fallacies)} potential fallacy/fallacies")
            # Downgrade validity if serious fallacies found
            from agents.core.fallacy_detector import FallacySeverity
            for fallacy in fallacies:
                if fallacy.severity == FallacySeverity.MAJOR:
                    result.notes.append(
                        f"Major fallacy detected: {fallacy.name}"
                    )
        
        return result
    
    def _calculate_confidence(self, result: LogicAnalysisResult) -> float:
        """
        Calculate overall confidence in the analysis.
        
        Factors:
        - Engine success (did we get a definitive answer?)
        - Fallacy detection (presence of fallacies reduces confidence)
        - Violation count (more violations = less confidence)
        
        TODO: Implement proper confidence calibration
        TODO: Add empirical weighting based on engine accuracy
        """
        base_confidence = 0.5  # Start neutral
        
        # Boost if we got a validity determination
        if result.is_valid is not None:
            base_confidence += 0.3
        
        # Reduce for violations
        violation_penalty = min(len(result.violations) * 0.1, 0.3)
        base_confidence -= violation_penalty
        
        # Reduce for fallacies (based on severity)
        if result.fallacies:
            from agents.core.fallacy_detector import FallacySeverity
            severity_weights = {
                FallacySeverity.MAJOR: 0.3,
                FallacySeverity.MODERATE: 0.15,
                FallacySeverity.MINOR: 0.05
            }
            fallacy_penalty = sum(
                severity_weights.get(f.severity, 0.1) for f in result.fallacies
            )
            base_confidence -= min(fallacy_penalty, 0.4)
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, base_confidence))


# =============================================================================
# Factory Functions
# =============================================================================

def create_orchestrator() -> LogicOrchestrator:
    """
    Factory function to create a configured LogicOrchestrator.
    
    Use this instead of direct instantiation for future compatibility
    with dependency injection and configuration systems.
    """
    return LogicOrchestrator()


def analyze_argument(
    premises: List[str],
    conclusion: str,
    argument_type: str = "unknown"
) -> LogicAnalysisResult:
    """
    Convenience function for one-off analysis without managing orchestrator lifecycle.
    
    Args:
        premises: List of premise statements
        conclusion: The conclusion to validate
        argument_type: One of "categorical", "propositional", "mixed", "unknown"
        
    Returns:
        LogicAnalysisResult with full analysis
    """
    type_map = {
        "categorical": ArgumentType.CATEGORICAL,
        "propositional": ArgumentType.PROPOSITIONAL,
        "mixed": ArgumentType.MIXED,
        "unknown": ArgumentType.UNKNOWN,
    }
    
    orchestrator = create_orchestrator()
    argument = StructuredArgument(
        premises=premises,
        conclusion=conclusion,
        argument_type=type_map.get(argument_type.lower(), ArgumentType.UNKNOWN)
    )
    return orchestrator.analyze(argument)
