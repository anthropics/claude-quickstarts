"""
Extended Thinking Demo

Demonstrates integration of Watson Glaser extended thinking with the agent system.
Shows chain-of-thought reasoning with multi-layer analysis.
"""

import asyncio
from agent import Agent
from tools.extended_thinking import ExtendedThinkingTool, WatsonGlaserThinkingTool


def demo_basic_extended_thinking():
    """Demonstrate basic extended thinking tool."""
    print("\n" + "="*70)
    print("🧠 DEMO 1: Basic Extended Thinking")
    print("="*70 + "\n")
    
    # Create tool
    et_tool = ExtendedThinkingTool(layers=4, verbose=True)
    
    # Test query
    query = """
    A company claims their new AI system improves customer satisfaction by 40%.
    The study involved 100 customers over 2 weeks.
    Should we trust this claim?
    """
    
    options = [
        "Yes, 40% improvement is significant",
        "Partially - need more data and longer timeframe",
        "No, the sample is too biased",
        "Cannot determine from this information"
    ]
    
    # Execute extended thinking
    result = et_tool.execute(
        query=query,
        options=options,
        depth=4
    )
    
    print("\n📊 SUMMARY:")
    print(f"Confidence: {result['confidence']:.1%}")
    print(f"Recommendation: {result.get('recommendation', 'N/A')}")
    print(f"Reasoning Depth: {result['reasoning_depth']}")
    
    return result


def demo_watson_glaser_thinking():
    """Demonstrate Watson Glaser specialized thinking."""
    print("\n" + "="*70)
    print("🎓 DEMO 2: Watson Glaser Critical Thinking")
    print("="*70 + "\n")
    
    # Create Watson Glaser tool
    wg_tool = WatsonGlaserThinkingTool(verbose=True)
    
    # Critical thinking query
    query = """
    All neural networks require training data to function.
    The Watson Glaser TIS is a neural network.
    Therefore, the Watson Glaser TIS requires training data.
    
    Is this reasoning valid?
    """
    
    options = [
        "Yes, the logic is sound",
        "No, neural networks don't always need training",
        "Invalid - false premise",
        "Cannot determine"
    ]
    
    result = wg_tool.execute(
        query=query,
        options=options,
        depth=3
    )
    
    print("\n📊 WATSON GLASER ANALYSIS:")
    print(f"Confidence: {result['confidence']:.1%}")
    print(f"Max Complexity: {wg_tool.max_complexity}")
    print(f"Total History: {len(wg_tool.thinking_history)} queries")
    
    # Test curriculum unlocking
    unlock_msg = wg_tool.unlock_complexity(0.85)
    if unlock_msg:
        print(f"\n{unlock_msg}")
    
    return result


async def demo_agent_with_extended_thinking():
    """Demonstrate agent using extended thinking tool."""
    print("\n" + "="*70)
    print("🤖 DEMO 3: Agent with Extended Thinking Integration")
    print("="*70 + "\n")
    
    # Create extended thinking tool
    et_tool = ExtendedThinkingTool(layers=4, verbose=False)
    
    # Create agent with extended thinking tool
    Agent(
        name="Critical Thinker",
        system="An agent that uses extended chain-of-thought reasoning",
        tools=[et_tool.get_schema()]
    )
    
    # Multi-turn conversation with deep thinking
    messages = [
        {
            "role": "user",
            "content": """
            I need to evaluate whether to adopt a new technology stack.
            
            Context:
            - Current stack: Python + Django + PostgreSQL
            - Proposed: Node.js + Express + MongoDB
            - Team: 5 developers, mostly Python experienced
            - Timeline: 3 months for migration
            - Budget: $50k
            
            Should we migrate? Use extended thinking to analyze this deeply.
            """
        }
    ]
    
    print("💬 User Query:")
    print(messages[0]["content"])
    print("\n🤔 Agent thinking...\n")
    
    # Simulate agent response (in real implementation, agent would use Claude API)
    print("Note: This would integrate with Agent class to make Claude API calls")
    print("Agent would invoke extended_thinking tool and receive structured analysis\n")
    
    # Show what the tool would return
    result = et_tool.execute(
        query=messages[0]["content"],
        options=[
            "Migrate immediately - new stack is better",
            "Don't migrate - too risky",
            "Gradual migration - hybrid approach",
            "Delay decision - need more research"
        ],
        depth=5  # Maximum depth analysis
    )
    
    print("📋 EXTENDED THINKING RESULT:")
    print(f"Confidence: {result['confidence']:.1%}")
    print(f"Recommendation: {result.get('recommendation', 'N/A')}")
    
    print("\n🔍 Key Insights:")
    for i, insight in enumerate(result['key_insights'], 1):
        print(f"  {i}. {insight}")
    
    print("\n📊 Meta-Analysis:")
    meta = result['meta_analysis']
    print(f"  Total Steps: {meta['total_steps']}")
    print(f"  Analysis Depth: {meta['analysis_depth']}")
    print(f"  Decision Quality: {meta['decision_quality']}")
    
    return result


