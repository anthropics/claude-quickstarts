from agents.logic.decision_model import (
    Constraints,
    DecisionConfig,
    DecisionModel,
    DecisionOption,
)


def test_hard_constraints_block_options():
    model = DecisionModel()
    constraints = Constraints(required_tags=["safe"])
    options = [
        DecisionOption(id="a", description="ok", tags=["safe"]),
        DecisionOption(id="b", description="blocked", tags=["risky"]),
    ]

    result = model.score_options(options, constraints)

    assert result.blocked is False
    assert any("blocked" not in r["description"] for r in result.ranked)
    assert any("blocked by constraints" in w for w in result.warnings)


def test_citation_penalty_applied():
    model = DecisionModel(DecisionConfig(citation_required=True, citation_penalty=0.5))
    options = [
        DecisionOption(id="cited", description="cited", value=1.0, cited=True),
        DecisionOption(id="uncited", description="uncited", value=1.0, cited=False),
    ]

    result = model.score_options(options)
    scores = {r["id"]: r["score"] for r in result.ranked}

    assert scores["cited"] > scores["uncited"]
    assert any("lacks citations" in w for w in result.warnings)


def test_contradiction_penalty_applied():
    model = DecisionModel()
    options = [
        DecisionOption(id="clean", description="clean", value=1.0),
        DecisionOption(
            id="contradictory", description="conflict", value=1.0, contradiction_flag=True
        ),
    ]

    result = model.score_options(options)
    scores = {r["id"]: r["score"] for r in result.ranked}

    assert scores["clean"] > scores["contradictory"]
    assert any("contradictions" in w for w in result.warnings)


def test_soft_penalty_and_risk_warning():
    model = DecisionModel()
    constraints = Constraints(soft_penalties={"slow": 0.2})
    options = [
        DecisionOption(
            id="risky", description="risky", value=1.0, risk=0.9, tags=["slow"], cited=True
        ),
        DecisionOption(id="safe", description="safe", value=0.9, risk=0.1, cited=True),
    ]

    result = model.score_options(options, constraints)
    assert any("high risk" in w for w in result.warnings)
    # Despite higher value, penalties may drop risky option below safe
    assert result.ranked[0]["id"] == "safe"
