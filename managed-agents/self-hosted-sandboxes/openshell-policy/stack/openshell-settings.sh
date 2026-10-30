#!/usr/bin/env bash
# The OpenShell gateway settings this design depends on, set gateway-wide so
# no sandbox can be created without them.
set -euo pipefail

# Agents may propose rules through http://policy.local. Proposals change
# nothing on their own; the reviewer decides each one, and rejects every
# proposal from a profile whose `proposals` setting is off.
openshell settings set --global --key agent_policy_proposals_enabled --value true --yes

# The gateway never approves anything itself. Automatic mode would approve
# any proposal its risk check finds nothing in, including new public hosts,
# without the ceiling proof. The reviewer is the only approver.
openshell settings set --global --key proposal_approval_mode --value manual --yes

# Network decisions as OCSF JSON files inside the sandbox, on drivers that can
# write them. The 0.1.2 docker driver cannot (ISSUES.md, 1), so `make audit`
# reads the gateway's log stream instead.
openshell settings set --global --key ocsf_json_enabled --value true --yes

openshell settings get --global

# A global policy replaces every sandbox's policy and blocks approvals. This
# design needs none; this lists any revisions so you can check.
echo "global policy revisions (expect none):"
openshell policy list --global || true
