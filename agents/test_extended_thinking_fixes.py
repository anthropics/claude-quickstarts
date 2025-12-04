#!/usr/bin/env python3
"""
Test script to verify extended thinking improvements.
Tests:
1. Attribute name fix (thinking_history)
2. Confidence score variation across different queries
3. Depth parameter effectiveness
"""

import sys
from pathlib import Path

# Add agents directory to path
agents_dir = Path(__file__).parent
sys.path.insert(0, str(agents_dir))

from tools.extended_thinking import ExtendedThinkingTool

print("="*70)
print("TESTING EXTENDED THINKING FIXES")
print("="*70)

# Test 1: Attribute access
print("\n✅ TEST 1: Attribute Name Fix")
et_tool = ExtendedThinkingTool(layers=4, verbose=False)
print(f"   thinking_history exists: {hasattr(et_tool, 'thinking_history')}")
print(f"   Initial history length: {len(et_tool.thinking_history)}")

# Test 2: Confidence variation across different queries
print("\n✅ TEST 2: Confidence Score Variation")
test_queries = [
    # Simple, clear logical query with strong structure
    ("All software engineers write code. Alice is a software engineer. What can we conclude?",
     ["Alice writes code", "Cannot determine"]),

    # Vague, ambiguous query
    ("Maybe we should do something about the thing?",
     ["Yes", "No"]),

    # Technical query with specific terminology
    ("The research study demonstrates that test-driven development improves software quality.",
     ["TDD is beneficial", "TDD is harmful"]),

    # Complex, multi-part question
    ("Should we invest in AI? And also, is blockchain good? What about remote work?",
     ["Yes to all", "No to all"]),
]

confidences = []
for i, (query, options) in enumerate(test_queries, 1):
    result = et_tool.execute(query=query, options=options, depth=2)
    conf = result['confidence']
    confidences.append(conf)
    print(f"   Query {i}: {conf:.1%} confidence")

print(f"\n   Confidence range: {min(confidences):.1%} - {max(confidences):.1%}")
print(f"   Standard deviation: {(sum((c - sum(confidences)/len(confidences))**2 for c in confidences) / len(confidences))**0.5:.3f}")
print(f"   ✓ Variation detected: {max(confidences) - min(confidences) > 0.05}")

# Test 3: Depth parameter effectiveness
print("\n✅ TEST 3: Depth Parameter Effectiveness")
query = """
Your company is considering implementing a 4-day work week.
Employee satisfaction increased 25% in pilot, but customer response times increased 15%.
What should the company do?
"""
options = [
    "Implement 4-day week company-wide immediately",
    "Expand pilot to more departments before full rollout",
    "Keep 5-day week but improve flexibility",
]

results_by_depth = {}
for depth in [1, 3, 5]:
    result = et_tool.execute(query=query, options=options, depth=depth)
    results_by_depth[depth] = result
    print(f"   Depth {depth}: {result['confidence']:.1%} confidence, "
          f"{len(result['thinking_chain'])} steps, "
          f"{result['meta_analysis']['analysis_depth']} analytical steps")

# Check that deeper analysis has higher confidence
conf_d1 = results_by_depth[1]['confidence']
conf_d3 = results_by_depth[3]['confidence']
conf_d5 = results_by_depth[5]['confidence']

print(f"\n   Confidence improvement (d1→d3): {conf_d3 - conf_d1:+.1%}")
print(f"   Confidence improvement (d3→d5): {conf_d5 - conf_d3:+.1%}")
print(f"   ✓ Depth increases confidence: {conf_d5 > conf_d1}")

# Test 4: History tracking
print("\n✅ TEST 4: History Tracking")
summary = et_tool.get_history_summary()
print(f"   Total queries processed: {summary['total_queries']}")
print(f"   Average confidence: {summary['avg_confidence']:.1%}")
print(f"   Recent queries tracked: {len(summary['recent_queries'])}")

print("\n" + "="*70)
print("ALL TESTS COMPLETED")
print("="*70)
