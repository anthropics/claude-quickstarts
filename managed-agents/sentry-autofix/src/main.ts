// The server: check the setup, then listen for Sentry.

import { serve } from "@hono/node-server";
import { createApp } from "./app";
import { fixIssue, loadConfig, preflight, requireEnv, runs } from "./fixer";

// A first run usually fails here, on something missing from .env. Say what,
// in one line, instead of a stack trace.
const { config, clientSecret } = await (async () => {
  const config = loadConfig();
  const clientSecret = requireEnv("SENTRY_CLIENT_SECRET");
  const problem = await preflight(config);
  if (problem) throw new Error(problem);
  return { config, clientSecret };
})().catch((err) => {
  console.error(err instanceof Error ? err.message : err);
  process.exit(1);
});

const app = createApp({
  clientSecret,
  project: process.env.SENTRY_PROJECT,
  status: () => ({ repository: config.repo.url, runs }),
  onIssue: (issue) => {
    fixIssue(issue, config)
      .then((run) => {
        if (!run) console.log(`[managed-agent] ${issue.shortId} already has a session, skipping`);
      })
      .catch((err) => console.error(`[managed-agent] could not start a session for ${issue.shortId}:`, err));
  },
});

// `||`, not `??`: an empty PORT= line in .env should mean the default.
const port = Number(process.env.PORT || 3000);
const hostname = process.env.HOST || "127.0.0.1";
serve({ fetch: app.fetch, port, hostname }, () => {
  console.log(`sentry-autofix on http://${hostname}:${port} for ${config.repo.url}`);
  console.log("webhook URL for your Sentry integration: <your tunnel>/webhooks/sentry");
});
