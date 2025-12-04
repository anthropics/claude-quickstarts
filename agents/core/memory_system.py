"""
Retrieval and Memory System - Phase 2

Episodic memory and case retrieval for:
- Vector/keyword search for similar past cases
- Episodic memory of prior queries and outcomes
- Bias future reasoning based on history
- Avoid repeating failed approaches
"""

from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import math


class MemoryType(Enum):
    """Types of memory entries."""
    QUERY = "query"  # A question or task
    REASONING = "reasoning"  # A reasoning chain
    FACT = "fact"  # A learned fact
    OUTCOME = "outcome"  # Result of an action
    FEEDBACK = "feedback"  # User feedback


class OutcomeStatus(Enum):
    """Status of an outcome."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass
class MemoryEntry:
    """A single memory entry."""
    id: str
    memory_type: MemoryType
    content: str
    embedding: Optional[List[float]] = None  # Vector embedding
    keywords: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0
    last_accessed: Optional[str] = None
    
    def __hash__(self) -> int:
        return hash(self.id)


@dataclass
class EpisodicMemory:
    """An episodic memory linking query to outcome."""
    query_id: str
    query_text: str
    reasoning_steps: List[str]
    tools_used: List[str]
    outcome: OutcomeStatus
    confidence: float
    feedback: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_ms: float = 0.0


@dataclass
class RetrievalResult:
    """Result of a retrieval query."""
    entries: List[MemoryEntry]
    scores: List[float]
    method: str  # "vector", "keyword", "hybrid"
    total_candidates: int
    retrieval_time_ms: float


class SimpleVectorStore:
    """
    Simple in-memory vector store using cosine similarity.
    
    For production, replace with proper vector DB (Pinecone, Weaviate, etc.)
    """
    
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.vectors: Dict[str, List[float]] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}
    
    def add(self, id: str, vector: List[float], metadata: Optional[Dict] = None) -> None:
        """Add a vector to the store."""
        if len(vector) != self.dimension:
            # Pad or truncate to match dimension
            if len(vector) < self.dimension:
                vector = vector + [0.0] * (self.dimension - len(vector))
            else:
                vector = vector[:self.dimension]
        
        self.vectors[id] = vector
        self.metadata[id] = metadata or {}
    
    def search(
        self, 
        query_vector: List[float], 
        top_k: int = 5,
        threshold: float = 0.0
    ) -> List[Tuple[str, float]]:
        """Search for similar vectors."""
        if len(query_vector) != self.dimension:
            if len(query_vector) < self.dimension:
                query_vector = query_vector + [0.0] * (self.dimension - len(query_vector))
            else:
                query_vector = query_vector[:self.dimension]
        
        scores = []
        for id, vector in self.vectors.items():
            score = self._cosine_similarity(query_vector, vector)
            if score >= threshold:
                scores.append((id, score))
        
        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    def delete(self, id: str) -> bool:
        """Delete a vector from the store."""
        if id in self.vectors:
            del self.vectors[id]
            del self.metadata[id]
            return True
        return False
    
    def size(self) -> int:
        """Get number of vectors in store."""
        return len(self.vectors)


class KeywordIndex:
    """Simple inverted index for keyword search."""
    
    def __init__(self):
        self.index: Dict[str, Set[str]] = {}  # keyword -> set of doc ids
        self.documents: Dict[str, List[str]] = {}  # doc id -> keywords
    
    def add(self, id: str, keywords: List[str]) -> None:
        """Add document keywords to index."""
        keywords = [k.lower() for k in keywords]
        self.documents[id] = keywords
        
        for keyword in keywords:
            if keyword not in self.index:
                self.index[keyword] = set()
            self.index[keyword].add(id)
    
    def search(self, query_keywords: List[str], top_k: int = 10) -> List[Tuple[str, float]]:
        """Search for documents matching keywords."""
        query_keywords = [k.lower() for k in query_keywords]
        
        # Count matches per document
        doc_scores: Dict[str, int] = {}
        for keyword in query_keywords:
            if keyword in self.index:
                for doc_id in self.index[keyword]:
                    doc_scores[doc_id] = doc_scores.get(doc_id, 0) + 1
        
        # Convert to similarity score
        results = []
        for doc_id, match_count in doc_scores.items():
            doc_keywords = self.documents.get(doc_id, [])
            if doc_keywords:
                # Jaccard-like similarity
                score = match_count / (len(query_keywords) + len(doc_keywords) - match_count)
                results.append((doc_id, score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def delete(self, id: str) -> bool:
        """Delete document from index."""
        if id not in self.documents:
            return False
        
        keywords = self.documents[id]
        for keyword in keywords:
            if keyword in self.index:
                self.index[keyword].discard(id)
        
        del self.documents[id]
        return True


class MemorySystem:
    """
    Complete memory system with retrieval capabilities.
    
    Combines:
    - Vector store for semantic similarity
    - Keyword index for exact matching
    - Episodic memory for learning from experience
    """
    
    def __init__(
        self, 
        vector_dim: int = 384,
        max_memories: int = 10000,
        episodic_window: int = 100
    ):
        self.vector_store = SimpleVectorStore(vector_dim)
        self.keyword_index = KeywordIndex()
        self.memories: Dict[str, MemoryEntry] = {}
        self.episodic_memories: List[EpisodicMemory] = []
        
        self.max_memories = max_memories
        self.episodic_window = episodic_window
        
        # Statistics
        self.stats = {
            "total_queries": 0,
            "successful_retrievals": 0,
            "cache_hits": 0
        }
    
    def store(
        self,
        content: str,
        memory_type: MemoryType,
        keywords: Optional[List[str]] = None,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store a new memory entry."""
        # Generate ID (using sha256 for better collision resistance)
        entry_id = hashlib.sha256(
            f"{content}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        # Extract keywords if not provided
        if keywords is None:
            keywords = self._extract_keywords(content)
        
        # Create entry
        entry = MemoryEntry(
            id=entry_id,
            memory_type=memory_type,
            content=content,
            embedding=embedding,
            keywords=keywords,
            metadata=metadata or {}
        )
        
        # Store in all indexes
        self.memories[entry_id] = entry
        self.keyword_index.add(entry_id, keywords)
        
        if embedding:
            self.vector_store.add(entry_id, embedding, {"type": memory_type.value})
        
        # Evict if over capacity
        if len(self.memories) > self.max_memories:
            self._evict_oldest()
        
        return entry_id
    
    def store_episode(
        self,
        query: str,
        reasoning_steps: List[str],
        tools_used: List[str],
        outcome: OutcomeStatus,
        confidence: float,
        feedback: Optional[str] = None,
        duration_ms: float = 0.0
    ) -> str:
        """Store an episodic memory of a complete interaction."""
        query_id = hashlib.sha256(query.encode()).hexdigest()[:16]
        
        episode = EpisodicMemory(
            query_id=query_id,
            query_text=query,
            reasoning_steps=reasoning_steps,
            tools_used=tools_used,
            outcome=outcome,
            confidence=confidence,
            feedback=feedback,
            duration_ms=duration_ms
        )
        
        self.episodic_memories.append(episode)
        
        # Also store as regular memory for retrieval
        self.store(
            content=query,
            memory_type=MemoryType.QUERY,
            metadata={
                "outcome": outcome.value,
                "confidence": confidence,
                "tools": tools_used
            }
        )
        
        # Maintain window
        if len(self.episodic_memories) > self.episodic_window:
            self.episodic_memories = self.episodic_memories[-self.episodic_window:]
        
        return query_id
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        method: str = "hybrid",
        embedding: Optional[List[float]] = None
    ) -> RetrievalResult:
        """Retrieve relevant memories."""
        start_time = datetime.now()
        self.stats["total_queries"] += 1
        
        if method == "vector" and embedding:
            results = self._vector_search(embedding, top_k)
        elif method == "keyword":
            results = self._keyword_search(query, top_k)
        else:
            # Hybrid: combine both methods
            results = self._hybrid_search(query, embedding, top_k)
        
        entries = []
        scores = []
        for id, score in results:
            if id in self.memories:
                entry = self.memories[id]
                entry.access_count += 1
                entry.last_accessed = datetime.now().isoformat()
                entries.append(entry)
                scores.append(score)
        
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        
        if entries:
            self.stats["successful_retrievals"] += 1
        
        return RetrievalResult(
            entries=entries,
            scores=scores,
            method=method,
            total_candidates=len(self.memories),
            retrieval_time_ms=elapsed
        )
    
    def get_similar_episodes(
        self,
        query: str,
        top_k: int = 5
    ) -> List[EpisodicMemory]:
        """Get similar past episodes for learning."""
        query_lower = query.lower()
        
        # Simple similarity based on word overlap
        scored = []
        for episode in self.episodic_memories:
            episode_lower = episode.query_text.lower()
            
            # Word overlap score
            query_words = set(query_lower.split())
            episode_words = set(episode_lower.split())
            
            if not query_words or not episode_words:
                continue
            
            overlap = len(query_words & episode_words)
            union = len(query_words | episode_words)
            score = overlap / union if union > 0 else 0
            
            scored.append((episode, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [ep for ep, _ in scored[:top_k]]
    
    def get_successful_patterns(self) -> Dict[str, Any]:
        """Analyze successful episodes to find patterns."""
        successful = [
            ep for ep in self.episodic_memories 
            if ep.outcome == OutcomeStatus.SUCCESS
        ]
        
        if not successful:
            return {"patterns": [], "tool_effectiveness": {}}
        
        # Analyze tool usage
        tool_counts: Dict[str, int] = {}
        tool_successes: Dict[str, int] = {}
        
        for ep in self.episodic_memories:
            for tool in ep.tools_used:
                tool_counts[tool] = tool_counts.get(tool, 0) + 1
                if ep.outcome == OutcomeStatus.SUCCESS:
                    tool_successes[tool] = tool_successes.get(tool, 0) + 1
        
        tool_effectiveness = {
            tool: tool_successes.get(tool, 0) / count
            for tool, count in tool_counts.items()
            if count > 0
        }
        
        # Find common reasoning patterns in successful episodes
        step_patterns: Dict[str, int] = {}
        for ep in successful:
            for step in ep.reasoning_steps:
                step_patterns[step] = step_patterns.get(step, 0) + 1
        
        common_patterns = sorted(
            step_patterns.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10]
        
        return {
            "patterns": [p for p, _ in common_patterns],
            "tool_effectiveness": tool_effectiveness,
            "success_rate": len(successful) / len(self.episodic_memories),
            "avg_confidence": sum(ep.confidence for ep in successful) / len(successful)
        }
    
    def should_avoid(self, query: str) -> Tuple[bool, Optional[str]]:
        """Check if similar queries have consistently failed."""
        similar = self.get_similar_episodes(query, top_k=3)
        
        if not similar:
            return False, None
        
        failures = [ep for ep in similar if ep.outcome == OutcomeStatus.FAILURE]
        
        if len(failures) >= 2:
            # Multiple similar failures - suggest avoiding
            return True, f"Similar queries failed {len(failures)} times"
        
        return False, None
    
    def _vector_search(
        self, 
        embedding: List[float], 
        top_k: int
    ) -> List[Tuple[str, float]]:
        """Search using vector similarity."""
        return self.vector_store.search(embedding, top_k)
    
    def _keyword_search(
        self, 
        query: str, 
        top_k: int
    ) -> List[Tuple[str, float]]:
        """Search using keyword matching."""
        keywords = self._extract_keywords(query)
        return self.keyword_index.search(keywords, top_k)
    
    def _hybrid_search(
        self,
        query: str,
        embedding: Optional[List[float]],
        top_k: int
    ) -> List[Tuple[str, float]]:
        """Combine vector and keyword search."""
        # Get keyword results
        keyword_results = self._keyword_search(query, top_k * 2)
        
        # Get vector results if embedding available
        vector_results = []
        if embedding:
            vector_results = self._vector_search(embedding, top_k * 2)
        
        # Combine with reciprocal rank fusion
        scores: Dict[str, float] = {}
        k = 60  # RRF constant
        
        for rank, (id, _) in enumerate(keyword_results):
            scores[id] = scores.get(id, 0) + 1 / (k + rank + 1)
        
        for rank, (id, _) in enumerate(vector_results):
            scores[id] = scores.get(id, 0) + 1 / (k + rank + 1)
        
        # Sort by combined score
        combined = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return combined[:top_k]
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        import re
        
        # Simple extraction: words that aren't stopwords
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "further", "then", "once",
            "here", "there", "when", "where", "why", "how", "all",
            "each", "few", "more", "most", "other", "some", "such",
            "no", "nor", "not", "only", "own", "same", "so", "than",
            "too", "very", "just", "and", "but", "if", "or", "because",
            "as", "until", "while", "this", "that", "these", "those"
        }
        
        words = re.findall(r'\b\w+\b', text.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        
        return list(set(keywords))[:20]  # Limit to 20 keywords
    
    def _evict_oldest(self) -> None:
        """Evict oldest, least-accessed memories."""
        if not self.memories:
            return
        
        # Sort by last access time and access count
        sorted_memories = sorted(
            self.memories.values(),
            key=lambda m: (m.access_count, m.last_accessed or m.timestamp)
        )
        
        # Remove oldest 10%
        to_remove = max(1, len(sorted_memories) // 10)
        for i in range(to_remove):
            memory = sorted_memories[i]
            self.forget(memory.id)
    
    def forget(self, id: str) -> bool:
        """Remove a memory entry."""
        if id not in self.memories:
            return False
        
        del self.memories[id]
        self.keyword_index.delete(id)
        self.vector_store.delete(id)
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory system statistics."""
        return {
            **self.stats,
            "total_memories": len(self.memories),
            "episodic_memories": len(self.episodic_memories),
            "vector_store_size": self.vector_store.size()
        }
    
    def export(self) -> Dict[str, Any]:
        """Export memory state for persistence."""
        return {
            "memories": [
                {
                    "id": m.id,
                    "type": m.memory_type.value,
                    "content": m.content,
                    "keywords": m.keywords,
                    "metadata": m.metadata,
                    "timestamp": m.timestamp
                }
                for m in self.memories.values()
            ],
            "episodes": [
                {
                    "query_id": ep.query_id,
                    "query_text": ep.query_text,
                    "reasoning_steps": ep.reasoning_steps,
                    "tools_used": ep.tools_used,
                    "outcome": ep.outcome.value,
                    "confidence": ep.confidence,
                    "feedback": ep.feedback,
                    "timestamp": ep.timestamp
                }
                for ep in self.episodic_memories
            ],
            "stats": self.stats
        }
    
    def import_state(self, state: Dict[str, Any]) -> None:
        """Import memory state from export."""
        # Import memories
        for m in state.get("memories", []):
            self.store(
                content=m["content"],
                memory_type=MemoryType(m["type"]),
                keywords=m.get("keywords"),
                metadata=m.get("metadata")
            )
        
        # Import episodes
        for ep in state.get("episodes", []):
            self.episodic_memories.append(EpisodicMemory(
                query_id=ep["query_id"],
                query_text=ep["query_text"],
                reasoning_steps=ep["reasoning_steps"],
                tools_used=ep["tools_used"],
                outcome=OutcomeStatus(ep["outcome"]),
                confidence=ep["confidence"],
                feedback=ep.get("feedback"),
                timestamp=ep.get("timestamp", datetime.now().isoformat())
            ))
        
        # Import stats
        self.stats.update(state.get("stats", {}))
