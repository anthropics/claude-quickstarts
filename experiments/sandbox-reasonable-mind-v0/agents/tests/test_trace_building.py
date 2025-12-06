from agents.logic.reasoning_agent import ReasoningAgent


def test_build_trace_contains_core_fields():
    agent = ReasoningAgent(name="tester", system_prompt="test")
    agent.add_knowledge("Socrates is mortal", source="kb", confidence=0.9)

    result = agent.reason("Socrates is mortal")
    trace = agent.build_trace(result)

    assert "conclusion" in trace
    assert "warnings" in trace
    assert "verified" in trace
    assert "reasoning_chain" in trace
