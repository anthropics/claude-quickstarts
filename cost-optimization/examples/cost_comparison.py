#!/usr/bin/env python3
"""
Cost Comparison Tool

Compare costs across different optimization strategies to find the best approach
for your use case.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# Claude API Pricing (per million tokens, as of 2026)
PRICING = {
    "claude-opus-4-5": {
        "input": 15.0,
        "output": 75.0,
        "batch_input": 7.5,
        "batch_output": 37.5,
        "cache_write": 18.75,  # +25%
        "cache_read": 1.5,     # -90%
    },
    "claude-sonnet-4-5": {
        "input": 3.0,
        "output": 15.0,
        "batch_input": 1.5,
        "batch_output": 7.5,
        "cache_write": 3.75,   # +25%
        "cache_read": 0.30,    # -90%
    },
    "claude-haiku-4-5": {
        "input": 1.0,
        "output": 5.0,
        "batch_input": 0.5,
        "batch_output": 2.5,
        "cache_write": 1.25,   # +25%
        "cache_read": 0.10,    # -90%
    }
}


def calculate_normal_cost(
    input_tokens: int,
    output_tokens: int,
    model: str = "claude-sonnet-4-5"
) -> float:
    """Calculate cost without any optimization."""
    p = PRICING[model]
    return (input_tokens / 1_000_000 * p["input"]) + (output_tokens / 1_000_000 * p["output"])


def calculate_batch_cost(
    input_tokens: int,
    output_tokens: int,
    model: str = "claude-sonnet-4-5"
) -> float:
    """Calculate cost using Batch API (50% off)."""
    p = PRICING[model]
    return (input_tokens / 1_000_000 * p["batch_input"]) + (output_tokens / 1_000_000 * p["batch_output"])


def calculate_cached_cost(
    system_tokens: int,
    user_tokens: int,
    output_tokens: int,
    num_requests: int,
    model: str = "claude-sonnet-4-5"
) -> float:
    """Calculate cost using Prompt Caching."""
    p = PRICING[model]
    
    # First request: cache write
    first_input = (system_tokens / 1_000_000 * p["cache_write"]) + (user_tokens / 1_000_000 * p["input"])
    first_output = output_tokens / 1_000_000 * p["output"]
    
    # Subsequent requests: cache read
    subsequent_input = ((num_requests - 1) * (
        (system_tokens / 1_000_000 * p["cache_read"]) + 
        (user_tokens / 1_000_000 * p["input"])
    ))
    subsequent_output = (num_requests - 1) * output_tokens / 1_000_000 * p["output"]
    
    return first_input + first_output + subsequent_input + subsequent_output


def calculate_batch_cached_cost(
    system_tokens: int,
    user_tokens: int,
    output_tokens: int,
    num_requests: int,
    model: str = "claude-sonnet-4-5"
) -> float:
    """Calculate cost using both Batch API and Prompt Caching."""
    p = PRICING[model]
    
    # First request in batch: cache write (at batch prices)
    first_input = (system_tokens / 1_000_000 * p["cache_write"] * 0.5) + (user_tokens / 1_000_000 * p["batch_input"])
    first_output = output_tokens / 1_000_000 * p["batch_output"]
    
    # Subsequent requests: cache read (at batch prices)
    subsequent_input = ((num_requests - 1) * (
        (system_tokens / 1_000_000 * p["cache_read"] * 0.5) + 
        (user_tokens / 1_000_000 * p["batch_input"])
    ))
    subsequent_output = (num_requests - 1) * output_tokens / 1_000_000 * p["batch_output"]
    
    return first_input + first_output + subsequent_input + subsequent_output


def compare_scenarios():
    """Compare costs across different scenarios."""
    print("=" * 70)
    print("CLAUDE API COST COMPARISON")
    print("=" * 70)
    
    scenarios = [
        {
            "name": "Daily Content Generation (30 requests)",
            "system_tokens": 2000,
            "user_tokens": 200,
            "output_tokens": 800,
            "num_requests": 30
        },
        {
            "name": "Bulk Translation (100 requests)",
            "system_tokens": 500,
            "user_tokens": 300,
            "output_tokens": 400,
            "num_requests": 100
        },
        {
            "name": "RAG Q&A (50 requests with large context)",
            "system_tokens": 5000,
            "user_tokens": 100,
            "output_tokens": 500,
            "num_requests": 50
        },
        {
            "name": "Code Review (10 complex reviews)",
            "system_tokens": 3000,
            "user_tokens": 2000,
            "output_tokens": 1500,
            "num_requests": 10
        }
    ]
    
    for scenario in scenarios:
        print(f"\n{'─' * 70}")
        print(f"📊 {scenario['name']}")
        print(f"   System: {scenario['system_tokens']} tokens | User: {scenario['user_tokens']} tokens")
        print(f"   Output: {scenario['output_tokens']} tokens | Requests: {scenario['num_requests']}")
        print(f"{'─' * 70}")
        
        # Calculate costs for different strategies
        total_input = scenario["system_tokens"] + scenario["user_tokens"]
        
        normal = scenario["num_requests"] * calculate_normal_cost(
            total_input, scenario["output_tokens"]
        )
        
        batch = scenario["num_requests"] * calculate_batch_cost(
            total_input, scenario["output_tokens"]
        )
        
        cached = calculate_cached_cost(
            scenario["system_tokens"],
            scenario["user_tokens"],
            scenario["output_tokens"],
            scenario["num_requests"]
        )
        
        batch_cached = calculate_batch_cached_cost(
            scenario["system_tokens"],
            scenario["user_tokens"],
            scenario["output_tokens"],
            scenario["num_requests"]
        )
        
        # Find best option
        options = {
            "Normal API": normal,
            "Batch API (50% off)": batch,
            "Prompt Caching (90% off)": cached,
            "Batch + Cache (max savings)": batch_cached
        }
        
        best_option = min(options.items(), key=lambda x: x[1])
        
        print(f"\n   {'Strategy':<30} {'Cost':>10} {'Savings':>10}")
        print(f"   {'─' * 50}")
        
        for name, cost in sorted(options.items(), key=lambda x: x[1]):
            savings_pct = ((normal - cost) / normal) * 100 if normal > 0 else 0
            marker = " ⭐" if name == best_option[0] else ""
            print(f"   {name:<30} ${cost:>9.4f} {savings_pct:>9.1f}%{marker}")
        
        print(f"\n   💡 Best: {best_option[0]} (saves ${normal - best_option[1]:.4f})")


def interactive_calculator():
    """Interactive cost calculator."""
    print("\n" + "=" * 70)
    print("INTERACTIVE COST CALCULATOR")
    print("=" * 70)
    
    print("\nEnter your usage parameters (or press Enter for defaults):")
    
    try:
        system_tokens = int(input("System prompt tokens [2000]: ") or "2000")
        user_tokens = int(input("User message tokens [200]: ") or "200")
        output_tokens = int(input("Output tokens [500]: ") or "500")
        num_requests = int(input("Number of requests [30]: ") or "30")
        
        total_input = system_tokens + user_tokens
        
        print(f"\n📊 Cost Analysis for Your Use Case:")
        print("─" * 50)
        
        normal = num_requests * calculate_normal_cost(total_input, output_tokens)
        batch = num_requests * calculate_batch_cost(total_input, output_tokens)
        cached = calculate_cached_cost(system_tokens, user_tokens, output_tokens, num_requests)
        batch_cached = calculate_batch_cached_cost(system_tokens, user_tokens, output_tokens, num_requests)
        
        print(f"{'Normal API:':<25} ${normal:.4f}")
        print(f"{'Batch API:':<25} ${batch:.4f} (saves {((normal-batch)/normal)*100:.1f}%)")
        print(f"{'Prompt Caching:':<25} ${cached:.4f} (saves {((normal-cached)/normal)*100:.1f}%)")
        print(f"{'Batch + Cache:':<25} ${batch_cached:.4f} (saves {((normal-batch_cached)/normal)*100:.1f}%)")
        
    except ValueError:
        print("Invalid input. Please enter numbers only.")


def recommendation_engine():
    """Provide recommendations based on use case."""
    print("\n" + "=" * 70)
    print("COST OPTIMIZATION RECOMMENDATIONS")
    print("=" * 70)
    
    print("""
