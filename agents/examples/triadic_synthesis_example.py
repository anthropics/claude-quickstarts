"""
Triadic Synthesis Example: Logic + AI + User → Reason

This example demonstrates how the three layers interact to produce reasoned output:

1. LOGIC (Skeleton): Validates structural correctness
2. AI (Muscles): Provides multiple interpretive perspectives
3. USER (Heart): Selects values and makes final judgment
4. REASON (Emergent): Synthesis of all three

Scenario: Analyzing an argument about economic policy
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum


# ==================== LOGIC LAYER (Skeleton) ====================

class LogicValidation:
    """Pure logical validation - no interpretation."""

    @staticmethod
    def validate_argument(premises: List[str], conclusion: str) -> Dict[str, Any]:
        """
        Validates argument structure.

        Returns ONLY structural validity, not truth or value.
        """
        # Simplified validation logic
        has_conditional = any("if" in p.lower() or "→" in p for p in premises)
        has_support = len(premises) >= 2

        valid = has_conditional and has_support

        return {
            "valid": valid,
            "confidence": 1.0,  # Logic is certain about structure
            "form": "conditional_argument" if valid else "incomplete",
            "explanation": "Valid structure" if valid else "Missing premises",
            "layer": "LOGIC"
        }


# ==================== AI LAYER (Muscles) ====================

class InterpretiveProfile(Enum):
    """Different intellectual traditions as interpretive lenses."""
    MARX = "marx"
    FREUD = "freud"
    BLACKSTONE = "blackstone"
    RAWLS = "rawls"


@dataclass
class Perspective:
    """A single interpretive perspective from AI."""
    profile: InterpretiveProfile
    interpretation: str
    confidence: float  # Always < 1.0 for non-formal interpretations
    reasoning: str
    concerns: List[str]


class AIInterpretation:
    """AI provides multiple perspectives, not singular truth."""

    @staticmethod
    def interpret_from_profile(
        argument: str,
        profile: InterpretiveProfile
    ) -> Perspective:
        """
        Interprets argument through a specific intellectual lens.

        Returns perspective, NOT verdict.
        """
        if profile == InterpretiveProfile.MARX:
            return Perspective(
                profile=profile,
                interpretation="This argument may reflect class interests",
                confidence=0.70,
                reasoning="Economic policies typically benefit specific classes",
                concerns=[
                    "Who benefits from this policy?",
                    "Does it perpetuate economic inequality?",
                    "What are the material conditions?"
                ]
            )

        elif profile == InterpretiveProfile.FREUD:
            return Perspective(
                profile=profile,
                interpretation="The argument may contain unconscious motivations",
                confidence=0.65,
                reasoning="Economic anxiety often masks deeper psychological needs",
                concerns=[
                    "What unconscious fears drive this position?",
                    "Is this a defense mechanism?",
                    "What is the latent content?"
                ]
            )

        elif profile == InterpretiveProfile.BLACKSTONE:
            return Perspective(
                profile=profile,
                interpretation="The argument has legal implications",
                confidence=0.75,
                reasoning="Policy arguments must consider legal precedent",
                concerns=[
                    "Does this violate established law?",
                    "What is the constitutional basis?",
                    "Are property rights respected?"
                ]
            )

        elif profile == InterpretiveProfile.RAWLS:
            return Perspective(
                profile=profile,
                interpretation="Consider fairness behind the veil of ignorance",
                confidence=0.72,
                reasoning="Just policies should be acceptable from any social position",
                concerns=[
                    "Would you accept this policy if you were disadvantaged?",
                    "Does it maximize benefit to the least advantaged?",
                    "Is it fair regardless of your position?"
                ]
            )

    @staticmethod
    def provide_multiple_perspectives(
        argument: str,
        profiles: List[InterpretiveProfile]
    ) -> List[Perspective]:
        """
        Returns MULTIPLE interpretations, never auto-selecting "best".
        """
        perspectives = []

        for profile in profiles:
            p = AIInterpretation.interpret_from_profile(argument, profile)
            perspectives.append(p)

        # AI does NOT select "best" - user decides
        return perspectives


# ==================== USER LAYER (Heart) ====================

@dataclass
class UserPreferences:
    """User's values, weightings, and preferences."""
    user_id: str
    profile_weights: Dict[InterpretiveProfile, float]
    values: Dict[str, float]
    constraints: List[str]


