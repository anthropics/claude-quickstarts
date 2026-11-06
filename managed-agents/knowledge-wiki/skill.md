# Setting up the knowledge-wiki quickstart

Follow these steps in order when the user asks you to set up or run
this quickstart. Confirm each step's output before moving to the next.

## 0. Check access

Everything runs on **Managed Agents** (beta) — memory stores, agents, sessions
and dynamic workflows — which is enabled by default for API organizations; the
SDK sends the beta headers itself. If `client.beta.memory_stores.create` or
`client.beta.agents.create` returns a permission error later, the user should ask their organization's
admin whether it was turned off or the key restricted. Python 3.11 or later is
required.

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt` pins the `anthropic` Python SDK at `>=2.0.0,<3`. If the user already
had an older version in the environment, confirm the upgrade took:

```bash
python3 -c "import anthropic; print(anthropic.__version__)"
```

If that prints a version below 2.0, run `pip install -U "anthropic>=2.0.0,<3"`.

## 2. Authentication and environment

The notebook constructs `Anthropic()` with no credential arguments, so it resolves
credentials through the standard chain and uses the first one it finds:
`ANTHROPIC_API_KEY`, then `ANTHROPIC_AUTH_TOKEN`, then the profile
`ANTHROPIC_PROFILE` names, then Workload Identity Federation, then the
active `ant auth login` profile. Pick whichever the user's org uses:

```bash
# Either an API key…
export ANTHROPIC_API_KEY=...

# …or an interactive login with the ant CLI, version 2.0 or later (ant --version prints it),
# which stores a profile the SDK finds on its own.
ant auth login
```

Do not set `ANTHROPIC_API_KEY` alongside a profile — a stale exported key
silently shadows the profile. A key set next to `ANTHROPIC_AUTH_TOKEN` wins
too (the SDK logs a warning and uses the key). `ant auth status` shows
which credential source won.

One more variable is required regardless:

```bash
export EDGAR_USER_AGENT="your-name your-email"  # SEC policy
```

If `EDGAR_USER_AGENT` is missing, the scripts send a placeholder contact,
which SEC may throttle or refuse.

## 3. Pick a tier and set the cost expectation

Before fetching, tell the user what the `core` run cost. For other tiers, say no
figure was recorded, and that the notebook prints an estimate before the build
and stops if it is over budget.

| Tier | Docs | Use when |
|---|---|---|
| `core` (default) | 8 filings (annual reports, proxies, a 10-Q, the deal's 8-Ks), 2.8 MB text | the recorded run, 23 min and ≈ $16 at list price on the default models: the demo questions and the measured comparison are written for it |
| `quickstart` | 8 short deal-window filings | a first look at the mechanics on short filings |
| `mini` | 26: the smaller deal-window filings | more documents, less text than core |
| `standard` | 37 | the larger room |
| `full` | all 42 deal-window filings | every filing in the deal window; it leaves out core's FY2022 annual report |

Only `core` was recorded (Claude Haiku 5.5 for the agents that read, Claude
Sonnet 5.5 for the lead agent and the raw-documents baseline, thinking at the
platform's default); the user's run will vary with model choice and API pricing
at the time. For any tier the notebook prints its own list-price estimate for
the chosen corpus before the build (the cell that creates the agents) and stops
if it is over `BUDGET_USD`; the build session also carries that budget as a cap
(the platform stops new work there, to within one model request per working
agent). Empty `data_room/docs` before fetching a different tier: the build
reads whatever is in the folder, and the fetch script stops if it finds
another tier's files there.

## 4. Fetch the corpus

Run in this order (network required):

```bash
python3 fetch_data_room.py --tier=core    # or the tier chosen in step 3
python3 fetch_real_deck.py                # optional: 6 slides of a real board deck (~1 MB)
python3 make_analyst_docx.py              # optional: regenerates the Word note that ships in example_data/
```

All five manifests ship with the folder, so nothing else is needed before the
fetch. `build_manifest.py` is an optional refresh from EDGAR: it rewrites the
quickstart, mini, standard and full manifests (never core), so run it before
`fetch_data_room.py` if at all, not after. Expected after this:
`data_room/docs/` contains one `.txt` file per document in the chosen tier
— 8 files for `core` (about 2.8 MB) or `quickstart`, 26 for `mini` — and
the notebook's normalize step adds the two synthetic files, plus the deck if it was
fetched.

## 5. Open the notebook

```bash
jupyter lab distill_documents_into_knowledge_wiki.ipynb
```

Recommend the user reads `README.md` §"How it works" before running cells
— the pipeline has a few non-obvious steps (the schema seeded into the
store, one message stating the goal and naming the agents, the checks on what ran, the
read-only analyst attach).

## Gotchas to warn about

- The build is one long cell (Run the build): it prints each phase and thread as it
  starts; tell the user to kick it off and check back rather than watching
  it. If the kernel is interrupted, the cell's `finally` asks the agent to
  stop the run, waits for it to end, then saves the records and archives the
  session; the wiki store keeps what was written. If it prints that a
  session was not archived, archive it by hand: an open run keeps spending
  until it reaches the budget.
- The message states the goal and names the agents, and the lead agent writes
  the workflow; after the run the notebook asks the lead agent to print the
  workflow it wrote and sets that beside the platform's records (Check what ran). The reprint is the
  lead agent's account; if it and the records disagree, the records win.
- Model choice: by default the agents that read (extractors, resolver,
  analyzers, organizer, analysts) run on `claude-haiku-5-5` and the lead agent
  and the raw-documents baseline on `claude-sonnet-5-5`. `COOKBOOK_MODEL` sets
  every stage; `COOKBOOK_BUILD_MODEL` (extractors, resolver),
  `COOKBOOK_CONSOLIDATE_MODEL` (analyzers, organizer), `COOKBOOK_QUERY_MODEL`
  (analysts), `COOKBOOK_LEAD_MODEL` (the lead agent) and
  `COOKBOOK_BASELINE_MODEL` (the baseline in "What it costs") override one
  stage each. The extractors and analyzers read the whole corpus and are most
  of the cost.
- Run records go under the system's temporary directory (`/tmp/knowledge_wiki-<uid>/runs/`,
  readable only by the user; or `COOKBOOK_RECORDS_DIR`), never into the repository: they
  hold the documents' contents.
- If the user hits a permission error on `client.beta.memory_stores.create`,
  see step 0.
