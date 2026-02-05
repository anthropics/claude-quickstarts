#!/usr/bin/env python3
"""
Rigorous Neuro-Symbolic Logic Demonstration

Addresses key challenges in hybrid AI systems:
1. Symbol grounding problem
2. Epistemic status vs. logical validity
3. Inference rule selection and validation
4. Confidence propagation
5. Fallacy detection
6. Unparseable fragments

This demonstrates a more rigorous approach than naive pattern matching.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from logic.grounding import (
    SemanticParser,
    SemanticContext,
    create_ml_context,
    QuantifierType,
    ModalityType
)
from logic.epistemic import (
    EpistemicStatus,
    ConfidenceCalculator,
    ValidityChecker,
    ValidityStatus,
    SoundnessStatus
)


def demo_symbol_grounding():
    """
    DEMO 1: Symbol Grounding Problem

    Shows how context-dependent meaning is handled explicitly.
    """
    print("\n" + "=" * 70)
    print("DEMO 1: SYMBOL GROUNDING PROBLEM")
    print("=" * 70)

    # Create ML-specific semantic context
    ml_context = create_ml_context()

    print("\n📚 Semantic Context: Machine Learning Domain")
    print(f"  Predicates defined: {list(ml_context.predicates.keys())}")
    print(f"\n  'biased' in ML context:")
    print(f"    → {ml_context.predicates['biased']}")

    # Parse statement with context
    parser = SemanticParser(ml_context)

    statement = "All ML models trained on biased data produce biased outputs"

    print(f"\n📝 Parsing: '{statement}'")

    result = parser.parse(statement)

    print(f"\n✅ Parse Result:")
    print(f"  Success: {result.success}")
    print(f"  Logical Form: {result.logical_form}")
    print(f"  Confidence: {result.confidence:.1%}")

    if result.assumptions:
        print(f"\n⚠️  Assumptions Made:")
        for assumption in result.assumptions:
            print(f"    • {assumption}")

    if result.unparseable_fragments:
        print(f"\n❌ Unparseable Fragments:")
        for fragment in result.unparseable_fragments:
            print(f"    • {fragment}")


def demo_quantification_types():
    """
    DEMO 2: Different Quantification Types

    Shows how "all", "most", "some", "generic" are handled differently.
    """
    print("\n" + "=" * 70)
    print("DEMO 2: QUANTIFICATION TYPES")
    print("=" * 70)

    context = create_ml_context()
    parser = SemanticParser(context)

    test_cases = [
        "All birds can fly",  # Universal - ∀x(Bird(x) → Fly(x))
        "Some birds can fly",  # Existential - ∃x(Bird(x) ∧ Fly(x))
        "Birds fly",  # Generic - Gen x(Bird(x) → Fly(x))
        "Most birds can fly",  # UNPARSEABLE in first-order logic
    ]

    for statement in test_cases:
        print(f"\n📝 '{statement}'")
        result = parser.parse(statement)

        print(f"  Quantifier: {result.quantifier.value if result.quantifier else 'none'}")
        print(f"  Success: {result.success}")

        if result.success:
            print(f"  Logical Form: {result.logical_form}")
            print(f"  Confidence: {result.confidence:.1%}")
        else:
            print(f"  ❌ Cannot formalize in first-order logic:")
            for fragment in result.unparseable_fragments:
                print(f"     • {fragment}")

        if result.assumptions:
            print(f"  ⚠️  Assumptions:")
            for assumption in result.assumptions:
                print(f"     • {assumption}")


def demo_epistemic_vs_validity():
    """
    DEMO 3: Epistemic Status vs. Logical Validity

    Shows the difference between:
    - Valid but unsound (structurally correct, premises false)
    - Invalid but believable (premises true, structure wrong)
    """
    print("\n" + "=" * 70)
    print("DEMO 3: EPISTEMIC STATUS VS. LOGICAL VALIDITY")
    print("=" * 70)

    checker = ValidityChecker()

    # Case 1: Valid but absurd (Socrates is a fish example)
    print("\n🔹 Case 1: Valid but Absurd")
    print("  Premise 1: If Socrates is a fish, then Socrates can swim")
    print("  Premise 2: Socrates is a fish")
    print("  Conclusion: Socrates can swim")

    status1 = checker.check_modus_ponens(
        "If Socrates is a fish, then Socrates can swim",
        "Socrates is a fish",
        "Socrates can swim"
    )

    print(f"\n  Validity: {status1.validity.value}")
    print(f"  Validity Confidence: {status1.validity_confidence:.1%}")
    print(f"  Soundness: {status1.soundness.value}")
    print(f"  Overall Confidence: {status1.overall_confidence:.1%}")
    print(f"  Justification: {status1.validity_justification}")
    print(f"\n  💡 This argument is VALID (correct structure)")
    print(f"     but UNSOUND (premise 2 is false)")

    # Case 2: Invalid but believable
    print("\n🔹 Case 2: Invalid but Believable")
    print("  Premise 1: Tech companies are successful")
    print("  Premise 2: Google is a tech company")
    print("  Conclusion: Google is successful")

    # This looks like modus ponens but isn't (missing universal quantifier)
    print(f"\n  ❌ FALLACY: Affirming the Consequent")
    print(f"     Missing: 'ALL tech companies are successful'")
    print(f"     Actual: 'Tech companies are successful' (generic/existential)")

    # Detect the fallacy
    from logic.epistemic import ConfidenceCalculator
    fallacy = ConfidenceCalculator.detect_fallacy(
        ["Tech companies are successful", "Google is a tech company"],
        "Google is successful",
        "modus_ponens"
    )

    if fallacy:
        print(f"\n  🚨 Detected Fallacy: {fallacy}")


def demo_confidence_propagation():
    """
    DEMO 4: Explicit Confidence Propagation

    Shows exactly how confidence is calculated through reasoning chains.
    """
    print("\n" + "=" * 70)
    print("DEMO 4: CONFIDENCE PROPAGATION")
    print("=" * 70)

    calc = ConfidenceCalculator()

    # Example chain:
    # P1: All ML models trained on biased data produce biased outputs (0.7)
    # P2: GPT-4 was trained on biased data (0.6)
    # R1: Universal instantiation (0.9)
    # C: GPT-4 produces biased outputs (?)

    print("\n📊 Reasoning Chain:")
    print("  P1: All ML models trained on biased data produce biased outputs")
    print("      Confidence: 0.7")
    print("  P2: GPT-4 was trained on biased data")
    print("      Confidence: 0.6")
    print("  R1: Universal Instantiation")
    print("      Confidence: 0.9")
    print("  C: GPT-4 produces biased outputs")
    print("      Confidence: ?")

    breakdown = calc.multi_step_chain(
        premise_confidences=[0.7, 0.6],
        rule_confidences=[0.9],
        rule_types=["universal_instantiation"]
    )

    print(f"\n🔬 Confidence Breakdown:")
    print(f"  Logical Confidence: {breakdown.logical_confidence:.1%}")
    print(f"    (How confident are we the argument is valid?)")
    print(f"  Source Confidence: {breakdown.source_confidence:.1%}")
    print(f"    (How confident are we the premises are true?)")
    print(f"  Propagation Method: {breakdown.propagation_method}")
    print(f"  Chain Length: {breakdown.chain_length}")

    # Show different propagation methods
    print(f"\n📉 Confidence Degradation with Chain Length:")

    for chain_length in [1, 3, 5, 10]:
        confidences = [0.9] * chain_length
        result = calc.conjunctive_chain(confidences)
        print(f"  {chain_length} steps at 0.9 each → {result:.1%}")

    print(f"\n💡 Observation: Confidence degrades exponentially with chain length")
    print(f"   This is why shorter proofs are preferred!")


def demo_modality_detection():
    """
    DEMO 5: Modality Detection

    Shows what types of reasoning can't be handled in first-order logic.
    """
    print("\n" + "=" * 70)
    print("DEMO 5: MODALITY DETECTION")
    print("=" * 70)

    context = create_ml_context()
    parser = SemanticParser(context)

    cases = [
        ("Most birds can fly", "requires higher-order logic"),
        ("John believes Mary is happy", "requires epistemic logic"),
        ("It's illegal to drive without insurance", "requires deontic logic"),
        ("The water boiled because it was heated", "requires causal logic"),
        ("All humans are mortal", "standard first-order logic"),
    ]

    for statement, expected in cases:
        print(f"\n📝 '{statement}'")
        result = parser.parse(statement)

        if result.modality:
            print(f"  Modality: {result.modality.value}")

        if result.success:
            print(f"  ✅ Parseable: {result.logical_form}")
        else:
            print(f"  ❌ Unparseable in FOL")
            if result.unparseable_fragments:
                print(f"     Reason: {result.unparseable_fragments[0]}")

        print(f"  Expected: {expected}")


def demo_fallacy_detection():
    """
    DEMO 6: Fallacy Detection

    Independent validation of LLM-generated reasoning.
    """
    print("\n" + "=" * 70)
    print("DEMO 6: FALLACY DETECTION")
    print("=" * 70)

    calc = ConfidenceCalculator()

    fallacy_cases = [
        {
            "name": "Affirming the Consequent",
            "premises": ["If it rains, the ground is wet", "The ground is wet"],
            "conclusion": "It rained",
            "claimed_rule": "modus_ponens",
            "expected_fallacy": "affirming_the_consequent"
        },
        {
            "name": "Missing Universal Quantifier",
            "premises": ["Tech companies are successful", "Google is a tech company"],
            "conclusion": "Google is successful",
            "claimed_rule": "modus_ponens",
            "expected_fallacy": "affirming_the_consequent"
        },
        {
            "name": "Hasty Generalization",
            "premises": ["Some swans I've seen are white"],
            "conclusion": "All swans are white",
            "claimed_rule": "universal_generalization",
            "expected_fallacy": "hasty_generalization"
        },
    ]

    for case in fallacy_cases:
        print(f"\n🔍 Testing: {case['name']}")
        print(f"  Premises: {', '.join(case['premises'])}")
        print(f"  Conclusion: {case['conclusion']}")
        print(f"  Claimed Rule: {case['claimed_rule']}")

        detected = calc.detect_fallacy(
            case['premises'],
            case['conclusion'],
            case['claimed_rule']
        )

        if detected:
            print(f"  🚨 FALLACY DETECTED: {detected}")
            print(f"  ✅ Matches expected: {detected == case['expected_fallacy']}")
        else:
            print(f"  ❌ No fallacy detected (but expected: {case['expected_fallacy']})")


def main():
    """Run all rigorous logic demonstrations."""
    print("\n" + "=" * 70)
    print("RIGOROUS NEURO-SYMBOLIC LOGIC SYSTEM")
    print("=" * 70)
    print("\nAddressing Key Challenges:")
    print("  1. Symbol Grounding Problem")
    print("  2. Epistemic Status vs. Logical Validity")
    print("  3. Quantification Types")
    print("  4. Confidence Propagation")
    print("  5. Modality Detection")
    print("  6. Fallacy Detection")
    print("=" * 70)

    demos = [
        ("Symbol Grounding", demo_symbol_grounding),
        ("Quantification Types", demo_quantification_types),
        ("Epistemic vs. Validity", demo_epistemic_vs_validity),
        ("Confidence Propagation", demo_confidence_propagation),
        ("Modality Detection", demo_modality_detection),
        ("Fallacy Detection", demo_fallacy_detection),
    ]

    for name, demo_func in demos:
        try:
            input(f"\nPress Enter to run: {name}...")
            demo_func()
        except KeyboardInterrupt:
            print("\n\nDemo interrupted by user.")
            break
        except Exception as e:
            print(f"\n❌ Error in {name}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print("KEY TAKEAWAYS")
    print("=" * 70)
    print("\n1️⃣ SYMBOL GROUNDING:")
    print("   • Context determines meaning (biased_ML ≠ biased_cognitive)")
    print("   • Make grounding explicit, not assumed")
    print("   • Track unparseable fragments")

    print("\n2️⃣ EPISTEMIC STATUS:")
    print("   • Separate validity (structure) from soundness (truth)")
    print("   • Valid ≠ believable (Socrates is a fish)")
    print("   • Invalid ≠ unbelievable (tech company example)")

    print("\n3️⃣ QUANTIFICATION:")
    print("   • 'All' ≠ 'most' ≠ 'some' ≠ generic plural")
    print("   • First-order logic can't express 'most'")
    print("   • Generics have exceptions (birds fly → penguins don't)")

    print("\n4️⃣ CONFIDENCE CALCULUS:")
    print("   • Explicit propagation rules (product, complement)")
    print("   • Separate logical, empirical, source confidence")
    print("   • Chain length matters (0.9^10 = 0.35)")

    print("\n5️⃣ MODALITY:")
    print("   • Beliefs, obligations, causation need specialized logics")
    print("   • FOL can't express 'because', 'should', 'knows'")
    print("   • Detect when reasoning exceeds formalism")

    print("\n6️⃣ FALLACY DETECTION:")
    print("   • Independent validation of LLM outputs")
    print("   • Affirming consequent, hasty generalization, etc.")
    print("   • Don't trust LLM to label its own reasoning")

    print("\n" + "=" * 70)
    print("NEXT STEPS FOR PRODUCTION SYSTEM")
    print("=" * 70)
    print("\n• Full NLP parser (dependency trees, semantic roles)")
    print("• Automated theorem prover (Coq, Lean, Isabelle)")
    print("• Probabilistic logic (Markov Logic Networks)")
    print("• Contradiction detection & resolution")
    print("• Ground truth oracles (external validation)")
    print("• Higher-order logic for 'most', 'few', etc.")
    print("• Modal logics for beliefs, time, causation")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
