---
# The deployment: which agent runs, where, when, with which memory and which
# spending cap. The body below the frontmatter is the first message of every run.
name: Daily brief
agent: ./agent.md
environment_id: ./environment.yaml
schedule:
  type: cron
  expression: "32 7 * * 1-5" # weekdays at 07:32
  timezone: America/New_York # when it fires; the body tells the agent which zone to use for dates
# The vault (vault.yaml) holds the Slack and GitHub credentials. A deployment
# takes vault IDs rather than a file reference, so agents/setup.sh writes the
# ID from claude-lock.json on the next line after `ant apply` creates the vault.
vault_ids: []
resources:
  - path: ./memory_store_preferences.yaml
    access: read_only
    instructions: The reader's preferences. Re-read them every run. Never write here.
  - path: ./memory_store_state.yaml
    access: read_write # set to read_only for a dry run: the agent then posts nothing and prints the brief
    instructions: Your state. Bookmarks, ledger, notes, proposals, and run records.
budget:
  type: limit
  max_list_cost:
    amount: "500" # a string, in cents: "500" is $5.00 per run
    currency: USD
---

Write today's brief.
The reader's time zone is America/New_York. Work out every date in that zone.
Follow your run steps in order. Today's edition is titled "Daily brief, <weekday> <month> <day>".
