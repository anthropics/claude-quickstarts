"""The judgement step, run as a Claude Managed Agents session.

The reviewer is an ordinary Managed Agents agent (agents/reviewer.md). It has no
built-in tools, no shell and no network: its only tool is ``decide``, a custom
tool this process answers. It never touches the OpenShell gateway; this
process applies whatever it decides, and only after every deterministic gate
in ``review.decide`` has already passed.

Because it has no built-in tools, its sessions need no worker. They run on an
environment of their own that no worker polls.
"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

from . import policyfile
from .gateway import Proposal
from .prover import Proof
from .review import APPROVE, DEFER, ESCALATE, REJECT, Context, Decision

@dataclass
class ReviewerIds:
    agent_id: str
    environment_id: str


def _inert(text: str) -> str:
    """Makes agent-written text unable to open or close markup of its own."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def dossier(proposal: Proposal, ctx: Context, proof: Proof, tag: str | None = None) -> str:
    tag = tag or secrets.token_hex(8)
    rule = policyfile.dump({proposal.rule_name: proposal.rule})
    return (
        "## Request (from the platform)\n"
        f"profile: {ctx.profile}\n"
        f"session: {ctx.session_id}\n"
        f"times the block was seen: {proposal.hit_count}\n\n"
        "## Agent's task (from the profile's task.md)\n"
        f"{ctx.agent_description or '(no description for this profile)'}\n\n"
        "## Checks already passed (from the platform)\n"
        f"- ceiling proof: {proof.summary()}\n"
        f"- OpenShell risk check: {_inert(proposal.validation_result) or 'none reported'}\n\n"
        f"<untrusted-{tag}>\n"
        "UNTRUSTED: written by the requesting agent\n\n"
        f"program that was blocked: {_inert(proposal.binary or 'unknown')}\n\n"
        "proposed rule:\n"
        f"{_inert(rule)}\n"
        "explanation:\n"
        f"{_inert(proposal.rationale or '(none given)')}\n"
        f"</untrusted-{tag}>\n"
    )


class ClaudeReviewer:
    name = "claude"

    def __init__(self, client: Any, ids: ReviewerIds, timeout_s: float = 180.0) -> None:
        self.client = client
        self.ids = ids
        self.timeout_s = timeout_s

    def review(self, proposal: Proposal, ctx: Context, proof: Proof) -> Decision:
        sessions = self.client.beta.sessions
        session = sessions.create(
            agent=self.ids.agent_id,
            environment_id=self.ids.environment_id,
            title=f"review {proposal.sandbox}/{proposal.chunk_id}",
            metadata={"agentpolicy_role": "review", "reviewed_session": ctx.session_id},
        )
        try:
            return self._run(session.id, dossier(proposal, ctx, proof))
        finally:
            try:
                sessions.archive(session.id)
            except Exception:  # archiving is housekeeping; the decision stands
                pass

    def _run(self, session_id: str, text: str) -> Decision:
        events = self.client.beta.sessions.events
        deadline = time.monotonic() + self.timeout_s
        # The timeout bounds each read, so a stream that goes quiet cannot
        # hold the grow loop; the deadline bounds the whole review.
        with events.stream(session_id, timeout=self.timeout_s) as stream:
            events.send(session_id, events=[{"type": "user.message", "content": [{"type": "text", "text": text}]}])
            for event in stream:
                if time.monotonic() > deadline:
                    break
                etype = getattr(event, "type", "")
                if etype == "agent.custom_tool_use" and getattr(event, "name", "") == "decide":
                    args = dict(getattr(event, "input", {}) or {})
                    events.send(session_id, events=[{
                        "type": "user.custom_tool_result",
                        "custom_tool_use_id": event.id,
                        "content": [{"type": "text", "text": "recorded"}],
                    }])
                    return _to_decision(args)
                if etype in ("session.status_terminated", "session.error"):
                    break
                if etype == "session.status_idle":
                    stop = getattr(event, "stop_reason", None)
                    if getattr(stop, "type", "") == "end_turn":
                        break
        return Decision(DEFER, "the reviewer did not record a decision", "reviewer_no_answer", reviewer=self.name)


def _to_decision(args: dict[str, Any]) -> Decision:
    action = args.get("action")
    if action not in (APPROVE, REJECT, ESCALATE):
        return Decision(ESCALATE, f"reviewer returned an unknown action {json.dumps(action)}", "unclear", reviewer="claude")
    return Decision(
        action,
        str(args.get("reason") or "").strip()[:1000] or "no reason given",
        str(args.get("code") or "unclear"),
        reviewer="claude",
    )
