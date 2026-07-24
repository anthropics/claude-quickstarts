# A knowledge wiki for cheap, correct agentic retrieval

When agents answer questions by searching a document corpus, every question
re-pays the reading tax. This cookbook reads the corpus **once** into a
knowledge wiki — plain markdown in a Claude Managed Agents memory store —
then answers from the wiki instead of re-reading the documents. Answers cost
a fraction of a raw-document search and carry provenance on every fact.

The pattern fits any slow-changing corpus that agents query repeatedly: M&A
due diligence (the worked example), legal discovery, support over product
docs.

**What it costs to run.** The default `mini` tier is about **$35** and **an
hour** end to end. The smaller `quickstart` tier is about **$25** and **40
minutes**. Both figures are from the committed run and will move with your
model choice, corpus, and current API pricing.

**No preview access yet?** The consolidation step uses a gated research
preview (see *Access* below), but every cell in the notebook ships with the
real output from the committed run. You can read it top to bottom as a
worked case study without running anything.

## The corpus

The worked example is a real, completed take-private transaction: 42 public
SEC filings spanning 11 months, from deal announcement through closing. It
was chosen because it is public, it has narrative structure worth mapping,
and it is maximally adversarial — a price that changed mid-process,
look-alike shell entities, code names, and numbers that exist only inside a
chart.

Every document is fetched live from SEC EDGAR by accession number; nothing
is redistributed here. Two small synthetic files, marked as synthetic in
their own text, stand in for the internal documents a real deal room adds —
and one of them deliberately conflicts with the filings, so you can watch
the wiki catch it.

## What's inside

| file | what it is |
|---|---|
| `distill_documents_into_knowledge_wiki.ipynb` | the cookbook — run top to bottom |
| `build_manifest.py` | queries SEC EDGAR, writes tiered document manifests |
| `fetch_data_room.py` | downloads the filings for a tier and converts to provenance-stamped text |
| `fetch_real_deck.py` | downloads a real board deck (scanned slides from 13E-3 exhibits) into a PDF |
| `make_analyst_docx.py` | generates the marked-synthetic Word analyst note |
| `utilities.py` | session polling helpers |
| `example_data/` | the synthetic companions (analyst note, vendor CSV) |

## How it works

The pipeline builds your corpus once into a knowledge wiki, then answers
every question from the wiki instead of re-reading the documents. These are
the main steps, in order; the notebook walks through each one.

1. **Assemble your corpus.** Gather the documents your agents will query
   repeatedly — a data room, a discovery set, a support knowledge base. The
   worked example fetches a real M&amp;A data room from public filings.
2. **Normalize every file type to provenance-stamped text.** Route each format
   (PDF, Word, spreadsheets, email, slides) to plain text with a `[SOURCE: …]`
   header, and fail loudly on anything unsupported — a loader that silently
   skips a format makes the wiki look complete when it is not.
3. **Extract in parallel into one shared memory store — that store is the
   wiki.** Split the corpus into batches, run one agent session per batch
   concurrently, and have each session write structured notes into the store.
   Put the note schema on the store's attachment instructions, and give every
   source document its own single-writer path so concurrent sessions never
   overwrite each other.
4. **Resolve the wiki's open questions before consolidating.** Have a pass
   cross-read the wiki and close the questions the extraction left open,
   marking anything genuinely missing as confirmed-unresolvable rather than
   guessing.
5. **Consolidate with one steered dream.** *Dreaming* is a server-side
   consolidation pass — sleep-time compute: it reads the build sessions'
   transcripts and the store, then writes a *new*, reorganized store with
   deduplicated entities, an index that turns exploratory reads into one
   lookup, a ranked escalations file, and repaired links. It never sees the
   raw corpus, so everything true in the wiki was won at extraction.
6. **Query read-only from a fresh session per question.** Attach the
   consolidated store read-only, require provenance on every fact, and script
   the miss behavior ("not in the data room" — name the document that would be
   needed, never guess).
7. **Operate: periodically dream over real usage.** After enough real queries,
   dream over the work transcripts together with the wiki so it reorganizes
   around what people actually ask.
8. **Evaluate and tune** *(not shipped here).* Grade each deliverable against
   a fixed rubric with an evaluator, then iterate the prompt files —
   extraction rules, store schema, analyst instructions, dream steering —
   against the evaluator's failure reasons until the scores hold. This package
   does not ship a grading harness or a tuning loop; it is the natural next
   step once you have a rubric for your own corpus.

## Access

Two features must be enabled on your organization:

- **Managed Agents** — the memory stores and agent sessions the build runs on.
- **Dreaming** — a gated research preview. Without it, `POST /v1/dreams`
  returns 404 and the notebook stops at step 5; everything before that still
  runs.

Request access at <https://claude.com/form/claude-managed-agents>. Dreaming
also ships in a dedicated preview SDK build rather than the public `anthropic`
package on PyPI — the preview onboarding tells you how to install it once
your organization is enrolled.

## Quickstart

The fastest path is to let Claude drive the setup:

```bash
cd managed-agents/knowledge-wiki
claude "walk me through setting up the knowledge-wiki quickstart"
```

Or follow the steps below by hand, once you have access and the preview SDK
installed.

```bash
pip install -r requirements.txt

export EDGAR_USER_AGENT="your-name your-email"   # SEC asks for a contact

python3 build_manifest.py
python3 fetch_data_room.py --tier=mini   # 26 documents, ~0.5 MB text
python3 fetch_real_deck.py               # 6 slides of a real board deck (~1 MB)
python3 make_analyst_docx.py

jupyter lab distill_documents_into_knowledge_wiki.ipynb
```

Authentication follows the standard Anthropic credential chain — construct
the client with no arguments and it picks up whichever of an API key, an
`ant auth login` profile, or Workload Identity Federation applies to you.

## Cost and tier expectations

| tier | documents | wall-clock | approx. cost |
|---|---|---|---|
| `quickstart` | 8 | ~40 min | ~$25 |
| `mini` (default) | 26 | ~1 h | ~$35 |
| `standard` | 37 | hours | tens of $ |
| `full` | 42 | hours | more |

Every number in the notebook's saved outputs comes from the `mini` tier.
Treat all costs as order-of-magnitude: your run will vary with model choice,
corpus, and current pricing. A query against the finished wiki runs roughly
five times cheaper than the same question answered by searching the raw
documents — the notebook measures both and shows the breakeven.
