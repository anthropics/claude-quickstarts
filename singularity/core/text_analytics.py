"""
Singularity — Text Analytics Suite (Fáze 50).

Capstone module that composes the standalone NLP analyzers built in
Fáze 42–49 into a single one-shot text report:

  - language       (Fáze 43)
  - sentiment      (Fáze 45)
  - readability    (Fáze 47)
  - keywords       (Fáze 46)
  - entities       (Fáze 49)
  - summary        (Fáze 42)

Each section can be toggled. Analyzers are injectable so the suite stays
unit-testable in isolation (defaults construct the real ones). Dependency-free
and offline.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from core.language_detector import LanguageDetector
from core.sentiment import SentimentAnalyzer
from core.readability import ReadabilityAnalyzer
from core.keyword_extractor import KeywordExtractor
from core.entity_extractor import EntityExtractor
from core.summarizer import ExtractiveSummarizer


# ── Result ──────────────────────────────────────────────────────────────────────

@dataclass
class AnalysisReport:
    char_count: int
    word_count: int
    language: dict | None = None
    sentiment: dict | None = None
    readability: dict | None = None
    keywords: list | None = None
    entities: list | None = None
    summary: dict | None = None
    sections: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "char_count": self.char_count,
            "word_count": self.word_count,
            "language": self.language,
            "sentiment": self.sentiment,
            "readability": self.readability,
            "keywords": self.keywords,
            "entities": self.entities,
            "summary": self.summary,
            "sections": self.sections,
        }


# ── Suite ───────────────────────────────────────────────────────────────────────

class TextAnalyticsSuite:
    """Run a configurable bundle of NLP analyzers over a single text."""

    def __init__(
        self,
        *,
        language_detector: LanguageDetector | None = None,
        sentiment_analyzer: SentimentAnalyzer | None = None,
        readability_analyzer: ReadabilityAnalyzer | None = None,
        keyword_extractor: KeywordExtractor | None = None,
        entity_extractor: EntityExtractor | None = None,
        summarizer: ExtractiveSummarizer | None = None,
    ) -> None:
        self.language_detector = language_detector or LanguageDetector()
        self.sentiment_analyzer = sentiment_analyzer or SentimentAnalyzer()
        self.readability_analyzer = readability_analyzer or ReadabilityAnalyzer()
        self.keyword_extractor = keyword_extractor or KeywordExtractor()
        self.entity_extractor = entity_extractor or EntityExtractor()
        self.summarizer = summarizer or ExtractiveSummarizer()
        self._lock = threading.Lock()

        # metrics
        self._total = 0
        self._section_counts: dict[str, int] = {}

    def analyze(
        self,
        text: str,
        *,
        language: bool = True,
        sentiment: bool = True,
        readability: bool = True,
        keywords: bool = True,
        entities: bool = True,
        summary: bool = True,
        top_keywords: int = 8,
    ) -> AnalysisReport:
        doc = text or ""
        report = AnalysisReport(
            char_count=len(doc),
            word_count=len(doc.split()),
        )
        sections: list[str] = []

        if language:
            report.language = self.language_detector.detect(doc).to_dict()
            sections.append("language")
        if sentiment:
            report.sentiment = self.sentiment_analyzer.analyze(doc).to_dict()
            sections.append("sentiment")
        if readability:
            report.readability = self.readability_analyzer.analyze(doc).to_dict()
            sections.append("readability")
        if keywords:
            kw = self.keyword_extractor.extract(doc, top_k=top_keywords)
            report.keywords = [k.to_dict() for k in kw.keywords]
            sections.append("keywords")
        if entities:
            report.entities = [e.to_dict() for e in self.entity_extractor.extract(doc).entities]
            sections.append("entities")
        if summary:
            report.summary = self.summarizer.summarize(doc).to_dict() if doc.strip() else {
                "summary": "", "selected_indices": [], "original_sentences": 0,
                "summary_sentences": 0, "compression_ratio": 0.0, "keywords": [],
            }
            sections.append("summary")

        report.sections = sections
        self._record(sections)
        return report

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def _record(self, sections: list[str]) -> None:
        with self._lock:
            self._total += 1
            for s in sections:
                self._section_counts[s] = self._section_counts.get(s, 0) + 1

    def metrics(self) -> dict:
        with self._lock:
            return {
                "total_analyses": self._total,
                "section_counts": dict(self._section_counts),
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total = 0
            self._section_counts = {}
