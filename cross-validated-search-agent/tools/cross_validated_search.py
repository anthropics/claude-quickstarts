"""
Cross-validated search tool implementation.
"""

from typing import Dict, Any
from cross_validated_search import CrossValidatedSearcher


class CrossValidatedSearchTool:
    """
    Tool for cross-validated web search.
    """
    
    name = "cross_validated_search"
    description = "Search the web with cross-validation for accurate facts"
    
    def __init__(self, min_confidence: str = "likely_true"):
        self.searcher = CrossValidatedSearcher()
        self.min_confidence = min_confidence
    
    def run(self, query: str, search_type: str = "text") -> str:
        results = self.searcher.search(query, search_type=search_type)
        
        response_parts = [
            f"Answer: {results.answer}",
            f"Confidence: {results.confidence}",
            "Sources:",
        ]
        
        for i, source in enumerate(results.sources[:5], 1):
            response_parts.append(f"  {i}. [{source.engine}] {source.title}")
            response_parts.append(f"     URL: {source.url}")
        
        return "\n".join(response_parts)
    
    def to_tool_definition(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "search_type": {"type": "string", "enum": ["text", "news", "images"]}
                },
                "required": ["query"]
            }
        }