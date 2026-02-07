#!/usr/bin/env python3
"""
Prompt Caching Example - Save 90% on repeated system prompts

Prompt Caching stores long system prompts on the server, reducing costs
by 90% when the same prompt is used in subsequent requests.

Requirements:
- Minimum 1024 tokens for Sonnet (2048 for Haiku, 1024 for Opus)
- Cache lasts 5 minutes (refreshes on each use)
"""

import os
import time
from dotenv import load_dotenv
import anthropic

load_dotenv()


class CachedClient:
    """A Claude client wrapper that uses prompt caching."""
    
    def __init__(self, system_prompt: str, model: str = "claude-sonnet-4-5-20250514"):
        """
        Initialize with a system prompt that will be cached.
        
        Args:
            system_prompt: Long system prompt (>1024 tokens for Sonnet)
            model: Claude model to use
        """
        self.client = anthropic.Anthropic()
        self.system_prompt = system_prompt
        self.model = model
        self.conversation_history = []
        
    def chat(self, user_message: str, max_tokens: int = 1024) -> dict:
        """
        Send a message with the cached system prompt.
        
        Args:
            user_message: The user's message
            max_tokens: Maximum tokens in response
            
        Returns:
            Dict with response text and cache statistics
        """
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=[{
                "type": "text",
                "text": self.system_prompt,
                "cache_control": {"type": "ephemeral"}  # Enable caching!
            }],
            messages=self.conversation_history
        )
        
        assistant_message = response.content[0].text
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })
        
        # Extract cache statistics
        usage = response.usage
        cache_stats = {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_read_tokens": getattr(usage, 'cache_read_input_tokens', 0),
            "cache_write_tokens": getattr(usage, 'cache_creation_input_tokens', 0)
        }
        
        return {
            "text": assistant_message,
            "cache_stats": cache_stats,
            "is_cache_hit": cache_stats["cache_read_tokens"] > 0
        }


def create_long_system_prompt() -> str:
    """Create a system prompt long enough to be cached (>1024 tokens)."""
    return """You are an expert AI assistant specializing in software engineering best practices.

Your areas of expertise include:

## Programming Languages
- Python: PEP 8, type hints, asyncio, pytest, modern packaging (pyproject.toml)
- TypeScript/JavaScript: ES6+, Node.js, React, Next.js, testing with Jest
- Rust: ownership, lifetimes, async/await, cargo ecosystem
- Go: goroutines, channels, effective Go patterns

## Software Architecture
- Microservices: API design, service mesh, event-driven architecture
- Monolith to microservices migration strategies
- Domain-Driven Design (DDD) principles
- Clean Architecture and hexagonal architecture
- CQRS and Event Sourcing patterns

## DevOps & Infrastructure
- Containerization: Docker, Kubernetes, Helm
- CI/CD: GitHub Actions, GitLab CI, Jenkins
- Infrastructure as Code: Terraform, Pulumi, CloudFormation
- Observability: Prometheus, Grafana, OpenTelemetry

## Database Design
- SQL: PostgreSQL, MySQL optimization, query planning
- NoSQL: MongoDB, Redis, DynamoDB patterns
- Data modeling and normalization
- Database migration strategies

## Security
- OWASP Top 10 vulnerabilities and mitigations
- Authentication: OAuth2, JWT, OIDC
- Authorization: RBAC, ABAC, policy engines
- Secure coding practices

## Testing
- Unit testing best practices
- Integration testing strategies
- End-to-end testing with Playwright/Cypress
- Test-Driven Development (TDD)
- Property-based testing

## Code Quality
- SOLID principles
- Design patterns (Gang of Four)
- Refactoring techniques
- Code review best practices
- Technical debt management

When providing assistance:
1. Always consider the broader context and potential side effects
2. Suggest incremental improvements when appropriate
3. Explain trade-offs between different approaches
4. Provide concrete code examples when helpful
5. Reference relevant documentation or standards
6. Consider performance, maintainability, and security implications

Format your responses with clear sections and use code blocks with syntax highlighting.
""" * 2  # Double to ensure >1024 tokens


