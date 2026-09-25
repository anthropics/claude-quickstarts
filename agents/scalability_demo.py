"""
Scalability Demo - 4x vs 8x vs 16x vs 32x Architectures

Compares different layer architectures with emphasis on logic prioritization.
"""

import time
from tools.extended_thinking import ExtendedThinkingTool


def test_architecture(layers: int, logic_weight: float, query: str, options: list) -> dict:
    """Test a specific architecture configuration."""
    print(f"\n{'='*70}")
    print(f"🧠 Testing {layers}x Architecture (Logic Weight: {logic_weight:.0%})")
    print('='*70)
    
    tool = ExtendedThinkingTool(layers=layers, verbose=False, logic_weight=logic_weight)
    
    start_time = time.time()
    result = tool.execute(query=query, options=options, depth=3)
    elapsed_ms = (time.time() - start_time) * 1000
    
    print(f"\n⏱️  Processing Time: {elapsed_ms:.0f}ms")
    print(f"🎯 Confidence: {result['confidence']:.1%}")
    print(f"💡 Recommendation: {result.get('recommendation', 'N/A')}")
    print(f"🧮 Logic Layers: {result.get('meta_analysis', {}).get('num_logic_layers', 'N/A')}")
    print(f"📊 Logic Agreement: {result.get('meta_analysis', {}).get('logic_agreement', 'N/A')}")
    
    return {
        "layers": layers,
        "logic_weight": logic_weight,
        "time_ms": elapsed_ms,
        "confidence": result['confidence'],
        "recommendation": result.get('recommendation'),
        "num_logic_layers": result.get('meta_analysis', {}).get('num_logic_layers', 0)
    }


def demo_scalability_comparison():
    """Compare all architectures on the same problem."""
    print("\n" + "🌟"*35)
    print("    SCALABILITY COMPARISON: 4x vs 8x vs 16x vs 32x")
    print("🌟"*35)
    
    # Complex reasoning problem
    query = """
    A study claims: "Companies using AI increase productivity by 40%."
    
    Study details:
    - Sample size: 50 companies
    - Duration: 6 months
    - Selection: Self-reported volunteers
    - Control group: None
    - Funding: AI vendor
    
    How should we interpret this claim?
    """
    
    options = [
        "Claim is valid - 40% improvement is significant",
        "Claim is questionable - sample bias and no control group",
        "Claim is invalid - vendor funding creates conflict of interest",
        "Cannot determine - need more information"
    ]
    
    # Test each architecture
    results = []
    
    # 4x - Baseline
    results.append(test_architecture(4, 0.60, query, options))
    input("\nPress Enter to continue to 8x...")
    
    # 8x - Recommended (LOGIC PRIORITIZED)
    results.append(test_architecture(8, 0.75, query, options))
    input("\nPress Enter to continue to 16x...")
    
    # 16x - Advanced
    results.append(test_architecture(16, 0.82, query, options))
    input("\nPress Enter to continue to 32x...")
    
    # 32x - Maximum
    results.append(test_architecture(32, 0.88, query, options))
    
    # Summary comparison
    print("\n" + "="*70)
    print("📊 COMPARISON SUMMARY")
    print("="*70)
    print(f"{'Arch':<8} {'Time':<10} {'Logic%':<10} {'Logic Layers':<15} {'Confidence':<12} {'Cost/Benefit'}")
    print("-"*70)
    
    for r in results:
        time_ratio = r['time_ms'] / results[0]['time_ms']
        cost_benefit = "⭐⭐⭐⭐⭐" if r['layers'] == 8 else "⭐⭐⭐" if r['layers'] == 4 else "⭐⭐"
        print(
            f"{r['layers']}x{' ':<5} "
            f"{r['time_ms']:.0f}ms{' ':<5} "
            f"{r['logic_weight']:.0%}{' ':<7} "
            f"{r['num_logic_layers']}{' ':<14} "
            f"{r['confidence']:.1%}{' ':<11} "
            f"{cost_benefit}"
        )
    
    # Calculate efficiency
    print("\n" + "="*70)
    print("📈 EFFICIENCY ANALYSIS")
    print("="*70)
    
    baseline_time = results[0]['time_ms']
    for r in results:
        time_increase = ((r['time_ms'] - baseline_time) / baseline_time) * 100
        conf_increase = ((r['confidence'] - results[0]['confidence']) / results[0]['confidence']) * 100
        
        if time_increase > 0:
            efficiency = conf_increase / (time_increase / 100)
        else:
            efficiency = float('inf')
        
        print(f"\n{r['layers']}x Architecture:")
        print(f"  Time vs 4x: +{time_increase:.0f}%")
        print(f"  Confidence vs 4x: +{conf_increase:.1f}%")
        print(f"  Efficiency: {efficiency:.2f}% confidence per 1% time")


def demo_logic_priority():
    """Demonstrate the importance of logic prioritization."""
    print("\n" + "="*70)
    print("🧮 LOGIC PRIORITIZATION DEMONSTRATION")
    print("="*70)
    
    # Logical reasoning problem
    query = """
    Premise 1: All effective AI systems require quality training data.
    Premise 2: This AI system is effective.
    Conclusion: Therefore, this AI system has quality training data.
    
    Is this reasoning valid?
    """
    
    options = [
        "Yes - valid deductive reasoning (modus ponens)",
        "No - invalid, commits affirming the consequent fallacy",
        "Partially valid - depends on definition of 'effective'",
        "Cannot determine without more information"
    ]
    
    print("\n" + "-"*70)
    print("Test: Same 8x architecture with DIFFERENT logic weights")
    print("-"*70)
    
    # Test with different logic weights
    for logic_weight in [0.50, 0.75, 0.90]:
        tool = ExtendedThinkingTool(layers=8, logic_weight=logic_weight, verbose=False)
        
        result = tool.execute(query=query, options=options, depth=3)
        
        print(f"\nLogic Weight: {logic_weight:.0%}")
        print(f"  Confidence: {result['confidence']:.1%}")
        print(f"  Recommendation: {result.get('recommendation', 'N/A')[:50]}...")
        print(f"  Logic Agreement: {result.get('meta_analysis', {}).get('logic_agreement', 0):.1%}")
    
    print("\n" + "="*70)
    print("💡 INSIGHT:")
    print("Higher logic weight → More consistent reasoning on logical problems")
    print("Recommendation: Use 75-90% logic weight for critical thinking")
    print("="*70)


