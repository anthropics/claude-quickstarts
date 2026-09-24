# Setup tips and tricks: assistant-ui × Claude Managed Agents

Things that aren't obvious from the docs and tend to cost debugging time. If you're Claude driving setup for a user, walk the **Setup checklist** and use the rest for reference when something looks off.

---

## Mental model

### The session is the state
There is no database, no message store, no in-memory transcript. The sidebar is `sessions.list()`, an old chat is `sessions.events.list()` replayed, and the live chat is the same reducer folding the tail. If you catch yourself adding a table "just to remember the conversations," you're re-implementing what the session already is. Restart the dev server mid-conversation and reload: the transcript comes back, because it never lived here.

### One pure function joins the two products
`lib/managed-agents/reducer.ts` maps events to assistant-ui messages and knows nothing about React or fetch. Every rendering question ("why is the gate not showing", "why did the text duplicate") is answered by which branch of `applyEvent` handled which event. The unit test (`npm test`) folds the golden turn from the wire protocol; when the mapping changes, change the test first.

### Stream first, then send
A Managed Agents stream only delivers events emitted after it attaches. The browser opens `/api/sessions/[id]/stream` before it posts a message, and keeps that one tail open across turns and across the pause while an approval waits. `session-controller.ts` enforces this order; don't move the send in front of the attach.

### The approval gate is a stopped session, not a UI state
When bash needs approval the session emits `session.status_idle` with `stop_reason: { type: "requires_action", event_ids: [...] }` and *waits*. The buttons render because the reducer stamped `approval: { id }` onto the tool part from that event, not because a component set a flag. That's why reloading with the gate open works: the pending request is in the event log.

### Never trust a conversation ID
The flip side of "the browser sends a session ID" is that the browser sends a session ID. It becomes an API path parameter, and the server's Anthropic credentials can see every session in the workspace, including other agents' sessions. `ownedSession()` in `lib/owned-session.ts` is the gate every session-touching route goes through: the ID must look like an ID, resolve, belong to this quickstart's agent, carry the metadata tag, and not be archived. The file download route adds a second check: the file must belong to *that* session. If you fork this, keep both checks in the path of anything that takes an ID from a client.

---

## Gotchas

### Token previews are gated per org
`event_deltas` streaming is part of the 2026-07-01 Managed Agents update and rolls out per organization. Without the gate, the parameter is silently ignored: no `event_start` arrives and replies land whole. That is not a bug; the same code path handles it. Confirm which behavior you have before "fixing" streaming.

### `agent.thinking` has no text
It's a start-of-work signal, not the reasoning content. The reducer renders an empty reasoning part on purpose. Don't wire a component that displays `thinking.text`; there isn't one.

### Batch confirmations, and the id is the *event* id
`tool_use_id` in `user.tool_confirmation` is the `sevt_...` id of the `agent.tool_use` event, taken from `stop_reason.event_ids`. If several tools block at once, answer them in **one** `events.send`; the controller debounces clicks into a batch for exactly this reason, because a second racing send can be rejected with `400 no non-archived thread is waiting on tool_use_id`. If you hit that 400, refetch the latest `requires_action` and answer only what's still listed.

### Custom tools take results, not confirmations
`show_chart` is answered with `user.custom_tool_result` keyed by `custom_tool_use_id`. Sending `user.tool_confirmation` for a custom tool id is a 400. The controller answers `show_chart` automatically the moment it renders; a tab closed mid-turn just means the answer goes out when the session is next opened.

### A long-parked approval can resume into a cold sandbox
The gate waits forever, but the sandbox underneath doesn't stay hot forever. Leave a `bash` approval sitting for several minutes and the first execution after Allow can come back as `Tool execution was interrupted by a crash. Please retry.` This is expected: the tool result carries the error, the agent says "let me retry that" and re-issues the command (a second, fresh gate), and the warm sandbox runs it. The UI renders the failed attempt in red above the retry, which is the honest transcript. Don't paper over it; do point demo audiences at it as the recovery path working.

### Stop abandons the response, not the turn
Closing the tab or navigating away only drops the SSE response; the agent keeps working server-side and the reply is waiting in history when you come back. The composer's stop button sends a real `user.interrupt`. Don't "fix" a slow turn by resending the message; you'll queue a duplicate.

### Uploads mount under `/mnt/session/uploads/`
`mount_path` on `sessions.resources.add` is the absolute in-container path (its default is `/mnt/session/uploads/<file_id>`). The composer mounts an attachment at `/mnt/session/uploads/<file_id>/<name>` — the file id keeps repeat uploads of the same filename from colliding, the basename keeps it readable — and the message tells the agent that exact path; the mounted path and the announced path must always be the same string. Deliverables belong in `/mnt/session/outputs/` to show up as download chips.

