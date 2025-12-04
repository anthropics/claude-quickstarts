from agents.logic.knowledge_base import KnowledgeBase, LogicType


def test_validate_with_contradiction_check_penalizes_conflicts():
    kb = KnowledgeBase(logic_system=LogicType.PROPOSITIONAL)
    kb.add_fact("Cats are cute", source="assertion", confidence=0.9)
    kb.add_fact("Cats are not cute", source="assertion", confidence=0.9)

    result = kb.validate_with_contradiction_check("Cats are cute", use_ml=False)

    assert result.valid is True  # direct match still holds
    assert result.confidence < 0.9  # penalized due to contradiction
    assert any("Contradiction" in r for r in result.reasoning_chain)
