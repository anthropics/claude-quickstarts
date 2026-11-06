# Knowledge wiki with a dynamic workflow

*A knowledge wiki for agentic retrieval that keeps its sources and its conflicts. For developers whose agents answer repeated questions over a slow-changing set of documents. A tutorial: run it top to bottom once on the worked example, then point it at your own corpus.*

![How it works: build the wiki, then ask it read-only.](assets/wiki_how_it_works.png)

This quickstart reads a corpus **once** into a knowledge wiki, plain markdown in a Claude Managed Agents memory store, then answers from the wiki. Provenance sits on every fact, conflicts between documents stay conflicts, and superseded figures stay superseded.

When agents search documents, every question starts from scratch, and the facts between documents aren't in any single passage. With the wiki, a small model answers within a point of a larger model that searches the raw documents with no wiki, at about 1/15 of the price per answer, and about 3 points better than it does searching the documents itself. The wiki costs about $19 to build once on the benchmark's average (the run recorded in the notebook cost about $16) and, on the benchmark's figures, pays for itself after about 240 questions against that larger model. The notebook measures these costs on your own run.

The build is one Managed Agents session running one **dynamic workflow**, described in one message.

The pattern fits any slow-changing corpus that agents query repeatedly: M&A due diligence (the worked example), legal discovery, support over product docs.

**Just reading?** Every cell in the notebook ships with the real output from the recorded run. You can read it top to bottom as a worked case study without running anything.

## The corpus

The worked example is a real, completed take-private deal, using public SEC filings fetched live from EDGAR. The filings themselves are not included. Two small files, marked as synthetic, stand in for internal documents; one gives an EBITDA estimate on a different basis from the company's reported figure, so you can watch the wiki keep the two apart.

To build from your own documents, set `COOKBOOK_DOCS` to a folder of provenance-stamped `.txt` files; `kw.normalize_any` converts PDFs, Word, Excel, PowerPoint and email to text. Office files from a counterparty are untrusted input: convert them in a container or on a machine you don't mind exposing to a malformed file, or convert them to text first with a tool you trust.

## What's inside

| file | what it is |
| --- | --- |
| `distill_documents_into_knowledge_wiki.ipynb` | the notebook: run top to bottom |
| `prompts/` | the consolidation method (`analyzer_system.md`, `organizer_system.md`, each ending in an instructions block the notebook fills when it creates the agents), the lead agent's prompt (`lead_system.md`, with the run's standing rules and the report's shape) and the baseline analyst's prompt (`baseline_system.md`) |
| `utilities.py` | the notebook's functions: uploads, session exports, following and stopping a workflow run, checks on what ran, memory-store copies and exports, pricing |
| `build_manifest.py` | queries SEC EDGAR, writes the size-tiered document manifests (`manifest_core.json`, the default tier, is a fixed list that ships here) |
| `fetch_data_room.py` | downloads the filings for a tier and converts to provenance-stamped text |
| `fetch_real_deck.py` | downloads a real board deck (scanned slides from 13E-3 exhibits) into a PDF |
| `make_analyst_docx.py` | generates the marked-synthetic Word analyst note |
| `example_data/` | the synthetic companions (analyst note, vendor CSV) |
| `requirements.txt` | the Python packages the notebook and scripts need |

## How it works

1. **Build the wiki.** A workflow run gives each batch of documents to an extractor. A resolver then works the top gaps the extractors flagged, and the consolidation follows: analyzers check what was filed against the documents, and an organizer tidies the whole wiki.
2. **Ask it.** Your agents mount the wiki read-only, one session per question, and cite every fact.

The notebook also checks what ran against the platform's records, measures what a question costs with the wiki and without it, and points to the dreaming cookbook for keeping the wiki current from your agents' transcripts.

## Access

Everything runs on **Managed Agents** (beta), which provides the memory stores, agents, sessions and dynamic workflows and is enabled by default for API organizations; the SDK sends the beta headers. If `client.beta.agents.create` returns a permission error, ask your organization's admin. The notebook needs Python 3.11 or later and the public `anthropic` Python SDK, version 2.0 or later, which `requirements.txt` installs.

## Quickstart

The fastest path is to let Claude drive the setup:

```bash
cd managed-agents/knowledge-wiki
claude "walk me through setting up the knowledge-wiki quickstart"
```

Or follow the steps by hand:

```bash
pip install -r requirements.txt

export EDGAR_USER_AGENT="your-name your-email"   # SEC asks for a contact

python3 fetch_data_room.py --tier=core   # 8 filings, 2.8 MB text: the recorded run (or --tier=quickstart)
python3 fetch_real_deck.py               # optional: 6 slides of a real board deck (~1 MB) for the normalize step
python3 make_analyst_docx.py             # optional: regenerates example_data/analyst_note.docx, which ships here
# All five manifests ship with the folder. build_manifest.py is an optional refresh from EDGAR that
# rewrites the quickstart, mini, standard and full manifests (never core); run it before fetching, not after.

jupyter lab distill_documents_into_knowledge_wiki.ipynb
```

Authentication follows the standard Anthropic credential chain. Construct the client with no credential arguments and it picks up whichever of `ANTHROPIC_API_KEY` (in the environment or a `.env` file here), an `ant auth login` profile (the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/authentication), version 2.0 or later), or Workload Identity Federation applies to you.

Run records go to a new folder under your system's temporary directory (`/tmp/knowledge_wiki-<uid>/runs/` on Linux), readable only by you, which most systems clear when the machine restarts. Set `COOKBOOK_RECORDS_DIR` to keep them somewhere lasting.

## Cost and tier expectations

- The recorded run on the default `core` tier (8 filings, 2.8 MB of text) took 23 minutes and cost about $16 at list price.
- It used the default models: Claude Haiku 5.5 for the agents that read, Claude Sonnet 5.5 for the lead agent and the raw-documents baseline.
- Only `core` was recorded. For any other tier or your own folder, the notebook prints a list-price estimate before it builds and stops if that is over your budget. Your run will vary with model, corpus and current pricing.

The other tiers:

- `quickstart`: 8 short filings around the deal.
- `mini`: 26 filings, less text than `core`.
- `standard`: 37 filings.
- `full`: all 42 from the deal window, which leaves out `core`'s FY2022 annual report.

Empty `data_room/docs` before you fetch a different tier: the build reads whatever is in the folder, and the fetch script stops if it finds another tier's files there.

- **File size:** a file in the store is capped at 100 KB. On a larger corpus the main company's entity page and the red-flags file (`escalations.md`) reach that sooner and have to be split into linked files.
- **Shared pages:** agents write straight onto shared pages, so they sometimes overwrite each other: about 5% of the lines filed to the busiest entity page lose content. We accept that because a shared page brings figures from different documents together, where agents can flag disagreements.
