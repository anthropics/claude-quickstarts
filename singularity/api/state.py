"""
Singularity — shared runtime singletons.

Extracted from api/main.py as part of the maintainability refactor: modules
under api/routers/ import their dependencies from here rather than from
api.main (which would be a circular import). As more endpoint groups move out
of the main.py monolith, their singletons migrate here.

These objects are built once at import and never reassigned, so importing them
by name yields a stable shared reference.
"""

from __future__ import annotations

from config.settings import settings
from core.anomaly_detector import AnomalyDetector, DetectionMethod
from core.anonymizer import PIIAnonymizer
from core.chunker import ChunkStrategy, DocumentChunker
from core.citation_tracker import CitationTracker
from core.coalescer import SingleFlight
from core.cost_estimator import CostEstimator
from core.deduplicator import Deduplicator
from core.embeddings import build_embedding_provider
from core.entity_extractor import EntityExtractor
from core.fuzzy_matcher import FuzzyMatcher
from core.histogram import PercentileTracker
from core.intent_classifier import IntentClassifier
from core.keyword_extractor import KeywordExtractor
from core.language_detector import LanguageDetector
from core.output_parser import OutputParser
from core.readability import ReadabilityAnalyzer
from core.reranker import FusionMethod, HybridReranker
from core.response_diff import ResponseComparator
from core.retriever import BM25Retriever
from core.sampler import ReservoirSampler
from core.sentiment import SentimentAnalyzer
from core.state_store import build_state_store
from core.streaming import StreamMetrics
from core.summarizer import ExtractiveSummarizer
from core.tenancy import TenantRegistry
from core.text_analytics import TextAnalyticsSuite
from core.vector_store import VectorStore

# Embedding Provider (Fáze 61, v2.0) — pluggable, offline feature-hashing
# default with lexical locality; swap for an API-backed provider in production.
embedding_provider = build_embedding_provider(
    settings.embedding_provider,
    dim=settings.embedding_dim,
    ngram=settings.embedding_ngram,
    cache_size=settings.embedding_cache_size,
)

# Vector Store (Fáze 69, v2.0 #9) — dense retriever sharing the embedding
# provider; semantic complement to BM25 (Fáze 37).
vector_store: VectorStore = VectorStore(embedder=embedding_provider)

# State Store (Fáze 62, v2.0) — backend-agnostic shared state; defaults to
# in-memory, swappable to Redis for multi-instance.
state_store = build_state_store(settings.state_backend, redis_url=settings.redis_url)

# Token-streaming metrics (Fáze 64), tenant registry (Fáze 65), request
# coalescer (Fáze 66) — each owned by its api/routers/* module.
stream_metrics: StreamMetrics = StreamMetrics()
tenants: TenantRegistry = TenantRegistry()
coalescer: SingleFlight = SingleFlight()


# ── NLP / Retrieval / Text / Stats singletons (Fáze 34–54) ───────────────────
# Owned by api/routers/{retrieval,nlp,text_ops,stats}.py; underscore-prefixed to
# match the original module-level names the extracted endpoint bodies reference.
# Intent Classifier (Fáze 34)
_intent_classifier: IntentClassifier = IntentClassifier(
    min_confidence=settings.intent_min_confidence,
    default_intent=settings.intent_default,
)

# Citation Tracker (Fáze 35)
_citation_tracker: CitationTracker = CitationTracker(
    threshold=settings.citation_threshold,
    max_citations=settings.citation_max_per_sentence,
)

# Document Chunker (Fáze 36)
_chunker: DocumentChunker = DocumentChunker(
    chunk_size=settings.chunk_size,
    overlap=settings.chunk_overlap,
    strategy=ChunkStrategy(settings.chunk_strategy),
)

# BM25 Retriever (Fáze 37)
_retriever: BM25Retriever = BM25Retriever(k1=settings.bm25_k1, b=settings.bm25_b)

# Hybrid Reranker (Fáze 38)
_reranker: HybridReranker = HybridReranker(
    rrf_k=settings.rrf_k,
    default_method=FusionMethod(settings.reranker_method),
)

# PII Anonymizer (Fáze 39)
_anonymizer: PIIAnonymizer = PIIAnonymizer()

# Cost Estimator (Fáze 40)
_cost_estimator: CostEstimator = CostEstimator()

# Response Comparator (Fáze 41)
_comparator: ResponseComparator = ResponseComparator()

# Extractive Summarizer (Fáze 42)
_summarizer: ExtractiveSummarizer = ExtractiveSummarizer(
    ratio=settings.summarizer_ratio,
    max_sentences=settings.summarizer_max_sentences,
)

# Language Detector (Fáze 43)
_language_detector: LanguageDetector = LanguageDetector(
    min_confidence=settings.language_min_confidence,
)

# Output Parser (Fáze 44)
_output_parser: OutputParser = OutputParser()

# Sentiment Analyzer (Fáze 45)
_sentiment: SentimentAnalyzer = SentimentAnalyzer(threshold=settings.sentiment_threshold)

# Keyword Extractor (Fáze 46)
_keyword_extractor: KeywordExtractor = KeywordExtractor(
    max_phrase_words=settings.keyword_max_phrase_words,
    min_word_length=settings.keyword_min_word_length,
)

# Readability Analyzer (Fáze 47)
_readability: ReadabilityAnalyzer = ReadabilityAnalyzer()

# Deduplicator (Fáze 48)
_deduplicator: Deduplicator = Deduplicator(
    threshold=settings.dedup_threshold,
    shingle_k=settings.dedup_shingle_k,
)

# Entity Extractor (Fáze 49)
_entity_extractor: EntityExtractor = EntityExtractor()

# Text Analytics Suite (Fáze 50) — composes the NLP analyzers above
_text_analytics: TextAnalyticsSuite = TextAnalyticsSuite(
    language_detector=_language_detector,
    sentiment_analyzer=_sentiment,
    readability_analyzer=_readability,
    keyword_extractor=_keyword_extractor,
    entity_extractor=_entity_extractor,
    summarizer=_summarizer,
)

# Fuzzy Matcher (Fáze 51)
_fuzzy_matcher: FuzzyMatcher = FuzzyMatcher(threshold=settings.fuzzy_threshold)

# Anomaly Detector (Fáze 52)
_anomaly_detector: AnomalyDetector = AnomalyDetector(
    method=DetectionMethod(settings.anomaly_method),
    window=settings.anomaly_window,
    z_threshold=settings.anomaly_z_threshold,
)

# Reservoir Sampler (Fáze 53)
_sampler: ReservoirSampler = ReservoirSampler(
    capacity=settings.sampler_capacity,
    seed=settings.sampler_seed,
)

# Percentile Tracker (Fáze 54)
_percentile_tracker: PercentileTracker = PercentileTracker(
    window=settings.percentile_window,
)
