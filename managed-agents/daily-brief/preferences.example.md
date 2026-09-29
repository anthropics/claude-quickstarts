# Daily brief preferences

The agent reads this file at the start of every run. Edit it in the Console or with `scripts/seed-preferences.sh`; the next run follows the change. The agent cannot edit it.

## Reader

- Your name, Slack user ID `U0456789123`, GitHub login `your-login`. The agent uses these to find pull requests waiting on you and threads you already answered.
- What you act on: reviews and decisions waiting on you, incidents and their follow-ups, people who are blocked.

## Destination

- Post to Slack channel `C0345678912` (#example-brief). Do not read it as a source.
- One post per weekday, titled "Daily brief, <weekday> <month> <day>".

## Sources

Slack channels to read (the bot must be a member of each):

- `C0123456789` (#example-support)
- `C0234567891` (#example-escalations)

GitHub repositories to read (open pull requests where the reader is a requested reviewer or the author):

- `example-org/example-repo`

## Length

- At most 8 lines. A count is never an item.

## Mentions

- Mention no one. Write names as plain text.

## Retired topics

- None yet.

## Exclusions

- Skip bot messages, dependabot pull requests, and anything in a thread the reader already replied to.

## Temporary rules

- None. (Format: `until 2026-10-01: <rule>`. The agent drops a rule after its date.)

## Stop condition

- Keep running until this line says `STOP`.
