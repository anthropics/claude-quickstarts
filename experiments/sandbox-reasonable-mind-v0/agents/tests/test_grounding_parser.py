import pytest

from agents.logic.grounding import (
    ModalityType,
    QuantifierType,
    SemanticParser,
    create_ml_context,
)


def test_epistemic_modality_is_stripped_and_parsed():
    parser = SemanticParser(create_ml_context())

    result = parser.parse("Alice believes all robots are helpful")

    assert result.success is True
    assert result.quantifier == QuantifierType.UNIVERSAL
    assert result.modality == ModalityType.EPISTEMIC
    assert result.logical_form.startswith("∀x(")
    assert any("Removed modality" in assumption for assumption in result.assumptions)


def test_probabilistic_quantifier_is_flagged():
    parser = SemanticParser(create_ml_context())

    result = parser.parse("Most models are biased")

    assert result.success is False
    assert result.quantifier == QuantifierType.MOST
    assert any("requires higher-order" in frag for frag in result.unparseable_fragments)
