"""
Multimodal Pipeline - Advanced Enhancement

Provides vision/text fusion capabilities:
- CLIP/VLM-style embedding fusion
- Image+text combined retrieval
- Multimodal decision scoring
- Cross-modal grounding
"""

from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import math
import hashlib


class ModalityType(Enum):
    """Types of input modalities."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    STRUCTURED = "structured"  # Tables, JSON, etc.


class FusionStrategy(Enum):
    """Strategies for fusing multimodal embeddings."""
    CONCATENATE = "concatenate"  # Simple concatenation
    AVERAGE = "average"  # Weighted average
    ATTENTION = "attention"  # Cross-modal attention
    GATED = "gated"  # Gated fusion
    PROJECTION = "projection"  # Project to shared space


@dataclass
class ModalityInput:
    """A single modality input."""
    modality: ModalityType
    content: Any  # Raw content (text string, image bytes, etc.)
    content_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        if not self.content_id:
            # Generate ID from content hash
            if isinstance(self.content, str):
                self.content_id = hashlib.md5(self.content.encode()).hexdigest()[:12]
            elif isinstance(self.content, bytes):
                self.content_id = hashlib.md5(self.content).hexdigest()[:12]
            else:
                self.content_id = hashlib.md5(str(self.content).encode()).hexdigest()[:12]


@dataclass
class EmbeddingVector:
    """An embedding vector with metadata."""
    vector: List[float]
    modality: ModalityType
    source_id: str
    dimension: int = 0
    model_name: str = "unknown"
    
    def __post_init__(self):
        self.dimension = len(self.vector)
    
    def normalize(self) -> "EmbeddingVector":
        """Return L2-normalized vector."""
        norm = math.sqrt(sum(x*x for x in self.vector))
        if norm > 0:
            normalized = [x / norm for x in self.vector]
            return EmbeddingVector(
                vector=normalized,
                modality=self.modality,
                source_id=self.source_id,
                model_name=self.model_name
            )
        return self


@dataclass
class FusedEmbedding:
    """A fused multimodal embedding."""
    vector: List[float]
    modalities: List[ModalityType]
    source_ids: List[str]
    fusion_strategy: FusionStrategy
    weights: Dict[ModalityType, float] = field(default_factory=dict)
    confidence: float = 1.0
    dimension: int = 0
    
    def __post_init__(self):
        self.dimension = len(self.vector)


@dataclass
class MultimodalQuery:
    """A multimodal query for retrieval."""
    inputs: List[ModalityInput]
    text_query: Optional[str] = None
    fusion_strategy: FusionStrategy = FusionStrategy.ATTENTION
    modality_weights: Dict[ModalityType, float] = field(default_factory=dict)
    
    def __post_init__(self):
        # Extract text query from inputs if not provided
        if self.text_query is None:
            for inp in self.inputs:
                if inp.modality == ModalityType.TEXT:
                    self.text_query = inp.content
                    break


class EmbeddingEncoder(ABC):
    """Abstract base for modality-specific encoders."""
    
    @property
    @abstractmethod
    def modality(self) -> ModalityType:
        """Which modality this encoder handles."""
        pass
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        """Output embedding dimension."""
        pass
    
    @abstractmethod
    def encode(self, content: Any) -> EmbeddingVector:
        """Encode content to embedding vector."""
        pass
    
    @abstractmethod
    def encode_batch(self, contents: List[Any]) -> List[EmbeddingVector]:
        """Encode multiple contents."""
        pass


class MockTextEncoder(EmbeddingEncoder):
    """Mock text encoder for testing (simulates BERT/sentence-transformers)."""
    
    def __init__(self, dim: int = 768):
        self._dim = dim
    
    @property
    def modality(self) -> ModalityType:
        return ModalityType.TEXT
    
    @property
    def dimension(self) -> int:
        return self._dim
    
    def encode(self, content: str) -> EmbeddingVector:
        """Generate deterministic embedding from text hash."""
        # Use content hash to generate reproducible embedding
        h = hashlib.sha256(content.encode()).digest()
        # Convert bytes to floats in [-1, 1]
        vector = []
        for i in range(self._dim):
            byte_idx = i % len(h)
            val = (h[byte_idx] / 127.5) - 1.0
            vector.append(val)
        
        return EmbeddingVector(
            vector=vector,
            modality=ModalityType.TEXT,
            source_id=hashlib.md5(content.encode()).hexdigest()[:12],
            model_name="mock_text_encoder"
        )
    
    def encode_batch(self, contents: List[str]) -> List[EmbeddingVector]:
        return [self.encode(c) for c in contents]


class MockImageEncoder(EmbeddingEncoder):
    """Mock image encoder for testing (simulates CLIP vision encoder)."""
    
    def __init__(self, dim: int = 512):
        self._dim = dim
    
    @property
    def modality(self) -> ModalityType:
        return ModalityType.IMAGE
    
    @property
    def dimension(self) -> int:
        return self._dim
    
    def encode(self, content: Union[bytes, str]) -> EmbeddingVector:
        """Generate deterministic embedding from image content hash."""
        if isinstance(content, str):
            # Treat as path or base64
            h = hashlib.sha256(content.encode()).digest()
        else:
            h = hashlib.sha256(content).digest()
        
        vector = []
        for i in range(self._dim):
            byte_idx = i % len(h)
            val = (h[byte_idx] / 127.5) - 1.0
            vector.append(val)
        
        source_id = hashlib.md5(
            content.encode() if isinstance(content, str) else content
        ).hexdigest()[:12]
        
        return EmbeddingVector(
            vector=vector,
            modality=ModalityType.IMAGE,
            source_id=source_id,
            model_name="mock_image_encoder"
        )
    
    def encode_batch(self, contents: List[Union[bytes, str]]) -> List[EmbeddingVector]:
        return [self.encode(c) for c in contents]


class CLIPStyleEncoder:
    """
    CLIP-style joint encoder for text and images.
    
    Projects both modalities to a shared embedding space.
    """
    
    def __init__(
        self,
        shared_dim: int = 512,
        text_encoder: Optional[EmbeddingEncoder] = None,
        image_encoder: Optional[EmbeddingEncoder] = None
    ):
        self.shared_dim = shared_dim
        self.text_encoder = text_encoder or MockTextEncoder(dim=768)
        self.image_encoder = image_encoder or MockImageEncoder(dim=512)
        
        # Projection matrices (mock - in reality would be learned)
        self._text_projection = self._create_projection_matrix(
            self.text_encoder.dimension, shared_dim
        )
        self._image_projection = self._create_projection_matrix(
            self.image_encoder.dimension, shared_dim
        )
    
    def _create_projection_matrix(self, in_dim: int, out_dim: int) -> List[List[float]]:
        """Create a deterministic projection matrix."""
        matrix = []
        for i in range(out_dim):
            row = []
            for j in range(in_dim):
                # Deterministic but varied values
                val = math.sin(i * 0.1 + j * 0.01) * 0.1
                row.append(val)
            matrix.append(row)
        return matrix
    
    def _project(
        self,
        vector: List[float],
        projection: List[List[float]]
    ) -> List[float]:
        """Apply projection matrix to vector."""
        result = []
        for row in projection:
            dot = sum(v * p for v, p in zip(vector, row))
            result.append(dot)
        return result
    
    def encode_text(self, text: str) -> EmbeddingVector:
        """Encode text to shared space."""
        raw_emb = self.text_encoder.encode(text)
        projected = self._project(raw_emb.vector, self._text_projection)
        
        return EmbeddingVector(
            vector=projected,
            modality=ModalityType.TEXT,
            source_id=raw_emb.source_id,
            model_name="clip_text"
        ).normalize()
    
    def encode_image(self, image: Union[bytes, str]) -> EmbeddingVector:
        """Encode image to shared space."""
        raw_emb = self.image_encoder.encode(image)
        projected = self._project(raw_emb.vector, self._image_projection)
        
        return EmbeddingVector(
            vector=projected,
            modality=ModalityType.IMAGE,
            source_id=raw_emb.source_id,
            model_name="clip_image"
        ).normalize()
    
    def similarity(self, emb1: EmbeddingVector, emb2: EmbeddingVector) -> float:
        """Compute cosine similarity between embeddings."""
        dot = sum(a * b for a, b in zip(emb1.vector, emb2.vector))
        return dot  # Already normalized


class EmbeddingFuser:
    """Fuses embeddings from multiple modalities."""
    
    def __init__(self, strategy: FusionStrategy = FusionStrategy.ATTENTION):
        self.strategy = strategy
    
    def fuse(
        self,
        embeddings: List[EmbeddingVector],
        weights: Optional[Dict[ModalityType, float]] = None
    ) -> FusedEmbedding:
        """Fuse multiple embeddings into one."""
        if not embeddings:
            raise ValueError("No embeddings to fuse")
        
        if len(embeddings) == 1:
            emb = embeddings[0]
            return FusedEmbedding(
                vector=emb.vector,
                modalities=[emb.modality],
                source_ids=[emb.source_id],
                fusion_strategy=self.strategy,
                weights={emb.modality: 1.0}
            )
        
        # Default equal weights
        if weights is None:
            weights = {}
            for emb in embeddings:
                if emb.modality not in weights:
                    weights[emb.modality] = 1.0 / len(embeddings)
        
        # Normalize weights
        total_weight = sum(weights.values())
        weights = {k: v / total_weight for k, v in weights.items()}
        
        if self.strategy == FusionStrategy.CONCATENATE:
            return self._fuse_concatenate(embeddings, weights)
        elif self.strategy == FusionStrategy.AVERAGE:
            return self._fuse_average(embeddings, weights)
        elif self.strategy == FusionStrategy.ATTENTION:
            return self._fuse_attention(embeddings, weights)
        elif self.strategy == FusionStrategy.GATED:
            return self._fuse_gated(embeddings, weights)
        else:
            return self._fuse_average(embeddings, weights)
    
    def _fuse_concatenate(
        self,
        embeddings: List[EmbeddingVector],
        weights: Dict[ModalityType, float]
    ) -> FusedEmbedding:
        """Concatenate all embeddings."""
        combined = []
        for emb in embeddings:
            combined.extend(emb.vector)
        
        return FusedEmbedding(
            vector=combined,
            modalities=[e.modality for e in embeddings],
            source_ids=[e.source_id for e in embeddings],
            fusion_strategy=FusionStrategy.CONCATENATE,
            weights=weights
        )
    
    def _fuse_average(
        self,
        embeddings: List[EmbeddingVector],
        weights: Dict[ModalityType, float]
    ) -> FusedEmbedding:
        """Weighted average of embeddings (requires same dimension)."""
        target_dim = embeddings[0].dimension
        result = [0.0] * target_dim
        
        for emb in embeddings:
            w = weights.get(emb.modality, 1.0 / len(embeddings))
            # Pad or truncate to target dim
            vec = emb.vector[:target_dim]
            vec = vec + [0.0] * (target_dim - len(vec))
            
            for i, v in enumerate(vec):
                result[i] += v * w
        
        return FusedEmbedding(
            vector=result,
            modalities=[e.modality for e in embeddings],
            source_ids=[e.source_id for e in embeddings],
            fusion_strategy=FusionStrategy.AVERAGE,
            weights=weights
        )
    
    def _fuse_attention(
        self,
        embeddings: List[EmbeddingVector],
        weights: Dict[ModalityType, float]
    ) -> FusedEmbedding:
        """Cross-modal attention fusion."""
        # Simplified: compute attention scores based on similarity
        target_dim = embeddings[0].dimension
        
        # Compute pairwise similarities
        n = len(embeddings)
        attention_weights = []
        
        for i, emb_i in enumerate(embeddings):
            score = weights.get(emb_i.modality, 1.0 / n)
            # Add cross-modal attention boost
            for j, emb_j in enumerate(embeddings):
                if i != j:
                    # Cosine similarity as attention
                    min_dim = min(len(emb_i.vector), len(emb_j.vector))
                    sim = sum(
                        a * b for a, b in zip(
                            emb_i.vector[:min_dim],
                            emb_j.vector[:min_dim]
                        )
                    )
                    score += sim * 0.1
            attention_weights.append(max(0.01, score))
        
        # Normalize attention
        total = sum(attention_weights)
        attention_weights = [w / total for w in attention_weights]
        
        # Weighted combination
        result = [0.0] * target_dim
        for emb, attn in zip(embeddings, attention_weights):
            vec = emb.vector[:target_dim]
            vec = vec + [0.0] * (target_dim - len(vec))
            for i, v in enumerate(vec):
                result[i] += v * attn
        
        return FusedEmbedding(
            vector=result,
            modalities=[e.modality for e in embeddings],
            source_ids=[e.source_id for e in embeddings],
            fusion_strategy=FusionStrategy.ATTENTION,
            weights=dict(zip([e.modality for e in embeddings], attention_weights)),
            confidence=max(attention_weights)
        )
    
    def _fuse_gated(
        self,
        embeddings: List[EmbeddingVector],
        weights: Dict[ModalityType, float]
    ) -> FusedEmbedding:
        """Gated fusion with learned gates (simplified)."""
        target_dim = embeddings[0].dimension
        
        # Compute gate values based on embedding magnitudes
        gates = []
        for emb in embeddings:
            magnitude = math.sqrt(sum(x*x for x in emb.vector))
            gate = 1.0 / (1.0 + math.exp(-magnitude))  # Sigmoid
            gates.append(gate * weights.get(emb.modality, 1.0 / len(embeddings)))
        
        # Normalize gates
        total = sum(gates)
        gates = [g / total for g in gates]
        
        # Gated combination
        result = [0.0] * target_dim
        for emb, gate in zip(embeddings, gates):
            vec = emb.vector[:target_dim]
            vec = vec + [0.0] * (target_dim - len(vec))
            for i, v in enumerate(vec):
                result[i] += v * gate
        
        return FusedEmbedding(
            vector=result,
            modalities=[e.modality for e in embeddings],
            source_ids=[e.source_id for e in embeddings],
            fusion_strategy=FusionStrategy.GATED,
            weights=dict(zip([e.modality for e in embeddings], gates))
        )


@dataclass
class MultimodalRetrievalResult:
    """Result from multimodal retrieval."""
    query: MultimodalQuery
    fused_query_embedding: FusedEmbedding
    results: List[Dict[str, Any]]
    retrieval_time_ms: float
    modality_contributions: Dict[ModalityType, float]


class MultimodalRetriever:
    """
    Retriever that handles multimodal queries.
    
    Fuses text and image embeddings for joint retrieval.
    """
    
    def __init__(
        self,
        encoder: Optional[CLIPStyleEncoder] = None,
        fuser: Optional[EmbeddingFuser] = None,
        fusion_strategy: FusionStrategy = FusionStrategy.ATTENTION
    ):
        self.encoder = encoder or CLIPStyleEncoder()
        self.fuser = fuser or EmbeddingFuser(strategy=fusion_strategy)
        self._index: List[Tuple[FusedEmbedding, Dict[str, Any]]] = []
    
    def index_document(
        self,
        doc_id: str,
        text: Optional[str] = None,
        image: Optional[Union[bytes, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Index a document with text and/or image."""
        embeddings = []
        
        if text:
            text_emb = self.encoder.encode_text(text)
            embeddings.append(text_emb)
        
        if image:
            image_emb = self.encoder.encode_image(image)
            embeddings.append(image_emb)
        
        if not embeddings:
            return
        
        fused = self.fuser.fuse(embeddings)
        
        self._index.append((fused, {
            "doc_id": doc_id,
            "text": text,
            "has_image": image is not None,
            "metadata": metadata or {},
            "modalities": [e.modality.value for e in embeddings]
        }))
    
    def retrieve(
        self,
        query: MultimodalQuery,
        top_k: int = 10
    ) -> MultimodalRetrievalResult:
        """Retrieve documents matching multimodal query."""
        import time
        start = time.perf_counter()
        
        # Encode query modalities
        query_embeddings = []
        for inp in query.inputs:
            if inp.modality == ModalityType.TEXT:
                emb = self.encoder.encode_text(inp.content)
                query_embeddings.append(emb)
            elif inp.modality == ModalityType.IMAGE:
                emb = self.encoder.encode_image(inp.content)
                query_embeddings.append(emb)
        
        if not query_embeddings:
            return MultimodalRetrievalResult(
                query=query,
                fused_query_embedding=FusedEmbedding(
                    vector=[], modalities=[], source_ids=[],
                    fusion_strategy=FusionStrategy.AVERAGE
                ),
                results=[],
                retrieval_time_ms=0,
                modality_contributions={}
            )
        
        # Fuse query embeddings
        fused_query = self.fuser.fuse(query_embeddings, query.modality_weights)
        
        # Score all indexed documents
        scored = []
        for fused_doc, doc_info in self._index:
            score = self._similarity(fused_query.vector, fused_doc.vector)
            scored.append({
                **doc_info,
                "score": score,
                "doc_modalities": fused_doc.modalities
            })
        
        # Sort by score
        scored.sort(key=lambda x: x["score"], reverse=True)
        results = scored[:top_k]
        
        elapsed = (time.perf_counter() - start) * 1000
        
        return MultimodalRetrievalResult(
            query=query,
            fused_query_embedding=fused_query,
            results=results,
            retrieval_time_ms=elapsed,
            modality_contributions=fused_query.weights
        )
    
    def _similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity."""
        min_dim = min(len(vec1), len(vec2))
        if min_dim == 0:
            return 0.0
        
        dot = sum(a * b for a, b in zip(vec1[:min_dim], vec2[:min_dim]))
        norm1 = math.sqrt(sum(x*x for x in vec1[:min_dim]))
        norm2 = math.sqrt(sum(x*x for x in vec2[:min_dim]))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot / (norm1 * norm2)


@dataclass
class MultimodalDecisionContext:
    """Context for multimodal decision making."""
    text_context: Optional[str] = None
    image_context: Optional[Union[bytes, str]] = None
    retrieved_evidence: List[Dict[str, Any]] = field(default_factory=list)
    modality_confidences: Dict[ModalityType, float] = field(default_factory=dict)
    cross_modal_alignment: float = 0.0  # How well modalities agree


class MultimodalDecisionScorer:
    """
    Scores decisions using multimodal context.
    
    Adjusts scores based on cross-modal grounding.
    """
    
    def __init__(
        self,
        cross_modal_weight: float = 0.2,
        require_grounding: bool = True
    ):
        self.cross_modal_weight = cross_modal_weight
        self.require_grounding = require_grounding
    
    def score_with_context(
        self,
        base_score: float,
        context: MultimodalDecisionContext
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Adjust decision score based on multimodal context.
        
        Returns adjusted score and scoring details.
        """
        adjustments = {}
        final_score = base_score
        
        # Cross-modal alignment bonus/penalty
        if context.cross_modal_alignment > 0:
            alignment_factor = 1.0 + (context.cross_modal_alignment * self.cross_modal_weight)
            final_score *= alignment_factor
            adjustments["alignment_boost"] = context.cross_modal_alignment * self.cross_modal_weight
        
        # Modality confidence weighting
        if context.modality_confidences:
            avg_conf = sum(context.modality_confidences.values()) / len(context.modality_confidences)
            conf_factor = 0.5 + (avg_conf * 0.5)  # Scale 0.5-1.0
            final_score *= conf_factor
            adjustments["confidence_factor"] = conf_factor
        
        # Evidence grounding bonus
        if context.retrieved_evidence:
            evidence_boost = min(0.2, len(context.retrieved_evidence) * 0.05)
            final_score *= (1.0 + evidence_boost)
            adjustments["evidence_boost"] = evidence_boost
        elif self.require_grounding:
            # Penalty for lack of grounding
            final_score *= 0.8
            adjustments["grounding_penalty"] = -0.2
        
        return min(1.0, max(0.0, final_score)), adjustments