def demo_thinking_history():
    """Demonstrate thinking history tracking."""
    print("\n" + "="*70)
    print("📚 DEMO 4: Thinking History & Pattern Learning")
    print("="*70 + "\n")
    
    et_tool = ExtendedThinkingTool(layers=4, verbose=False)
    
    # Multiple queries to build history
    queries = [
        "Should we invest in AI research?",
        "Is remote work more productive?",
        "Should we expand to international markets?"
    ]
    
    print("Processing multiple queries to build thinking history...\n")
    
    for i, query in enumerate(queries, 1):
        print(f"{i}. {query}")
        result = et_tool.execute(query=query, depth=2)
        print(f"   → Confidence: {result['confidence']:.1%}\n")
    
    # Get history summary
    summary = et_tool.get_history_summary()
    
    print("📊 HISTORY SUMMARY:")
    print(f"Total Queries: {summary['total_queries']}")
    print(f"Avg Confidence: {summary['avg_confidence']:.1%}")
    print("\nRecent Queries:")
    for q in summary['recent_queries']:
        print(f"  • {q}")
    
    return summary


def compare_thinking_approaches():
    """Compare different thinking depths and approaches."""
    print("\n" + "="*70)
    print("⚖️  DEMO 5: Comparing Thinking Depths")
    print("="*70 + "\n")
    
    query = "Should we open source our core product?"
    
    results = {}
    
    for depth in [1, 3, 5]:
        print(f"\n{'─'*70}")
        print(f"Thinking Depth: {depth}")
        print('─'*70)
        
        et_tool = ExtendedThinkingTool(layers=4, verbose=False)
        result = et_tool.execute(query=query, depth=depth)
        
        results[depth] = result
        
        print(f"Confidence: {result['confidence']:.1%}")
        print(f"Steps: {len(result['thinking_chain'])}")
        print(f"Decision Quality: {result['meta_analysis']['decision_quality']}")
    
    print("\n" + "="*70)
    print("📊 COMPARISON SUMMARY")
    print("="*70)
    print(f"{'Depth':<10} {'Confidence':<15} {'Steps':<10} {'Quality'}")
    print("─"*70)
    
    for depth, result in results.items():
        print(
            f"{depth:<10} "
            f"{result['confidence']:.1%:<15} "
            f"{len(result['thinking_chain']):<10} "
            f"{result['meta_analysis']['decision_quality']}"
        )


def main():
    """Run all demonstrations."""
    print("\n" + "🌟"*35)
    print("    EXTENDED THINKING TOOL DEMONSTRATION")
    print("🌟"*35)
    
    # Demo 1: Basic extended thinking
    demo_basic_extended_thinking()
    input("\n\nPress Enter to continue to next demo...")
    
    # Demo 2: Watson Glaser specific
    demo_watson_glaser_thinking()
    input("\n\nPress Enter to continue to next demo...")
    
    # Demo 3: Agent integration
    asyncio.run(demo_agent_with_extended_thinking())
    input("\n\nPress Enter to continue to next demo...")
    
    # Demo 4: History tracking
    demo_thinking_history()
    input("\n\nPress Enter to continue to next demo...")
    
    # Demo 5: Comparison
    compare_thinking_approaches()
    
    print("\n" + "="*70)
    print("✅ All demonstrations complete!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
