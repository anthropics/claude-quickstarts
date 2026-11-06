# Knowledge-wiki quickstart — agent guidance

This directory is a Managed Agents quickstart: it builds a real M&A data
room into a knowledge wiki (a versioned memory store) with one dynamic
workflow run, and queries it. The runnable artifact is
`distill_documents_into_knowledge_wiki.ipynb`; `prompts/` holds the
consolidation agents' prompts, the lead agent's prompt and the baseline
analyst's prompt, `utilities.py` the notebook's functions; everything else exists to set that notebook
up.

When a user asks you to walk them through setting this quickstart up,
read `skill.md` in this directory and follow it step by step. Do not
improvise the setup — the SDK version, the SEC user-agent, and the fetch
order all matter.

The notebook is the source of truth and is edited directly. If you are editing
this folder to commit a change, leave the notebook's saved outputs alone: they
record a real run, so don't regenerate them or hand-edit them to match later
source changes. A user running the notebook for themselves runs it as normal.
