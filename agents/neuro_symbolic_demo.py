#!/usr/bin/env python3
"""
Neuro-Symbolic Agent Demonstration

Shows how to combine ML-powered reasoning (backend) with
formal logic systems (frontend) for transparent, verifiable AI reasoning.

This demonstrates:
1. Knowledge base with formal logic
2. Extended chain-of-thought reasoning
3. Formal argument construction
4. Logic-weighted consensus
5. Validation against knowledge base
"""

import sys
from pathlib import Path

# Add agents directory to path
sys.path.insert(0, str(Path(__file__).parent))

from logic import (
    ReasoningAgent,
    LogicType
)


def demo_basic_reasoning():
    """Demonstrate basic logical reasoning with neuro-symbolic agent."""
    print("\n" + "=" * 70)
    print("DEMO 1: BASIC LOGICAL REASONING")
    print("=" * 70)

    # Create reasoning agent with first-order logic
    agent = ReasoningAgent(
        name="Critical Thinker",
        system_prompt="An agent that uses extended chain-of-thought reasoning with formal logic",
        logic_framework=LogicType.FIRST_ORDER,
        reasoning_depth=3,
        logic_weight=0.75,  # Prioritize logic over consensus
        verbose=True
    )

    # Add knowledge to the knowledge base
    print("\n📚 Building Knowledge Base...")
    agent.add_knowledge(
        "All software engineers write code",
        source="domain_knowledge",
        confidence=1.0
    )
    agent.add_knowledge(
        "Alice is a software engineer",
        source="user_input",
        confidence=1.0
    )

    # Query the agent
    query = "What can we conclude about Alice?"

    print(f"\n❓ Query: {query}")

    result = agent.reason(query)

    # Display formal argument
    print("\n📜 FORMAL ARGUMENT:")
    print("=" * 70)
    formatter = agent.argument_builder.formatter
    print(formatter.format_argument(result["formal_argument"]))

    return agent


def demo_complex_reasoning():
    """Demonstrate complex multi-step reasoning."""
    print("\n" + "=" * 70)
    print("DEMO 2: COMPLEX MULTI-STEP REASONING")
    print("=" * 70)

    agent = ReasoningAgent(
        name="Logic Analyzer",
        system_prompt="Specialized in complex logical deduction",
        logic_framework=LogicType.FIRST_ORDER,
        reasoning_depth=5,
        verbose=True
    )

    # Build a more complex knowledge base
    print("\n📚 Building Complex Knowledge Base...")

    knowledge_facts = [
        ("All ML models trained on biased data produce biased outputs", 0.95),
        ("GPT-4 is an ML model", 1.0),
        ("GPT-4 was trained on internet data", 0.95),
        ("Internet data contains bias", 0.9),
    ]

    for fact, confidence in knowledge_facts:
        agent.add_knowledge(fact, source="research", confidence=confidence)
        print(f"  ✓ Added: {fact} (confidence: {confidence:.0%})")

    # Complex query requiring multiple inference steps
    query = "Does GPT-4 produce biased outputs?"

    print(f"\n❓ Complex Query: {query}")

    agent.reason(query)

    print("\n📊 Knowledge Base Statistics:")
    stats = agent.get_knowledge_stats()
    for key, value in stats.items():
        print(f"  • {key}: {value}")

    return agent


def demo_logic_types():
    """Demonstrate different logic systems."""
    print("\n" + "=" * 70)
    print("DEMO 3: DIFFERENT LOGIC SYSTEMS")
    print("=" * 70)

    logic_types = [
        LogicType.PROPOSITIONAL,
        LogicType.FIRST_ORDER,
        LogicType.MODAL
    ]

    for logic_type in logic_types:
        print(f"\n🔷 Testing with {logic_type.value.upper()} logic")

        agent = ReasoningAgent(
            name=f"{logic_type.value.capitalize()} Reasoner",
            system_prompt=f"Agent using {logic_type.value} logic",
            logic_framework=logic_type,
            verbose=False
        )

        agent.add_knowledge("If it rains, the ground is wet")
        agent.add_knowledge("It is raining")

        result = agent.reason("Is the ground wet?")

        print(f"  Conclusion: {result['conclusion']}")
        print(f"  Formal: {result['formal_conclusion']}")
        print(f"  Confidence: {result['confidence']:.1%}")


def demo_inference_rules():
    """Demonstrate different inference rules."""
    print("\n" + "=" * 70)
    print("DEMO 4: INFERENCE RULES IN ACTION")
    print("=" * 70)

    agent = ReasoningAgent(
        name="Inference Demonstrator",
        system_prompt="Demonstrates various inference rules",
        logic_framework=LogicType.FIRST_ORDER,
        verbose=False
    )

    # Modus Ponens: P, P→Q ⊢ Q
    print("\n🔹 MODUS PONENS")
    agent.add_knowledge("If it rains, the ground is wet")
    agent.add_knowledge("It is raining")
    result = agent.reason("Is the ground wet?")
    print("  P: It is raining")
    print("  P→Q: If it rains, the ground is wet")
    print(f"  ∴ Q: {result['conclusion']}")
    print(f"  Confidence: {result['confidence']:.1%}")

    # Universal Instantiation: ∀x P(x) ⊢ P(a)
    print("\n🔹 UNIVERSAL INSTANTIATION")
    agent.add_knowledge("All humans are mortal")
    agent.add_knowledge("Socrates is human")
    result = agent.reason("Is Socrates mortal?")
    print("  ∀x(Human(x) → Mortal(x))")
    print("  Human(Socrates)")
    print(f"  ∴ {result['formal_conclusion']}")
    print(f"  Natural language: {result['conclusion']}")
    print(f"  Confidence: {result['confidence']:.1%}")


