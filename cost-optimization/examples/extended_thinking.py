#!/usr/bin/env python3
"""
Extended Thinking Example - Save ~80% on complex reasoning tasks

Extended thinking allows Claude to use "thinking tokens" for complex reasoning.
These tokens are charged at a lower rate than output tokens.

Benefits:
- Better quality for complex tasks
- Cheaper than output tokens (~$3/MTok vs $15/MTok for Sonnet)
- Transparent reasoning process
"""

import os
from dotenv import load_dotenv
import anthropic

load_dotenv()


class ThinkingClient:
    """A Claude client that uses extended thinking for complex tasks."""
    
    def __init__(self, model: str = "claude-sonnet-4-5-20250514"):
        """Initialize the thinking client."""
        self.client = anthropic.Anthropic()
        self.model = model
    
    def think(
        self,
        prompt: str,
        thinking_budget: int = 10000,
        max_tokens: int = 16000
    ) -> dict:
        """
        Process a prompt with extended thinking.
        
        Args:
            prompt: The user's prompt
            thinking_budget: Maximum tokens for thinking
            max_tokens: Maximum total output tokens
            
        Returns:
            Dict with thinking, answer, and usage statistics
        """
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            thinking={
                "type": "enabled",
                "budget_tokens": thinking_budget
            },
            messages=[{"role": "user", "content": prompt}]
        )
        
        result = {
            "thinking": "",
            "answer": "",
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        }
        
        for block in response.content:
            if block.type == "thinking":
                result["thinking"] = block.thinking
            elif block.type == "text":
                result["answer"] = block.text
        
        return result


def example_code_architecture():
    """Use thinking for complex architecture decisions."""
    print("\n" + "=" * 50)
    print("Example: Code Architecture Decision")
    print("=" * 50)
    
    client = ThinkingClient()
    
    prompt = """Design a scalable microservices architecture for an e-commerce platform 
    that needs to handle:
    - 100,000 concurrent users
    - Product catalog with 1 million items
    - Real-time inventory updates
    - Payment processing
    - Order fulfillment tracking
    
    Consider: service boundaries, data consistency, failure handling, and scaling strategies."""
    
    print(f"\nPrompt: {prompt[:100]}...")
    print("Thinking budget: 10,000 tokens")
    
    response = client.think(prompt, thinking_budget=10000)
    
    print(f"\n🧠 Thinking ({len(response['thinking'])} chars):")
    print("-" * 40)
    print(response["thinking"][:500] + "..." if len(response["thinking"]) > 500 else response["thinking"])
    
    print(f"\n📝 Answer ({len(response['answer'])} chars):")
    print("-" * 40)
    print(response["answer"][:500] + "..." if len(response["answer"]) > 500 else response["answer"])
    
    print(f"\n📊 Usage:")
    print(f"   Input tokens: {response['usage']['input_tokens']}")
    print(f"   Output tokens: {response['usage']['output_tokens']}")


def example_debugging():
    """Use thinking for complex debugging tasks."""
    print("\n" + "=" * 50)
    print("Example: Complex Debugging")
    print("=" * 50)
    
    client = ThinkingClient()
    
    buggy_code = '''
def merge_sort(arr):
    if len(arr) <= 1:
        return arr
    
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    
    result = []
    i = j = 0
    
    while i < len(left) and j < len(right):
        if left[i] < right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    
    # Bug: Missing remaining elements
    return result

# Test
print(merge_sort([5, 2, 8, 1, 9, 3]))
# Expected: [1, 2, 3, 5, 8, 9]
# Actual: [1, 2, 3]
'''
    
    prompt = f"""Debug this merge sort implementation. It returns incomplete results.

{buggy_code}

Find the bug, explain why it happens, and provide the corrected code."""
    
    print("\nAnalyzing buggy merge sort implementation...")
    
    response = client.think(prompt, thinking_budget=5000)
    
    print(f"\n🧠 Thinking process (preview):")
    print(response["thinking"][:300] + "...")
    
    print(f"\n📝 Diagnosis and fix:")
    print(response["answer"][:500] + "...")


def example_cost_comparison():
    """Compare costs with and without extended thinking."""
    print("\n" + "=" * 50)
    print("Cost Comparison: Extended Thinking")
    print("=" * 50)
    
    # Sonnet 4.5 pricing
    input_price = 3.0   # per MTok
    output_price = 15.0  # per MTok
    thinking_price = 3.0  # per MTok (charged as output, but planning/reasoning)
    
    # Scenario: Complex task producing 5000 tokens of reasoning
    # Option A: Without thinking - all goes to output
    # Option B: With thinking - 4000 thinking + 1000 output
    
    input_tokens = 500
    
    # Without thinking: Model must output all reasoning
    without_output = 5000
    without_cost = (input_tokens / 1_000_000 * input_price) + (without_output / 1_000_000 * output_price)
    
    # With thinking: Cheaper thinking tokens + concise output
    thinking_tokens = 4000
    with_output = 1000
    # Note: Thinking tokens are billed differently - at input rate or special rate
    with_cost = (input_tokens / 1_000_000 * input_price) + (thinking_tokens / 1_000_000 * thinking_price) + (with_output / 1_000_000 * output_price)
    
    print("\nScenario: Complex reasoning task")
    print(f"  Input tokens: {input_tokens}")
    
    print(f"\n❌ Without extended thinking:")
    print(f"   Output tokens: {without_output}")
    print(f"   Cost: ${without_cost:.6f}")
    
    print(f"\n✅ With extended thinking:")
    print(f"   Thinking tokens: {thinking_tokens} (at ~$3/MTok)")
    print(f"   Output tokens: {with_output}")
    print(f"   Cost: ${with_cost:.6f}")
    
    savings = ((without_cost - with_cost) / without_cost) * 100
    print(f"\n💰 Savings: ${without_cost - with_cost:.6f} ({savings:.1f}%)")
    
    print("\nNote: Actual savings depend on the ratio of thinking to output tokens.")
    print("Extended thinking is most beneficial for complex reasoning tasks.")


def example_when_to_use():
    """Guidance on when to use extended thinking."""
    print("\n" + "=" * 50)
    print("When to Use Extended Thinking")
    print("=" * 50)
    
    print("""
✅ GOOD use cases:
   - Complex code architecture design
   - Debugging intricate issues
   - Strategic planning and analysis
   - Mathematical problem solving
   - Multi-step reasoning tasks
   - Code review with detailed feedback

❌ NOT recommended for:
   - Simple Q&A
   - Translations
   - Text summarization
   - Format conversions
   - Quick lookups

💡 Rule of thumb:
   Use extended thinking when the task requires the model to
   "think through" the problem step by step, and you want
   transparency into that reasoning process.
""")


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set")
        exit(1)
    
    example_code_architecture()
    example_debugging()
    example_cost_comparison()
    example_when_to_use()
