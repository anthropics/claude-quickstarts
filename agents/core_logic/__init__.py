"""
Core Logic Foundation - Deterministic Reasoning Layer

This module provides the deterministic foundation for neuro-symbolic reasoning.

Philosophy: "Logic is the skeleton, AI is the muscles"
- Logic provides rigid, reliable, deterministic validation
- AI provides flexibility, learning, and natural language understanding
- Together they create a rigorous but practical reasoning system

Components:
- logic_engine: Propositional logic validation (MP, MT, HS, DS, etc.)
- categorical_engine: Syllogistic reasoning (Barbara, Celarent, etc.)
- Both integrate with agents/core/ for full neuro-symbolic pipeline

Usage:
    from agents.core_logic import LogicEngine, CategoricalEngine

    # Propositional logic
    engine = LogicEngine()
    result = engine.validate(argument)

    # Categorical logic
    cat_engine = CategoricalEngine()
    syl_result = cat_engine.validate(syllogism)
"""

from .logic_engine import (
    LogicEngine,
    LogicForm,
    TruthValue,
    Proposition,
    LogicalArgument,
    ValidationResult,
    parse_argument,
    validate_modus_ponens,
    validate_modus_tollens,
)

from .categorical_engine import (
    CategoricalEngine,
    StatementType,
    Figure,
    CategoricalStatement,
    Syllogism,
    SyllogismValidation,
    parse_categorical_statement,
    parse_syllogism,
    validate_barbara,
)

__all__ = [
    # Logic Engine
    "LogicEngine",
    "LogicForm",
    "TruthValue",
    "Proposition",
    "LogicalArgument",
    "ValidationResult",
    "parse_argument",
    "validate_modus_ponens",
    "validate_modus_tollens",
    # Categorical Engine
    "CategoricalEngine",
    "StatementType",
    "Figure",
    "CategoricalStatement",
    "Syllogism",
    "SyllogismValidation",
    "parse_categorical_statement",
    "parse_syllogism",
    "validate_barbara",
]

__version__ = "1.0.0"
__author__ = "Claude Quickstarts"
__description__ = "Deterministic logic foundation for neuro-symbolic AI"
