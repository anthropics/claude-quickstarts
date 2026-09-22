#!/usr/bin/env bash
# Start one analyst session per subject, a company or a person. Every session
# mounts the same EDGAR disk and writes its report to its own directory on it,
# so the research runs in parallel and the results land in one place.
#
#   ./fanout.sh "Tesla" "Venture Global (NYSE: VG)" "Sanjit Biswas, CEO of Samsara"
set -euo pipefail
cd "$(dirname "$0")"
[ -f claude-lock.json ] || { echo "no claude-lock.json: run 'ant apply .' from this directory first" >&2; exit 1; }
[ -f .env ] || { echo "no .env: copy .env.example to .env and fill it in" >&2; exit 1; }
set -a; . ./.env; set +a

# The agent and environment `ant apply` created, by the files that declare them.
agent=$(jq -r '.resources["./agents/edgar-analyst.md"].id // empty' claude-lock.json)
environment=$(jq -r '.resources["./environments/self-hosted.yaml"].id // empty' claude-lock.json)
: "${agent:?claude-lock.json has no agent yet: run \"ant apply .\" again}" \
  "${environment:?claude-lock.json has no environment yet: run \"ant apply .\" again}"

for subject in "$@"; do
  session=$(ant beta:sessions create --agent "$agent" --environment-id "$environment" \
    --title "$subject" \
    --initial-event "{type: user.message, content: [{type: text, text: \"Build a profile of: $subject\"}]}" \
    --transform id --raw-output)
  echo "$session  $subject"
done

cat <<EOF

Each analyst's summary is the last message in its session:
  ant beta:sessions:events list --session-id <session> --type agent.message --order desc --max-items 1 \\
    --transform content.0.text --raw-output
The full reports are on the disk at reports/<session>/report.md. Read them from
any machine with the archil CLI and the mount token:
  archil mount $ARCHIL_DISK /mnt/edgar --region $ARCHIL_REGION --shared
EOF
