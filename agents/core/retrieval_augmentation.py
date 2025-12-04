"""
Retrieval Augmentation System - Phase 2 Enhancement

Provides advanced retrieval capabilities:
- Semantic chunking and splitting
- Re-ranking with cross-encoders
- Query expansion and reformulation
- Hybrid retrieval (dense + sparse)
- Context compression
"""

from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import re
import math


class ChunkingStrategy(Enum):
    """Strategies for document chunking."""
    FIXED_SIZE = "fixed_size"  # Fixed token/character count
    SENTENCE = "sentence"  # Split on sentences
    PARAGRAPH = "paragraph"  # Split on paragraphs
    SEMANTIC = "semantic"  # Split on semantic boundaries
    RECURSIVE = "recursive"  # Recursive splitting with fallback


class RetrievalMode(Enum):
    """Retrieval modes."""
    DENSE = "dense"  # Vector similarity only
    SPARSE = "sparse"  # Keyword/BM25 only
    HYBRID = "hybrid"  # Combination of dense and sparse


@dataclass
class Chunk:
    """A chunk of text with metadata."""
    chunk_id: str
    content: str
    source_id: str
    start_offset: int
    end_offset: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    token_count: int = 0
    source: Optional[str] = None
    start_idx: Optional[int] = None
    end_idx: Optional[int] = None

    def __post_init__(self):
        # Alias handling for tests/compat
        if self.source and not self.source_id:
            self.source_id = self.source
        if self.start_idx is not None:
            self.start_offset = self.start_idx
        if self.end_idx is not None:
            self.end_offset = self.end_idx


@dataclass
class RetrievedDocument:
    """A retrieved document with relevance info."""
    doc_id: str
    content: str
    score: float
    rank: int
    retrieval_method: RetrievalMode
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunks: List[Chunk] = field(default_factory=list)


@dataclass
class QueryExpansion:
    """Expanded query with variants."""
    original_query: str
    expanded_terms: List[str]
    synonyms: Dict[str, List[str]]
    reformulations: List[str]
    hypothetical_answer: Optional[str] = None  # For HyDE
    expanded_queries: List[str] = field(default_factory=list)

    def __post_init__(self):
        # Provide a consolidated list of expansions
        if not self.expanded_queries:
            combined = list(self.expanded_terms) + list(self.reformulations)
            self.expanded_queries = combined


@dataclass
class RetrievalResult:
    """Result of a retrieval operation."""
    query: str
    documents: List[RetrievedDocument]
    total_candidates: int
    retrieval_time_ms: float
    mode: RetrievalMode
    query_expansion: Optional[QueryExpansion] = None


class SimpleReranker:
    """
    Lightweight reranker placeholder.

    Reorders documents by a heuristic score (default: length-based)
    to simulate a cross-encoder/LLM reranker without heavy deps.
    """

    def __init__(self, scorer: Optional[Callable[[RetrievedDocument], float]] = None):
        self.scorer = scorer or (lambda doc: len(doc.content))

    def rerank(self, docs: List[RetrievedDocument]) -> List[RetrievedDocument]:
        return sorted(docs, key=self.scorer, reverse=True)


