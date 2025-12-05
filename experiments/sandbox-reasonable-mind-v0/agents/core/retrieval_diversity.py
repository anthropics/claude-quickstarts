"""
Retrieval Diversity System - Advanced Enhancement

Provides hybrid retrieval with diversity:
- BM25 keyword matching
- Vector similarity search
- Reranking with cross-encoders
- MMR (Maximal Marginal Relevance) diversification
"""

from typing import List, Dict, Any, Optional, Tuple, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
from functools import lru_cache
import math
import re
import time
import hashlib
from collections import Counter


class RetrievalMethod(Enum):
    """Methods for document retrieval."""
    BM25 = "bm25"
    VECTOR = "vector"
    HYBRID = "hybrid"
    RERANKED = "reranked"


class DiversityMethod(Enum):
    """Methods for result diversification."""
    MMR = "mmr"  # Maximal Marginal Relevance
    CLUSTERING = "clustering"
    TOPIC_COVERAGE = "topic_coverage"


@dataclass
class Document:
    """A document for retrieval."""
    doc_id: str
    content: str
    title: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    term_frequencies: Optional[Dict[str, int]] = None
    source: str = ""
    timestamp: Optional[datetime] = None


@dataclass
class RetrievalResult:
    """Result from retrieval."""
    document: Document
    score: float
    method: RetrievalMethod
    rank: int
    diversity_score: float = 0.0
    relevance_explanation: str = ""


@dataclass
class HybridResult:
    """Combined hybrid retrieval result."""
    results: List[RetrievalResult]
    bm25_count: int
    vector_count: int
    overlap_count: int
    diversity_score: float
    query_expansion_terms: List[str] = field(default_factory=list)


class Tokenizer:
    """Simple tokenizer for BM25."""
    
    def __init__(
        self,
        lowercase: bool = True,
        remove_punctuation: bool = True,
        stopwords: Optional[Set[str]] = None
    ):
        self.lowercase = lowercase
        self.remove_punctuation = remove_punctuation
        self.stopwords = stopwords or {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into", "about"
        }
    
    def tokenize(self, text: str) -> List[str]:
        """Tokenize text into terms."""
        if self.lowercase:
            text = text.lower()
        
        if self.remove_punctuation:
            text = re.sub(r'[^\w\s]', ' ', text)
        
        tokens = text.split()
        
        if self.stopwords:
            tokens = [t for t in tokens if t not in self.stopwords]
        
        return tokens


