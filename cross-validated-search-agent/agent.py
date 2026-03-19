"""
Cross-Validated Search Agent for Claude

A Claude agent that uses cross-validated web search for hallucination-free responses.
"""

import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    from anthropic import Anthropic
except ImportError:
    raise ImportError("anthropic library required: pip install anthropic")

try:
    from cross_validated_search import CrossValidatedSearcher
except ImportError:
    raise ImportError("cross-validated-search library required: pip install cross-validated-search")


@dataclass
class SearchResult:
    """Result from cross-validated search."""
    answer: str
    confidence: str
    sources: List[Dict[str, str]]


class CrossValidatedSearchTool:
    """
    Tool for cross-validated web search.
    
    This tool searches the web and verifies facts across multiple sources
    to prevent hallucinations.
    """
    
    name = "cross_validated_search"
    description = "Search the web with cross-validation for accurate facts"
    
    def __init__(self, min_confidence: str = "likely_true"):
        """
        Initialize the tool.
        
        Args:
            min_confidence: Minimum confidence level (verified, likely_true, uncertain, likely_false)
        """
        self.searcher = CrossValidatedSearcher()
        self.min_confidence = min_confidence
    
    def run(self, query: str, search_type: str = "text") -> str:
        """
        Search the web with cross-validation.
        
        Args:
            query: The search query
            search_type: Type of search (text, news, images)
        
        Returns:
            Formatted search result with confidence and sources
        """
        results = self.searcher.search(query, search_type=search_type)
        
        # Format response
        response_parts = [
            f"Answer: {results.answer}",
            f"Confidence: {results.confidence}",
            f"Sources:",
        ]
        
        for i, source in enumerate(results.sources[:5], 1):
            response_parts.append(f"  {i}. [{source.engine}] {source.title}")
            response_parts.append(f"     URL: {source.url}")
        
        return "\n".join(response_parts)
    
    def to_tool_definition(self) -> Dict[str, Any]:
        """Convert to Claude tool definition."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "search_type": {
                        "type": "string",
                        "enum": ["text", "news", "images"],
                        "description": "Type of search"
                    }
                },
                "required": ["query"]
            }
        }


class FactCheckTool:
    """
    Tool for fact-checking claims.
    """
    
    name = "fact_check"
    description = "Verify a claim with cross-validated search"
    
    def __init__(self):
        self.searcher = CrossValidatedSearcher()
    
    def run(self, claim: str) -> str:
        """
        Fact-check a claim.
        
        Args:
            claim: The claim to verify
        
        Returns:
            Fact-check result with status and evidence
        """
        results = self.searcher.search(claim, search_type="text")
        
        # Determine status
        if results.confidence == "verified":
            status = "✅ VERIFIED"
        elif results.confidence == "likely_true":
            status = "🟢 LIKELY TRUE"
        elif results.confidence == "uncertain":
            status = "🟡 UNCERTAIN"
        else:
            status = "🔴 LIKELY FALSE"
        
        response_parts = [
            f"Claim: {claim}",
            f"Status: {status}",
            f"Evidence:",
        ]
        
        for source in results.sources[:3]:
            response_parts.append(f"  - {source.title}")
            response_parts.append(f"    {source.url}")
        
        return "\n".join(response_parts)
    
    def to_tool_definition(self) -> Dict[str, Any]:
        """Convert to Claude tool definition."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "claim": {
                        "type": "string",
                        "description": "The claim to fact-check"
                    }
                },
                "required": ["claim"]
            }
        }


class CrossValidatedSearchAgent:
    """
    Claude agent with cross-validated search capabilities.
    
    This agent uses Claude API with cross-validated search tools to provide
    hallucination-free responses.
    """
    
    def __init__(
        self,
        name: str = "FactChecker",
        system: str = None,
        model: str = "claude-3-5-sonnet-20241022",
        tools: List = None,
    ):
        """
        Initialize the agent.
        
        Args:
            name: Agent name
            system: System prompt
            model: Claude model to use
            tools: List of tools to use
        """
        self.name = name
        self.model = model
        self.client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        
        # Default system prompt
        if system is None:
            system = """You are a helpful assistant that provides accurate, verified information.
            
When answering factual questions:
1. Use the cross_validated_search tool to find verified information
2. Always report the confidence level of your answers
3. Cite your sources
4. If information is uncertain, acknowledge it

Never present unverified information as fact."""
        
        self.system = system
        
        # Default tools
        if tools is None:
            tools = [CrossValidatedSearchTool(), FactCheckTool()]
        self.tools = tools
    
    def run(self, message: str, max_turns: int = 10) -> str:
        """
        Run the agent with a message.
        
        Args:
            message: User message
            max_turns: Maximum number of tool use turns
        
        Returns:
            Agent response
        """
        messages = [{"role": "user", "content": message}]
        tool_definitions = [tool.to_tool_definition() for tool in self.tools]
        
        for _ in range(max_turns):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self.system,
                tools=tool_definitions,
                messages=messages,
            )
            
            # Check if we need to use tools
            if response.stop_reason == "tool_use":
                # Find tool use blocks
                tool_use_blocks = [
                    block for block in response.content if block.type == "tool_use"
                ]
                
                if tool_use_blocks:
                    # Add assistant response
                    messages.append({"role": "assistant", "content": response.content})
                    
                    # Process each tool use
                    for tool_use in tool_use_blocks:
                        tool_name = tool_use.name
                        tool_input = tool_use.input
                        
                        # Find and run the tool
                        for tool in self.tools:
                            if tool.name == tool_name:
                                result = tool.run(**tool_input)
                                messages.append({
                                    "role": "user",
                                    "content": [{
                                        "type": "tool_result",
                                        "tool_use_id": tool_use.id,
                                        "content": result
                                    }]
                                })
                                break
                else:
                    # No tool use, return the response
                    return response.content[0].text
            else:
                # No tool use needed, return the response
                return response.content[0].text
        
        return "Maximum turns reached without completion."
    
    def chat(self, message: str) -> str:
        """Alias for run()."""
        return self.run(message)


def create_fact_checker():
    """Create a fact-checking agent."""
    return CrossValidatedSearchAgent(
        name="FactChecker",
        system="""You are a fact-checking assistant.
        
Use the fact_check tool to verify claims.
Always report the status (verified/likely_true/uncertain/likely_false).
Provide evidence from multiple sources.""",
    )


def create_research_agent():
    """Create a research agent."""
    return CrossValidatedSearchAgent(
        name="ResearchAgent",
        system="""You are a research assistant.
        
Use cross_validated_search to find verified information.
Always cite your sources.
Report confidence levels for all claims.""",
    )


if __name__ == "__main__":
    # Example usage
    print("Cross-Validated Search Agent for Claude")
    print("=" * 40)
    
    # Create agent
    agent = create_fact_checker()
    
    # Run a query
    response = agent.run("What is the latest version of Python?")
    print(response)
    
    print("\n" + "=" * 40)
    print("For more examples, see README.md")