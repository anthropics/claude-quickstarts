"""
Neuro-Symbolic Logic System for Agent Framework

Combines ML-powered reasoning with formal logic representation.
"""

from .knowledge_base import (
    KnowledgeBase,
    Fact,
    ValidationResult,
    LogicalStatement,
    LogicType,
    InferenceRule
)

from .reasoning_agent import (
    ReasoningAgent,
    ReasoningStep,
    FormalArgument,
    ArgumentBuilder,
    ArgumentFormatter
)

__all__ = [
    "KnowledgeBase",
    "Fact",
    "ValidationResult",
    "LogicalStatement",
    "LogicType",
    "InferenceRule",
    "ReasoningAgent",
    "ReasoningStep",
    "FormalArgument",
    "ArgumentBuilder",
    "ArgumentFormatter"
]