class UserContext:
    """Captures user intent and allows user control."""

    @staticmethod
    def get_user_preferences(user_id: str) -> UserPreferences:
        """
        Retrieves user's persistent preferences.

        User has previously indicated which lenses they trust.
        """
        # In practice, load from database
        # Here, we simulate user who trusts Marxist and Rawlsian analyses
        return UserPreferences(
            user_id=user_id,
            profile_weights={
                InterpretiveProfile.MARX: 0.8,
                InterpretiveProfile.FREUD: 0.3,
                InterpretiveProfile.BLACKSTONE: 0.5,
                InterpretiveProfile.RAWLS: 0.9,
            },
            values={
                "fairness": 0.9,
                "economic_equality": 0.8,
                "legal_correctness": 0.6,
            },
            constraints=[
                "Must not violate human rights",
                "Must consider impact on disadvantaged",
            ]
        )

    @staticmethod
    def request_clarification(question: str) -> str:
        """
        Asks user for clarification when intent is ambiguous.

        System NEVER guesses - always asks.
        """
        # In practice, this would trigger UI
        print(f"\n[CLARIFICATION NEEDED]: {question}")
        # Simulated user response
        return "I care most about fairness and equality"

    @staticmethod
    def user_override(
        system_suggestion: str,
        user_choice: Optional[str]
    ) -> str:
        """
        Allows user to override any system recommendation.

        User agency is preserved.
        """
        if user_choice:
            print(f"\n[USER OVERRIDE]: User chose '{user_choice}' over system suggestion '{system_suggestion}'")
            return user_choice
        return system_suggestion


# ==================== SYNTHESIS LAYER (Reason) ====================

@dataclass
class SynthesizedDecision:
    """
    The emergent output: Reason

    Arises from interaction of Logic + AI + User
    """
    recommendation: str
    confidence: float
    provenance: Dict[str, Any]
    explanation: str
    requires_user_approval: bool


