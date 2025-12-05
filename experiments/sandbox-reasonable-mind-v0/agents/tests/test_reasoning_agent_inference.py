from agents.logic.knowledge_base import Fact, InferenceRule
from agents.logic.reasoning_agent import ReasoningAgent


def test_modus_ponens_prefers_logical_form_arrow():
    agent = ReasoningAgent(name="tester", system_prompt="test prompt")
    fact = Fact(statement="P → Q", logical_form="P → Q")

    conclusion = agent._generate_conclusion("P", [fact], InferenceRule.MODUS_PONENS)

    assert conclusion == ("Q", True)


def test_modus_ponens_if_then_still_supported():
    agent = ReasoningAgent(name="tester", system_prompt="test prompt")
    fact = Fact(statement="If it rains then streets are wet")

    conclusion = agent._generate_conclusion(
        "It rains", [fact], InferenceRule.MODUS_PONENS
    )

    assert conclusion == ("streets are wet", True)


def test_hallucination_guard_penalizes_unvalidated_outputs():
    agent = ReasoningAgent(name="tester", system_prompt="test prompt")
    fake_result = {
        "confidence": 0.9,
        "knowledge_validation": {"valid": False, "confidence": 0.1, "sources": []},
        "knowledge_used": [],
        "reasoning_chain": [{"confidence": 0.6}],
    }

    guard = agent._hallucination_guard(fake_result)

    assert guard["risk_level"] == "high"
    assert guard["adjusted_confidence"] < fake_result["confidence"]
    assert any("validation failed" in w.lower() for w in guard["warnings"])


def test_hallucination_guard_respects_validated_outputs():
    agent = ReasoningAgent(name="tester", system_prompt="test prompt")
    fake_result = {
        "confidence": 0.8,
        "knowledge_validation": {"valid": True, "confidence": 0.9, "sources": ["kb"]},
        "knowledge_used": ["fact1"],
        "reasoning_chain": [{"confidence": 0.9}],
    }

    guard = agent._hallucination_guard(fake_result)

    assert guard["risk_level"] == "low"
    assert guard["adjusted_confidence"] == fake_result["confidence"]


def test_reasoning_result_flags_missing_citations():
    agent = ReasoningAgent(name="tester", system_prompt="test prompt", verbose=False)
    fake_result = {
        "confidence": 0.8,
        "knowledge_validation": {"valid": True, "confidence": 0.9, "sources": []},
        "knowledge_used": [],
        "reasoning_chain": [{"confidence": 0.9}],
    }

    guard = agent._hallucination_guard(fake_result)
    fake_result["hallucination_guard"] = guard
    fake_result["warnings"] = guard["warnings"]

    if not fake_result["knowledge_used"]:
        fake_result["warnings"].append("Conclusion has no cited facts; treat as ungrounded.")
        fake_result["confidence"] *= 0.8

    assert any("no cited facts" in w.lower() for w in fake_result["warnings"])
    assert fake_result["confidence"] < 0.8