📌 DECISION GUIDE

┌─────────────────────────────────────────────────────────────────────┐
│ Can your tasks wait up to 24 hours?                                 │
├──────────┬──────────────────────────────────────────────────────────┤
│   YES    │ Use BATCH API for 50% savings                            │
│   NO     │ Continue to next question                                │
└──────────┴──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Do you have a system prompt > 1024 tokens used repeatedly?          │
├──────────┬──────────────────────────────────────────────────────────┤
│   YES    │ Use PROMPT CACHING for 90% savings on that portion       │
│   NO     │ Continue to next question                                │
└──────────┴──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Is this a complex reasoning task?                                   │
├──────────┬──────────────────────────────────────────────────────────┤
│   YES    │ Use EXTENDED THINKING for cheaper reasoning tokens       │
│   NO     │ Standard API call is fine                                │
└──────────┴──────────────────────────────────────────────────────────┘

💡 COMBINE TECHNIQUES for maximum savings:
   - Batch + Cache: Up to 95% off for bulk tasks with shared context
   - Cache + Thinking: Great for repeated complex analysis
""")


if __name__ == "__main__":
    compare_scenarios()
    recommendation_engine()
    
    print("\n" + "─" * 70)
    user_input = input("\nWould you like to try the interactive calculator? (y/n): ")
    if user_input.lower() == 'y':
        interactive_calculator()
