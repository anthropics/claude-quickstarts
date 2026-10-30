"""The demo's agents as `ant apply` creates them, and how agentpolicy finds them."""

from __future__ import annotations

import json

import yaml
from conftest import ROOT

from agentpolicy import managed_agents


def agent_file(name: str) -> tuple[dict, str]:
    front, _, body = (ROOT / "agents" / name).read_text()[4:].partition("\n---\n")
    return yaml.safe_load(front), body


def test_the_agents_are_what_the_design_needs():
    hello, hello_prompt = agent_file("hello.md")
    reviewer, reviewer_prompt = agent_file("reviewer.md")
    # The demo agent: the toolset the sandbox's worker serves, the web tools
    # off so the sandbox is its only route to the network.
    assert hello["tools"][0]["type"] == "agent_toolset_20260401"
    assert {c["name"]: c["enabled"] for c in hello["tools"][0]["configs"]} == {"web_fetch": False, "web_search": False}
    assert "policy_advisor.md" in hello_prompt
    # The reviewer: one custom tool, no built-in tools, so no worker serves it.
    assert [(t["type"], t["name"]) for t in reviewer["tools"]] == [("custom", "decide")]
    assert "UNTRUSTED" in reviewer_prompt
    for agent in (hello, reviewer):
        assert agent["metadata"]["anthropic_cookbook"] == "claude-quickstarts/self-hosted-sandboxes"


def test_resource_ids_come_from_the_lockfile(tmp_path):
    lock = {"resources": {f: {"id": f"id-{key}"} for key, f in managed_agents.RESOURCES.items()}}
    (tmp_path / "claude-lock.json").write_text(json.dumps(lock))
    assert managed_agents.resource_ids(tmp_path) == {key: f"id-{key}" for key in managed_agents.RESOURCES}
