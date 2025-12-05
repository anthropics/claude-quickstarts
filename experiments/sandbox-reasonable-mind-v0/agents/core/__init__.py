"""
Core logic modules for deterministic reasoning.

This package provides the foundational logic components:
- logic_engine: Propositional logic validation
- categorical_engine: Aristotelian syllogistic reasoning
- fallacy_detector: Pattern-based fallacy detection
"""

from .logic_engine import LogicEngine, ArgumentForm, LogicResult
from .categorical_engine import CategoricalEngine, SyllogismType
from .fallacy_detector import FallacyDetector, FallacyCategory, FallacySeverity, FallacyPattern

__all__ = [
    'LogicEngine',
    'ArgumentForm',
    'LogicResult',
    'CategoricalEngine',
    'SyllogismType',
    'FallacyDetector',
    'FallacyCategory',
    'FallacySeverity',
    'FallacyPattern',
]
