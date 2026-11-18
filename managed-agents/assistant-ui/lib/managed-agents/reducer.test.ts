// Fold the golden turn from the Managed Agents wire protocol and assert the
// conversation it produces: think, web search, a bash call that parks on
// approval, allow, then a streamed answer. Run with `npm test`.

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { StreamEvent } from "./events";
import {
  applyEvent,
  evictOptimisticMessage,
  initialProjection,
  isBusy,
  markResuming,
  project,
  restoreGates,
} from "./reducer";
import type { ToolPart } from "./reducer";

// A minimal typed builder so the fixture reads like the wire log. The
// events are structurally the SDK's; we cast at the array boundary.
const T = (o: Record<string, unknown>) => o as unknown as StreamEvent;

const userTurn = [
  T({ type: "user.message", id: "sevt_01", content: [{ type: "text", text: "What's the latest Node LTS? Then check this repo." }], processed_at: "2026-07-23T10:00:00Z" }),
  T({ type: "session.status_running", id: "sevt_02", processed_at: "2026-07-23T10:00:00Z" }),
  T({ type: "span.model_request_start", id: "sevt_03", processed_at: "2026-07-23T10:00:00Z" }),
  T({ type: "event_start", event: { type: "agent.thinking", id: "sevt_04" } }),
  T({ type: "agent.thinking", id: "sevt_04", processed_at: "2026-07-23T10:00:01Z" }),
  T({ type: "agent.tool_use", id: "sevt_05", name: "web_search", input: { query: "Node.js current LTS" }, evaluated_permission: "allow", processed_at: "2026-07-23T10:00:01Z" }),
  T({ type: "span.model_request_end", id: "sevt_06", model_request_start_id: "sevt_03", is_error: false, processed_at: "2026-07-23T10:00:02Z" }),
  T({ type: "agent.tool_result", id: "sevt_07", tool_use_id: "sevt_05", content: [{ type: "search_result", source: "https://nodejs.org/en/about/previous-releases", title: "Node.js — Releases", content: [{ type: "text", text: "Node.js 22 is the current LTS." }] }], is_error: false, processed_at: "2026-07-23T10:00:03Z" }),
  T({ type: "span.model_request_start", id: "sevt_08", processed_at: "2026-07-23T10:00:03Z" }),
  T({ type: "agent.tool_use", id: "sevt_09", name: "bash", input: { command: "node --version" }, evaluated_permission: "ask", processed_at: "2026-07-23T10:00:04Z" }),
  T({ type: "span.model_request_end", id: "sevt_10", model_request_start_id: "sevt_08", is_error: false, processed_at: "2026-07-23T10:00:04Z" }),
  T({ type: "session.status_idle", id: "sevt_11", stop_reason: { type: "requires_action", event_ids: ["sevt_09"] }, processed_at: "2026-07-23T10:00:04Z" }),
];

const afterAllow = [
  T({ type: "user.tool_confirmation", id: "sevt_12", tool_use_id: "sevt_09", result: "allow", processed_at: "2026-07-23T10:00:20Z" }),
  T({ type: "session.status_running", id: "sevt_13", processed_at: "2026-07-23T10:00:20Z" }),
  T({ type: "agent.tool_result", id: "sevt_14", tool_use_id: "sevt_09", content: [{ type: "text", text: "v22.11.0\n" }], is_error: false, processed_at: "2026-07-23T10:00:21Z" }),
  T({ type: "span.model_request_start", id: "sevt_15", processed_at: "2026-07-23T10:00:21Z" }),
  T({ type: "event_start", event: { type: "agent.message", id: "sevt_16" } }),
  T({ type: "event_delta", event_id: "sevt_16", delta: { type: "content_delta", index: 0, content: { type: "text", text: "The current LTS is " } } }),
  T({ type: "event_delta", event_id: "sevt_16", delta: { type: "content_delta", index: 0, content: { type: "text", text: "Node 22. This repo runs v22.11.0." } } }),
  T({ type: "agent.message", id: "sevt_16", content: [{ type: "text", text: "The current LTS is Node 22. This repo runs v22.11.0." }], processed_at: "2026-07-23T10:00:22Z" }),
  T({ type: "span.model_request_end", id: "sevt_17", model_request_start_id: "sevt_15", is_error: false, processed_at: "2026-07-23T10:00:22Z" }),
  T({ type: "session.status_idle", id: "sevt_18", stop_reason: { type: "end_turn" }, processed_at: "2026-07-23T10:00:22Z" }),
];

