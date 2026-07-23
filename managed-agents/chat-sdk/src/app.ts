// The platform-neutral core: the four /api routes as one fetch-native Hono
// app. Every import is Web-standard, so the same app drops into any host
// that can run a fetch handler -- with one ambient dependency: credentials
// come from process.env, read at module scope (src/managed-agents.ts), so
// the host must populate it before imports run. src/main.ts mounts this
// behind the Node server that also serves the page; a deployed host mounts
// deployedApi() below instead.

import { Hono, type Context } from "hono";
import { subscribeActivity } from "./activity";
import { activityThreadId, authenticate, bot } from "./bot";
import { createSession, historyOf, listSessions, ownedSession } from "./sessions";

// The one definition of "configured": main.ts calls this at boot and refuses
// to start; the middleware below calls it per request, because a serverless
// function has no boot to refuse and should fail loudly instead of
// half-working.
export function missingConfig(): string | null {
  for (const name of ["CLAUDE_AGENT_ID", "CLAUDE_ENVIRONMENT_ID"]) {
    const value = process.env[name];
    if (!value || value.endsWith("...")) return name;
  }
  return null;
}

// Same identity boundary as /api/chat: an anonymous caller gets a 401 before
// any Managed Agents call happens.
function withUser(handler: (request: Request) => Promise<Response>) {
  return async (c: Context): Promise<Response> => {
    if (!(await authenticate(c.req.raw))) return new Response("Unauthorized", { status: 401 });
    return handler(c.req.raw);
  };
}

// Routes carry their full /api/... paths: hosts' rewrites forward the
// original request URL, so a plain route("/", api) mount matches with no
// prefix juggling.
export const api = new Hono();

api.use("/api/*", async (c, next) => {
  const missing = missingConfig();
  if (missing) return new Response(`Server misconfigured: ${missing} is not set`, { status: 500 });
  await next();
});

api.post("/api/chat", (c) => bot.webhooks.web(c.req.raw));

// The sidebar: conversations are Managed Agents sessions, nothing more.
api.get(
  "/api/sessions",
  withUser(async () => Response.json(await listSessions())),
);
api.post(
  "/api/sessions",
  withUser(async () => Response.json(await createSession())),
);

// Transcript replay from the session's event log. The ownership check
// matters: the conversation ID comes from the browser, and this route
// must not replay sessions that belong to other agents in the org.
api.get(
  "/api/history",
  withUser(async (request) => {
    const conversation = new URL(request.url).searchParams.get("conversation");
    if (!conversation) return new Response("missing ?conversation", { status: 400 });
    const session = await ownedSession(conversation);
    if (!session) return new Response("Not found", { status: 404 });
    // A still-running turn hasn't earned its "Brief ready" card yet.
    return Response.json(await historyOf(conversation, session.status));
  }),
);

// Server-sent activity for one conversation: tool calls, model requests,
// retries, all published by the bridge while its turn runs. Progress
// only -- message text travels exclusively on /api/chat. The fan-out is
// in-process (src/activity.ts): on a host that may route this request to a
// different instance than the turn's /api/chat, the feed stays silent --
// cosmetic only, the chat lane is unaffected.
api.get("/api/activity", (c) => activityTail(c.req.raw));

// What a deployed host mounts instead of `api` directly. The one extra
// check: locally the Anthropic SDK can discover CLI credentials
// (`ant auth login`), but a deployed host has no credential files, so a
// missing key would otherwise pass the config guard and die deep inside the
// SDK on the first call. `ANTHROPIC_AUTH_TOKEN` counts too -- it's the
// bearer-token form the SDK accepts.
export function deployedApi(): Hono {
  const app = new Hono();
  app.use("/api/*", async (c, next) => {
    if (!process.env.ANTHROPIC_API_KEY && !process.env.ANTHROPIC_AUTH_TOKEN) {
      return new Response("Server misconfigured: ANTHROPIC_API_KEY is not set", { status: 500 });
    }
    await next();
  });
  app.route("/", api);
  return app;
}

async function activityTail(request: Request): Promise<Response> {
  const conversation = new URL(request.url).searchParams.get("conversation");
  if (!conversation) return new Response("missing ?conversation", { status: 400 });
  // Beyond withUser's 401, the watched thread is scoped to the caller
  // getUser resolves.
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
          // The tab is gone but cancel() has not run yet -- drop the subscription.
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
