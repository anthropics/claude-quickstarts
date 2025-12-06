#!/usr/bin/env python3
"""
Full Neuro-Symbolic Integration with Agent Framework

Integrates:
1. Agent class (from agent.py) - for LLM interaction
2. ExtendedThinkingTool (from tools/extended_thinking.py) - for chain-of-thought
3. ReasoningAgent (from logic/reasoning_agent.py) - for formal logic
4. KnowledgeBase (from logic/knowledge_base.py) - for knowledge management

This demonstrates the complete architecture:
- Backend: ML-powered reasoning via Claude with extended thinking
- Frontend: Logic-based formal argument presentation
- Integration: Bidirectional translation between neural and symbolic
"""

import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, List

# Add agents directory to path
sys.path.insert(0, str(Path(__file__).parent))

from agent import Agent, ModelConfig
from tools.base import Tool
from tools.extended_thinking import ExtendedThinkingTool
from logic import (
    ReasoningAgent,
    LogicType,
    ReasoningStep,
    InferenceRule
)


class LogicTool(Tool):
    """
    Tool wrapper that bridges ExtendedThinkingTool with formal logic.

    When the agent calls this tool:
    1. Extended thinking generates ML reasoning
    2. Results are formalized into logical arguments
    3. Knowledge base validates conclusions
    4. Both representations are returned
    """

    def __init__(
        self,
        logic_agent: ReasoningAgent,
        extended_thinking: ExtendedThinkingTool
    ):
        self.logic_agent = logic_agent
        self.extended_thinking = extended_thinking

        # Get extended thinking schema and extend it
        et_schema = extended_thinking.get_schema()

        super().__init__(
            name="logic_reasoning",
            description=(
                "Engage in deep logical reasoning with formal argument construction. "
                "Uses extended chain-of-thought reasoning (ML backend) combined with "
                "formal logic validation (symbolic frontend). Returns both natural "
                "language reasoning and formal logical proofs."
            ),
            input_schema=et_schema["input_schema"]
        )

    async def execute(self, **kwargs) -> str:
        """
        Execute neuro-symbolic reasoning.

        Args:
            query: The question to reason about
            context: Optional context
            options: Optional answer choices
            depth: Reasoning depth (1-5)

        Returns:
            JSON string with ML reasoning + formal logic
        """
        # Step 1: Run extended thinking (ML backend)
        et_result = self.extended_thinking.execute(**kwargs)

        # Step 2: Extract reasoning chain and convert to logical steps
        reasoning_steps = self._convert_to_logic_steps(et_result)

        # Step 3: Build formal argument using logic agent
        if reasoning_steps:
            self.logic_agent.reasoning_chain = reasoning_steps
            formal_argument = self.logic_agent.argument_builder.build_argument(
                reasoning_steps
            )

            # Step 4: Validate conclusion against knowledge base
            validation = self.logic_agent.knowledge_base.validate(
                et_result.get("recommendation", ""),
                use_ml=False
            )

            # Step 5: Format result combining both representations
            result = {
                "ml_reasoning": {
                    "thinking_chain": et_result["thinking_chain"],
                    "key_insights": et_result["key_insights"],
                    "confidence": et_result["confidence"],
                    "recommendation": et_result.get("recommendation")
                },
                "formal_logic": {
                    "premises": [
                        {
                            "natural": p.natural_language,
                            "formal": p.formal_notation
                        }
                        for p in formal_argument.premises
                    ],
                    "inference_rules": [r.value for r in formal_argument.inference_steps],
                    "conclusion": {
                        "natural": formal_argument.conclusion.natural_language,
                        "formal": formal_argument.conclusion.formal_notation
                    },
                    "overall_confidence": formal_argument.overall_confidence,
                },
                "validation": {
                    "valid": validation.valid,
                    "kb_confidence": validation.confidence,
                    "sources": validation.sources,
                    "reasoning_chain": validation.reasoning_chain
                },
                "combined_confidence": self._calculate_combined_confidence(
                    et_result["confidence"],
                    formal_argument.overall_confidence,
                    validation.confidence
                )
            }

            return self._format_output(result)
        else:
            # Fallback to just extended thinking result
            return str(et_result)

    def _convert_to_logic_steps(
        self,
        et_result: Dict[str, Any]
    ) -> List[ReasoningStep]:
        """
        Convert extended thinking output to formal reasoning steps.

        Maps ML reasoning chain to symbolic logic steps.
        """
        steps = []

        thinking_chain = et_result.get("thinking_chain", [])

        for i, thought in enumerate(thinking_chain):
            # Extract premise from thinking step
            premise = thought.get("content", "")

            # Infer appropriate inference rule
            rule = self._infer_rule_from_thought(thought)

            # Generate conclusion (simplified)
            if i < len(thinking_chain) - 1:
                conclusion = thinking_chain[i + 1].get("content", "")
            else:
                conclusion = et_result.get("recommendation", premise)

            # Get confidence from thought details
            confidence = thought.get("details", {}).get("confidence", 0.8)

            step = ReasoningStep(
                premise=premise,
                inference_rule=rule,
                conclusion=conclusion,
                confidence=confidence,
                supporting_evidence=[thought.get("name", "extended_thinking")],
                layer_id=thought.get("step")
            )
            steps.append(step)

        return steps

    def _infer_rule_from_thought(self, thought: Dict[str, Any]) -> InferenceRule:
        """Infer which logical rule corresponds to a thinking step."""
        name = thought.get("name", "").lower()
        thought.get("content", "").lower()

        if "analysis" in name:
            return InferenceRule.UNIVERSAL_INSTANTIATION
        elif "evaluation" in name:
            return InferenceRule.MODUS_PONENS
        elif "synthesis" in name or "consensus" in name:
            return InferenceRule.CONJUNCTION
        elif "option" in name:
            return InferenceRule.DISJUNCTIVE_SYLLOGISM
        else:
            return InferenceRule.MODUS_PONENS

    def _calculate_combined_confidence(
        self,
        ml_confidence: float,
        logic_confidence: float,
        kb_confidence: float
    ) -> float:
        """
        Calculate combined confidence from all sources.

        Weighted average:
        - ML reasoning: 40%
        - Logic structure: 35%
        - KB validation: 25%
        """
        if kb_confidence > 0:
            combined = (
                ml_confidence * 0.40 +
                logic_confidence * 0.35 +
                kb_confidence * 0.25
            )
        else:
            # No KB validation available
            combined = (
                ml_confidence * 0.55 +
                logic_confidence * 0.45
            )

        return combined

    def _format_output(self, result: Dict[str, Any]) -> str:
        """Format the combined result for the agent."""
        lines = []
        lines.append("=== NEURO-SYMBOLIC REASONING RESULT ===\n")

        # ML Reasoning Summary
        ml = result["ml_reasoning"]
        lines.append("🧠 ML REASONING:")
        lines.append(f"  Recommendation: {ml.get('recommendation', 'N/A')}")
        lines.append(f"  Confidence: {ml['confidence']:.1%}")
        lines.append(f"  Key Insights: {len(ml.get('key_insights', []))}")

        # Formal Logic Summary
        logic = result["formal_logic"]
        lines.append("\n📜 FORMAL LOGIC:")
        lines.append(f"  Premises: {len(logic['premises'])}")
        lines.append(f"  Inference Rules: {', '.join(logic['inference_rules'])}")
        lines.append(f"  Conclusion (formal): {logic['conclusion']['formal']}")
        lines.append(f"  Logic Confidence: {logic['overall_confidence']:.1%}")

        # Knowledge Base Validation
        val = result["validation"]
        lines.append("\n✓ KNOWLEDGE BASE VALIDATION:")
        lines.append(f"  Valid: {val['valid']}")
        lines.append(f"  KB Confidence: {val['kb_confidence']:.1%}")
        if val['sources']:
            lines.append(f"  Sources: {', '.join(val['sources'])}")

        # Combined Assessment
        lines.append(f"\n📊 COMBINED CONFIDENCE: {result['combined_confidence']:.1%}")

        lines.append("\n" + "=" * 60)

        return "\n".join(lines)


