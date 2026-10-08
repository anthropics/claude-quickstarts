#!/usr/bin/env bash
# Put the Slack bot token and the GitHub token into the vault. Each one is asked
# for at a hidden prompt, checked against Slack or GitHub so a wrong paste is
# caught here rather than on the first run, and sent to the vault on ant's
# stdin. No token is echoed, written to a file, or put on a command line, so
# you can run this next to a coding agent and the agent never sees a token:
# run it in your own terminal, not through the agent.
#
# Usage:
#   scripts/credentials.sh            add whichever of the two is missing (both, on first setup)
#   scripts/credentials.sh slack      replace the Slack token (rotation); same for `github`
#   SLACK_BOT_TOKEN=... GITHUB_TOKEN=... scripts/credentials.sh
#                                     no prompts, e.g. SLACK_BOT_TOKEN=$(op read op://...) from a password manager
set -euo pipefail
cd "$(dirname "$0")/.."

for tool in ant jq curl; do
  command -v "$tool" >/dev/null || { echo "install $tool first (see README)" >&2; exit 1; }
done
VAULT_ID=$(jq -r '.resources["./agents/daily-brief/vault.yaml"].id // empty' claude-lock.json 2>/dev/null || true)
[ -n "$VAULT_ID" ] || { echo "no vault yet: run agents/setup.sh first (it creates the vault, then calls this)" >&2; exit 1; }

say() { printf '%s\n' "$*" >&2; }
existing=$(ant beta:vaults:credentials list --vault-id "$VAULT_ID" --format jsonl --transform '{id,display_name}')
cred_id() { jq -r --arg n "$1" 'select(.display_name == $n) | .id' <<<"$existing" | head -1; }

# Which credentials to do: the one named on the command line (replacing what is
# there), otherwise whichever is missing.
case "${1:-}" in
  slack) want="slack" ;; github) want="github" ;;
  "") want=""
      [ -n "$(cred_id SLACK_BOT_TOKEN)" ] || want="slack"
      [ -n "$(cred_id 'GitHub (read-only)')" ] || want="$want github" ;;
  *) echo "usage: scripts/credentials.sh [slack|github]" >&2; exit 2 ;;
esac
if [ -z "$want" ]; then
  say "vault: $VAULT_ID already holds the Slack and GitHub credentials."
  say "       To replace one (a rotated token): scripts/credentials.sh slack   or   scripts/credentials.sh github"
  exit 0
fi

# Prompting needs a real terminal on stdin. A coding agent's shell has none, and
# that is the point: the agent should hand this step to you rather than ask you
# for a token. Tokens supplied in the environment skip the prompt.
needs_prompt=
case " $want " in *" slack "*) [ -n "${SLACK_BOT_TOKEN:-}" ] || needs_prompt=1 ;; esac
case " $want " in *" github "*) [ -n "${GITHUB_TOKEN:-}" ] || needs_prompt=1 ;; esac
if [ -n "$needs_prompt" ] && ! [ -t 0 ]; then
  cat >&2 <<EOF
This step asks for secrets, so it needs a person at a terminal.
Run it yourself, in your own terminal, from $(pwd):

    scripts/credentials.sh${1:+ $1}

It shows where to get each token, reads it at a hidden prompt, checks it, and
puts it in the vault. Nothing you paste is printed or saved to a file.
EOF
  exit 3
fi

# ask VAR "prompt": hidden read into VAR. Ctrl-C or Ctrl-D gives up.
ask() {
  IFS= read -rs -p "$2" "$1" || { echo >&2; say "   (no input; stopped without storing this one)"; exit 1; }
  echo >&2
}

# store <display_name> <create body> <update body>: bodies arrive as here-strings
# on ant's stdin, so the token is never an argument (visible in `ps`).
store() {
  local id; id=$(cred_id "$1")
  if [ -n "$id" ]; then
    ant beta:vaults:credentials update --vault-id "$VAULT_ID" --credential-id "$id" >/dev/null <<<"$3"
    say "   ✓ replaced \"$1\" in vault $VAULT_ID"
  else
    ant beta:vaults:credentials create --vault-id "$VAULT_ID" >/dev/null <<<"$2"
    say "   ✓ added \"$1\" to vault $VAULT_ID"
  fi
}

