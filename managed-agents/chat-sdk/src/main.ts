// Long-running Bun server. Five routes: the chat page, the Chat SDK web
// adapter endpoint that `useChat` POSTs to, the live activity tail the page
// subscribes to while a turn runs, and two thin wrappers over the Managed
// Agents sessions API (list/create + transcript replay) that power the
// sidebar. Bun bundles web/app.tsx on the fly from the HTML import, so one
// process serves all of it.

import index from "../web/index.html";
import { subscribeActivity } from "./activity";
import { activityThreadId, authenticate, bot } from "./bot";
import { createSession, historyOf, listSessions, ownedSession } from "./sessions";

for (const name of ["CLAUDE_AGENT_ID", "CLAUDE_ENVIRONMENT_ID"]) {
  const value = process.env[name];
  if (!value || value.endsWith("...")) {
    console.error(`FATAL: ${name} is not set. Copy .env.example to .env and fill it in.`);
    process.exit(1);
  }
}

const PORT = Number(process.env.PORT) || 3000;

// Same identity boundary as /api/chat: an anonymous caller gets a 401 before
// any Managed Agents call happens.
function withUser(handler: (request: Request) => Promise<Response>) {
  return async (request: Request): Promise<Response> => {
    if (!(await authenticate(request))) return new Response("Unauthorized", { status: 401 });
    return handler(request);
  };
}

Bun.serve({
  port: PORT,
  // The demo getUser trusts every caller, so only listen on the loopback
  // interface. Widen this only after wiring real auth into src/bot.ts.
  hostname: "localhost",
  // Agent turns hold the response stream open for minutes; never reap.
  idleTimeout: 0,
  routes: {
    "/": index,
    "/api/chat": { POST: (request) => bot.webhooks.web(request) },
    // The sidebar: conversations are Managed Agents sessions, nothing more.
    "/api/sessions": {
      GET: withUser(async () => Response.json(await listSessions())),
      POST: withUser(async () => Response.json(await createSession())),
    },
    // Transcript replay from the session's event log. The ownership check
    // matters: the conversation ID comes from the browser, and this route
    // must not replay sessions that belong to other agents in the org.
    "/api/history": {
      GET: withUser(async (request) => {
        const conversation = new URL(request.url).searchParams.get("conversation");
        if (!conversation) return new Response("missing ?conversation", { status: 400 });
        const session = await ownedSession(conversation);
        if (!session) return new Response("Not found", { status: 404 });
        // A still-running turn hasn't earned its "Brief ready" card yet.
        return Response.json(await historyOf(conversation, session.status));
      }),
    },
    // Server-sent activity for one conversation: tool calls, model requests,
    // retries, all published by the bridge while its turn runs. Progress
    // only -- message text travels exclusively on /api/chat.
    "/api/activity": { GET: (request) => activityTail(request) },
  },
});

async function activityTail(request: Request): Promise<Response> {
  const conversation = new URL(request.url).searchParams.get("conversation");
  if (!conversation) return new Response("missing ?conversation", { status: 400 });
  // Same identity check as /api/chat: an anonymous caller gets a 401, and the
  // thread being watched is scoped to the caller getUser resolves.
  const threadId = await activityThreadId(request, conversation);
  if (!threadId) return new Response("Unauthorized", { status: 401 });
  // Same ownership rule as /api/history: this route also takes a
  // browser-supplied session ID, so it goes through the same gate.
  if (!(await ownedSession(conversation))) return new Response("Not found", { status: 404 });
  const encoder = new TextEncoder();
  let unsubscribe = () => {};
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      // A first byte so EventSource reports the connection open immediately.
      controller.enqueue(encoder.encode(": connected\n\n"));
      unsubscribe = subscribeActivity(threadId, (item) => {
        try {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(item)}\n\n`));
        } catch {
          // The tab is gone but cancel() has not run yet; never let a dead
          // subscriber take down the turn that is publishing.
          unsubscribe();
        }
      });
      // A closed tab that never receives another publish would otherwise
      // leave its subscriber registered until one arrives and throws.
      request.signal.addEventListener("abort", () => unsubscribe());
    },
    cancel() {
      unsubscribe();
    },
  });
  return new Response(stream, {
    headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
  });
}

console.log(`VC analyst running at http://localhost:${PORT}`);
