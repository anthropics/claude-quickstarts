// The local Node host: the chat page and its two assets, plus the four
// fetch-native /api routes mounted from src/app.ts. esbuild bundles
// web/app.tsx on request, so one process serves all of it. The page routes
// lean on node:fs and runtime esbuild, which is why they live here and not
// in src/app.ts -- the API core has no Node dependencies and drops into the
// serverless shims unchanged (see skill.md, "Deploying off the Node server").

import { readFile } from "node:fs/promises";
import { serve } from "@hono/node-server";
import * as esbuild from "esbuild";
import { Hono } from "hono";
import { api, missingConfig } from "./app";
import { webBundleOptions, webFile } from "./bundle";

const missing = missingConfig();
if (missing) {
  console.error(`FATAL: ${missing} is not set. Copy .env.example to .env and fill it in.`);
  process.exit(1);
}

const PORT = Number(process.env.PORT) || 3000;

// The demo getUser trusts every caller, so the default only listens on the
// loopback interface; set HOST only after wiring real auth into src/bot.ts.
// (Explicit 127.0.0.1 rather than "localhost": Node would resolve
// "localhost" to ::1 on some systems and refuse IPv4 connections.)
const HOST = process.env.HOST || "127.0.0.1";

// The page bundle, built from the shared recipe in src/bundle.ts. In
// development it is rebuilt on every request -- a bundle this size takes
// esbuild ~100ms, and it means edits to web/ show up on the next reload with
// no build step and no server restart. In production the first build is
// cached (sources can't change under a running deploy).
const NODE_ENV = process.env.NODE_ENV || "development";
const PRODUCTION = NODE_ENV === "production";
let cachedBundle: string | undefined;
async function bundleApp(): Promise<string> {
  if (PRODUCTION && cachedBundle) return cachedBundle;
  const result = await esbuild.build({ ...webBundleOptions(NODE_ENV), write: false });
  const text = result.outputFiles![0].text;
  if (PRODUCTION) cachedBundle = text;
  return text;
}

const app = new Hono();

app.get("/", async (c) => c.html(await readFile(webFile("index.html"), "utf8")));
app.get("/app.css", async (c) =>
  c.body(await readFile(webFile("app.css"), "utf8"), 200, { "content-type": "text/css" }),
);
app.get("/app.js", async (c) =>
  c.body(await bundleApp(), 200, { "content-type": "text/javascript" }),
);

app.route("/", api);

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