slack() {
  local token=${SLACK_BOT_TOKEN:-} from_env=${SLACK_BOT_TOKEN:+1} resp err bot team
  say ""; say "== Slack bot token${from_env:+ (from \$SLACK_BOT_TOKEN)}"
  # The same link as README step 2: slack/manifest.yaml, URL-encoded.
  cat >&2 <<EOF
   1. Create the app from the manifest (choose a workspace, Next, Create):
      https://api.slack.com/apps?new_app=1&manifest_yaml=$(jq -rRs @uri slack/manifest.yaml)
   2. Install App (left sidebar), Install to your workspace, Allow.
   3. Copy the Bot User OAuth Token shown there. It starts with xoxb-.
EOF
  while :; do
    [ -n "$token" ] || ask token "   Paste the bot token here (nothing will show): "
    case "$token" in
      "") say "   (empty; Ctrl-C to stop)"; continue ;;
      xoxb-*) ;;
      xoxp-* | xoxe*) say "   That is a user or config token. Copy the Bot User OAuth Token (xoxb-) from Install App or OAuth & Permissions." ;;
      *) say "   That is not a bot token: they start with xoxb-. The signing secret and client secret on Basic Information are not it." ;;
    esac
    if [[ $token == xoxb-* ]]; then
      resp=$(curl -sS -m 20 -X POST -H @- https://slack.com/api/auth.test <<<"Authorization: Bearer $token") || resp=
      if [ "$(jq -r '.ok // false' <<<"$resp" 2>/dev/null)" = true ]; then
        bot=$(jq -r .user <<<"$resp"); team=$(jq -r .team <<<"$resp")
        say "   ✓ Slack accepts it: bot @$bot in workspace \"$team\""
        break
      fi
      err=$(jq -r '.error // empty' <<<"$resp" 2>/dev/null || true)
      say "   Slack rejected it: ${err:-could not reach slack.com}. Copy the token again from Install App, after installing."
    fi
    [ -z "$from_env" ] || exit 1
    token=
  done
  store SLACK_BOT_TOKEN \
    "$(T=$token jq -nc '{display_name: "SLACK_BOT_TOKEN", auth: {type: "environment_variable", secret_name: "SLACK_BOT_TOKEN", secret_value: $ENV.T,
        networking: {type: "limited", allowed_hosts: ["slack.com"]}, injection_location: {header: true}}}')" \
    "$(T=$token jq -nc '{auth: {type: "environment_variable", secret_value: $ENV.T}}')"
  say "   Next, in Slack: /invite @$bot in each channel the brief should read and in the channel it posts to."
}

github() {
  local token=${GITHUB_TOKEN:-} from_env=${GITHUB_TOKEN:+1} resp code login
  say ""; say "== GitHub token (fine-grained, read-only)${from_env:+ (from \$GITHUB_TOKEN)}"
  cat >&2 <<'EOF'
   1. Open the prefilled token form:
      https://github.com/settings/personal-access-tokens/new?name=daily-brief&description=Read-only+token+for+the+daily+brief+agent&expires_in=90&contents=read&pull_requests=read
      Resource owner: you, or the org that owns the repositories (an org may hold the token
      for admin approval). Repository access: Only select repositories, and pick the ones the
      brief should cover. Leave the permissions as filled in (Contents and Pull requests,
      read-only), then Generate token.
   2. Copy the token. It starts with github_pat_.
EOF
  while :; do
    [ -n "$token" ] || ask token "   Paste the GitHub token here (nothing will show): "
    case "$token" in
      "") say "   (empty; Ctrl-C to stop)"; continue ;;
      github_pat_*) ;;
      gh?_*) say "   That is a classic or app token. Classic tokens cannot be limited to chosen repositories or made read-only, and the agent runs every GitHub tool without asking, so use the fine-grained form above." ;;
      *) say "   That is not a fine-grained token: they start with github_pat_." ;;
    esac
    if [[ $token == github_pat_* ]]; then
      resp=$(curl -sS -m 20 -w $'\n%{http_code}' -H @- -H "Accept: application/vnd.github+json" -H "User-Agent: daily-brief-quickstart" \
        https://api.github.com/user <<<"Authorization: Bearer $token") || resp=$'\n000'
      code=${resp##*$'\n'}
      if [ "$code" = 200 ]; then
        login=$(jq -r .login <<<"${resp%$'\n'*}")
        say "   ✓ GitHub accepts it: token belongs to $login"
        say "     (GitHub does not report a fine-grained token's permissions, so this cannot confirm it is read-only: keep it to what the form filled in)"
        break
      fi
      case "$code" in
        401) say "   GitHub rejected it (401): wrong, revoked or expired. Generate a new one with the link above." ;;
        000) say "   Could not reach api.github.com. Check your network and paste it again." ;;
        *) say "   GitHub answered $code: $(jq -r '.message // ""' <<<"${resp%$'\n'*}" 2>/dev/null)" ;;
      esac
    fi
    [ -z "$from_env" ] || exit 1
    token=
  done
  store "GitHub (read-only)" \
    "$(T=$token jq -nc '{display_name: "GitHub (read-only)", auth: {type: "static_bearer", mcp_server_url: "https://api.githubcopilot.com/mcp/", token: $ENV.T}}')" \
    "$(T=$token jq -nc '{auth: {type: "static_bearer", token: $ENV.T}}')"
  say "   It expires in 90 days unless you changed that on the form; scripts/credentials.sh github replaces it then."
}

for c in $want; do "$c"; done
say ""
say "vault: done. The agent sees a placeholder for the Slack token (the real one is added on requests to slack.com only)"
say "       and reaches GitHub through its MCP server with the read-only token."
