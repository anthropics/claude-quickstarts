# Knowledge graphs for cheap, correct agentic retrieval — customer preview

When agents answer questions by searching a document corpus, every question
re-pays the reading tax. This cookbook builds the corpus **once** into a
knowledge graph (Claude Managed Agents memory + the dreaming API), then
answers from the graph — at a fraction of the per-question cost, with
provenance on every fact. The pattern fits any slow-changing corpus agents
query repeatedly — M&A due diligence (the worked example), legal discovery,
support over product docs.

The worked example is a real M&A data room (public SEC filings from a
completed take-private), chosen because it is maximally adversarial:
mid-process price changes, shell entities, code names, chart-only numbers.

**Status: preview.** We're sharing this with a small group for feedback
before publishing. Please don't redistribute yet; do tell us everything
that's unclear, broken, or missing for your own document rooms.

## What's inside

| file | what it is |
|---|---|
| `distill_documents_into_knowledge_graph.ipynb` | the cookbook — run top to bottom |
| `build_manifest.py` | queries SEC EDGAR, writes tiered document manifests (mini/standard/full) |
| `fetch_data_room.py` | downloads the filings for a tier and converts to provenance-stamped text |
| `fetch_real_deck.py` | downloads a real board deck (scanned slides from 13E-3 exhibits) into a PDF |
| `make_analyst_docx.py` | generates the marked-synthetic Word analyst note |
| `utilities.py` | session streaming helpers |
| `example_data/` | the synthetic companions (analyst note, vendor CSV) |

The example corpus is the 2024 take-private of Squarespace, Inc. by Permira — every
fetched document is a public SEC filing, referenced by accession number and
fetched from the source (nothing redistributed). Two small synthetic files
(clearly marked in their own text) stand in for the internal documents a
real deal room adds.

## How it works

The pipeline builds your corpus once into a knowledge wiki, then answers every
question from the wiki instead of re-reading the documents. These are the main
steps, in order; the notebook walks through each one.

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
5. **Consolidate with one steered dream.** The dream reads the extraction
   sessions' transcripts and the store and writes a *new*, reorganized store:
   deduplicated entities, an index meant to turn exploratory reads into one
   lookup, a ranked escalations file, and repaired links. It never sees the
   raw corpus, so everything true in the wiki was won at extraction.
6. **Query read-only from a fresh session per question.** Attach the
   consolidated store read-only, require provenance on every fact, and script
   the miss behavior ("not in the data room" — name the document that would be
   needed, never guess).
7. **Operate: periodically dream over real usage.** After enough real queries,
   dream over the work transcripts together with the wiki so it reorganizes
   around what people actually ask; in the study behind this cookbook, one
   such usage dream lowered the reading cost of later hard questions.
8. **Evaluate and tune** *(not part of this preview package).* The full
   process grades each deliverable against a fixed rubric with an evaluator,
   then iterates the prompt files — extraction rules, store schema, analyst
   instructions, dream steering — against the evaluator's failure reasons
   until the scores hold. This package does not yet ship a grading harness or
   a tuning loop; it is the natural next step once you have a rubric for your
   own corpus.

## Lessons from the studies

Each lesson is tagged by where it comes from. **Deal-room study** is the
13-arm ablation on this transaction described under "The numbers behind the
design." **Legal study** is a companion study that applied the same method to a
legal-tasks benchmark. **Both** means both studies bear it out.

- **(deal-room study)** Truth is won at extraction. The dream reorganizes
  what extraction learned but cannot verify a claim against the source
  documents, so extraction and resolution are where correctness is made.
- **(deal-room study)** Resolve gaps before the dream, not after — a resolver
  pass ahead of the dream was the single best architectural change tested.
- **(deal-room study)** Steer the dream. A short steering instruction telling
  the dream what the analysts will look for was the highest-leverage prompt in
  the study.
- **(deal-room study)** Dream with the wiki as its sole source, and query with
  the wiki as the sole source. Both "let it also see the documents"
  configurations backfired (see *Pitfalls and gotchas*).
- **(both)** Coordination rules matter as much as writing rules. Parallel
  writers clobber shared files; give each source its own single-writer path.
- **(legal study)** The wiki pays off where questions are hard to answer from
  raw text — answers that no single passage states and that span several
  documents. On sources that are already well-organized, one-document lookups
  dominate and the wiki is pure overhead; the pattern is not always a win, and
  the wiki can grow larger than the source it maps.
- **(legal study)** A good map is opinionated. Spend compute deciding what to
  join and at what granularity of entity, shaped for the questions the wiki
  will later be asked; prompting is what defines the entities the wiki
  pre-joins.
- **(legal study)** When the default schema is too coarse for a task, *add* a
  purpose-built page — for example a per-document inventory of every defined
  term, amount, and date with its source — so the facts the question needs
  arrive pre-joined, without re-keying the entity schema.
- **(legal study)** Dreaming buys organization and lower per-query cost more
  reliably than a quality jump — most likely because the analyst needs fewer
  reads, though the read count itself was not directly measured. Small quality
  gaps between a dreamed and an undreamed wiki are within run-to-run noise
  until replicated.
- **(both)** Replicate before believing. In both studies, identical
  configurations spread by several points of rubric score (the task's list of
  graded criteria) from run to run; a single-run delta is noise until it
  repeats.