# Convenience functions

def create_multimodal_pipeline(
    fusion_strategy: str = "attention",
    shared_dim: int = 512
) -> Tuple[CLIPStyleEncoder, EmbeddingFuser, MultimodalRetriever]:
    """Create a complete multimodal pipeline."""
    strategy = FusionStrategy[fusion_strategy.upper()]
    encoder = CLIPStyleEncoder(shared_dim=shared_dim)
    fuser = EmbeddingFuser(strategy=strategy)
    retriever = MultimodalRetriever(encoder=encoder, fuser=fuser)
    
    return encoder, fuser, retriever


def create_multimodal_query(
    text: Optional[str] = None,
    image: Optional[Union[bytes, str]] = None,
    modality_weights: Optional[Dict[str, float]] = None
) -> MultimodalQuery:
    """Create a multimodal query from text and/or image."""
    inputs = []
    
    if text:
        inputs.append(ModalityInput(
            modality=ModalityType.TEXT,
            content=text
        ))
    
    if image:
        inputs.append(ModalityInput(
            modality=ModalityType.IMAGE,
            content=image
        ))
    
    weights = {}
    if modality_weights:
        for k, v in modality_weights.items():
            weights[ModalityType[k.upper()]] = v
    
    return MultimodalQuery(
        inputs=inputs,
        text_query=text,
        modality_weights=weights
    )