async def demo_integrated_agent():
    """Demonstrate fully integrated neuro-symbolic agent."""
    print("\n" + "=" * 70)
    print("FULL NEURO-SYMBOLIC INTEGRATION DEMONSTRATION")
    print("=" * 70)

    # Step 1: Create logic reasoning agent (symbolic backend)
    print("\n1️⃣ Initializing Logic Reasoning Agent...")
    logic_agent = ReasoningAgent(
        name="Logic Backend",
        system_prompt="Formal logic validation and argument construction",
        logic_framework=LogicType.FIRST_ORDER,
        reasoning_depth=4,
        logic_weight=0.75,
        verbose=False
    )

    # Add domain knowledge
    print("   Adding domain knowledge to KB...")
    logic_agent.add_knowledge(
        "All ML models trained on biased data produce biased outputs",
        confidence=0.95
    )
    logic_agent.add_knowledge(
        "GPT-4 is an ML model",
        confidence=1.0
    )
    logic_agent.add_knowledge(
        "GPT-4 was trained on internet data",
        confidence=0.95
    )
    logic_agent.add_knowledge(
        "Internet data contains bias",
        confidence=0.90
    )

    # Step 2: Create extended thinking tool (ML backend)
    print("\n2️⃣ Initializing Extended Thinking Tool...")
    extended_thinking = ExtendedThinkingTool(
        layers=8,  # 8-layer architecture
        verbose=False,
        logic_weight=0.75
    )

    # Step 3: Create integrated logic tool
    print("\n3️⃣ Creating Integrated Logic Tool...")
    logic_tool = LogicTool(
        logic_agent=logic_agent,
        extended_thinking=extended_thinking
    )

    # Step 4: Create Agent with logic tool
    print("\n4️⃣ Initializing Claude Agent with Logic Tool...")
    agent = Agent(
        name="Neuro-Symbolic Reasoner",
        system=(
            "You are an advanced reasoning agent that combines neural network "
            "reasoning with formal logic. When asked to reason about complex "
            "questions, use the logic_reasoning tool to provide both intuitive "
            "ML-powered insights AND formal logical proofs. Always cite both "
            "perspectives in your final answer."
        ),
        tools=[logic_tool],
        config=ModelConfig(
            model="claude-sonnet-4-20250514",
            max_tokens=4096
        ),
        verbose=True
    )

    # Step 5: Query the integrated agent
    print("\n5️⃣ Querying Integrated Agent...")
    query = """
    Given the following question, please reason about it deeply and provide
    both intuitive reasoning AND formal logical proof:

    Question: Does GPT-4 produce biased outputs?

    Use the logic_reasoning tool to analyze this question.
    """

    print("\n" + "=" * 70)
    print("QUERY:")
    print("=" * 70)
    print(query)
    print("=" * 70)

    try:
        response = await agent.run_async(query)

        print("\n" + "=" * 70)
        print("AGENT RESPONSE:")
        print("=" * 70)

        for block in response.content:
            if block.type == "text":
                print(block.text)

        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    # Step 6: Show knowledge base stats
    print("\n6️⃣ Knowledge Base Statistics:")
    stats = logic_agent.get_knowledge_stats()
    for key, value in stats.items():
        print(f"   • {key}: {value}")