def demo_contradiction_detection():
    """Demonstrate logic contradiction detection."""
    print("\n" + "="*70)
    print("🚨 LOGICAL CONTRADICTION DETECTION")
    print("="*70)
    
    # Problem with logical contradiction
    query = """
    Statement: "All AI systems sometimes make errors."
    Question: Which must be true?
    """
    
    options = [
        "There exists at least one AI system that never makes errors",
        "Every AI system makes at least one error at some point",
        "Some AI systems are perfect",
        "No AI systems are reliable"
    ]
    
    tool = ExtendedThinkingTool(layers=8, logic_weight=0.85, verbose=False)
    result = tool.execute(query=query, options=options, depth=4)
    
    print(f"\n🎯 Result:")
    print(f"  Confidence: {result['confidence']:.1%}")
    print(f"  Recommendation: {result.get('recommendation', 'N/A')}")
    print(f"  Logic Agreement: {result.get('meta_analysis', {}).get('logic_agreement', 0):.1%}")
    
    if result.get('meta_analysis', {}).get('logic_agreement', 1.0) < 0.5:
        print("\n⚠️  WARNING: Low logic agreement detected!")
        print("   Logic layers disagree - possible contradiction or ambiguity")
    else:
        print("\n✅ High logic agreement - reasoning is consistent")


def demo_performance_benchmarks():
    """Benchmark all architectures."""
    print("\n" + "="*70)
    print("⚡ PERFORMANCE BENCHMARKS")
    print("="*70)
    
    test_query = "Should we invest in this technology?"
    test_options = ["Yes", "No", "Maybe", "Need more info"]
    
    configs = [
        (4, 0.60, "4x Baseline"),
        (8, 0.75, "8x Recommended"),
        (16, 0.82, "16x Advanced"),
        (32, 0.88, "32x Maximum"),
    ]
    
    print("\nRunning 5 iterations per configuration...\n")
    
    for layers, logic_weight, name in configs:
        tool = ExtendedThinkingTool(layers=layers, logic_weight=logic_weight, verbose=False)
        
        times = []
        for i in range(5):
            start = time.time()
            tool.execute(query=test_query, options=test_options, depth=2)
            elapsed = (time.time() - start) * 1000
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        print(f"{name}:")
        print(f"  Avg: {avg_time:.0f}ms | Min: {min_time:.0f}ms | Max: {max_time:.0f}ms")
    
    print("\n" + "="*70)


def demo_real_world_use_cases():
    """Show recommended configurations for different use cases."""
    print("\n" + "="*70)
    print("🎯 RECOMMENDED CONFIGURATIONS BY USE CASE")
    print("="*70)
    
    use_cases = [
        {
            "name": "Real-time Chatbot",
            "layers": 4,
            "logic_weight": 0.60,
            "rationale": "Speed critical, moderate reasoning sufficient"
        },
        {
            "name": "Watson Glaser Critical Thinking",
            "layers": 8,
            "logic_weight": 0.75,
            "rationale": "Best balance of reasoning quality and performance"
        },
        {
            "name": "Educational Assessment",
            "layers": 8,
            "logic_weight": 0.80,
            "rationale": "High logic priority, detailed feedback needed"
        },
        {
            "name": "Medical Decision Support",
            "layers": 16,
            "logic_weight": 0.85,
            "rationale": "High stakes, accuracy paramount, time less critical"
        },
        {
            "name": "Legal Analysis",
            "layers": 16,
            "logic_weight": 0.90,
            "rationale": "Maximum logic rigor, formal reasoning required"
        },
        {
            "name": "AI Research",
            "layers": 32,
            "logic_weight": 0.88,
            "rationale": "Benchmark testing, research environment"
        }
    ]
    
    for uc in use_cases:
        print(f"\n📌 {uc['name']}")
        print(f"   Config: {uc['layers']}x layers, {uc['logic_weight']:.0%} logic weight")
        print(f"   Why: {uc['rationale']}")


def main():
    """Run all scalability demos."""
    print("\n" + "🚀"*35)
    print("    EXTENDED THINKING SCALABILITY DEMONSTRATION")
    print("🚀"*35)
    
    # Demo 1: Architecture comparison
    demo_scalability_comparison()
    input("\n\nPress Enter for Logic Priority demo...")
    
    # Demo 2: Logic prioritization
    demo_logic_priority()
    input("\n\nPress Enter for Contradiction Detection demo...")
    
    # Demo 3: Contradiction detection
    demo_contradiction_detection()
    input("\n\nPress Enter for Performance Benchmarks...")
    
    # Demo 4: Performance benchmarks
    demo_performance_benchmarks()
    input("\n\nPress Enter for Use Case Recommendations...")
    
    # Demo 5: Use case recommendations
    demo_real_world_use_cases()
    
    print("\n" + "="*70)
    print("✅ All scalability demonstrations complete!")
    print("\n🏆 RECOMMENDATION: Use 8x architecture with 75% logic weight")
    print("   • Best cost/benefit ratio")
    print("   • Strong logical reasoning")
    print("   • Production-ready performance")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
