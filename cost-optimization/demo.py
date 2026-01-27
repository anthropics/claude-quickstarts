#!/usr/bin/env python3
"""
Claude API Cost Optimization Demo

This script demonstrates all three cost optimization techniques:
1. Batch API (50% off)
2. Prompt Caching (90% off on repeated calls)
3. Extended Thinking (~80% off thinking tokens)

Run with: python demo.py
"""

import os
import time
from dotenv import load_dotenv
import anthropic

load_dotenv()


def demo_prompt_caching():
    """Demonstrate prompt caching - 90% savings on repeated prompts."""
    print("\n" + "=" * 60)
    print("📦 PROMPT CACHING DEMO")
    print("=" * 60)
    
    client = anthropic.Anthropic()
    
    # Long system prompt (must be >1024 tokens for caching to work)
    system_prompt = """You are an expert code reviewer with deep knowledge of:
    - Python best practices and PEP 8 guidelines
    - Software architecture patterns (MVC, microservices, etc.)
    - Security vulnerabilities (OWASP Top 10)
    - Performance optimization techniques
    - Testing methodologies (unit, integration, e2e)
    - Clean code principles and SOLID
    - Database optimization and query performance
    - API design best practices (REST, GraphQL)
    - Concurrent and parallel programming
    - Memory management and garbage collection
    
    When reviewing code, analyze:
    1. Code quality and readability
    2. Potential bugs and edge cases
    3. Security vulnerabilities
    4. Performance bottlenecks
    5. Test coverage gaps
    6. Documentation completeness
    7. Error handling robustness
    
    Provide specific, actionable feedback with code examples where helpful.
    Format your response as a structured review with sections for each category.
    """ * 3  # Repeat to ensure >1024 tokens
    
    questions = [
        "Review this function: def add(a, b): return a + b",
        "Review this: if x == True: pass",
        "Review this: except: pass"
    ]
    
    print(f"\n✅ System prompt: {len(system_prompt)} characters")
    print("   (Must be >1024 tokens for caching)")
    
    for i, question in enumerate(questions):
        print(f"\n{'First call (cache write)' if i == 0 else f'Call {i+1} (cache read)'}:")
        print(f"   Question: {question}")
        
        response = client.messages.create(
            model="claude-sonnet-4-5-20250514",
            max_tokens=200,
            system=[{
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"}  # Enable caching
            }],
            messages=[{"role": "user", "content": question}]
        )
        
        # Check cache usage in response
        usage = response.usage
        print(f"   Input tokens: {usage.input_tokens}")
        if hasattr(usage, 'cache_read_input_tokens'):
            print(f"   Cache read tokens: {usage.cache_read_input_tokens}")
        if hasattr(usage, 'cache_creation_input_tokens'):
            print(f"   Cache write tokens: {usage.cache_creation_input_tokens}")
        
        time.sleep(1)  # Small delay between calls


def demo_batch_api():
    """Demonstrate Batch API - 50% savings on bulk tasks."""
    print("\n" + "=" * 60)
    print("📦 BATCH API DEMO")
    print("=" * 60)
    
    client = anthropic.Anthropic()
    
    # Create batch request
    tasks = [
        {"id": "task-1", "content": "Translate to French: Hello, how are you?"},
        {"id": "task-2", "content": "Translate to French: Goodbye, see you later!"},
        {"id": "task-3", "content": "Translate to French: Thank you very much!"},
    ]
    
    print(f"\n✅ Creating batch with {len(tasks)} tasks...")
    
    batch = client.messages.batches.create(
        requests=[
            {
                "custom_id": task["id"],
                "params": {
                    "model": "claude-sonnet-4-5-20250514",
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": task["content"]}]
                }
            }
            for task in tasks
        ]
    )
    
    print(f"   Batch ID: {batch.id}")
    print(f"   Status: {batch.processing_status}")
    print("\n⏳ Batch processing usually takes <1 hour (up to 24h max)")
    print("   In production, poll batch.processing_status until 'ended'")
    print("\n💰 Batch API gives 50% off normal pricing!")


def demo_extended_thinking():
    """Demonstrate Extended Thinking - cheaper thinking tokens."""
    print("\n" + "=" * 60)
    print("🧠 EXTENDED THINKING DEMO")
    print("=" * 60)
    
    client = anthropic.Anthropic()
    
    question = "What's the most efficient sorting algorithm for nearly-sorted data?"
    
    print(f"\n✅ Question: {question}")
    print("   Using thinking budget of 5000 tokens...")
    
    response = client.messages.create(
        model="claude-sonnet-4-5-20250514",
        max_tokens=8000,
        thinking={
            "type": "enabled",
            "budget_tokens": 5000
        },
        messages=[{"role": "user", "content": question}]
    )
    
    # Process response
    for block in response.content:
        if block.type == "thinking":
            thinking_preview = block.thinking[:200] + "..." if len(block.thinking) > 200 else block.thinking
            print(f"\n🧠 Thinking (preview): {thinking_preview}")
        elif block.type == "text":
            print(f"\n📝 Answer: {block.text[:500]}...")
    
    print(f"\n💰 Thinking tokens are charged at ~$3/MTok (vs $15/MTok output)")
    print(f"   Input tokens: {response.usage.input_tokens}")
    print(f"   Output tokens: {response.usage.output_tokens}")


def main():
    print("=" * 60)
    print("💰 CLAUDE API COST OPTIMIZATION DEMO")
    print("=" * 60)
    print("\nThis demo shows three techniques to save 50-90% on API costs:")
    print("1. Prompt Caching - 90% off repeated system prompts")
    print("2. Batch API - 50% off bulk tasks")
    print("3. Extended Thinking - ~80% off thinking tokens")
    
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n❌ Error: ANTHROPIC_API_KEY not set")
        print("   Set it with: export ANTHROPIC_API_KEY=your_key_here")
        return
    
    print("\n" + "-" * 60)
    
    # Run demos
    demo_prompt_caching()
    demo_batch_api()
    demo_extended_thinking()
    
    print("\n" + "=" * 60)
    print("✅ DEMO COMPLETE")
    print("=" * 60)
    print("\nSee individual examples in the examples/ folder for more details:")
    print("  - examples/batch_api.py")
    print("  - examples/prompt_caching.py")
    print("  - examples/extended_thinking.py")
    print("  - examples/cost_comparison.py")


if __name__ == "__main__":
    main()
