"""
Epistemic Status and Confidence Calculus

Separates two critical concepts:
1. Logical Validity: Is the argument structure correct?
2. Soundness: Are the premises actually true?

A single "confidence" score conflates these. We need separate tracking.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class ValidityStatus(Enum):
    """Logical validity of an argument."""
    VALID = "valid"  # Conclusion follows from premises
    INVALID = "invalid"  # Conclusion doesn't follow
    UNKNOWN = "unknown"  # Can't determine validity


class SoundnessStatus(Enum):
    """Epistemic status of premises."""
    SOUND = "sound"  # Premises are true AND argument is valid
    UNSOUND = "unsound"  # At least one premise is false OR argument invalid
    UNKNOWN = "unknown"  # Can't determine truth of premises


class ConfidenceType(Enum):
    """Different types of confidence/uncertainty."""
    LOGICAL = "logical"  # Confidence in argument structure
    EMPIRICAL = "empirical"  # Confidence in factual claims
    DEFINITIONAL = "definitional"  # Confidence in term meanings
    SOURCE = "source"  # Confidence in information source


@dataclass
class EpistemicStatus:
    """
    Complete epistemic status of a claim or argument.

    Separates structural validity from factual truth.
    """
    # Logical properties
    validity: ValidityStatus
    validity_confidence: float  # How sure are we it's valid/invalid?

    # Epistemic properties
    soundness: SoundnessStatus
    premise_confidences: List[float]  # Confidence in each premise

    # Combined assessment
    overall_confidence: float  # For the conclusion

    # Justification
    validity_justification: str
    soundness_justification: str

    def is_reliable(self, threshold: float = 0.7) -> bool:
        """
        Is this conclusion reliable enough to act on?

        Requires BOTH structural validity AND empirical soundness.
        """
        return (
            self.validity == ValidityStatus.VALID and
            self.validity_confidence >= threshold and
            self.soundness != SoundnessStatus.UNSOUND and
            self.overall_confidence >= threshold
        )


@dataclass
class ConfidenceBreakdown:
    """
    Detailed breakdown of confidence components.

    Makes confidence propagation explicit and auditable.
    """
    logical_confidence: float  # Argument structure is valid
    premise_confidences: List[float]  # Each premise is true
    source_confidence: float  # Sources are reliable
    definitional_confidence: float  # Terms are well-defined

    propagation_method: str  # How was confidence calculated?
    chain_length: int  # Number of inference steps

    def to_dict(self) -> Dict[str, Any]:
        return {
            "logical": self.logical_confidence,
            "premises": self.premise_confidences,
            "source": self.source_confidence,
            "definitional": self.definitional_confidence,
            "propagation": self.propagation_method,
            "chain_length": self.chain_length
        }


class ConfidenceCalculator:
    """
    Explicit confidence propagation rules.

    Addresses the question: "What's your confidence calculus?"
    """

    @staticmethod
    def conjunctive_chain(confidences: List[float]) -> float:
        """
        Confidence for AND chain: P1 ∧ P2 ∧ ... ∧ Pn

        Use product rule (independent assumptions):
        P(P1 ∧ P2) = P(P1) × P(P2)

        This is conservative - confidence degrades with chain length.
        """
        if not confidences:
            return 0.0

        result = 1.0
        for conf in confidences:
            result *= conf

        return result

    @staticmethod
    def disjunctive_chain(confidences: List[float]) -> float:
        """
        Confidence for OR chain: P1 ∨ P2 ∨ ... ∨ Pn

        Use complement rule:
        P(P1 ∨ P2) = 1 - (1 - P(P1)) × (1 - P(P2))

        This is optimistic - confidence increases with alternatives.
        """
        if not confidences:
            return 0.0

        result = 1.0
        for conf in confidences:
            result *= (1.0 - conf)

        return 1.0 - result

    @staticmethod
    def inference_step(
        premise_confidence: float,
        rule_confidence: float,
        rule_type: str = "modus_ponens"
    ) -> float:
        """
        Confidence after one inference step.

        P: premise (confidence = c_p)
        R: inference rule is valid (confidence = c_r)
        Q: conclusion

        P(Q) = P(P) × P(R) × P(R applies correctly)

        Rule application confidence varies by rule complexity:
        - Modus ponens: 0.95 (very reliable)
        - Abduction: 0.7 (less certain)
        """
        rule_application_confidence = {
            "modus_ponens": 0.95,
            "modus_tollens": 0.95,
            "hypothetical_syllogism": 0.90,
            "universal_instantiation": 0.90,
            "existential_generalization": 0.85,
            "resolution": 0.85,
            "abduction": 0.70,  # Weaker inference
        }

        application_conf = rule_application_confidence.get(rule_type, 0.80)

        return premise_confidence * rule_confidence * application_conf

    @staticmethod
    def multi_step_chain(
        premise_confidences: List[float],
        rule_confidences: List[float],
        rule_types: List[str]
    ) -> ConfidenceBreakdown:
        """
        Confidence for multi-step reasoning chain.

        Tracks exactly how confidence propagates through chain.
        """
        if not premise_confidences or not rule_confidences:
            return ConfidenceBreakdown(
                logical_confidence=0.0,
                premise_confidences=[],
                source_confidence=0.0,
                definitional_confidence=0.0,
                propagation_method="none",
                chain_length=0
            )

        # Start with first premise
        current_confidence = premise_confidences[0]

        # Apply each inference step
        for i, (rule_conf, rule_type) in enumerate(zip(rule_confidences, rule_types)):
            current_confidence = ConfidenceCalculator.inference_step(
                current_confidence,
                rule_conf,
                rule_type
            )

        # Logical confidence = how confident are we the rules are valid?
        logical_conf = ConfidenceCalculator.conjunctive_chain(rule_confidences)

        # Source confidence = how reliable are our premises?
        source_conf = ConfidenceCalculator.conjunctive_chain(premise_confidences)

        return ConfidenceBreakdown(
            logical_confidence=logical_conf,
            premise_confidences=premise_confidences,
            source_confidence=source_conf,
            definitional_confidence=0.9,  # Default - would come from grounding
            propagation_method="sequential_product",
            chain_length=len(rule_types)
        )

    @staticmethod
    def detect_fallacy(
        premises: List[str],
        conclusion: str,
        claimed_rule: str
    ) -> Optional[str]:
        """
        Detect common logical fallacies.

        Returns fallacy name if detected, None otherwise.

        Example:
        Premises: ["Tech companies are successful", "Google is a tech company"]
        Conclusion: "Google is successful"
        Claimed rule: "modus_ponens"

        This is actually "affirming the consequent" (fallacy).
        Valid form requires: "ALL tech companies are successful"
        """
        # Affirming the consequent
        # Pattern: "A are B", "X is A", conclude "X is B"
        # Valid only if "ALL A are B"
        if claimed_rule == "modus_ponens":
            for premise in premises:
                if ("are" in premise.lower() and
                    "all" not in premise.lower() and
                    "every" not in premise.lower()):
                    # This might be affirming consequent
                    return "affirming_the_consequent"

        # Denying the antecedent
        # Pattern: "If P then Q", "not P", conclude "not Q" (INVALID)
        if claimed_rule == "modus_tollens":
            # Check if actually denying antecedent
            if any("not" in p.lower() for p in premises):
                # Would need more sophisticated analysis
                pass

        # Hasty generalization
        # Pattern: Few examples → universal conclusion
        if claimed_rule == "universal_generalization":
            # Check if sample size is mentioned
            small_sample_indicators = ["few", "some", "a couple", "one", "two"]
            if any(ind in " ".join(premises).lower() for ind in small_sample_indicators):
                return "hasty_generalization"

        return None


class ValidityChecker:
    """
    Formal validity checker independent of LLM.

    This provides ground truth for logical validity,
    addressing the circular validation problem.
    """

    @staticmethod
    def check_modus_ponens(
        premise1: str,
        premise2: str,
        conclusion: str
    ) -> EpistemicStatus:
        """
        Check if argument follows modus ponens form:
        P → Q, P ⊢ Q

        Returns validity status with justification.
        """
        # Simplified checker - production would use full parser
        p1_lower = premise1.lower()
        p2_lower = premise2.lower()
        conc_lower = conclusion.lower()

        # Check for implication in premise1
        has_implication = ("if" in p1_lower and "then" in p1_lower) or "→" in premise1

        if has_implication:
            # Extract antecedent and consequent
            if "→" in premise1:
                parts = premise1.split("→")
            elif "then" in p1_lower:
                parts = p1_lower.split("then")
            else:
                return EpistemicStatus(
                    validity=ValidityStatus.UNKNOWN,
                    validity_confidence=0.0,
                    soundness=SoundnessStatus.UNKNOWN,
                    premise_confidences=[0.5, 0.5],
                    overall_confidence=0.0,
                    validity_justification="Could not parse implication",
                    soundness_justification="Unknown"
                )

            if len(parts) == 2:
                antecedent = parts[0].replace("if", "").strip()
                consequent = parts[1].strip()

                # Check if premise2 asserts antecedent
                if antecedent in p2_lower:
                    # Check if conclusion asserts consequent
                    if consequent in conc_lower:
                        return EpistemicStatus(
                            validity=ValidityStatus.VALID,
                            validity_confidence=0.95,
                            soundness=SoundnessStatus.UNKNOWN,  # Can't verify premises
                            premise_confidences=[0.5, 0.5],  # Unknown
                            overall_confidence=0.5,
                            validity_justification="Valid modus ponens form: P→Q, P ⊢ Q",
                            soundness_justification="Cannot verify premise truth"
                        )

        return EpistemicStatus(
            validity=ValidityStatus.INVALID,
            validity_confidence=0.9,
            soundness=SoundnessStatus.UNSOUND,
            premise_confidences=[0.5, 0.5],
            overall_confidence=0.0,
            validity_justification="Does not follow modus ponens form",
            soundness_justification="Invalid argument form"
        )

    @staticmethod
    def check_universal_instantiation(
        universal_premise: str,
        instance_premise: str,
        conclusion: str
    ) -> EpistemicStatus:
        """
        Check universal instantiation:
        ∀x P(x), a ⊢ P(a)

        Example:
        "All humans are mortal"
        "Socrates is human"
        ⊢ "Socrates is mortal"
        """
        up_lower = universal_premise.lower()
        ip_lower = instance_premise.lower()
        conc_lower = conclusion.lower()

        # Check for universal quantifier
        has_universal = any(q in up_lower for q in ["all", "every", "each"])

        if not has_universal:
            return EpistemicStatus(
                validity=ValidityStatus.INVALID,
                validity_confidence=0.95,
                soundness=SoundnessStatus.UNSOUND,
                premise_confidences=[0.5, 0.5],
                overall_confidence=0.0,
                validity_justification="Universal quantifier required for UI",
                soundness_justification="Invalid: premise not universal"
            )

        # Extract class and property
        if "are" in up_lower:
            parts = up_lower.split("are")
            if len(parts) == 2:
                category = parts[0].replace("all", "").replace("every", "").strip()
                property_pred = parts[1].strip()

                # Check if instance belongs to category
                if category in ip_lower:
                    # Check if conclusion applies property to instance
                    if property_pred in conc_lower:
                        return EpistemicStatus(
                            validity=ValidityStatus.VALID,
                            validity_confidence=0.95,
                            soundness=SoundnessStatus.UNKNOWN,
                            premise_confidences=[0.5, 0.5],
                            overall_confidence=0.5,
                            validity_justification="Valid universal instantiation: ∀x P(x), a ⊢ P(a)",
                            soundness_justification="Cannot verify premise truth"
                        )

        return EpistemicStatus(
            validity=ValidityStatus.INVALID,
            validity_confidence=0.8,
            soundness=SoundnessStatus.UNSOUND,
            premise_confidences=[0.5, 0.5],
            overall_confidence=0.0,
            validity_justification="Does not match UI form",
            soundness_justification="Invalid argument"
        )
