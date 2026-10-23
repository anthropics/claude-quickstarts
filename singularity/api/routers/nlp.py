"""
NLP / text analysis endpoints. Extracted from api/main.py (maintainability refactor).

Routes and behaviour are identical to the originals.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.state import (
    _entity_extractor,
    _intent_classifier,
    _keyword_extractor,
    _language_detector,
    _output_parser,
    _readability,
    _sentiment,
    _summarizer,
    _text_analytics,
)

router = APIRouter()

# ── Intent Classifier (Fáze 34) ────────────────────────────────────────────────

class IntentClassifyRequest(BaseModel):
    text: str


@router.post("/intent/classify", tags=["Intent"])
async def intent_classify(req: IntentClassifyRequest):
    """Classify a query into an intent with confidence and a provider hint."""
    return _intent_classifier.classify(req.text).to_dict()


@router.get("/intent/list", tags=["Intent"])
async def intent_list():
    """List all registered intent names."""
    return {"intents": _intent_classifier.list_intents()}


@router.get("/intent/metrics", tags=["Intent"])
async def intent_metrics():
    """Intent classifier metrics: per-intent counts, fallback rate."""
    return _intent_classifier.metrics()


# ── Extractive Summarizer (Fáze 42) ─────────────────────────────────────────────

class SummarizeRequest(BaseModel):
    text: str
    ratio: float | None = None
    max_sentences: int | None = None
    top_keywords: int = 5


@router.post("/summarize", tags=["Summarizer"])
async def summarize_text(req: SummarizeRequest):
    """Extractively summarize a text by selecting the most salient sentences."""
    try:
        result = _summarizer.summarize(
            req.text,
            ratio=req.ratio,
            max_sentences=req.max_sentences,
            top_keywords=req.top_keywords,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.to_dict()


@router.get("/summarize/metrics", tags=["Summarizer"])
async def summarize_metrics():
    """Summarizer metrics: overall compression across calls."""
    return _summarizer.metrics()


# ── Language Detector (Fáze 43) ─────────────────────────────────────────────────

class LanguageDetectRequest(BaseModel):
    text: str


@router.post("/language/detect", tags=["Language"])
async def language_detect(req: LanguageDetectRequest):
    """Detect the dominant language of a text with confidence + per-language scores."""
    return _language_detector.detect(req.text).to_dict()


@router.get("/language/list", tags=["Language"])
async def language_list():
    """List supported language codes."""
    return {"languages": _language_detector.list_languages()}


@router.get("/language/metrics", tags=["Language"])
async def language_metrics():
    """Language detector metrics: per-language counts, unknown rate."""
    return _language_detector.metrics()


# ── Output Parser (Fáze 44) ─────────────────────────────────────────────────────

class ParseRequest(BaseModel):
    text: str


@router.post("/parse/json", tags=["Parser"])
async def parse_json(req: ParseRequest):
    """Extract JSON from free-form text (fences, balanced spans, light repair)."""
    return _output_parser.extract_json(req.text).to_dict()


@router.post("/parse/key-values", tags=["Parser"])
async def parse_key_values(req: ParseRequest):
    """Extract 'key: value' pairs from text into a dict."""
    return _output_parser.extract_key_values(req.text).to_dict()


@router.post("/parse/list", tags=["Parser"])
async def parse_list(req: ParseRequest):
    """Extract bullet / numbered list items from text."""
    return _output_parser.extract_list(req.text).to_dict()


@router.get("/parse/metrics", tags=["Parser"])
async def parse_metrics():
    """Output parser metrics: success/repair rates."""
    return _output_parser.metrics()


# ── Sentiment Analyzer (Fáze 45) ────────────────────────────────────────────────

class SentimentRequest(BaseModel):
    text: str


@router.post("/sentiment", tags=["Sentiment"])
async def analyze_sentiment(req: SentimentRequest):
    """Lexicon-based sentiment: polarity + normalized score with negation handling."""
    return _sentiment.analyze(req.text).to_dict()


@router.get("/sentiment/metrics", tags=["Sentiment"])
async def sentiment_metrics():
    """Sentiment analyzer metrics: polarity distribution."""
    return _sentiment.metrics()


# ── Keyword Extractor (Fáze 46) ─────────────────────────────────────────────────

class KeywordRequest(BaseModel):
    text: str
    top_k: int = 10


@router.post("/keywords", tags=["Keywords"])
async def extract_keywords(req: KeywordRequest):
    """Extract top keyphrases from text via RAKE-style scoring."""
    try:
        result = _keyword_extractor.extract(req.text, top_k=req.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.to_dict()


@router.get("/keywords/metrics", tags=["Keywords"])
async def keywords_metrics():
    """Keyword extractor metrics: average keywords per extraction."""
    return _keyword_extractor.metrics()


# ── Readability Analyzer (Fáze 47) ──────────────────────────────────────────────

class ReadabilityRequest(BaseModel):
    text: str


@router.post("/readability", tags=["Readability"])
async def analyze_readability(req: ReadabilityRequest):
    """Compute Flesch readability metrics (ease, grade, syllables, averages)."""
    return _readability.analyze(req.text).to_dict()


@router.get("/readability/metrics", tags=["Readability"])
async def readability_metrics():
    """Readability analyzer metrics: average reading ease and grade level."""
    return _readability.metrics()


# ── Entity Extractor (Fáze 49) ──────────────────────────────────────────────────

class EntityRequest(BaseModel):
    text: str


@router.post("/entities", tags=["Entities"])
async def extract_entities(req: EntityRequest):
    """Extract typed named entities (date, money, email, phone, proper noun, …)."""
    return _entity_extractor.extract(req.text).to_dict()


@router.get("/entities/metrics", tags=["Entities"])
async def entities_metrics():
    """Entity extractor metrics: counts by entity type."""
    return _entity_extractor.metrics()


# ── Text Analytics Suite (Fáze 50) ──────────────────────────────────────────────

class TextAnalyticsRequest(BaseModel):
    text: str
    language: bool = True
    sentiment: bool = True
    readability: bool = True
    keywords: bool = True
    entities: bool = True
    summary: bool = True
    top_keywords: int = 8


@router.post("/analyze/text", tags=["Analytics"])
async def analyze_text(req: TextAnalyticsRequest):
    """One-shot composed NLP report: language, sentiment, readability, keywords, entities, summary."""
    report = _text_analytics.analyze(
        req.text,
        language=req.language,
        sentiment=req.sentiment,
        readability=req.readability,
        keywords=req.keywords,
        entities=req.entities,
        summary=req.summary,
        top_keywords=req.top_keywords,
    )
    return report.to_dict()


@router.get("/analyze/text/metrics", tags=["Analytics"])
async def analyze_text_metrics():
    """Text analytics suite metrics: total analyses, per-section counts."""
    return _text_analytics.metrics()
