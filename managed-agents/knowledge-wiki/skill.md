# Setting up the knowledge-wiki quickstart

Follow these steps in order when the user asks you to set up or run
this cookbook. Confirm each step's output before moving to the next.

## 0. Check access (blocks everything else)

Dreaming is a gated research preview. Ask the user to confirm their
organization has both **Managed Agents** and **dreaming** enabled
(request form: <https://claude.com/form/claude-managed-agents>). If
not, `POST /v1/dreams` returns 404 and the notebook will fail at the
consolidation step — everything before that still runs, so it's fine
to proceed for a partial walkthrough, but say so up front.

## 1. Install the research-preview SDK

The public PyPI `anthropic` package does **not** expose
`client.beta.dreams`. Install the preview wheel and verify its digest:

```bash
curl -sL -o anthropic-0.100.0-py3-none-any.whl \
  "https://pkg.stainless.com/l/anthropic-python/5f5a2aac-6775-4d5f-bfac-fd747f5c661c"
shasum -a 256 anthropic-0.100.0-py3-none-any.whl
# expected: b92fe0480cd15f52830b572343e6e4b0be7a9c4eea058b64c9dfca958c4af539
pip install anthropic-0.100.0-py3-none-any.whl
pip install -r requirements.txt
```

Confirm with `python3 -c "import anthropic; print(anthropic.__version__)"`.

## 2. Environment variables

```bash
export ANTHROPIC_API_KEY=...                    # from an org with both features enabled
export EDGAR_USER_AGENT="your-name your-email"  # SEC policy — required for the fetch step
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

Confirm `data_room/docs/` now contains one `.txt` file per document.

## 5. Open the notebook

```bash
jupyter lab distill_documents_into_knowledge_graph.ipynb
```

Recommend the user reads `README.md` §"How it works" and §"Pitfalls
and gotchas" before running cells — the pipeline has a few
non-obvious steps (the resolve pass, the read-only analyst attach,
the usage-driven re-dream).

## Gotchas to warn about

- **Don't run `_build_notebook.py`** — it regenerates the notebook
  and wipes the saved outputs.
- The dream step can take 20–60 minutes; tell the user to kick it off
  and check back rather than watching it.
- Model choice: the default is `claude-sonnet-5` everywhere. The setup
  cell explains the mixed Fable/Opus configuration for a cheaper
  build; `claude-opus-5` is a good dream-model alternative to A/B.
- If the user hits a 400 on `client.beta.memory_stores.create`, their
  org likely doesn't have Managed Agents enabled — see step 0.
