"""Retry initialization until its feature-list artifact exists."""

from unittest.mock import AsyncMock

import agent
import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("creates_features", [False, True])
@pytest.mark.parametrize("first_status", ["error", "continue"])
async def test_next_session_uses_feature_list(
    tmp_path, monkeypatch, creates_features, first_status
):
    prompts = []

    async def run_session(client, prompt, project_dir):
        prompts.append(prompt)
        if len(prompts) == 1 and creates_features:
            (project_dir / "feature_list.json").write_text("[]")
        return first_status if len(prompts) == 1 else "continue", ""

    monkeypatch.setattr(agent, "create_client", lambda *_: AsyncMock())
    monkeypatch.setattr(agent, "run_agent_session", run_session)
    monkeypatch.setattr(agent, "get_initializer_prompt", lambda: "initialize")
    monkeypatch.setattr(agent, "get_coding_prompt", lambda: "code")
    monkeypatch.setattr(agent.asyncio, "sleep", AsyncMock())

    await agent.run_autonomous_agent(tmp_path, "unused-model", max_iterations=2)

    assert prompts == ["initialize", "code" if creates_features else "initialize"]
