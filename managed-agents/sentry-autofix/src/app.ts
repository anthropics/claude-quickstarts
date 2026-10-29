// The HTTP surface: one route Sentry calls, one page you look at. It knows
// nothing about sessions; src/main.ts passes in what to do with a new issue.
//
//   POST /webhooks/sentry   a new issue -> onIssue (202, work continues)
//   GET  /                  the fixes this process has started, as JSON

import { Hono } from "hono";
import { issueFromWebhook, verifySignature, type SentryIssue } from "./sentry";

export type AppOptions = {
  clientSecret: string;
  // Only accept issues from this Sentry project slug. Empty accepts all.
  project?: string;
  onIssue: (issue: SentryIssue) => void;
  status: () => unknown;
};

export function createApp(options: AppOptions): Hono {
  const app = new Hono();

  app.get("/", (c) => c.json(options.status()));

  app.post("/webhooks/sentry", async (c) => {
    // Verify against the bytes as sent, before parsing anything.
    const raw = await c.req.text();
    if (!verifySignature(raw, c.req.header("sentry-hook-signature"), options.clientSecret)) {
      return c.json({ error: "bad signature" }, 401);
    }
    let body: { action?: string };
    try {
      body = JSON.parse(raw);
    } catch {
      return c.json({ error: "not JSON" }, 400);
    }
    // Only new issues start a fix. Sentry also sends resolved, assigned,
    // archived, and unresolved for the same resource, plus other resources
    // entirely; acknowledge and ignore them.
    if (c.req.header("sentry-hook-resource") !== "issue" || body?.action !== "created") {
      return c.json({ ignored: true });
    }
    const issue = issueFromWebhook(body);
    if (!issue || (options.project && issue.project !== options.project)) {
      return c.json({ ignored: true });
    }
    // A fix takes minutes and Sentry expects an answer in seconds, so
    // acknowledge now and let the work continue.
    options.onIssue(issue);
    return c.json({ accepted: issue.shortId }, 202);
  });

  return app;
}
