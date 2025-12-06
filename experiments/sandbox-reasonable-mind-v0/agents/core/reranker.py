"""
Simple reranker placeholder for retrieval results.

Combines sparse/dense scores and optional provenance weight.
"""
from typing import List, Dict, Any


class Reranker:
    def __init__(self, provenance_weight: float = 0.1):
        self.provenance_weight = provenance_weight

    def rerank(self, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Re-rank documents based on score and provenance weight.

        Expects each doc to have:
        - score: base relevance
        - metadata: may contain 'provenance_score'
        """
        for d in docs:
            prov = d.get("metadata", {}).get("provenance_score", 0)
            d["_final_score"] = d.get("score", 0) + self.provenance_weight * prov
        reranked = sorted(docs, key=lambda x: x["_final_score"], reverse=True)
        for i, d in enumerate(reranked):
            d["rank"] = i + 1
        return reranked
