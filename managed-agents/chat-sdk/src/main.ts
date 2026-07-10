// Long-running Node server. The routes: the chat page and its two assets,
// the Chat SDK web adapter endpoint that `useChat` POSTs to, the live
// activity tail the page subscribes to while a turn runs, and two thin
// wrappers over the Managed Agents sessions API (list/create + transcript
// replay) that power the sidebar. esbuild bundles web/app.tsx on request, so
// one process serves all of it. The four /api routes are fetch-native Hono
// handlers, so they drop into the Cloudflare Workers, Vercel, and Netlify
// adapters; the page routes lean on node:fs and runtime esbuild, so they
// need a Node host (see skill.md, "Production notes").

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { serve } from "@hono/node-server";
import * as esbuild from "esbuild";
import { Hono, type Context } from "hono";
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

// The demo getUser trusts every caller, so the default only listens on the
// loopback interface; set HOST only after wiring real auth into src/bot.ts.
// (Explicit 127.0.0.1 rather than "localhost": Node would resolve
// "localhost" to ::1 on some systems and refuse IPv4 connections.)
const HOST = process.env.HOST || "127.0.0.1";

const webFile = (name: string) => fileURLToPath(new URL(`../web/${name}`, import.meta.url));

// The page bundle. In development it is rebuilt on every request -- a bundle
// this size takes esbuild ~100ms, and it means edits to web/ show up on the
// next reload with no build step and no server restart. In production the
// first build is cached (sources can't change under a running deploy) and
// the sourcemap is dropped, which is most of the bundle's weight.
const NODE_ENV = process.env.NODE_ENV || "development";
const PRODUCTION = NODE_ENV === "production";
let cachedBundle: string | undefined;
async function bundleApp(): Promise<string> {
  if (PRODUCTION && cachedBundle) return cachedBundle;
  const result = await esbuild.build({
    entryPoints: [webFile("app.tsx")],
    bundle: true,
    format: "esm",
    write: false,
    sourcemap: PRODUCTION ? false : "inline",
    minify: PRODUCTION,
    // React's entry points branch on this at require time; without the
    // define, the browser bundle would reference a `process` that isn't there.
    define: { "process.env.NODE_ENV": JSON.stringify(NODE_ENV) },
  });
  const text = result.outputFiles[0].text;
  if (PRODUCTION) cachedBundle = text;
  return text;
}

// Same identity boundary as /api/chat: an anonymous caller gets a 401 before
// any Managed Agents call happens.
function withUser(handler: (request: Request) => Promise<Response>) {
  return async (c: Context): Promise<Response> => {
    if (!(await authenticate(c.req.raw))) return new Response("Unauthorized", { status: 401 });
    return handler(c.req.raw);
  };
}

const app = new Hono();

app.get("/", async (c) => c.html(await readFile(webFile("index.html"), "utf8")));
app.get("/app.css", async (c) =>
  c.body(await readFile(webFile("app.css"), "utf8"), 200, { "content-type": "text/css" }),
);
app.get("/app.js", async (c) =>
  c.body(await bundleApp(), 200, { "content-type": "text/javascript" }),
);

app.post("/api/chat", (c) => bot.webhooks.web(c.req.raw));

// The sidebar: conversations are Managed Agents sessions, nothing more.
app.get(
  "/api/sessions",
  withUser(async () => Response.json(await listSessions())),
);
app.post(
  "/api/sessions",
  withUser(async () => Response.json(await createSession())),
);

// Transcript replay from the session's event log. The ownership check
// matters: the conversation ID comes from the browser, and this route
// must not replay sessions that belong to other agents in the org.
app.get(
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
// only -- message text travels exclusively on /api/chat.
app.get("/api/activity", (c) => activityTail(c.req.raw));

serve(
  {
    fetch: app.fetch,
    port: PORT,
    hostname: HOST,
    // Agent turns hold the response stream open for minutes; never reap.
    // (Node's socket timeout is already off by default; this disables the
    // 5-minute request timeout too.)
    serverOptions: { requestTimeout: 0 },
  },
  () => console.log(`Research analyst running at http://${HOST}:${PORT}`),
);

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
