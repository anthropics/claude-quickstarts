// The Sentry side of the loop: authenticate a webhook delivery and pull out
// the few issue fields the fixer needs. Everything else about the issue
// (stack trace, events, Seer's analysis) the agent reads itself through the
// Sentry MCP server.

import { createHmac, timingSafeEqual } from "node:crypto";

export type SentryIssue = {
  id: string;
  shortId: string;
  title: string;
  url: string;
  project: string;
};

// Sentry signs the raw request body with the integration's client secret
// (HMAC-SHA256, hex) and sends it as Sentry-Hook-Signature. Verify against the
// bytes as received: re-serializing the parsed JSON changes them.
export function verifySignature(rawBody: string, signature: string | undefined, secret: string): boolean {
  if (!signature) return false;
  const expected = createHmac("sha256", secret).update(rawBody, "utf8").digest();
  const received = Buffer.from(signature, "hex");
  return received.length === expected.length && timingSafeEqual(received, expected);
}

// An issue webhook body is {action, data: {issue: {...}}}. Returns null for
// anything that is not a usable issue, so the caller can 200 and move on.
export function issueFromWebhook(body: unknown): SentryIssue | null {
  const issue = (body as { data?: { issue?: Record<string, unknown> } } | null)?.data?.issue;
  if (!issue) return null;
  const project = issue.project as { slug?: unknown } | undefined;
  const fields = {
    id: issue.id,
    shortId: issue.shortId,
    title: issue.title,
    url: issue.web_url ?? issue.permalink,
    project: project?.slug,
  };
  for (const value of Object.values(fields)) {
    if (typeof value !== "string" || !value) return null;
  }
  return fields as SentryIssue;
}

// `npm run fix -- SHOP-1A [issue URL]` starts a fix without a webhook. The
// agent looks the issue up through the Sentry MCP server, so nothing here
// calls the Sentry API.
// A short ID is what links the pull request back ("Fixes SHOP-1A"), so a URL
// alone is not enough: Sentry issue URLs carry the numeric ID.
export function issueFromArguments(shortId: string, url = ""): SentryIssue {
  if (!/^[A-Z0-9][A-Z0-9_-]{0,62}-[A-Z0-9]+$/i.test(shortId)) {
    throw new Error(`expected a Sentry short ID like SHOP-1A, got ${shortId}`);
  }
  if (url && !/^https:\/\/[\w.-]+\/\S*issues\/\d+/.test(url)) throw new Error(`not a Sentry issue URL: ${url}`);
  return { id: shortId.toUpperCase(), shortId: shortId.toUpperCase(), title: "", url, project: "" };
}
