from agents.logic.decision_model import DecisionModel, DecisionOption


def test_all_uncited_unverified_blocks():
    model = DecisionModel()
    options = [
        DecisionOption(id="a", description="no evidence", value=1.0, cited=False, verified=False),
        DecisionOption(id="b", description="no evidence", value=0.9, cited=False, verified=False),
    ]

    result = model.score_options(options)

    assert result.blocked is True
    assert result.evidence_blocked is True
    assert any("lacks citations" in w.lower() or "unverified" in w.lower() for w in result.warnings)
