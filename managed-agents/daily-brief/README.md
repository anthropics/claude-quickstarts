# Daily brief: a scheduled agent that tells you what changed

An agent that briefs you every weekday morning. It reads your Slack channels and GitHub pull requests, works out what you would act on today, and posts one short brief to a Slack channel. It runs on [Claude Managed Agents](https://platform.claude.com/docs/en/managed-agents/overview) as a [scheduled deployment](https://platform.claude.com/docs/en/managed-agents/scheduled-deployments), so there is no server to keep alive: the agent, its sandbox, its schedule, its memory, its spending cap and its credential vault are six files applied with [`ant apply`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/apply).

Most of the design is about failing well when nobody is watching. Each source has a bookmark, so a late or skipped run loses nothing. A ledger stops it repeating yesterday's items. A source it could not read is reported as unreadable, never as a quiet day. The post is confirmed before anything is recorded. Your preferences live in a store the agent reads every run and cannot edit.

## Quickstart

You need the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli) (1.34 or later, the first release whose `ant apply` manages vaults) signed in with `ant auth login` or an `ANTHROPIC_API_KEY`, plus `jq`.

1. **Create the Slack app** (one click, then Install to Workspace):

   <!-- This link is slack/manifest.yaml, URL-encoded. After editing the manifest, regenerate it with:
        echo "https://api.slack.com/apps?new_app=1&manifest_yaml=$(jq -rRs @uri slack/manifest.yaml)" -->
   [Create the Slack app](https://api.slack.com/apps?new_app=1&manifest_yaml=display_information%3A%0A%20%20name%3A%20Daily%20brief%0A%20%20description%3A%20Posts%20one%20short%20brief%20each%20weekday%20morning.%0Afeatures%3A%0A%20%20bot_user%3A%0A%20%20%20%20display_name%3A%20Daily%20brief%0A%20%20%20%20always_online%3A%20false%0A%20%20app_home%3A%0A%20%20%20%20home_tab_enabled%3A%20false%0A%20%20%20%20messages_tab_enabled%3A%20true%0A%20%20%20%20messages_tab_read_only_enabled%3A%20true%0Aoauth_config%3A%0A%20%20scopes%3A%0A%20%20%20%20bot%3A%0A%20%20%20%20%20%20-%20channels%3Ahistory%0A%20%20%20%20%20%20-%20chat%3Awrite%0Asettings%3A%0A%20%20org_deploy_enabled%3A%20false%0A%20%20socket_mode_enabled%3A%20false%0A%20%20token_rotation_enabled%3A%20false%0A)

   Copy the **Bot User OAuth Token** (`xoxb-...`) from OAuth & Permissions. In Slack, `/invite @Daily brief` into each channel it should read and into the channel it should post to. Those invitations are the bot's only access.

2. **Create a GitHub token**: a [fine-grained personal access token](https://github.com/settings/personal-access-tokens/new) with read-only access (Contents: read, Pull requests: read) to the repositories you want covered. Keep it read-only: the agent runs every GitHub tool without asking.

3. **Set up**:

   ```bash
   cp .env.example .env        # put the two tokens in it
   agents/setup.sh
   ```

   One `ant apply` creates the agent, environment, memory stores, vault and deployment in your workspace; the script then adds the two credentials to the vault (no secret ever passes through `ant apply`), attaches the vault to the deployment, and pauses the schedule.

4. **Write your preferences**: the agent reads `/preferences.md` from the read-only `preferences` store at the start of every run, and `ant apply` creates the store but not the file.

   ```bash
   cp preferences.example.md preferences.md    # who you are, your channel IDs, repositories, destination channel, length cap
   scripts/seed-preferences.sh preferences.md
   ```

   Later edits take effect on the next run: change the file and seed it again.

5. **Try a run**: `scripts/run.sh` starts one now, waits, and prints the agent's last message, any source it could not read, and the run record it wrote. When a run looks right, turn the schedule on:

   ```bash
   ant beta:deployments unpause --deployment-id <the depl_ id setup printed>
   ```

## How a run works

The run steps are the body of [`agents/daily-brief/agent.md`](agents/daily-brief/agent.md) and are worth reading in full. In short:

1. Read `preferences.md` fresh. If it says stop, stop.
2. Read the state: `bookmarks.json` (where each source was last read), `ledger.md` (what was already reported), `notes.md`, and the last run record.
3. Read each source from ten minutes before its bookmark. A source that fails keeps its bookmark and is named in the brief as unreadable.
4. Decide: an item earns a line only if you would act on it today.
5. Verify every item against its live source just before posting.
6. Write the brief inside the length cap, with one line for gaps.
7. Look for today's edition before posting, post, and read Slack's response body (`"ok": true` and a `ts`) before counting it as posted.
8. Only then move the bookmarks, add ledger lines, and write `runs/<date>.md`.

Slack is called from the sandbox shell with `curl`. The bot token is a [vault](https://platform.claude.com/docs/en/managed-agents/vaults) credential: the agent sees a placeholder in `$SLACK_BOT_TOKEN`, and the real token is substituted at egress on requests to `slack.com` only. GitHub goes through its MCP server with the read-only token from the same vault.

## Files

```
agents/daily-brief/agent.md          model and tools in frontmatter, the run steps as the body
agents/daily-brief/deployment.md     schedule, time zone, budget, vault and memory stores; the first message as the body
agents/daily-brief/environment.yaml  the sandbox's network allowlist
agents/daily-brief/memory_store_*.yaml  your preferences (read-only to the agent) and the agent's state
agents/daily-brief/vault.yaml        the vault that holds the Slack and GitHub credentials (the container; credentials are added by setup.sh)
agents/setup.sh                      applies all of the above, adds the credentials, attaches the vault
preferences.example.md               starting point for preferences.md
scripts/run.sh                       start a run now and show what happened
scripts/seed-preferences.sh          write preferences.md into the preferences store
scripts/reset-state.sh               empty the state store after test runs
scripts/teardown.sh                  remove everything setup.sh created
slack/manifest.yaml                  the Slack app (two scopes: channels:history, chat:write)
claude-lock.json                     resource IDs, written by ant apply (git-ignored here)
```

## Things worth knowing

- **Dry run.** Set the `state` store to `access: read_only` in `deployment.md` and apply. The agent then posts nothing, prints the brief in its final message, and cannot move a bookmark.
- **Cost.** On a busy day (two channels and two repositories with around 140 messages and 25 pull requests between them) a run cost about $1.50 on Claude Opus 5 and about $1.00 on Claude Sonnet 5 in our tests; a run that finds every source unreadable costs $0.15 to $0.30. Doubling the sources added roughly a third, not double. Change `model:` in `agent.md` to trade depth for cost.
- **Budget.** `deployment.md` caps each run at $5.00 (`amount: "500"` is cents, as a string). A run that reaches it pauses rather than fails, which from the channel looks like silence, so check the deployment's runs in the Console if a brief goes missing. Tighten it after a week of real runs.
- **Time zone.** The cron fires in the `timezone` from `deployment.md`, and the first message tells the agent which zone to use for dates. Change both together.
- **After testing**, `scripts/reset-state.sh` empties the state store so the first real run starts clean. `scripts/teardown.sh` removes all six resources when you are done with the quickstart.
- **Private channels** need the `groups:history` scope added to `slack/manifest.yaml`. Read the security notes first.

## Security notes

The agent reads text other people wrote, and any of it can try to steer the agent. What limits the damage:

- **The GitHub token is the control on GitHub.** It is read-only, so a planted instruction cannot write to a repository even though every GitHub tool runs without approval.
- **The agent cannot edit your rules.** `preferences` is mounted read-only at the filesystem level. Treat `proposals.md` as untrusted text when you review it.
- **Slack posting is limited by membership, not by scope.** The bot token can post to any channel the bot is in, and it has to be in your source channels to read them. The run steps tell the agent to post only the brief and only to the destination, but that is a prompt rule. Keep the bot out of channels it does not need, and if your source channels are sensitive, use two Slack apps: a read-only one for sources and a `chat:write` one invited only to the destination, as two vault credentials.
- **The sandbox reaches only `slack.com` and the GitHub MCP server** (`environment.yaml`).