class TriadicSynthesis:
    """
    Synthesizes Logic + AI + User into Reason.

    Reason is NOT calculated by any single layer - it EMERGES.
    """

    @staticmethod
    def synthesize(
        logic_validation: Dict[str, Any],
        ai_perspectives: List[Perspective],
        user_prefs: UserPreferences
    ) -> SynthesizedDecision:
        """
        Produces reasoned output from three layers.

        All three layers must contribute.
        """
        # STEP 1: Check logical validity (Skeleton blocks if invalid)
        if not logic_validation["valid"]:
            return SynthesizedDecision(
                recommendation="Cannot proceed - invalid logical structure",
                confidence=0.0,
                provenance={
                    "logic": logic_validation,
                    "reason": "Skeleton blocks: invalid structure"
                },
                explanation="The argument has an invalid logical form. Logic prevents synthesis.",
                requires_user_approval=False
            )

        # STEP 2: Weight AI perspectives by user preferences (Muscles + Heart)
        weighted_perspectives = []
        for perspective in ai_perspectives:
            user_weight = user_prefs.profile_weights.get(perspective.profile, 0.5)
            weighted_conf = perspective.confidence * user_weight
            weighted_perspectives.append((perspective, weighted_conf))

        # Sort by weighted confidence
        weighted_perspectives.sort(key=lambda x: x[1], reverse=True)

        # STEP 3: Synthesize based on user values
        # The user values fairness (0.9) and equality (0.8)
        # So Rawls (fairness) and Marx (equality) should dominate

        top_perspectives = weighted_perspectives[:2]  # Top 2 weighted

        synthesis = []
        total_weight = sum(w for _, w in top_perspectives)

        for perspective, weight in top_perspectives:
            contribution = weight / total_weight if total_weight > 0 else 0
            synthesis.append(
                f"{perspective.profile.value.capitalize()} perspective ({contribution:.0%}): "
                f"{perspective.interpretation}"
            )

        # STEP 4: Generate explanation with provenance
        explanation = f"""
        SYNTHESIS OF THREE LAYERS:

        1. LOGIC (Skeleton): {logic_validation['explanation']}
           - Structure is valid, reasoning can proceed

        2. AI (Muscles): {len(ai_perspectives)} perspectives considered
           {chr(10).join(f'   - {s}' for s in synthesis)}

        3. USER (Heart): Applied your preferences
           - Fairness weight: {user_prefs.values.get('fairness', 0):.0%}
           - Equality weight: {user_prefs.values.get('economic_equality', 0):.0%}
           - Emphasized: {', '.join(p.profile.value for p, _ in top_perspectives)}

        4. REASON (Emergent): Based on this synthesis, the argument should be
           evaluated primarily through fairness and equality lenses.
        """

        # Compute synthesis confidence
        # Not just AI confidence - weighted by user preferences
        synth_confidence = sum(w for _, w in top_perspectives) / len(weighted_perspectives)

        recommendation = (
            f"Consider this argument through {top_perspectives[0][0].profile.value.capitalize()} "
            f"and {top_perspectives[1][0].profile.value.capitalize()} lenses, "
            f"emphasizing {', '.join(user_prefs.constraints)}"
        )

        return SynthesizedDecision(
            recommendation=recommendation,
            confidence=synth_confidence,
            provenance={
                "logic_layer": logic_validation,
                "ai_layer": [
                    {
                        "profile": p.profile.value,
                        "interpretation": p.interpretation,
                        "confidence": p.confidence,
                        "user_weight": user_prefs.profile_weights.get(p.profile, 0.5),
                        "weighted_confidence": w
                    }
                    for p, w in weighted_perspectives
                ],
                "user_layer": {
                    "user_id": user_prefs.user_id,
                    "values_applied": user_prefs.values,
                    "constraints": user_prefs.constraints
                }
            },
            explanation=explanation.strip(),
            requires_user_approval=True  # High-stakes = user approval required
        )


# ==================== DEMONSTRATION ====================