### `files.list({ scope_id })` may not be enabled everywhere
Listing a session's produced files by `scope_id` is newer than the rest of the API. `lib/managed-agents/session-files.ts` catches the failure and still returns the mounted uploads, and downloads of anything not in the session's file set stay refused. If download chips never appear after the agent writes a file, this is the first thing to check.

### Two servers on port 3000 split traffic silently
`next dev` will happily start next to a leftover server. If clicks seem to do nothing or the SSE tail never connects, `lsof -ti:3000 -sTCP:LISTEN` should print exactly one PID. Kill strays with `lsof -ti:3000 -sTCP:LISTEN | xargs kill` (the `-sTCP:LISTEN` matters; without it lsof also matches unrelated processes).

### Two known-minor edges (converge on their own)
Both were left deliberately after review, since fixing them costs more complexity than they're worth:
- If a chat's very first history fetch fails while the live tail stays healthy, the transcript can sit empty behind an error banner until the next send (or a tail hiccup) retries the load. Sending a message always re-awaits the load first, so it self-heals.
- Two custom-tool calls parked at once whose result POSTs *both* fail can retry a beat out of step (one shared backoff timer). Each success or failure re-sweeps the pending set, so they converge; a hard stall needs one of them to silently exhaust all its attempts first.

### The dev server binds localhost only
`npm run dev` passes `--hostname localhost`. There's no auth in this demo, so don't tunnel it to the public internet without adding real authentication and per-user session scoping (put a user id in session `metadata` and check it in `ownedSession()`).

---

## Setup checklist

1. **Node 22 or later**, and an Anthropic account with Managed Agents access. `node --version`.
2. **Install**: `npm install`. The `.npmrc` pins the public npm registry so a machine-wide mirror config doesn't get in the way of `@assistant-ui`.
3. **Auth**: run `ant auth login` once (the SDK and the CLI share that login), or export `ANTHROPIC_API_KEY` and also put it in `.env` (`cp .env.example .env`) for the app. `ant apply` does not read `.env`.
4. **Provision**: `ant apply agents environments` (the `ant` CLI, 1.30 or later). It creates one environment (cloud, pandas preinstalled) and one agent (opus, spreadsheet-analyst prompt, bash set to `always_ask`, the `show_chart` custom tool) and writes their IDs to `claude-lock.json`, which the app reads. Nothing to paste.
5. **Run**: `npm run dev`, open http://localhost:3000.
6. **Drive the golden turn**: click *Summarize the attached spreadsheet*... first drag `sample_data/sales.csv` onto the composer, then send. Expect a file card, then an Allow/Deny gate on the first `bash` command. Deny it once with a note to watch the agent adapt, then Allow the next.
7. **Try the chart**: *"Chart revenue by month."* Expect a `show_chart` card to render inline.
8. **Confirm persistence**: reload the page mid-conversation. History, the settled gates, and the sidebar title all come back.

## Debugging a failed run

| Symptom | Likely cause |
|---|---|
| `No agent ID` on the first request | `ant apply agents environments` hasn't run in this directory, so there is no `claude-lock.json` beside `package.json` (or it stopped partway: run it again and read its output). |
| First call 404s | The org has no Managed Agents access, or the agent in `claude-lock.json` was archived: `ant apply` will say so and `--force` creates a replacement. |
| Sidebar empty though sessions exist | They aren't tagged `metadata.quickstart="assistant-ui"` (made by another quickstart or the Console). This is intended; `ownedSession()` filters them. |
| Message sent, nothing streams, no error | Streaming gate off: replies still arrive, whole. If nothing ever arrives, check the tail: DevTools → Network → `stream` should be a pending `text/event-stream`. |
| Approve does nothing | Two servers on the port, or the confirmation raced. Check `lsof -ti:3000 -sTCP:LISTEN`; look for a 400 on `/confirm` and re-open the chat to re-fold the current `requires_action`. |
| Gate reappears after clicking | The optimistic settle rolled back because `/confirm` failed. Read the response body; it names the real error. |
| `400 no non-archived thread is waiting on tool_use_id` | Confirmations sent one at a time and raced. They must be batched into a single `events.send`. |
| Chart never renders, session stuck idle | The `show_chart` result never went out (tab was closed). Re-open the chat; the controller answers pending custom tools on attach. |
| Upload succeeds but agent can't find the file | It's at `/mnt/session/uploads/<file_id>/<name>`; the message note carries the exact mounted path. |
| Download chips never appear | `files.list({scope_id})` not enabled on the org yet; uploads still show, outputs won't. |

## Cleanup

The agent and environment are durable and reused; keep them. To tear everything down:

```bash
ant beta:agents archive --agent-id "$(jq -r '.resources["./agents/spreadsheet-analyst.md"].id' claude-lock.json)"
ant beta:environments archive --environment-id "$(jq -r '.resources["./environments/spreadsheet-analyst.yaml"].id' claude-lock.json)"
rm claude-lock.json   # so the next `ant apply` creates fresh ones
```

Sessions are cheap; archive them from the sidebar, or leave them.