const toolParts = (state: ReturnType<typeof initialProjection>) =>
  state.messages
    .filter((m) => m.role === "assistant")
    .flatMap((m) => m.content)
    .filter((p): p is ToolPart => p.type === "tool-call");

describe("reducer: the golden turn", () => {
  it("parks the turn on an approval gate for the always_ask bash call", () => {
    const state = project(userTurn);

    assert.equal(state.messages[0]?.role, "user");
    const assistant = state.messages[1]!;
    assert.equal(assistant.role, "assistant");

    // thinking preview + buffered event dedupe into ONE reasoning part
    const reasoning = assistant.content.filter((p) => p.type === "reasoning");
    assert.equal(reasoning.length, 1, "start + buffered agent.thinking must not double up");

    // web_search resolved with structured search results
    const [search, bash] = toolParts(state);
    assert.equal(search?.toolName, "web_search");
    assert.equal(search?.result?.searchResults?.[0]?.url, "https://nodejs.org/en/about/previous-releases");
    assert.equal(search?.approval, undefined);

    // bash is gated: approval id is the tool_use *event* id, no result yet
    assert.equal(bash?.toolName, "bash");
    assert.deepEqual(bash?.approval, { id: "sevt_09" });
    assert.equal(bash?.result, undefined);

    assert.deepEqual(state.pendingApprovals, ["sevt_09"]);
    assert.equal(state.isRunning, false, "session is idle while it waits for a click");
    assert.equal(isBusy(state), true, "but the composer must still be busy");
    assert.deepEqual(assistant.status, { type: "requires-action", reason: "tool-calls" });
  });

  it("streams the answer after Allow and lands complete with the buffered text", () => {
    const state = project([...userTurn, ...afterAllow]);
    const assistant = state.messages[1]!;

    const bash = toolParts(state)[1]!;
    assert.deepEqual(bash.approval, { id: "sevt_09", approved: true });
    assert.equal(bash.result?.text, "v22.11.0\n");

    // Preview reconciled: exactly one text part holding the buffered message
    const texts = assistant.content.filter((p) => p.type === "text");
    assert.equal(texts.length, 1);
    assert.equal(texts[0]?.type === "text" && texts[0].text, "The current LTS is Node 22. This repo runs v22.11.0.");

    assert.deepEqual(state.pendingApprovals, []);
    assert.equal(state.isRunning, false);
    assert.deepEqual(assistant.status, { type: "complete", reason: "unknown" });
  });

  it("streams tokens incrementally as deltas arrive", () => {
    let state = project(userTurn.slice(0, 2));
    state = applyEvent(state, T({ type: "event_start", event: { type: "agent.message", id: "m1" } }));
    state = applyEvent(state, T({ type: "event_delta", event_id: "m1", delta: { type: "content_delta", index: 0, content: { type: "text", text: "Hel" } } }));
    let text = state.messages[1]!.content.find((p) => p.type === "text");
    assert.equal(text?.type === "text" && text.text, "Hel");
    state = applyEvent(state, T({ type: "event_delta", event_id: "m1", delta: { type: "content_delta", index: 0, content: { type: "text", text: "lo" } } }));
    text = state.messages[1]!.content.find((p) => p.type === "text");
    assert.equal(text?.type === "text" && text.text, "Hello");
  });

  it("dedupes when history replay and the live tail overlap", () => {
    const once = project(userTurn);
    const twice = project([...userTurn, ...userTurn]);
    assert.deepEqual(twice.messages.length, once.messages.length);
    assert.equal(toolParts(twice).length, toolParts(once).length);
  });

  it("settles a deny with its message and lets the turn continue", () => {
    const state = project([
      ...userTurn,
      T({ type: "user.tool_confirmation", id: "sevt_20", tool_use_id: "sevt_09", result: "deny", deny_message: "Not on the box.", processed_at: "t" }),
      T({ type: "session.status_running", id: "sevt_21", processed_at: "t" }),
    ]);
    const bash = toolParts(state)[1]!;
    assert.deepEqual(bash.approval, { id: "sevt_09", approved: false, reason: "Not on the box." });
    assert.deepEqual(state.pendingApprovals, []);
  });

  it("tracks a custom tool the client owes a result for, then clears it", () => {
    const parked = project([
      T({ type: "user.message", id: "u", content: [{ type: "text", text: "chart it" }], processed_at: "t" }),
      T({ type: "session.status_running", id: "r", processed_at: "t" }),
      T({ type: "agent.custom_tool_use", id: "c1", name: "show_chart", input: { title: "Revenue", kind: "bar", x: ["Jan"], series: [{ name: "rev", values: [10] }] }, processed_at: "t" }),
      T({ type: "session.status_idle", id: "i", stop_reason: { type: "requires_action", event_ids: ["c1"] }, processed_at: "t" }),
    ]);
    assert.deepEqual(parked.pendingCustomTools, ["c1"]);
    const chart = toolParts(parked)[0]!;
    assert.equal(chart.toolKind, "custom");
    assert.equal(chart.approval, undefined, "custom tools are answered, never approved");

    const answered = applyEvent(
      parked,
      T({ type: "user.custom_tool_result", id: "res", custom_tool_use_id: "c1", content: [{ type: "text", text: "Rendered." }], is_error: false, processed_at: "t" }),
    );
    assert.deepEqual(answered.pendingCustomTools, []);
    assert.equal(answered.answeredCustomTools.has("c1"), true);
  });

  // Regression: the review found a replayed chart chat double-posted its
  // custom_tool_result. A whole-log fold must NOT leave the tool pending when
  // the answer is already later in the same history array.
  it("does not treat a custom tool as owed when its answer is later in the log", () => {
    const state = project([
      T({ type: "user.message", id: "u", content: [{ type: "text", text: "chart" }], processed_at: "t" }),
      T({ type: "agent.custom_tool_use", id: "c1", name: "show_chart", input: {}, processed_at: "t" }),
      T({ type: "session.status_idle", id: "i", stop_reason: { type: "requires_action", event_ids: ["c1"] }, processed_at: "t" }),
      T({ type: "user.custom_tool_result", id: "r", custom_tool_use_id: "c1", content: [], is_error: false, processed_at: "t" }),
      T({ type: "session.status_running", id: "run", processed_at: "t" }),
    ]);
    assert.deepEqual(state.pendingCustomTools, [], "answered later in the log, so nothing is owed");
    assert.equal(state.answeredCustomTools.has("c1"), true);
  });

  // Regression: an approval abandoned by an interrupt kept live buttons.
  it("strips an unresolved approval when the turn ends without answering it", () => {
    const state = project([
      ...userTurn, // parks on the bash gate
      T({ type: "user.interrupt", id: "int", processed_at: "t" }),
      T({ type: "session.status_idle", id: "done", stop_reason: { type: "end_turn" }, processed_at: "t" }),
    ]);
    const bash = toolParts(state)[1]!;
    assert.equal(bash.toolName, "bash");
    assert.equal(bash.approval, undefined, "an abandoned gate must not keep Allow/Deny");
    assert.deepEqual(state.pendingApprovals, []);
  });

  // Regression: a failed /confirm can't be repaired by replay (dedupe skips
  // the parked status_idle); the controller restores the gate explicitly.
  it("restoreGates puts an optimistically-settled gate back", () => {
    let state = project(userTurn); // gate open on sevt_09
    // optimistic settle, as the controller does on click (id scheme:
    // optimistic-confirm-N; anything else counts as the server's own record)
    state = applyEvent(
      state,
      T({ type: "user.tool_confirmation", id: "optimistic-confirm-1", tool_use_id: "sevt_09", result: "allow" }),
    );
    assert.deepEqual(state.pendingApprovals, []);
    assert.deepEqual(toolParts(state)[1]!.approval, { id: "sevt_09", approved: true });
    // the POST failed: put the gate back
    state = restoreGates(state, ["sevt_09"]);
    assert.deepEqual(state.pendingApprovals, ["sevt_09"]);
    assert.deepEqual(toolParts(state)[1]!.approval, { id: "sevt_09" }, "buttons must return");
    assert.deepEqual(state.messages[1]!.status, { type: "requires-action", reason: "tool-calls" });
  });

  // Regression: a failed send left the optimistic bubble reading as delivered.
  it("evictOptimisticMessage removes an unsent bubble", () => {
    let state = applyEvent(
      initialProjection(),
      T({ type: "user.message", id: "optimistic-1", content: [{ type: "text", text: "hi" }], processed_at: "t" }),
    );
    assert.equal(state.messages.length, 1);
    state = evictOptimisticMessage(state, "optimistic-1");
    assert.equal(state.messages.length, 0);
    assert.equal(state.isRunning, false);
  });

  // Regression: restoreGates re-added a gate the server had already left
  // (user clicked Allow then Stop; the interrupt ended the turn), wedging the
  // composer. It must only restore ids the session is still parked on.
  it("restoreGates is a no-op once the session left the gate", () => {
    let state = project([
      ...userTurn, // parked on sevt_09
      T({ type: "user.tool_confirmation", id: "optimistic-confirm-1", tool_use_id: "sevt_09", result: "allow" }), // optimistic
      T({ type: "user.interrupt", id: "int", processed_at: "t" }),
      T({ type: "session.status_running", id: "run", processed_at: "t" }),
      T({ type: "session.status_idle", id: "done", stop_reason: { type: "end_turn" }, processed_at: "t" }),
    ]);
    assert.deepEqual(state.parkedIds, [], "server left the gate");
    state = restoreGates(state, ["sevt_09"]); // the /confirm then 400s
    assert.deepEqual(state.pendingApprovals, [], "must not resurrect the gate");
    assert.deepEqual(state.messages[1]!.status?.type, "complete");
  });

  // Regression: restoreGates overwrote an approval that had already been
  // answered on the wire (echo + result raced ahead of our failed fetch).
  it("restoreGates leaves an already-answered gate alone", () => {
    let state = project([
      ...userTurn,
      // the real confirmation + result land via the tail before our fetch errors
      T({ type: "user.tool_confirmation", id: "conf", tool_use_id: "sevt_09", result: "allow", processed_at: "t" }),
      T({ type: "agent.tool_result", id: "res", tool_use_id: "sevt_09", content: [{ type: "text", text: "ok" }], is_error: false, processed_at: "t" }),
    ]);
    // still notionally parked (no status_running yet), but the part is answered
    assert.equal(state.parkedIds.includes("sevt_09"), true);
    state = restoreGates(state, ["sevt_09"]);
    const bash = toolParts(state)[1]!;
    assert.deepEqual(bash.approval, { id: "sevt_09", approved: true }, "answered gate untouched");
    assert.equal(bash.result?.text, "ok");
  });

  // Regression: the send rollback deleted a message whose echo had already
  // landed (the fetch errored after delivery). Echoed bubbles are kept.
  it("evictOptimisticMessage keeps a bubble whose echo already landed", () => {
    let state = applyEvent(
      initialProjection(),
      T({ type: "user.message", id: "optimistic-1", content: [{ type: "text", text: "hi" }], processed_at: "2026-07-23T10:00:00.000Z" }),
    );
    // the real echo (a moment later, same opening) replaces the optimistic
    // bubble, keeping the id and marking it echoed/delivered
    state = applyEvent(
      state,
      T({ type: "user.message", id: "sevt_real", content: [{ type: "text", text: "hi" }], processed_at: "2026-07-23T10:00:00.400Z" }),
    );
    assert.equal(state.echoedOptimistic.has("optimistic-1"), true);
    state = evictOptimisticMessage(state, "optimistic-1"); // late failure fires
    assert.equal(state.messages.length, 1, "delivered message must stay");
  });

  // Regression: a message sent before history finished loading had its
  // bubble overwritten by the first replayed (older) user.message.
  it("does not reconcile an optimistic bubble against older replayed history", () => {
    let state = applyEvent(
      initialProjection(),
      T({ type: "user.message", id: "optimistic-1", content: [{ type: "text", text: "brand new question" }], processed_at: "2026-07-23T12:00:00Z" }),
    );
    // an older historic message with different text folds in afterwards
    state = applyEvent(
      state,
      T({ type: "user.message", id: "sevt_old", content: [{ type: "text", text: "some earlier question" }], processed_at: "2026-07-22T09:00:00Z" }),
    );
    assert.equal(state.messages.length, 2, "historic message must append, not overwrite");
    assert.equal(state.echoedOptimistic.has("optimistic-1"), false);
    const first = state.messages[0]!.content[0]!;
    assert.equal(first.type === "text" && first.text, "brand new question");
  });

  // Regression: restoreGates reopened a gate whose REAL confirmation had
  // already landed via the tail (only the tool_result/status were pending).
  it("restoreGates never reopens a gate settled by a persisted confirmation", () => {
    let state = project([
      ...userTurn,
      T({ type: "user.tool_confirmation", id: "sevt_conf", tool_use_id: "sevt_09", result: "allow", processed_at: "t" }),
    ]);
    assert.equal(state.confirmedIds.has("sevt_09"), true);
    state = restoreGates(state, ["sevt_09"]); // our own fetch then errors
    assert.deepEqual(toolParts(state)[1]!.approval, { id: "sevt_09", approved: true });
    assert.deepEqual(state.pendingApprovals, []);
  });

  // Regression: a gate reopened by a failed /confirm survived the resumed
  // turn. status_running is proof nothing is parked, so it sweeps gates.
  it("session.status_running sweeps any gate left over from a rollback", () => {
    let state = project(userTurn); // parked
    state = applyEvent(
      state,
      T({ type: "user.tool_confirmation", id: "optimistic-confirm-1", tool_use_id: "sevt_09", result: "allow" }),
    );
    state = restoreGates(state, ["sevt_09"]); // fetch failed → gate reopened
    assert.deepEqual(state.pendingApprovals, ["sevt_09"]);
    state = applyEvent(state, T({ type: "session.status_running", id: "sevt_run", processed_at: "t" }));
    assert.deepEqual(state.pendingApprovals, [], "running means nothing is parked");
    assert.equal(toolParts(state)[1]!.approval, undefined, "stale buttons removed");
  });

  // Two gates parked at once: answering one re-emits requires_action with
  // the remainder (per the protocol), which re-stamps the other gate. The
  // status_running sweep therefore can't clobber a still-owed gate.
  it("keeps the second gate live after a partial resolution", () => {
    const state = project([
      T({ type: "user.message", id: "u", content: [{ type: "text", text: "two things" }], processed_at: "t" }),
      T({ type: "session.status_running", id: "r1", processed_at: "t" }),
      T({ type: "agent.tool_use", id: "A", name: "bash", input: { command: "one" }, evaluated_permission: "ask", processed_at: "t" }),
      T({ type: "agent.tool_use", id: "B", name: "bash", input: { command: "two" }, evaluated_permission: "ask", processed_at: "t" }),
      T({ type: "session.status_idle", id: "i1", stop_reason: { type: "requires_action", event_ids: ["A", "B"] }, processed_at: "t" }),
      // user allows A only; the API re-parks on the remainder
      T({ type: "user.tool_confirmation", id: "confA", tool_use_id: "A", result: "allow", processed_at: "t" }),
      T({ type: "session.status_idle", id: "i2", stop_reason: { type: "requires_action", event_ids: ["B"] }, processed_at: "t" }),
    ]);
    const [a, b] = toolParts(state);
    assert.deepEqual(a?.approval, { id: "A", approved: true });
    assert.deepEqual(b?.approval, { id: "B" }, "B still owes an answer, buttons must be live");
    assert.deepEqual(state.pendingApprovals, ["B"]);
    assert.deepEqual(state.parkedIds, ["B"]);
  });

  // The optimistic bubble and the server both use messageText(), so an echo
  // of a short message WITH an attachment reconciles instead of duplicating.
  it("reconciles a short attachment message echo (identical text)", () => {
    const text = "chart\n\n[Attached file, mounted read-only in the sandbox:\n- sales.csv → /mnt/session/uploads/file_011/sales.csv]";
    let state = applyEvent(
      initialProjection(),
      T({ type: "user.message", id: "optimistic-1", content: [{ type: "text", text }], processed_at: "2026-07-23T10:00:00Z" }),
    );
    state = applyEvent(
      state,
      T({ type: "user.message", id: "sevt_echo", content: [{ type: "text", text }], processed_at: "2026-07-23T10:00:00.3Z" }),
    );
    assert.equal(state.messages.length, 1, "echo replaces the optimistic bubble, no duplicate");
    assert.equal(state.echoedOptimistic.has("optimistic-1"), true);
  });

  // Regression: starting a second turn flipped the PREVIOUS turn's answer
  // back to "running" (the derived status landed on the last assistant
  // message with no check that it belonged to the current turn) and nothing
  // ever settled it again.
  it("keeps the previous turn's answer complete when a new turn begins", () => {
    let state = project([...userTurn, ...afterAllow]); // turn 1 done
    // Turn 2 opens exactly as the controller folds it: optimistic
    // user.message, then optimistic session.status_running.
    state = applyEvent(
      state,
      T({ type: "user.message", id: "optimistic-2", content: [{ type: "text", text: "and one more thing" }], processed_at: "2026-07-23T10:05:00Z" }),
    );
    state = applyEvent(state, T({ type: "session.status_running", id: "optimistic-run-2", processed_at: "2026-07-23T10:05:00Z" }));
    assert.deepEqual(state.messages[1]!.status, { type: "complete", reason: "unknown" }, "turn 1's answer is settled history");
    // Turn 2's own assistant message carries the live status once it exists.
    state = applyEvent(state, T({ type: "agent.message", id: "sevt_30", content: [{ type: "text", text: "Sure." }], processed_at: "2026-07-23T10:05:01Z" }));
    assert.deepEqual(state.messages[1]!.status, { type: "complete", reason: "unknown" });
    assert.deepEqual(state.messages[3]!.status, { type: "running" });
  });

  // Regression: a message opened by event_start (which carries no timestamp)
  // kept createdAt = epoch 0 while live, but got the real time on replay.
  it("backfills the assistant timestamp from the buffered event", () => {
    const live = project(userTurn);
    assert.equal(
      live.messages[1]!.createdAt.toISOString(),
      "2026-07-23T10:00:01.000Z",
      "live projection must carry the buffered agent.thinking's time, not 1970",
    );
    // Replay sees only persisted events (no event_start/event_delta).
    const replayed = project(userTurn.filter((e) => e.type !== "event_start" && e.type !== "event_delta"));
    assert.equal(
      replayed.messages[1]!.createdAt.getTime(),
      live.messages[1]!.createdAt.getTime(),
      "replay and live must agree",
    );
  });

  // Regression: a buffered preview arriving AFTER its persisted event had
  // already folded (attach mid-turn: replay finishes after the message
  // completed) opened a duplicate part that nothing ever reconciled away.
  it("ignores a preview whose persisted event already folded", () => {
    let state = project(userTurn.filter((e) => e.type !== "event_start")); // history has sevt_04
    const before = state.messages[1]!.content.length;
    state = applyEvent(state, T({ type: "event_start", event: { type: "agent.thinking", id: "sevt_04" } }));
    assert.equal(state.messages[1]!.content.length, before, "no duplicate reasoning part");
    // Same for a message preview: the persisted agent.message is in seen.
    state = applyEvent(state, T({ type: "agent.message", id: "m9", content: [{ type: "text", text: "done" }], processed_at: "t" }));
    const count = state.messages[1]!.content.length;
    state = applyEvent(state, T({ type: "event_start", event: { type: "agent.message", id: "m9" } }));
    assert.equal(state.messages[1]!.content.length, count, "no duplicate text part");
  });

  // assistant-ui drops blank text/reasoning parts during conversion, so the
  // thinking part must carry text or the indicator never renders.
  it("gives the thinking part non-empty text", () => {
    const state = project(userTurn);
    const reasoning = state.messages[1]!.content.find((p) => p.type === "reasoning");
    assert.ok(reasoning && reasoning.type === "reasoning" && reasoning.text.trim().length > 0);
  });

  // Regression: answering the last open gate dropped isBusy until the real
  // status_running arrived, briefly re-enabling the composer mid-resume.
  it("markResuming keeps the session busy after the last gate is answered", () => {
    let state = project(userTurn); // parked on sevt_09
    state = applyEvent(
      state,
      T({ type: "user.tool_confirmation", id: "optimistic-confirm-1", tool_use_id: "sevt_09", result: "allow" }),
    );
    assert.equal(isBusy(state), false, "the optimistic settle alone leaves a gap");
    state = markResuming(state);
    assert.equal(isBusy(state), true, "resuming must keep the composer busy");
    assert.deepEqual(state.parkedIds, ["sevt_09"], "parkedIds stays intact for a rollback");
    // The POST fails: restoreGates reopens the gate and clears the flag.
    state = restoreGates(state, ["sevt_09"]);
    assert.equal(state.isRunning, false);
    assert.deepEqual(state.pendingApprovals, ["sevt_09"]);
  });

  // Regression: a mid-turn transient error's "retrying" banner survived the
  // turn — an in-place recovery never re-emits status_running, and neither
  // agent.message nor the closing status_idle cleared lastError.
  it("clears a retrying error once the turn recovers", () => {
    const base = [
      T({ type: "user.message", id: "u", content: [{ type: "text", text: "go" }], processed_at: "t" }),
      T({ type: "session.status_running", id: "r", processed_at: "t" }),
      T({ type: "session.error", id: "e", error: { type: "unknown_error", message: "blip", retry_status: { type: "retrying" } }, processed_at: "t" }),
    ];
    // Recovery proven by output:
    let state = project([...base, T({ type: "agent.message", id: "m", content: [{ type: "text", text: "ok" }], processed_at: "t" })]);
    assert.equal(state.lastError, null, "output clears the retrying banner");
    // Recovery proven by the turn simply ending:
    state = project([...base, T({ type: "session.status_idle", id: "i", stop_reason: { type: "end_turn" }, processed_at: "t" })]);
    assert.equal(state.lastError, null, "end of turn clears the retrying banner");
    // Recovery proven by parking on a gate (no message, no end of turn):
    state = project([
      ...base,
      T({ type: "agent.tool_use", id: "tu", name: "bash", input: { command: "ls" }, evaluated_permission: "ask", processed_at: "t" }),
      T({ type: "session.status_idle", id: "ip", stop_reason: { type: "requires_action", event_ids: ["tu"] }, processed_at: "t" }),
    ]);
    assert.equal(state.lastError, null, "parking on a gate clears the retrying banner");
    // A terminal error is the outcome, not progress — it must stay.
    state = project([
      ...base.slice(0, 2),
      T({ type: "session.error", id: "e2", error: { type: "unknown_error", message: "boom", retry_status: { type: "terminal" } }, processed_at: "t" }),
      T({ type: "session.status_idle", id: "i2", stop_reason: { type: "retries_exhausted" }, processed_at: "t" }),
    ]);
    assert.equal(state.lastError?.message, "boom", "terminal errors survive the idle");
  });

  it("surfaces a terminal session error as an incomplete assistant message", () => {
    const state = project([
      T({ type: "user.message", id: "u", content: [{ type: "text", text: "go" }], processed_at: "t" }),
      T({ type: "session.status_running", id: "r", processed_at: "t" }),
      T({ type: "session.error", id: "e", error: { type: "unknown_error", message: "boom", retry_status: { type: "terminal" } }, processed_at: "t" }),
      T({ type: "session.status_idle", id: "i", stop_reason: { type: "retries_exhausted" }, processed_at: "t" }),
    ]);
    assert.deepEqual(state.messages[1]!.status, { type: "incomplete", reason: "error", error: "boom" });
  });

  it("propagates isError onto a custom tool part when user.custom_tool_result fails", () => {
    const state = project([
      T({ type: "user.message", id: "u", content: [{ type: "text", text: "chart" }], processed_at: "t" }),
      T({ type: "session.status_running", id: "r", processed_at: "t" }),
      T({ type: "agent.custom_tool_use", id: "c1", name: "show_chart", input: {}, processed_at: "t" }),
      T({ type: "session.status_idle", id: "i", stop_reason: { type: "requires_action", event_ids: ["c1"] }, processed_at: "t" }),
      T({ type: "user.custom_tool_result", id: "res", custom_tool_use_id: "c1", content: [{ type: "text", text: "bad data" }], is_error: true, processed_at: "t" }),
    ]);
    const chart = toolParts(state)[0]!;
    assert.equal(chart.result?.isError, true);
    assert.equal(chart.isError, true);
  });

  it("does not overwrite a pending optimistic bubble with a textless user.message", () => {
    let state = applyEvent(
      initialProjection(),
      T({ type: "user.message", id: "optimistic-1", content: [{ type: "text", text: "analyze this" }], processed_at: "2026-07-23T12:00:00Z" }),
    );
    state = applyEvent(
      state,
      T({ type: "user.message", id: "sevt_img", content: [{ type: "image" }], processed_at: "2026-07-23T11:59:00Z" }),
    );
    assert.equal(state.messages.length, 2);
    assert.equal(state.echoedOptimistic.has("optimistic-1"), false);
    const first = state.messages[0]!.content[0]!;
    assert.equal(first.type === "text" && first.text, "analyze this");
  });

  it("clears open previews when a turn ends so later model errors do not mutate settled turns", () => {
    let state = project([
      T({ type: "user.message", id: "u1", content: [{ type: "text", text: "start" }], processed_at: "t" }),
      T({ type: "session.status_running", id: "r1", processed_at: "t" }),
      T({ type: "event_start", event: { type: "agent.message", id: "m1" } }),
      T({ type: "event_delta", event_id: "m1", delta: { type: "content_delta", index: 0, content: { type: "text", text: "Partial reply" } } }),
      T({ type: "user.interrupt", id: "int", processed_at: "t" }),
      T({ type: "session.status_idle", id: "i1", stop_reason: { type: "end_turn" }, processed_at: "t" }),
    ]);
    assert.equal(state.previews.size, 0);

    state = project(
      [
        T({ type: "user.message", id: "u2", content: [{ type: "text", text: "next" }], processed_at: "t2" }),
        T({ type: "session.status_running", id: "r2", processed_at: "t2" }),
        T({ type: "span.model_request_end", id: "end2", model_request_start_id: "req2", is_error: true, processed_at: "t2" }),
      ],
      state,
    );
    const turn1Text = state.messages[1]!.content.find((p) => p.type === "text");
    assert.equal(turn1Text?.type === "text" && turn1Text.text, "Partial reply");
  });

  it("ignores event_start for non-text/thinking events and shifts preview indices on eviction", () => {
    let state = project([
      T({ type: "user.message", id: "optimistic-1", content: [{ type: "text", text: "failed send" }], processed_at: "t" }),
      T({ type: "user.message", id: "u2", content: [{ type: "text", text: "real turn" }], processed_at: "t" }),
      T({ type: "session.status_running", id: "r2", processed_at: "t" }),
      T({ type: "event_start", event: { type: "agent.tool_use", id: "tu1" } }),
      T({ type: "event_start", event: { type: "agent.message", id: "m2" } }),
    ]);
    assert.equal(state.previews.has("tu1"), false);
    assert.equal(state.messages[2]!.content.length, 1);

    state = evictOptimisticMessage(state, "optimistic-1");
    state = applyEvent(
      state,
      T({ type: "event_delta", event_id: "m2", delta: { type: "content_delta", index: 0, content: { type: "text", text: "Recovered" } } }),
    );
    const reply = state.messages[1]!.content[0]!;
    assert.equal(reply.type === "text" && reply.text, "Recovered");
  });
});
