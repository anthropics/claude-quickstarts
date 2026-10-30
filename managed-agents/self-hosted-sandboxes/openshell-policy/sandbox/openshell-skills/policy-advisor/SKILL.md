---
name: openshell-policy-advisor
description: Use when an OpenShell sandbox returns policy_denied, mentions policy.local, or needs a narrow network policy proposal.
---

# OpenShell Policy Advisor

When a request fails with `policy_denied`, do not treat the denial as final if the user task still needs the request. Read `/etc/openshell/skills/policy_advisor.md`, inspect `http://policy.local/v1/policy/current`, submit the narrowest proposal to `http://policy.local/v1/proposals`, wait on `/v1/proposals/{chunk_id}/wait?timeout=300`, and retry only after approval with `policy_reloaded: true`.
