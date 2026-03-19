"""
Fact-check tool implementation.
"""

from typing import Dict, Any
from cross_validated_search import CrossValidatedSearcher


class FactCheckTool:
    """
    Tool for fact-checking claims.
    """
    
    name = "fact_check"
    description = "Verify a claim with cross-validated search"
    
    def __init__(self):
        self.searcher = CrossValidatedSearcher()
    
    def run(self, claim: str) -> str:
        results = self.searcher.search(claim, search_type="text")
        
        # Determine status
        status_map = {
            "verified": "✅ VERIFIED",
            "likely_true": "🟢 LIKELY TRUE",
            "uncertain": "🟡 UNCERTAIN",
            "likely_false": "🔴 LIKELY FALSE"
        }
        status = status_map.get(results.confidence, "❓ UNKNOWN")
        
        response_parts = [
            f"Claim: {claim}",
            f"Status: {status}",
            "Evidence:",
        ]
        
        for source in results.sources[:3]:
            response_parts.append(f"  - {source.title}")
            response_parts.append(f"    {source.url}")
        
        return "\n".join(response_parts)
    
    def to_tool_definition(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string", "description": "The claim to fact-check"}
                },
                "required": ["claim"]
            }
        }