class BM25Retriever:
    """
    BM25 keyword-based retrieval.
    
    Token optimization: Caches query results to avoid recomputation.
    """
    
    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        tokenizer: Optional[Tokenizer] = None,
        cache_size: int = 128
    ):
        self.k1 = k1
        self.b = b
        self.tokenizer = tokenizer or Tokenizer()
        self.cache_size = cache_size
        
        self.documents: List[Document] = []
        self.doc_lengths: List[int] = []
        self.avg_doc_length: float = 0.0
        self.term_doc_freqs: Dict[str, int] = {}
        self.doc_term_freqs: List[Dict[str, int]] = []
        
        # Cache for query results
        self._query_cache: Dict[str, Tuple[List[RetrievalResult], float]] = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    def index(self, documents: List[Document]):
        """Index documents for BM25 retrieval."""
        self.documents = documents
        self.doc_lengths = []
        self.doc_term_freqs = []
        self.term_doc_freqs = Counter()
        
        for doc in documents:
            tokens = self.tokenizer.tokenize(doc.content)
            self.doc_lengths.append(len(tokens))
            
            term_freqs = Counter(tokens)
            self.doc_term_freqs.append(dict(term_freqs))
            
            # Track document frequency for each term
            for term in set(tokens):
                self.term_doc_freqs[term] += 1
        
        total_length = sum(self.doc_lengths)
        if self.documents:
            self.avg_doc_length = total_length / len(self.documents)
        # Clear cache when index changes
        self._query_cache.clear()
    
    def search(self, query: str, top_k: int = 10) -> List[RetrievalResult]:
        """
        Search for documents matching query.
        
        Token optimization: Caches results for repeated queries.
        """
        # Check cache
        cache_key = f"{query}:{top_k}"
        if cache_key in self._query_cache:
            self._cache_hits += 1
            return self._query_cache[cache_key][0]
        self._cache_misses += 1
        
        query_terms = self.tokenizer.tokenize(query)
        scores: List[Tuple[int, float]] = []
        
        n_docs = len(self.documents)
        
        for doc_idx, doc in enumerate(self.documents):
            score = 0.0
            doc_len = self.doc_lengths[doc_idx]
            term_freqs = self.doc_term_freqs[doc_idx]
            
            for term in query_terms:
                if term not in term_freqs:
                    continue
                
                tf = term_freqs[term]
                df = self.term_doc_freqs.get(term, 0)
                
                # IDF component
                idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
                
                # TF component with length normalization
                tf_norm = tf * (self.k1 + 1) / (
                    tf + self.k1 * (
                        1 - self.b + self.b * doc_len / max(self.avg_doc_length, 1)
                    )
                )
                
                score += idf * tf_norm
            
            if score > 0:
                scores.append((doc_idx, score))
        
        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for rank, (doc_idx, score) in enumerate(scores[:top_k]):
            results.append(RetrievalResult(
                document=self.documents[doc_idx],
                score=score,
                method=RetrievalMethod.BM25,
                rank=rank + 1,
                relevance_explanation=f"BM25 keyword match: {score:.3f}"
            ))
        
        # Cache results (with LRU eviction)
        if len(self._query_cache) >= self.cache_size:
            oldest_key = min(self._query_cache, key=lambda k: self._query_cache[k][1])
            del self._query_cache[oldest_key]
        self._query_cache[cache_key] = (results, time.time())
        
        return results
    
    def cache_stats(self) -> Dict[str, Any]:
        """Return cache statistics for monitoring."""
        total = self._cache_hits + self._cache_misses
        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": self._cache_hits / max(1, total),
            "cache_size": len(self._query_cache)
        }


class VectorRetriever:
    """Vector similarity-based retrieval."""
    
    def __init__(self, embedding_dim: int = 384):
        self.embedding_dim = embedding_dim
        self.documents: List[Document] = []
        self.embeddings: List[List[float]] = []
    
    def index(self, documents: List[Document]):
        """Index documents with embeddings."""
        self.documents = []
        self.embeddings = []
        
        for doc in documents:
            if doc.embedding:
                self.documents.append(doc)
                self.embeddings.append(doc.embedding)
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 10
    ) -> List[RetrievalResult]:
        """Search for documents by vector similarity."""
        scores: List[Tuple[int, float]] = []
        
        for doc_idx, doc_embedding in enumerate(self.embeddings):
            sim = self._cosine_similarity(query_embedding, doc_embedding)
            scores.append((doc_idx, sim))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for rank, (doc_idx, score) in enumerate(scores[:top_k]):
            results.append(RetrievalResult(
                document=self.documents[doc_idx],
                score=score,
                method=RetrievalMethod.VECTOR,
                rank=rank + 1,
                relevance_explanation=f"Vector similarity: {score:.3f}"
            ))
        
        return results
    
    def _cosine_similarity(
        self,
        vec1: List[float],
        vec2: List[float]
    ) -> float:
        """Compute cosine similarity."""
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot / (norm1 * norm2)


class Reranker(ABC):
    """Abstract base for reranking strategies."""
    
    @abstractmethod
    def rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: int = 10
    ) -> List[RetrievalResult]:
        """Rerank retrieval results."""


