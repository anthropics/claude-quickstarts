# Setting up the knowledge-wiki quickstart

Follow these steps in order when the user asks you to set up or run
this cookbook. Confirm each step's output before moving to the next.

## 0. Check access (blocks the consolidation step)

Two features must be enabled on the user's organization:

- **Managed Agents** — memory stores and agent sessions.
- **Dreaming** — a gated research preview.

Ask the user to confirm both, and point them at
<https://claude.com/form/claude-managed-agents> if not. Without dreaming,
`POST /v1/dreams` returns 404 and the notebook fails at the consolidation
step. Everything before that still runs, so it's fine to proceed for a
partial walkthrough — just say so up front rather than letting them
discover it an hour in.

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

Dreaming is not in the public PyPI `anthropic` package — it ships in a
dedicated preview SDK build. Do not try to source that build yourself:
the preview onboarding provides it when the org is enrolled. If the user
is enrolled, ask them to install it per those instructions; confirm with:

```bash
python3 -c "import anthropic; print(hasattr(anthropic.Anthropic().beta, 'dreams'))"
```

If that prints `False`, the notebook will run up to the consolidation step
and no further.

## 2. Authentication and environment

The notebook constructs `Anthropic()` with no arguments, so it resolves
credentials through the standard chain: `ANTHROPIC_API_KEY`, then
`ANTHROPIC_AUTH_TOKEN`, then an `ant auth login` profile, then Workload
Identity Federation. Pick whichever the user's org uses:

```bash
# Either an API key…
export ANTHROPIC_API_KEY=...

# …or an interactive login, which stores a profile the SDK finds on its own.
ant auth login
```

Do not set `ANTHROPIC_API_KEY` alongside a profile — a stale exported key
silently shadows the profile, and a key set next to `ANTHROPIC_AUTH_TOKEN`
makes the SDK send both headers, which the API rejects. `ant auth status`
shows which credential source won.

One more variable is required regardless:

```bash
export EDGAR_USER_AGENT="your-name your-email"  # SEC policy
```

If `EDGAR_USER_AGENT` is missing, EDGAR requests will be refused.

## 3. Pick a tier and set the cost expectation

Tell the user what they're about to spend before fetching anything.

| Tier | Docs | Wall-clock | Approx. cost | Use when |
|---|---|---|---|---|
| `quickstart` | 8 | ~40 min | ~$25 | first look, lunch break |
| `mini` (default) | 26 | ~1 h | ~$35 | full walkthrough |
| `standard` | 37 | hours | tens of $ | study-scale reproduction |
| `full` | 42 | hours | more | the ambitious |

Costs are order-of-magnitude estimates from the committed run on
`claude-sonnet-5`; the user's run will vary with model choice and API
pricing at the time.

## 4. Fetch the corpus

Run in this order (network required):

```bash
python3 build_manifest.py
python3 fetch_data_room.py --tier=mini    # or the tier chosen in step 3
python3 fetch_real_deck.py                # 6 slides of a real board deck (~1 MB)
python3 make_analyst_docx.py
```

Expected after this: `data_room/docs/` contains one `.txt` file per
document in the chosen tier — 8 files for `quickstart`, 26 for `mini`.

## 5. Open the notebook

```bash
jupyter lab distill_documents_into_knowledge_wiki.ipynb
```

Recommend the user reads `README.md` §"How it works" before running cells
— the pipeline has a few non-obvious steps (the resolve pass, the
read-only analyst attach, the usage-driven re-dream).

## Gotchas to warn about

- The dream step can take 20–60 minutes; tell the user to kick it off
  and check back rather than watching it.
- Model choice: the default is `claude-sonnet-5` everywhere. The setup
  cell notes that an Opus-tier dream model (`claude-opus-5`) is a
  reasonable A/B against the default.
- If the user hits an error on `client.beta.memory_stores.create`, their
  org likely doesn't have Managed Agents enabled — see step 0.