def example_basic_caching():
    """Demonstrate basic prompt caching behavior."""
    print("\n" + "=" * 50)
    print("Example: Basic Prompt Caching")
    print("=" * 50)
    
    system_prompt = create_long_system_prompt()
    print(f"\nSystem prompt: {len(system_prompt)} characters")
    
    client = CachedClient(system_prompt)
    
    questions = [
        "What's the best way to handle errors in Python?",
        "How should I structure a FastAPI project?",
        "What are the key principles of clean code?"
    ]
    
    for i, question in enumerate(questions):
        print(f"\n{'─' * 40}")
        print(f"Question {i+1}: {question[:50]}...")
        
        response = client.chat(question, max_tokens=200)
        stats = response["cache_stats"]
        
        if i == 0:
            print(f"📝 Cache WRITE: {stats['cache_write_tokens']} tokens (+25% cost)")
        else:
            print(f"🚀 Cache READ: {stats['cache_read_tokens']} tokens (-90% cost!)")
        
        print(f"Response preview: {response['text'][:100]}...")
        
        time.sleep(1)


def example_cost_calculation():
    """Show cost comparison: Without vs With caching."""
    print("\n" + "=" * 50)
    print("Cost Comparison: Without vs With Caching")
    print("=" * 50)
    
    # Pricing (Claude Sonnet 4.5, per million tokens)
    normal_input = 3.0
    cache_write = 3.75  # +25%
    cache_read = 0.30   # -90%
    output_price = 15.0
    
    # Scenario: 10 requests with shared 2000-token system prompt
    num_requests = 10
    system_tokens = 2000
    user_tokens = 100
    output_tokens = 500
    
    # Without caching
    without_input_cost = (num_requests * (system_tokens + user_tokens) / 1_000_000) * normal_input
    without_output_cost = (num_requests * output_tokens / 1_000_000) * output_price
    without_total = without_input_cost + without_output_cost
    
    # With caching
    # First request: cache write
    first_input_cost = ((system_tokens * (cache_write / normal_input)) + user_tokens) / 1_000_000 * normal_input
    # Subsequent requests: cache read
    subsequent_input_cost = ((num_requests - 1) * ((system_tokens * (cache_read / normal_input)) + user_tokens)) / 1_000_000 * normal_input
    with_output_cost = (num_requests * output_tokens / 1_000_000) * output_price
    with_total = first_input_cost + subsequent_input_cost + with_output_cost
    
    print(f"\nScenario: {num_requests} requests with shared system prompt")
    print(f"  - System prompt: {system_tokens} tokens")
    print(f"  - User message: {user_tokens} tokens")
    print(f"  - Response: {output_tokens} tokens")
    
    print(f"\n💰 Without caching: ${without_total:.6f}")
    print(f"💰 With caching:    ${with_total:.6f}")
    savings_pct = ((without_total - with_total) / without_total) * 100
    print(f"💰 Savings:         ${without_total - with_total:.6f} ({savings_pct:.1f}%)")


def example_rag_application():
    """Show how caching helps in RAG applications."""
    print("\n" + "=" * 50)
    print("Example: RAG Application with Caching")
    print("=" * 50)
    
    # In a RAG application, you often have a large context
    rag_context = """[Knowledge Base Context]
    
    Document 1: Company Policies
    - Remote work policy: Employees may work remotely up to 3 days per week...
    - Expense policy: All expenses over $100 require manager approval...
    - PTO policy: Employees receive 20 days PTO plus 10 company holidays...
    
    Document 2: Technical Guidelines
    - Code review requirements: All PRs require at least one approval...
    - Deployment process: Use CI/CD pipeline for all production deployments...
    - Security standards: All API endpoints must use authentication...
    
    Document 3: FAQ
    Q: How do I request time off? A: Use the HR portal to submit PTO requests...
    Q: What's the password policy? A: Minimum 12 characters, changed every 90 days...
    """ * 5  # Simulate larger context
    
    system_prompt = f"""You are a helpful company assistant. Answer questions based on this context:

{rag_context}

Always cite which document you're referencing in your answer."""
    
    print(f"\nRAG context: {len(rag_context)} characters")
    print("This context would be cached for all user questions!")
    print("\nWith caching, users asking multiple questions about the same")
    print("documents get 90% off on the context tokens for each follow-up.")


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set")
        exit(1)
    
    example_basic_caching()
    example_cost_calculation()
    example_rag_application()