class CrossEncoderReranker(Reranker):
    """Cross-encoder style reranking (simulated)."""
    
    def __init__(self, score_fn: Optional[Callable[[str, str], float]] = None):
        # In practice, this would use a cross-encoder model
        self.score_fn = score_fn or self._default_score
    
    def rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: int = 10
    ) -> List[RetrievalResult]:
        """Rerank using cross-encoder scores."""
        scored = []
        
        for result in results:
            ce_score = self.score_fn(query, result.document.content)
            # Combine with original score
            combined_score = 0.3 * result.score + 0.7 * ce_score
            scored.append((result, combined_score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        
        reranked = []
        for rank, (result, score) in enumerate(scored[:top_k]):
            reranked.append(RetrievalResult(
                document=result.document,
                score=score,
                method=RetrievalMethod.RERANKED,
                rank=rank + 1,
                diversity_score=result.diversity_score,
                relevance_explanation=f"Reranked: {score:.3f}"
            ))
        
        return reranked
    
    def _default_score(self, query: str, document: str) -> float:
        """Default scoring using term overlap."""
        query_terms = set(query.lower().split())
        doc_terms = set(document.lower().split())
        
        if not query_terms:
            return 0.0
        
        overlap = len(query_terms & doc_terms)
        return overlap / len(query_terms)


class ColBERTReranker(Reranker):
    """ColBERT-style late interaction reranking (simulated)."""
    
    def __init__(self):
        self.token_embeddings: Dict[str, List[float]] = {}
    
    def rerank(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: int = 10
    ) -> List[RetrievalResult]:
        """Rerank using ColBERT-style MaxSim."""
        query_tokens = query.lower().split()
        
        scored = []
        for result in results:
            doc_tokens = result.document.content.lower().split()[:100]
            
            # Simulated MaxSim scoring
            max_sim_sum = 0.0
            for q_token in query_tokens:
                max_sim = max(
                    (self._token_similarity(q_token, d_token) for d_token in doc_tokens),
                    default=0.0
                )
                max_sim_sum += max_sim
            
            score = max_sim_sum / max(len(query_tokens), 1)
            scored.append((result, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        
        reranked = []
        for rank, (result, score) in enumerate(scored[:top_k]):
            reranked.append(RetrievalResult(
                document=result.document,
                score=score,
                method=RetrievalMethod.RERANKED,
                rank=rank + 1,
                relevance_explanation=f"ColBERT MaxSim: {score:.3f}"
            ))
        
        return reranked
    
    def _token_similarity(self, token1: str, token2: str) -> float:
        """Simulated token similarity."""
        if token1 == token2:
            return 1.0
        
        # Character overlap heuristic
        chars1 = set(token1)
        chars2 = set(token2)
        overlap = len(chars1 & chars2)
        total = len(chars1 | chars2)
        
        return overlap / total if total > 0 else 0.0


class MMRDiversifier:
    """Maximal Marginal Relevance diversification."""
    
    def __init__(self, lambda_param: float = 0.5):
        self.lambda_param = lambda_param
    
    def diversify(
        self,
        results: List[RetrievalResult],
        top_k: int = 10
    ) -> List[RetrievalResult]:
        """Apply MMR diversification."""
        if not results:
            return []
        
        selected: List[RetrievalResult] = []
        candidates = list(results)
        
        # Select first by relevance
        selected.append(candidates.pop(0))
        
        while len(selected) < top_k and candidates:
            best_mmr = float('-inf')
            best_idx = 0
            
            for idx, candidate in enumerate(candidates):
                # Relevance component
                relevance = candidate.score
                
                # Diversity component (max similarity to selected)
                max_sim = max(
                    self._document_similarity(candidate.document, s.document)
                    for s in selected
                )
                
                # MMR score
                mmr = self.lambda_param * relevance - (1 - self.lambda_param) * max_sim
                
                if mmr > best_mmr:
                    best_mmr = mmr
                    best_idx = idx
            
            best = candidates.pop(best_idx)
            best.diversity_score = 1 - max(
                self._document_similarity(best.document, s.document)
                for s in selected
            )
            selected.append(best)
        
        # Update ranks
        for rank, result in enumerate(selected):
            result.rank = rank + 1
        
        return selected
    
    def _document_similarity(self, doc1: Document, doc2: Document) -> float:
        """Compute document similarity."""
        if doc1.embedding and doc2.embedding:
            # Vector similarity
            dot = sum(a * b for a, b in zip(doc1.embedding, doc2.embedding))
            norm1 = math.sqrt(sum(a * a for a in doc1.embedding))
            norm2 = math.sqrt(sum(b * b for b in doc2.embedding))
            if norm1 > 0 and norm2 > 0:
                return dot / (norm1 * norm2)
        
        # Fallback to term overlap
        terms1 = set(doc1.content.lower().split())
        terms2 = set(doc2.content.lower().split())
        
        if not terms1 or not terms2:
            return 0.0
        
        overlap = len(terms1 & terms2)
        return overlap / len(terms1 | terms2)


class HybridRetriever:
    """Hybrid retrieval combining BM25 and vector search."""
    
    def __init__(
        self,
        bm25_weight: float = 0.4,
        vector_weight: float = 0.6,
        diversify: bool = True,
        mmr_lambda: float = 0.7
    ):
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight
        self.diversify = diversify
        
        self.bm25 = BM25Retriever()
        self.vector = VectorRetriever()
        self.reranker: Optional[Reranker] = None
        self.mmr = MMRDiversifier(lambda_param=mmr_lambda)
    
    def set_reranker(self, reranker: Reranker):
        """Set the reranker to use."""
        self.reranker = reranker
    
    def index(self, documents: List[Document]):
        """Index documents for hybrid retrieval."""
        self.bm25.index(documents)
        self.vector.index(documents)
    
    def search(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 10,
        bm25_k: int = 50,
        vector_k: int = 50
    ) -> HybridResult:
        """Perform hybrid search."""
        # BM25 retrieval
        bm25_results = self.bm25.search(query, top_k=bm25_k)
        
        # Vector retrieval
        vector_results: List[RetrievalResult] = []
        if query_embedding:
            vector_results = self.vector.search(query_embedding, top_k=vector_k)
        
        # Reciprocal Rank Fusion
        fused = self._reciprocal_rank_fusion(
            bm25_results, vector_results
        )
        
        # Apply reranking if available
        if self.reranker:
            fused = self.reranker.rerank(query, fused, top_k=top_k * 2)
        
        # Apply diversification
        if self.diversify:
            fused = self.mmr.diversify(fused, top_k=top_k)
        else:
            fused = fused[:top_k]
        
        # Compute overlap
        bm25_ids = {r.document.doc_id for r in bm25_results}
        vector_ids = {r.document.doc_id for r in vector_results}
        overlap = len(bm25_ids & vector_ids)
        
        # Compute diversity score
        diversity = self._compute_diversity(fused)
        
        return HybridResult(
            results=fused,
            bm25_count=len(bm25_results),
            vector_count=len(vector_results),
            overlap_count=overlap,
            diversity_score=diversity
        )
    
    def _reciprocal_rank_fusion(
        self,
        bm25_results: List[RetrievalResult],
        vector_results: List[RetrievalResult],
        k: int = 60
    ) -> List[RetrievalResult]:
        """Combine results using RRF."""
        scores: Dict[str, float] = {}
        doc_map: Dict[str, RetrievalResult] = {}
        
        # Score BM25 results
        for result in bm25_results:
            doc_id = result.document.doc_id
            scores[doc_id] = scores.get(doc_id, 0) + self.bm25_weight / (k + result.rank)
            doc_map[doc_id] = result
        
        # Score vector results
        for result in vector_results:
            doc_id = result.document.doc_id
            scores[doc_id] = scores.get(doc_id, 0) + self.vector_weight / (k + result.rank)
            if doc_id not in doc_map:
                doc_map[doc_id] = result
        
        # Sort by combined score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        results = []
        for rank, doc_id in enumerate(sorted_ids):
            original = doc_map[doc_id]
            results.append(RetrievalResult(
                document=original.document,
                score=scores[doc_id],
                method=RetrievalMethod.HYBRID,
                rank=rank + 1,
                relevance_explanation=f"RRF hybrid: {scores[doc_id]:.3f}"
            ))
        
        return results
    
    def _compute_diversity(self, results: List[RetrievalResult]) -> float:
        """Compute overall diversity of results."""
        if len(results) < 2:
            return 1.0
        
        similarities = []
        for i, r1 in enumerate(results):
            for r2 in results[i + 1:]:
                sim = self.mmr._document_similarity(r1.document, r2.document)
                similarities.append(sim)
        
        if not similarities:
            return 1.0
        
        avg_similarity = sum(similarities) / len(similarities)
        return 1 - avg_similarity


class QueryExpander:
    """Expands queries for better recall."""
    
    def __init__(self):
        self.synonyms: Dict[str, List[str]] = {}
    
    def add_synonyms(self, term: str, synonyms: List[str]):
        """Add synonyms for a term."""
        self.synonyms[term.lower()] = [s.lower() for s in synonyms]
    
    def expand(
        self,
        query: str,
        max_expansions: int = 3
    ) -> Tuple[str, List[str]]:
        """Expand query with synonyms."""
        terms = query.lower().split()
        expanded_terms: List[str] = []
        
        for term in terms:
            if term in self.synonyms:
                synonyms = self.synonyms[term][:max_expansions]
                expanded_terms.extend(synonyms)
        
        if expanded_terms:
            expanded_query = f"{query} {' '.join(expanded_terms)}"
            return expanded_query, expanded_terms
        
        return query, []


class RetrievalEvaluator:
    """Evaluates retrieval quality."""
    
    def evaluate(
        self,
        results: List[RetrievalResult],
        relevant_ids: Set[str],
        k_values: List[int] = None
    ) -> Dict[str, float]:
        """Compute retrieval metrics."""
        if k_values is None:
            k_values = [1, 3, 5, 10]
        
        metrics: Dict[str, float] = {}
        result_ids = [r.document.doc_id for r in results]
        
        for k in k_values:
            top_k = result_ids[:k]
            hits = len(set(top_k) & relevant_ids)
            
            metrics[f"precision@{k}"] = hits / k if k > 0 else 0.0
            metrics[f"recall@{k}"] = hits / len(relevant_ids) if relevant_ids else 0.0
        
        # MRR
        for rank, doc_id in enumerate(result_ids, 1):
            if doc_id in relevant_ids:
                metrics["mrr"] = 1.0 / rank
                break
        else:
            metrics["mrr"] = 0.0
        
        # NDCG
        metrics["ndcg@10"] = self._compute_ndcg(result_ids[:10], relevant_ids)
        
        return metrics
    
    def _compute_ndcg(
        self,
        result_ids: List[str],
        relevant_ids: Set[str]
    ) -> float:
        """Compute NDCG@k."""
        dcg = 0.0
        for i, doc_id in enumerate(result_ids):
            if doc_id in relevant_ids:
                dcg += 1.0 / math.log2(i + 2)
        
        ideal_dcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant_ids), len(result_ids))))
        
        if ideal_dcg == 0:
            return 0.0
        
        return dcg / ideal_dcg


# Factory functions
def create_hybrid_retriever(
    bm25_weight: float = 0.4,
    vector_weight: float = 0.6,
    use_reranker: bool = True
) -> HybridRetriever:
    """Create a hybrid retriever."""
    retriever = HybridRetriever(
        bm25_weight=bm25_weight,
        vector_weight=vector_weight,
        diversify=True
    )
    
    if use_reranker:
        retriever.set_reranker(CrossEncoderReranker())
    
    return retriever


def create_document(
    doc_id: str,
    content: str,
    title: str = "",
    embedding: Optional[List[float]] = None
) -> Document:
    """Create a document for retrieval."""
    return Document(
        doc_id=doc_id,
        content=content,
        title=title,
        embedding=embedding
    )
