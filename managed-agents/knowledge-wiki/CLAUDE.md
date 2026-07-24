# Knowledge-wiki cookbook — agent guidance

This directory is a Managed Agents cookbook: it builds a real M&A data
room into a knowledge wiki (a versioned memory store) and queries it.
The runnable artifact is `distill_documents_into_knowledge_graph.ipynb`;
everything else exists to set that notebook up.

When a user asks you to walk them through setting this quickstart up,
read `skill.md` in this directory and follow it step by step. Do not
improvise the setup — the SDK build, the SEC user-agent, and the fetch
order all matter.

Do not run `_build_notebook.py`. It regenerates the notebook and would
overwrite the committed run's saved outputs.
