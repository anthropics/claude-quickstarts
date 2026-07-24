# Managed Agents quickstarts

Projects built on [Claude Managed Agents](https://platform.claude.com/docs/en/managed-agents/overview): agents Anthropic runs for you, with server-side sessions, sandboxed tools, and an event stream your app consumes. Each quickstart is a complete, runnable app that pairs Managed Agents with a real product surface.

## Quickstarts

- **[chat-sdk/](chat-sdk/)** puts a research analyst in a
  browser chat with Vercel's Chat SDK. Each conversation is one
  persistent session (the conversation ID is the session ID); the
  analyst researches with web search and streams the final brief
  token by token over the same held response (session `event_deltas`
  previews) while a live feed shows the tool calls. No third-party
  credentials, and the same handler moves to Slack, Teams, Discord,
  Telegram, or WhatsApp by swapping the adapter.

- **[knowledge-wiki/](knowledge-wiki/)** distills a document corpus
  once into a knowledge wiki (a versioned memory store) using
  parallel extraction sessions, a resolve pass, and a steered
  consolidation dream (research-preview `client.beta.dreams`), then
  answers repeated analyst questions from the wiki instead of
  re-reading documents — with `[source | as-of]` provenance on every
  fact and a fraction of the per-question token cost. The worked
  example is a real M&A data room: the 2024 Squarespace / Permira
  take-private, fetched from public SEC EDGAR filings.