def demo_knowledge_validation():
    """Demonstrate knowledge base validation."""
    print("\n" + "=" * 70)
    print("DEMO 5: KNOWLEDGE VALIDATION")
    print("=" * 70)

    agent = ReasoningAgent(
        name="Validator",
        system_prompt="Validates claims against knowledge base",
        logic_framework=LogicType.FIRST_ORDER,
        verbose=False
    )

    # Add knowledge
    agent.add_knowledge("All birds have wings")
    agent.add_knowledge("Penguins are birds")
    agent.add_knowledge("Penguins cannot fly")

    # Validate claims
    claims = [
        "Penguins have wings",  # Can be inferred
        "Penguins can fly",  # Contradicts known fact
        "All birds can fly",  # Cannot be inferred (counter-example exists)
    ]

    for claim in claims:
        print(f"\n📋 Validating: '{claim}'")
        validation = agent.knowledge_base.validate(claim, use_ml=False)

        print(f"  Valid: {validation.valid}")
        print(f"  Confidence: {validation.confidence:.1%}")
        print(f"  Sources: {', '.join(validation.sources) if validation.sources else 'None'}")

        if validation.reasoning_chain:
            print("  Reasoning:")
            for step in validation.reasoning_chain:
                print(f"    • {step}")


def demo_argument_structure():
    """Demonstrate formal argument structure visualization."""
    print("\n" + "=" * 70)
    print("DEMO 6: FORMAL ARGUMENT STRUCTURE")
    print("=" * 70)

    agent = ReasoningAgent(
        name="Argument Builder",
        system_prompt="Constructs formal logical arguments",
        logic_framework=LogicType.FIRST_ORDER,
        reasoning_depth=4,
        verbose=False
    )

    # Build knowledge base for complex argument
    agent.add_knowledge("All organisms need energy to survive")
    agent.add_knowledge("Plants are organisms")
    agent.add_knowledge("Photosynthesis produces energy")
    agent.add_knowledge("Plants perform photosynthesis")

    result = agent.reason("Do plants need photosynthesis to survive?")

    print("\n📊 ARGUMENT BREAKDOWN:")
    print("=" * 70)

    print("\nPremises:")
    for i, step in enumerate(result["reasoning_chain"], 1):
        print(f"  P{i}: {step['premise']}")

    print("\nInference Chain:")
    for i, step in enumerate(result["reasoning_chain"], 1):
        print(f"  Step {i}: {step['premise']}")
        print(f"         → [{step['rule']}]")
        print(f"         → {step['conclusion']}")
        print(f"         (confidence: {step['confidence']:.1%})")

    print(f"\n∴ Final Conclusion: {result['conclusion']}")
    print(f"  Overall Confidence: {result['confidence']:.1%}")

    # Show formal representation
    print("\n" + "=" * 70)
    print("FORMAL REPRESENTATION:")
    print("=" * 70)
    formatter = agent.argument_builder.formatter
    print(formatter.format_argument(result["formal_argument"]))


def main():
    """Run all demonstrations."""
    print("\n" + "=" * 70)
    print("NEURO-SYMBOLIC REASONING AGENT DEMONSTRATION")
    print("=" * 70)
    print("\nCombining ML-Powered Reasoning with Formal Logic")
    print("Backend: Machine Learning (Extended Thinking)")
    print("Frontend: Symbolic Logic (Formal Arguments)")
    print("=" * 70)

    demos = [
        ("Basic Reasoning", demo_basic_reasoning),
        ("Complex Multi-Step Reasoning", demo_complex_reasoning),
        ("Different Logic Systems", demo_logic_types),
        ("Inference Rules", demo_inference_rules),
        ("Knowledge Validation", demo_knowledge_validation),
        ("Argument Structure", demo_argument_structure),
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
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)
    print("\n✅ Key Takeaways:")
    print("  1. ML backend provides flexible, powerful reasoning")
    print("  2. Logic frontend ensures transparency and verifiability")
    print("  3. Knowledge base enables validation and fact-checking")
    print("  4. Formal arguments make reasoning explicit and auditable")
    print("  5. Different logic systems support different reasoning needs")
    print("\n💡 This hybrid approach combines the best of both worlds:")
    print("  • Neural networks: Learning, generalization, handling ambiguity")
    print("  • Symbolic logic: Transparency, verification, formal guarantees")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