def demo_without_api():
    """
    Demonstrate the system without requiring API calls.

    This shows the logic layer working independently.
    """
    print("\n" + "=" * 70)
    print("STANDALONE LOGIC SYSTEM DEMONSTRATION")
    print("(No API calls required)")
    print("=" * 70)

    # Create logic agent
    logic_agent = ReasoningAgent(
        name="Standalone Logic",
        system_prompt="Pure symbolic reasoning",
        logic_framework=LogicType.FIRST_ORDER,
        verbose=True
    )

    # Add knowledge
    print("\n📚 Building Knowledge Base...")
    logic_agent.add_knowledge("All software engineers write code")
    logic_agent.add_knowledge("Alice is a software engineer")

    # Reason
    print("\n🧠 Reasoning...")
    result = logic_agent.reason("What can we conclude about Alice?")

    # Display formal argument
    print("\n📜 FORMAL ARGUMENT:")
    formatter = logic_agent.argument_builder.formatter
    print(formatter.format_argument(result["formal_argument"]))

    print("\n✅ This demonstrates the symbolic layer working independently")
    print("   of the ML backend. It can validate and construct formal proofs")
    print("   using pure logic.")


def main():
    """Run demonstrations."""
    print("\n" + "=" * 70)
    print("NEURO-SYMBOLIC AGENT INTEGRATION")
    print("=" * 70)
    print("\nThis demonstrates a hybrid architecture where:")
    print("  Backend: ML reasoning (Claude + Extended Thinking)")
    print("  Frontend: Formal logic (Symbolic reasoning + KB)")
    print("=" * 70)

    # Run standalone demo first (no API needed)
    try:
        input("\nPress Enter to run standalone logic demo...")
        demo_without_api()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted.")
        return

    # Ask if user wants to run API demo
    print("\n" + "=" * 70)
    print("The next demo requires ANTHROPIC_API_KEY to be set.")
    response = input("Run integrated agent demo? (y/n): ")

    if response.lower() == 'y':
        try:
            asyncio.run(demo_integrated_agent())
        except Exception as e:
            print(f"\n❌ Error running integrated demo: {e}")
            print("   Make sure ANTHROPIC_API_KEY is set in your environment.")
    else:
        print("\nSkipped integrated demo.")

    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)
    print("\n🎯 Key Architecture Components:")
    print("  1. Agent: Claude-powered LLM interaction")
    print("  2. ExtendedThinkingTool: Multi-layer chain-of-thought")
    print("  3. ReasoningAgent: Formal logic construction")
    print("  4. KnowledgeBase: Symbolic knowledge + inference")
    print("  5. LogicTool: Bridge between neural and symbolic")
    print("\n💡 Benefits of Neuro-Symbolic Approach:")
    print("  • Transparency: Logic proofs are auditable")
    print("  • Verification: KB validates conclusions")
    print("  • Flexibility: ML handles ambiguity and learning")
    print("  • Guarantees: Formal logic ensures soundness")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
