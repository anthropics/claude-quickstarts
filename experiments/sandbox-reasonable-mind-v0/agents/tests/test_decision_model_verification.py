from agents.logic.decision_model import DecisionModel, DecisionOption


def test_unverified_options_penalized():
    model = DecisionModel()
    options = [
        DecisionOption(id="verified", description="ok", value=1.0, cited=True, verified=True),
        DecisionOption(id="unverified", description="no evidence", value=1.0, cited=False, verified=False),
    ]

    result = model.score_options(options)
    scores = {r["id"]: r["score"] for r in result.ranked}

    assert scores["verified"] > scores["unverified"]
    assert result.unverified_penalized is True
    assert any("unverified" in w.lower() for w in result.warnings)