- **(deal-room study)** Treat absence claims as hypotheses. Record "not in
  this document," never a global "not disclosed" — a false absence filed into
  the wiki is nearly impossible to dislodge.
- **(both)** For report-scale outputs, tell the agent that its reply is the
  deliverable; otherwise an agent with file tools writes the report to a file
  and hands you a summary.

## Pitfalls and gotchas

- **Access and the SDK.** Dreaming is a gated research preview: if your
  organization is not enrolled, `/v1/dreams` returns 404 even with the beta
  header, and the Managed Agents beta must be enabled too. The public
  `anthropic` package does not expose `client.beta.dreams` yet — install the
  research-preview wheel and verify its checksum first (see *Quickstart*).
- **Silent loader drops.** The costliest ingestion failure is the quiet one: a
  loader that handles only the formats you anticipated drops the rest and the
  wiki still looks complete. Make unhandled formats raise rather than skip, and
  treat a transcription that hits a token limit as a truncation error, not a
  success.
- **False global-absence claims.** "Not disclosed" filed once becomes fact for
  every later query. Scope every absence to the document it came from.
- **Concurrent writers.** Sessions appending to a shared file or table invite
  one session's wholesale rewrite to destroy another's work — it happened in
  both studies. Single-writer paths per source are the fix.
- **Two tempting configurations that backfired.** *Corpus-aware dreaming*
  (telling the dream the analysts will also have the raw documents) gutted
  the wiki — the dream took document access as license not to write things
  down. *Query-time document fallback* (letting the analyst read raw
  documents when the wiki is thin) cost quality and a large share of extra
  tokens on the best wiki. Document access is insurance against a bad wiki,
  not an enhancement of a good one.
- **Query-time writes.** An analyst writing back into the wiki during a query
  bypasses every quality gate; one analyst's plausible inference becomes the
  next analyst's fact. Analyst writes should propose; a later dream disposes.
- **Run-to-run noise.** Re-run before you conclude anything from a
  one-or-two-point difference.
- **Store lifecycle.** A dream never mutates its input — it writes a *new*
  store and the input remains a separate store you own. Point the analyst at
  the output store, and export every store you may want before any cleanup
  step runs, since a deleted input cannot be recovered from the dream.
- **Operational timeouts and retries.** Give the client a generous timeout
  and a retry policy so a transient overloaded error costs a back-off rather
  than a run; sessions can be rescheduled server-side mid-turn and still
  finish, so keep polling; and respect source-site rate limits and User-Agent
  requirements when fetching a corpus.

## Quickstart

The fastest path is to let Claude drive the setup:

```bash
cd managed-agents/knowledge-wiki
claude "walk me through setting up the knowledge-wiki quickstart"
```

Or follow the steps below by hand.

**Access first:** dreaming is a gated research preview — request access for
your organization at https://claude.com/form/claude-managed-agents, or
`/v1/dreams` will 404. The Managed Agents beta must be enabled too.

```bash
# dreaming ships in a dedicated research-preview SDK build (public PyPI
# anthropic does not expose client.beta.dreams yet). Verify the wheel's
# digest before installing (expected sha256 for the tested build:
# b92fe0480cd15f52830b572343e6e4b0be7a9c4eea058b64c9dfca958c4af539):
curl -sL -o anthropic-0.100.0-py3-none-any.whl "https://pkg.stainless.com/l/anthropic-python/5f5a2aac-6775-4d5f-bfac-fd747f5c661c"
shasum -a 256 anthropic-0.100.0-py3-none-any.whl   # compare before installing
pip install anthropic-0.100.0-py3-none-any.whl httpx python-docx pillow python-dotenv jupyter
export ANTHROPIC_API_KEY=...            # key from an org with both features enabled
export EDGAR_USER_AGENT="your-name your-email"   # SEC asks for a contact

python3 build_manifest.py
python3 fetch_data_room.py --tier=mini   # 26 real documents, ~0.5 MB text
python3 fetch_real_deck.py               # 6 slides of a real board deck (~1 MB)
python3 make_analyst_docx.py

jupyter lab distill_documents_into_knowledge_graph.ipynb
```

## Cost expectations

- `mini` tier end-to-end: about **$35** on the committed run (extraction sessions + one dream + demo queries) — treat this as an order-of-magnitude estimate; your run will vary with model choice and corpus
- `standard` tier (adds merger proxy, tender docs, 10-Qs): tens of dollars — study scale
- Queries against the finished graph: ~70k tokens each at full scale, ~5x cheaper than raw-document search

## The numbers behind the design

This pipeline is the winning configuration from a 13-arm ablation study on
this same transaction: 96.2% on a 21-question judged battery vs 85.7% for
agentic search over raw documents, at one-fifth the per-question cost. The
notebook's callout boxes carry the design rules the ablations produced —
including the tempting configurations that backfired (corpus-aware dreaming,
query-time document fallback).

## Feedback we want

1. Did the notebook run end-to-end for you? Where did it stall?
2. Are the cost tiers right for evaluation?
3. What do YOUR document rooms contain that this pattern doesn't cover
   (formats, scale, access control, update cadence)?
4. Would you run build+dream on a schedule as documents arrive?
