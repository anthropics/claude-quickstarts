// Serves the chat page and its assets, plus the /api routes from src/app.ts.

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { serve } from "@hono/node-server";
import * as esbuild from "esbuild";
import { Hono } from "hono";
import { api, missingConfig } from "./app";

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

const webFile = (name: string) => fileURLToPath(new URL(`../web/${name}`, import.meta.url));

// Dev rebuilds the bundle on each request (~100ms), so web/ edits show on
// reload -- production caches the first build.
const NODE_ENV = process.env.NODE_ENV || "development";
const PRODUCTION = NODE_ENV === "production";
let cachedBundle: string | undefined;
async function bundleApp(): Promise<string> {
  if (PRODUCTION && cachedBundle) return cachedBundle;
  const result = await esbuild.build({
    entryPoints: [webFile("app.tsx")],
    bundle: true,
    format: "esm",
    sourcemap: PRODUCTION ? false : "inline",
    minify: PRODUCTION,
    // React's entry points branch on this at require time; without the
    // define, the browser bundle would reference a `process` that isn't there.
    define: { "process.env.NODE_ENV": JSON.stringify(NODE_ENV) },
    write: false,
  });
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
    // Agent turns hold the response open for minutes -- requestTimeout: 0
    // disables Node's 5-minute reap.
    serverOptions: { requestTimeout: 0 },
  },
  () => console.log(`Research analyst running at http://${HOST}:${PORT}`),
);
