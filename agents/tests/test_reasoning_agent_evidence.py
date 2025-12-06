from agents.logic.reasoning_agent import ReasoningAgent


def test_reason_fail_closed_without_evidence():
    agent = ReasoningAgent(name="tester", system_prompt="test")
    result = agent.reason("Socrates is mortal")

    assert result["verified"] is False
    assert "insufficient evidence" in result["conclusion"].lower()
    assert any("insufficient evidence" in w.lower() for w in result["warnings"])
    assert result["confidence"] <= 0.1


def test_reason_passes_with_evidence():
    agent = ReasoningAgent(name="tester", system_prompt="test")
    agent.add_knowledge("Socrates is mortal", source="kb", confidence=0.9)

    result = agent.reason("Socrates is mortal")

    assert result["verified"] is True
    assert result["knowledge_validation"]["valid"] is True
    assert result["knowledge_validation"]["sources"]
    assert result["formal_argument"].overall_confidence == result["confidence"]