class TextChunker:
    """Handles text chunking with various strategies."""
    
    def __init__(
        self,
        strategy: ChunkingStrategy = ChunkingStrategy.SEMANTIC,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100
    ):
        self.strategy = strategy
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        
        # Sentence boundary patterns
        self._sentence_pattern = re.compile(
            r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])\s*\n'
        )
        
        # Paragraph boundary
        self._paragraph_pattern = re.compile(r'\n\s*\n')
        
        # Semantic boundary indicators
        self._semantic_markers = [
            r'^#{1,6}\s+',  # Markdown headers
            r'^(?:def|class|function)\s+',  # Code definitions
            r'^\d+\.\s+',  # Numbered lists
            r'^[-*]\s+',  # Bullet points
            r'^```',  # Code blocks
        ]
    
    def chunk(
        self, 
        text: str, 
        source_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """Chunk text using the configured strategy."""
        if self.strategy == ChunkingStrategy.FIXED_SIZE:
            return self._chunk_fixed(text, source_id, metadata)
        elif self.strategy == ChunkingStrategy.SENTENCE:
            return self._chunk_sentences(text, source_id, metadata)
        elif self.strategy == ChunkingStrategy.PARAGRAPH:
            return self._chunk_paragraphs(text, source_id, metadata)
        elif self.strategy == ChunkingStrategy.SEMANTIC:
            return self._chunk_semantic(text, source_id, metadata)
        else:  # RECURSIVE
            return self._chunk_recursive(text, source_id, metadata)
    
    def _chunk_fixed(
        self, 
        text: str, 
        source_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """Split into fixed-size chunks with overlap."""
        chunks = []
        start = 0
        chunk_idx = 0
        
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            
            # Try to break at word boundary
            if end < len(text):
                while end > start and text[end] not in ' \n\t':
                    end -= 1
                if end == start:
                    end = start + self.chunk_size
            
            content = text[start:end].strip()
            
            if len(content) >= self.min_chunk_size:
                chunks.append(Chunk(
                    chunk_id=f"{source_id}_chunk_{chunk_idx}",
                    content=content,
                    source_id=source_id,
                    start_offset=start,
                    end_offset=end,
                    metadata=metadata or {},
                    token_count=len(content.split())
                ))
                chunk_idx += 1
            
            start = end - self.chunk_overlap
            if start >= end:
                start = end
        
        return chunks
    
    def _chunk_sentences(
        self, 
        text: str, 
        source_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """Split on sentence boundaries."""
        sentences = self._sentence_pattern.split(text)
        chunks = []
        current_chunk = ""
        start_offset = 0
        chunk_idx = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            if len(current_chunk) + len(sentence) <= self.chunk_size:
                current_chunk += (" " if current_chunk else "") + sentence
            else:
                if len(current_chunk) >= self.min_chunk_size:
                    chunks.append(Chunk(
                        chunk_id=f"{source_id}_chunk_{chunk_idx}",
                        content=current_chunk,
                        source_id=source_id,
                        start_offset=start_offset,
                        end_offset=start_offset + len(current_chunk),
                        metadata=metadata or {},
                        token_count=len(current_chunk.split())
                    ))
                    chunk_idx += 1
                    start_offset += len(current_chunk)
                
                current_chunk = sentence
        
        # Don't forget the last chunk
        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            chunks.append(Chunk(
                chunk_id=f"{source_id}_chunk_{chunk_idx}",
                content=current_chunk,
                source_id=source_id,
                start_offset=start_offset,
                end_offset=start_offset + len(current_chunk),
                metadata=metadata or {},
                token_count=len(current_chunk.split())
            ))
        
        return chunks
    
    def _chunk_paragraphs(
        self, 
        text: str, 
        source_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """Split on paragraph boundaries."""
        paragraphs = self._paragraph_pattern.split(text)
        chunks = []
        current_chunk = ""
        start_offset = 0
        chunk_idx = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            if len(current_chunk) + len(paragraph) <= self.chunk_size:
                current_chunk += ("\n\n" if current_chunk else "") + paragraph
            else:
                if len(current_chunk) >= self.min_chunk_size:
                    chunks.append(Chunk(
                        chunk_id=f"{source_id}_chunk_{chunk_idx}",
                        content=current_chunk,
                        source_id=source_id,
                        start_offset=start_offset,
                        end_offset=start_offset + len(current_chunk),
                        metadata=metadata or {},
                        token_count=len(current_chunk.split())
                    ))
                    chunk_idx += 1
                    start_offset += len(current_chunk)
                
                current_chunk = paragraph
        
        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            chunks.append(Chunk(
                chunk_id=f"{source_id}_chunk_{chunk_idx}",
                content=current_chunk,
                source_id=source_id,
                start_offset=start_offset,
                end_offset=start_offset + len(current_chunk),
                metadata=metadata or {},
                token_count=len(current_chunk.split())
            ))
        
        return chunks
    
    def _chunk_semantic(
        self, 
        text: str, 
        source_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """Split on semantic boundaries (headers, code blocks, etc.)."""
        # Find all semantic boundary positions
        boundaries = [0]
        
        for pattern in self._semantic_markers:
            for match in re.finditer(pattern, text, re.MULTILINE):
                if match.start() not in boundaries:
                    boundaries.append(match.start())
        
        boundaries.append(len(text))
        boundaries.sort()
        
        # Create chunks from boundaries
        chunks = []
        chunk_idx = 0
        
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            content = text[start:end].strip()
            
            if len(content) >= self.min_chunk_size:
                # If chunk is too large, split further
                if len(content) > self.chunk_size:
                    sub_chunks = self._chunk_fixed(content, f"{source_id}_sub", metadata)
                    for sub in sub_chunks:
                        sub.chunk_id = f"{source_id}_chunk_{chunk_idx}"
                        sub.start_offset += start
                        sub.end_offset += start
                        chunks.append(sub)
                        chunk_idx += 1
                else:
                    chunks.append(Chunk(
                        chunk_id=f"{source_id}_chunk_{chunk_idx}",
                        content=content,
                        source_id=source_id,
                        start_offset=start,
                        end_offset=end,
                        metadata=metadata or {},
                        token_count=len(content.split())
                    ))
                    chunk_idx += 1
        
        return chunks
    
    def _chunk_recursive(
        self, 
        text: str, 
        source_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """Recursive splitting with fallback to simpler strategies."""
        # Try semantic first
        chunks = self._chunk_semantic(text, source_id, metadata)
        
        # If chunks are still too large, split paragraphs
        final_chunks = []
        for chunk in chunks:
            if len(chunk.content) > self.chunk_size * 1.5:
                sub_chunks = self._chunk_paragraphs(
                    chunk.content, chunk.source_id, metadata
                )
                final_chunks.extend(sub_chunks)
            else:
                final_chunks.append(chunk)
        
        return final_chunks


class QueryExpander:
    """Handles query expansion and reformulation."""
    
    def __init__(self):
        # Simple synonym dictionary (would use WordNet or embeddings in production)
        self._synonyms: Dict[str, List[str]] = {
            "find": ["search", "locate", "discover", "get"],
            "create": ["make", "generate", "build", "construct"],
            "delete": ["remove", "erase", "clear", "eliminate"],
            "update": ["modify", "change", "edit", "revise"],
            "error": ["bug", "issue", "problem", "fault"],
            "fast": ["quick", "rapid", "speedy", "efficient"],
            "big": ["large", "huge", "massive", "extensive"],
            "small": ["tiny", "little", "minimal", "compact"],
        }
    
    def expand(self, query: str) -> QueryExpansion:
        """Expand a query with synonyms and reformulations."""
        words = query.lower().split()
        expanded_terms = []
        synonyms_found = {}
        
        for word in words:
            if word in self._synonyms:
                synonyms_found[word] = self._synonyms[word]
                expanded_terms.extend(self._synonyms[word])
        
        # Generate reformulations
        reformulations = self._generate_reformulations(query)
        
        return QueryExpansion(
            original_query=query,
            expanded_terms=expanded_terms,
            synonyms=synonyms_found,
            reformulations=reformulations
        )
    
    def _generate_reformulations(self, query: str) -> List[str]:
        """Generate query reformulations."""
        reformulations = []
        
        # Question to statement
        if query.lower().startswith(("what", "how", "why", "when", "where")):
            # Remove question word and question mark
            statement = re.sub(r'^(what|how|why|when|where)\s+', '', query, flags=re.IGNORECASE)
            statement = statement.rstrip('?')
            reformulations.append(statement)
        
        # Add context hints
        reformulations.append(f"information about {query}")
        reformulations.append(f"examples of {query}")
        
        return reformulations
    
    def generate_hyde(self, query: str) -> str:
        """
        Generate a Hypothetical Document Embedding (HyDE).
        
        In production, this would use an LLM to generate a hypothetical answer.
        """
        # Simple template-based approach
        templates = [
            f"The answer to '{query}' is that",
            f"When asked about {query}, the response should explain that",
            f"Regarding {query}, it is important to note that"
        ]
        return templates[0]  # Would use LLM in production


class BM25Scorer:
    """BM25 scoring for sparse retrieval."""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._documents: Dict[str, List[str]] = {}
        self._doc_lengths: Dict[str, int] = {}
        self._avg_doc_length: float = 0
        self._idf: Dict[str, float] = {}
    
    def index(self, doc_id: str, tokens: List[str]) -> None:
        """Index a document."""
        self._documents[doc_id] = tokens
        self._doc_lengths[doc_id] = len(tokens)
        self._update_stats()
    
    def _update_stats(self) -> None:
        """Update average document length and IDF scores."""
        if not self._doc_lengths:
            return
        
        self._avg_doc_length = sum(self._doc_lengths.values()) / len(self._doc_lengths)
        
        # Calculate IDF for all terms
        n = len(self._documents)
        term_doc_counts: Dict[str, int] = {}
        
        for tokens in self._documents.values():
            seen = set()
            for token in tokens:
                if token not in seen:
                    term_doc_counts[token] = term_doc_counts.get(token, 0) + 1
                    seen.add(token)
        
        for term, doc_count in term_doc_counts.items():
            # IDF with smoothing
            self._idf[term] = math.log((n - doc_count + 0.5) / (doc_count + 0.5) + 1)
    
    def score(self, doc_id: str, query_tokens: List[str]) -> float:
        """Score a document against a query."""
        if doc_id not in self._documents:
            return 0.0
        
        doc_tokens = self._documents[doc_id]
        doc_length = self._doc_lengths[doc_id]
        
        # Count term frequencies in document
        tf: Dict[str, int] = {}
        for token in doc_tokens:
            tf[token] = tf.get(token, 0) + 1
        
        score = 0.0
        for term in query_tokens:
            if term not in tf:
                continue
            
            term_freq = tf[term]
            idf = self._idf.get(term, 0)
            
            # BM25 formula
            numerator = term_freq * (self.k1 + 1)
            denominator = term_freq + self.k1 * (
                1 - self.b + self.b * (doc_length / self._avg_doc_length)
            )
            
            score += idf * (numerator / denominator)
        
        return score


class Reranker:
    """Re-ranks retrieved documents for better relevance."""
    
    def __init__(self):
        self._feature_weights = {
            "lexical_overlap": 0.3,
            "position_bias": 0.1,
            "recency": 0.1,
            "source_quality": 0.2,
            "semantic_similarity": 0.3
        }
    
    def rerank(
        self, 
        query: str, 
        documents: List[RetrievedDocument],
        top_k: int = 10
    ) -> List[RetrievedDocument]:
        """Re-rank documents using multiple signals."""
        if not documents:
            return []
        
        # Calculate reranking scores
        scored_docs = []
        query_words = set(query.lower().split())
        
        for i, doc in enumerate(documents):
            features = self._extract_features(query_words, doc, i, len(documents))
            rerank_score = sum(
                self._feature_weights.get(f, 0) * v 
                for f, v in features.items()
            )
            scored_docs.append((doc, rerank_score))
        
        # Sort by reranking score
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        # Update ranks and return
        result = []
        for new_rank, (doc, _score) in enumerate(scored_docs[:top_k]):
            doc.rank = new_rank + 1
            result.append(doc)
        
        return result
    
    def _extract_features(
        self, 
        query_words: set, 
        doc: RetrievedDocument,
        position: int,
        total: int
    ) -> Dict[str, float]:
        """Extract features for reranking."""
        doc_words = set(doc.content.lower().split())
        
        # Lexical overlap (Jaccard similarity)
        if query_words and doc_words:
            overlap = len(query_words & doc_words) / len(query_words | doc_words)
        else:
            overlap = 0.0
        
        # Position bias (earlier is often better)
        position_score = 1.0 - (position / max(total, 1))
        
        # Source quality (from metadata)
        source_quality = doc.metadata.get("quality_score", 0.5)
        
        # Recency (from metadata)
        recency = doc.metadata.get("recency_score", 0.5)
        
        # Semantic similarity (use original retrieval score as proxy)
        semantic = doc.score
        
        return {
            "lexical_overlap": overlap,
            "position_bias": position_score,
            "recency": recency,
            "source_quality": source_quality,
            "semantic_similarity": semantic
        }


class ContextCompressor:
    """Compresses retrieved context to fit token limits."""
    
    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens
    
    def compress(
        self, 
        documents: List[RetrievedDocument],
        query: str
    ) -> str:
        """Compress documents into a context string."""
        # Estimate tokens (rough: 1 token ≈ 4 chars)
        total_tokens = 0
        selected_content = []
        
        for doc in documents:
            doc_tokens = len(doc.content) // 4
            
            if total_tokens + doc_tokens <= self.max_tokens:
                selected_content.append(doc.content)
                total_tokens += doc_tokens
            else:
                # Truncate this document
                remaining_tokens = self.max_tokens - total_tokens
                if remaining_tokens > 50:  # Only include if meaningful
                    truncated = doc.content[:remaining_tokens * 4]
                    # Try to break at sentence
                    last_period = truncated.rfind('.')
                    if last_period > len(truncated) // 2:
                        truncated = truncated[:last_period + 1]
                    selected_content.append(truncated + "...")
                break
        
        return "\n\n---\n\n".join(selected_content)
    
    def extract_relevant_sentences(
        self, 
        text: str, 
        query: str,
        max_sentences: int = 10
    ) -> str:
        """Extract most relevant sentences from text."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        query_words = set(query.lower().split())
        
        # Score sentences by query word overlap
        scored = []
        for sentence in sentences:
            sentence_words = set(sentence.lower().split())
            overlap = len(query_words & sentence_words)
            scored.append((sentence, overlap))
        
        # Sort by relevance and take top sentences
        scored.sort(key=lambda x: x[1], reverse=True)
        selected = [s for s, _ in scored[:max_sentences]]
        
        return " ".join(selected)


class HybridRetriever:
    """
    Hybrid retrieval combining dense and sparse methods.
    
    Uses reciprocal rank fusion for combining results.
    """
    
    def __init__(
        self,
        dense_weight: float = 0.6,
        sparse_weight: float = 0.4,
        rrf_k: int = 60
    ):
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.rrf_k = rrf_k
        
        self.chunker = TextChunker()
        self.query_expander = QueryExpander()
        self.bm25 = BM25Scorer()
        self.reranker = Reranker()
        self.compressor = ContextCompressor()
        
        # Document store
        self._documents: Dict[str, str] = {}
        self._embeddings: Dict[str, List[float]] = {}
    
    def add_document(
        self, 
        doc_id: str, 
        content: str,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """Add a document to the retriever."""
        self._documents[doc_id] = content
        
        if embedding:
            self._embeddings[doc_id] = embedding
        
        # Index for BM25
        tokens = content.lower().split()
        self.bm25.index(doc_id, tokens)
        
        # Create chunks
        chunks = self.chunker.chunk(content, doc_id, metadata)
        
        return chunks
    
    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        mode: RetrievalMode = RetrievalMode.HYBRID,
        expand_query: bool = True,
        rerank: bool = True
    ) -> RetrievalResult:
        """Retrieve relevant documents."""
        import time
        start_time = time.time()
        
        # Query expansion
        expansion = None
        if expand_query:
            expansion = self.query_expander.expand(query)
        
        # Retrieve based on mode
        if mode == RetrievalMode.DENSE:
            documents = self._dense_retrieve(query, top_k * 2)
        elif mode == RetrievalMode.SPARSE:
            documents = self._sparse_retrieve(query, expansion, top_k * 2)
        else:  # HYBRID
            documents = self._hybrid_retrieve(query, expansion, top_k * 2)
        
        # Rerank if enabled
        if rerank and documents:
            documents = self.reranker.rerank(query, documents, top_k)
        else:
            documents = documents[:top_k]
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        return RetrievalResult(
            query=query,
            documents=documents,
            total_candidates=len(self._documents),
            retrieval_time_ms=elapsed_ms,
            mode=mode,
            query_expansion=expansion
        )
    
    def _dense_retrieve(
        self, 
        query: str, 
        top_k: int
    ) -> List[RetrievedDocument]:
        """Dense retrieval using embeddings."""
        # In production, would use actual embedding model
        # For now, return empty (placeholder)
        return []
    
    def _sparse_retrieve(
        self, 
        query: str,
        expansion: Optional[QueryExpansion],
        top_k: int
    ) -> List[RetrievedDocument]:
        """Sparse retrieval using BM25."""
        query_tokens = query.lower().split()
        
        # Add expanded terms
        if expansion:
            query_tokens.extend(expansion.expanded_terms)
        
        # Score all documents
        scores = []
        for doc_id in self._documents:
            score = self.bm25.score(doc_id, query_tokens)
            scores.append((doc_id, score))
        
        # Sort by score
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # Create retrieved documents
        results = []
        for rank, (doc_id, score) in enumerate(scores[:top_k]):
            results.append(RetrievedDocument(
                doc_id=doc_id,
                content=self._documents[doc_id],
                score=score,
                rank=rank + 1,
                retrieval_method=RetrievalMode.SPARSE
            ))
        
        return results
    
    def _hybrid_retrieve(
        self,
        query: str,
        expansion: Optional[QueryExpansion],
        top_k: int
    ) -> List[RetrievedDocument]:
        """Hybrid retrieval with reciprocal rank fusion."""
        # Get results from both methods
        dense_results = self._dense_retrieve(query, top_k)
        sparse_results = self._sparse_retrieve(query, expansion, top_k)
        
        # Compute RRF scores
        rrf_scores: Dict[str, float] = {}
        
        for rank, doc in enumerate(dense_results, 1):
            rrf_scores[doc.doc_id] = rrf_scores.get(doc.doc_id, 0) + \
                self.dense_weight / (self.rrf_k + rank)
        
        for rank, doc in enumerate(sparse_results, 1):
            rrf_scores[doc.doc_id] = rrf_scores.get(doc.doc_id, 0) + \
                self.sparse_weight / (self.rrf_k + rank)
        
        # Sort by RRF score
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        
        # Create result documents
        results = []
        for rank, doc_id in enumerate(sorted_ids[:top_k]):
            results.append(RetrievedDocument(
                doc_id=doc_id,
                content=self._documents.get(doc_id, ""),
                score=rrf_scores[doc_id],
                rank=rank + 1,
                retrieval_method=RetrievalMode.HYBRID
            ))
        
        return results
    
    def get_context(
        self,
        query: str,
        top_k: int = 5,
        max_tokens: int = 4000
    ) -> str:
        """Get compressed context for a query."""
        result = self.retrieve(query, top_k)
        self.compressor.max_tokens = max_tokens
        return self.compressor.compress(result.documents, query)


class RAGPipeline:
    """
    Complete RAG pipeline integrating all retrieval components.
    """
    
    def __init__(
        self,
        chunking_strategy: ChunkingStrategy = ChunkingStrategy.SEMANTIC,
        retrieval_mode: RetrievalMode = RetrievalMode.HYBRID,
        max_context_tokens: int = 4000
    ):
        self.retriever = HybridRetriever()
        self.retriever.chunker = TextChunker(strategy=chunking_strategy)
        self.retrieval_mode = retrieval_mode
        self.max_context_tokens = max_context_tokens
        
        self._indexed_count = 0
    
    def add_documents(
        self, 
        documents: List[Dict[str, Any]]
    ) -> int:
        """
        Add multiple documents to the pipeline.
        
        Each document should have 'id' and 'content' keys.
        """
        added = 0
        for doc in documents:
            doc_id = doc.get("id", f"doc_{self._indexed_count}")
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            embedding = doc.get("embedding")
            
            if content:
                self.retriever.add_document(doc_id, content, embedding, metadata)
                self._indexed_count += 1
                added += 1
        
        return added
    
    def query(
        self,
        query: str,
        top_k: int = 5,
        return_context: bool = True
    ) -> Dict[str, Any]:
        """
        Query the RAG pipeline.
        
        Returns retrieval results and optionally compressed context.
        """
        result = self.retriever.retrieve(
            query, 
            top_k, 
            self.retrieval_mode,
            expand_query=True,
            rerank=True
        )
        
        response = {
            "query": query,
            "documents": [
                {
                    "id": doc.doc_id,
                    "content": doc.content[:500] + "..." if len(doc.content) > 500 else doc.content,
                    "score": doc.score,
                    "rank": doc.rank
                }
                for doc in result.documents
            ],
            "total_candidates": result.total_candidates,
            "retrieval_time_ms": result.retrieval_time_ms
        }
        
        if return_context:
            response["context"] = self.retriever.get_context(
                query, top_k, self.max_context_tokens
            )
        
        if result.query_expansion:
            response["query_expansion"] = {
                "expanded_terms": result.query_expansion.expanded_terms,
                "reformulations": result.query_expansion.reformulations
            }
        
        return response
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        return {
            "indexed_documents": self._indexed_count,
            "retrieval_mode": self.retrieval_mode.value,
            "max_context_tokens": self.max_context_tokens
        }


# Convenience factory functions

def create_semantic_rag(max_context_tokens: int = 4000) -> RAGPipeline:
    """Create a RAG pipeline with semantic chunking."""
    return RAGPipeline(
        chunking_strategy=ChunkingStrategy.SEMANTIC,
        retrieval_mode=RetrievalMode.HYBRID,
        max_context_tokens=max_context_tokens
    )


def create_simple_rag(max_context_tokens: int = 4000) -> RAGPipeline:
    """Create a simple RAG pipeline with fixed-size chunking."""
    return RAGPipeline(
        chunking_strategy=ChunkingStrategy.FIXED_SIZE,
        retrieval_mode=RetrievalMode.SPARSE,
        max_context_tokens=max_context_tokens
    )
