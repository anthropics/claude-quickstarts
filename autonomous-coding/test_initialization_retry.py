"""Retry initialization until feature_list.json exists."""

import asyncio
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

sdk = types.ModuleType("claude_code_sdk")


class ClaudeSDKClient:
    pass


class ClaudeCodeOptions:
    pass


sdk.ClaudeSDKClient = ClaudeSDKClient
sdk.ClaudeCodeOptions = ClaudeCodeOptions
sys.modules["claude_code_sdk"] = sdk

sdk_types = types.ModuleType("claude_code_sdk.types")


class HookMatcher:
    pass


sdk_types.HookMatcher = HookMatcher
sys.modules["claude_code_sdk.types"] = sdk_types

import agent
import pytest


@pytest.mark.parametrize("creates_features", [False, True])
@pytest.mark.parametrize("first_status", ["error", "continue"])
def test_next_session_uses_feature_list(tmp_path, monkeypatch, creates_features, first_status):
    prompts = []

    async def run_session(client, prompt, project_dir):
        prompts.append(prompt)
        if len(prompts) == 1 and creates_features:
            (project_dir / "feature_list.json").write_text("[]", encoding="utf-8")
        status = first_status if len(prompts) == 1 else "continue"
        return status, ""

    async def no_sleep(*_args, **_kwargs):
        return None

    class Ready:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr(agent, "create_client", lambda *_args: Ready())
    monkeypatch.setattr(agent, "run_agent_session", run_session)
    monkeypatch.setattr(agent, "get_initializer_prompt", lambda: "initialize")
    monkeypatch.setattr(agent, "get_coding_prompt", lambda: "code")
    monkeypatch.setattr(agent.asyncio, "sleep", no_sleep)

    asyncio.run(agent.run_autonomous_agent(tmp_path, "unused-model", max_iterations=2))

    assert prompts == ["initialize", "code" if creates_features else "initialize"]
