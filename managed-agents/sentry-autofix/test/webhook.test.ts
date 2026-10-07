import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { test } from "node:test";
import { createApp } from "../src/app";
import type { SentryIssue } from "../src/sentry";

const secret = "integration-client-secret";

function setup(project?: string) {
  const issues: SentryIssue[] = [];
  const app = createApp({ clientSecret: secret, project, onIssue: (issue) => issues.push(issue), status: () => ({}) });
  const deliver = (body: unknown, overrides: Record<string, string> = {}) => {
    const raw = JSON.stringify(body);
    return app.request("/webhooks/sentry", {
      method: "POST",
      body: raw,
      headers: {
        "content-type": "application/json",
        "sentry-hook-resource": "issue",
        "sentry-hook-signature": createHmac("sha256", secret).update(raw).digest("hex"),
        ...overrides,
      },
    });
  };
  return { issues, deliver };
}

const created = {
  action: "created",
  data: {
    issue: {
      id: "42",
      shortId: "SHOP-1A",
      title: "TypeError: boom",
      web_url: "https://acme.sentry.io/issues/42/",
      project: { slug: "shop" },
    },
  },
};

test("a signed issue.created delivery starts one fix and is acknowledged with 202", async () => {
  const { issues, deliver } = setup();
  const response = await deliver(created);
  assert.equal(response.status, 202);
  assert.deepEqual(await response.json(), { accepted: "SHOP-1A" });
  assert.deepEqual(issues.map((issue) => issue.id), ["42"]);
});

test("an unsigned or wrongly signed delivery is rejected and starts nothing", async () => {
  const { issues, deliver } = setup();
  assert.equal((await deliver(created, { "sentry-hook-signature": "" })).status, 401);
  assert.equal((await deliver(created, { "sentry-hook-signature": "00".repeat(32) })).status, 401);
  assert.equal(issues.length, 0);
});

test("other actions, other resources, and other projects are acknowledged and ignored", async () => {
  const { issues, deliver } = setup("shop");
  for (const response of [
    await deliver({ ...created, action: "resolved" }),
    await deliver(created, { "sentry-hook-resource": "error" }),
    await deliver({ ...created, data: { issue: { ...created.data.issue, project: { slug: "billing" } } } }),
    await deliver({ action: "created", data: {} }),
  ]) {
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { ignored: true });
  }
  assert.equal(issues.length, 0);
});