def demonstrate_triadic_synthesis():
    """
    Shows the full triadic synthesis in action.
    """
    print("=" * 70)
    print(" TRIADIC SYNTHESIS DEMONSTRATION")
    print(" Logic (Skeleton) + AI (Muscles) + User (Heart) → Reason (Emergent)")
    print("=" * 70)

    # The argument to analyze
    argument = """
    If we increase minimum wage, then workers will have more purchasing power.
    We should increase minimum wage.
    Therefore, workers will have more purchasing power.
    """

    premises = [
        "If we increase minimum wage, then workers will have more purchasing power",
        "We should increase minimum wage"
    ]
    conclusion = "Workers will have more purchasing power"

    print("\n📋 ARGUMENT:")
    print(argument)

    # ====== LAYER 1: LOGIC (Skeleton) ======
    print("\n" + "=" * 70)
    print("🔲 LAYER 1: LOGIC (Skeleton)")
    print("   Role: Validates structural correctness")
    print("=" * 70)

    logic_result = LogicValidation.validate_argument(premises, conclusion)

    print(f"\n   Valid: {logic_result['valid']}")
    print(f"   Form: {logic_result['form']}")
    print(f"   Confidence: {logic_result['confidence']} (logic is certain)")
    print("   Note: Logic says NOTHING about truth, value, or meaning")

    # ====== LAYER 2: AI (Muscles) ======
    print("\n" + "=" * 70)
    print("💪 LAYER 2: AI (Muscles)")
    print("   Role: Provides multiple interpretive perspectives")
    print("=" * 70)

    profiles_to_use = [
        InterpretiveProfile.MARX,
        InterpretiveProfile.RAWLS,
        InterpretiveProfile.BLACKSTONE,
        InterpretiveProfile.FREUD
    ]

    ai_perspectives = AIInterpretation.provide_multiple_perspectives(
        argument,
        profiles_to_use
    )

    for p in ai_perspectives:
        print(f"\n   {p.profile.value.upper()} Perspective:")
        print(f"      Interpretation: {p.interpretation}")
        print(f"      Confidence: {p.confidence:.0%} (AI is uncertain)")
        print(f"      Key Concerns: {', '.join(p.concerns[:2])}")

    print(f"\n   Note: AI provides {len(ai_perspectives)} perspectives, NOT a verdict")
    print("   Note: AI does NOT select 'best' - user decides")

    # ====== LAYER 3: USER (Heart) ======
    print("\n" + "=" * 70)
    print("❤️  LAYER 3: USER (Heart)")
    print("   Role: Determines purpose, values, and final judgment")
    print("=" * 70)

    user_prefs = UserContext.get_user_preferences("user_001")

    print(f"\n   User ID: {user_prefs.user_id}")
    print("   Profile Weights:")
    for profile, weight in user_prefs.profile_weights.items():
        print(f"      {profile.value.capitalize()}: {weight:.0%}")

    print("\n   User Values:")
    for value, importance in user_prefs.values.items():
        print(f"      {value}: {importance:.0%}")

    print("\n   User Constraints:")
    for constraint in user_prefs.constraints:
        print(f"      - {constraint}")

    print("\n   Note: User weighs perspectives based on personal values")
    print("   Note: User can override any system suggestion")

    # ====== LAYER 4: REASON (Emergent Synthesis) ======
    print("\n" + "=" * 70)
    print("✨ LAYER 4: REASON (Emergent Synthesis)")
    print("   Role: Arises from interaction of all three layers")
    print("=" * 70)

    synthesis = TriadicSynthesis.synthesize(
        logic_result,
        ai_perspectives,
        user_prefs
    )

    print(f"\n   Recommendation: {synthesis.recommendation}")
    print(f"   Confidence: {synthesis.confidence:.0%}")
    print(f"   Requires User Approval: {synthesis.requires_user_approval}")

    print(f"\n   {synthesis.explanation}")

    print("\n" + "=" * 70)
    print("🔍 PROVENANCE TRACE")
    print("=" * 70)

    print("\n   Logic Layer Contribution:")
    print(f"      Valid: {synthesis.provenance['logic_layer']['valid']}")
    print(f"      Form: {synthesis.provenance['logic_layer']['form']}")

    print("\n   AI Layer Contribution:")
    for ai_contrib in synthesis.provenance['ai_layer']:
        print(f"      {ai_contrib['profile'].capitalize()}: "
              f"confidence={ai_contrib['confidence']:.0%}, "
              f"user_weight={ai_contrib['user_weight']:.0%}, "
              f"weighted={ai_contrib['weighted_confidence']:.2f}")

    print("\n   User Layer Contribution:")
    print(f"      Values: {synthesis.provenance['user_layer']['values_applied']}")
    print(f"      Constraints: {synthesis.provenance['user_layer']['constraints']}")

    print("\n" + "=" * 70)
    print("🎯 KEY INSIGHTS")
    print("=" * 70)

    print("""
    1. LOGIC (Skeleton) provided the frame:
       - Validated structure (can't proceed if invalid)
       - Did NOT judge truth or value

    2. AI (Muscles) extended reasoning:
       - Provided 4 different perspectives
       - Did NOT claim any is "correct"
       - Expressed uncertainty (confidence < 1.0)

    3. USER (Heart) determined meaning:
       - Weighted perspectives based on personal values
       - Emphasized fairness and equality
       - Retained final decision authority

    4. REASON emerged from interaction:
       - Not calculated by any single layer
       - Traceable to all three sources
       - Respects all three constraints

    This is not:
       - Logic alone (would just say "valid structure")
       - AI alone (would provide interpretations without user values)
       - User alone (would lack rigorous structure and diverse perspectives)

    This IS:
       - A synthesis that respects structural validity (skeleton)
       - Extends cognitive reach (muscles)
       - Preserves human agency (heart)
       - Produces contextual, value-aligned reason (emergent)
    """)

    print("\n" + "=" * 70)
    print(" END DEMONSTRATION")
    print("=" * 70)


if __name__ == "__main__":
    demonstrate_triadic_synthesis()
