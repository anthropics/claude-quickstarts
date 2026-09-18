import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { test } from "node:test";
import { budgetCents, fixIssue } from "../src/fixer";
import {
  branchProblem,
  defuseClosingReferences,
  hasClosingReference,
  MAX_BRANCH_COMMITS,
  openPullRequest,
  parseRepo,
  pullRequestState,
} from "../src/github";
import { issueFromArguments, issueFromWebhook, verifySignature } from "../src/sentry";

const secret = "integration-client-secret";
const sign = (body: string, key = secret) => createHmac("sha256", key).update(body, "utf8").digest("hex");

const webhook = {
  action: "created",
  data: {
    issue: {
      id: "4509877862",
      shortId: "SHOP-1A",
      title: "TypeError: Cannot read properties of undefined (reading 'percentOff')",
      web_url: "https://acme.sentry.io/issues/4509877862/",
      project: { id: "1", slug: "shop", name: "Shop" },
    },
  },
};

test("accepts a body signed with the client secret", () => {
  const raw = JSON.stringify(webhook);
  assert.equal(verifySignature(raw, sign(raw), secret), true);
});

test("rejects a missing, wrong-key, malformed, or stale signature", () => {
  const raw = JSON.stringify(webhook);
  assert.equal(verifySignature(raw, undefined, secret), false);
  assert.equal(verifySignature(raw, sign(raw, "someone-elses-secret"), secret), false);
  assert.equal(verifySignature(raw, "not-hex", secret), false);
  assert.equal(verifySignature(raw, sign(raw).slice(0, 10), secret), false);
  assert.equal(verifySignature(`${raw} `, sign(raw), secret), false);
});

test("pulls the issue fields out of a webhook body", () => {
  assert.deepEqual(issueFromWebhook(webhook), {
    id: "4509877862",
    shortId: "SHOP-1A",
    title: webhook.data.issue.title,
    url: "https://acme.sentry.io/issues/4509877862/",
    project: "shop",
  });
});

test("returns null for bodies that are not a usable issue", () => {
  assert.equal(issueFromWebhook(null), null);
  assert.equal(issueFromWebhook({ action: "created", data: {} }), null);
  assert.equal(issueFromWebhook({ data: { issue: { ...webhook.data.issue, shortId: 7 } } }), null);
  assert.equal(issueFromWebhook({ data: { issue: { ...webhook.data.issue, project: {} } } }), null);
});

test("builds an issue from CLI arguments and rejects anything else", () => {
  assert.equal(issueFromArguments("shop-1a").shortId, "SHOP-1A");
  assert.equal(issueFromArguments("SHOP-1A", "https://acme.sentry.io/issues/42/").url, "https://acme.sentry.io/issues/42/");
  assert.throws(() => issueFromArguments("4509877862"));
  assert.throws(() => issueFromArguments("SHOP-1A; rm -rf /"));
  assert.throws(() => issueFromArguments("SHOP-1A", "https://example.com/not-an-issue"));
});

// These follow the parsers that act on the text: Sentry's
// src/sentry/utils/groupreference.py and GitHub's keyword-then-reference rule.
test("finds what Sentry and GitHub would act on", () => {
  for (const text of [
    "Fixes SHOP-99",
    "Resolved: BILLING-7",
    "fixed shop-1a",
    "closes #12",
    "Closes: #12",
    "Fixes:#12",
    "fixes acme/shop#3",
    "closes https://github.com/acme/shop/issues/3",
    "Resolves https://acme.sentry.io/issues/42/",
    // Sentry's span runs through plain words, commas, and newlines.
    "Fixes the crash, BILLING-7",
    "Fix crash when coupon is missing\n\nBILLING-7 is related",
    "Fixes SHOP-1A, BILLING-7",
    // Sentry reduces a markdown link to its text before matching.
    "Fixes [BILLING-7](https://acme.sentry.io/issues/7/)",
    // Not an issue anywhere, but the host cannot know that. It reads as one.
    "Fix off-by-one in the coupon lookup",
  ]) {
    assert.equal(hasClosingReference(text), true, text);
  }
});

test("leaves text alone when neither parser would find a reference", () => {
  for (const prose of [
    "Fix crash when coupon is missing",
    "## Fix\nGuard the lookup",
    "This fixes the lookup and resolves a promise early",
    "Fixed: the total is now an integer",
    // Punctuation ends Sentry's span before the ID, and no keyword is adjacent to it.
    "Fix the crash. BILLING-7 is a separate problem",
    "Fixes (see) BILLING-7",
    // Sentry needs whitespace after the colon, and this is not a GitHub reference.
    "Fixes:SHOP-1A",
    "Handle a cart with no coupon, see BILLING-7",
  ]) {
    assert.equal(hasClosingReference(prose), false, prose);
    assert.equal(defuseClosingReferences(prose), prose);
  }
});

test("defused text no longer holds a reference for either parser", () => {
  for (const text of [
    "Fixes SHOP-99 and closes #12",
    "Resolved: BILLING-7",
    "Fix crash when coupon is missing\n\nBILLING-7 is related",
    "Fixes [BILLING-7](https://acme.sentry.io/issues/7/), closes acme/shop#3",
    "Closes https://github.com/acme/shop/issues/3",
  ]) {
    const defused = defuseClosingReferences(text);
    assert.notEqual(defused, text);
    assert.equal(hasClosingReference(defused), false, defused);
  }
  assert.equal(defuseClosingReferences("Fixes SHOP-99 and closes #12"), "Fixes (see) SHOP-99 and closes (see) #12");
});

// What the host itself writes under the agent's body must link exactly one
// issue, whatever the agent's text ends with.
test("the host's trailer references only its own short ID", () => {
  const trailer = "\n\nFixes SHOP-1A.\n\nOpened by an automated session (sesn_01AbC-9), commits inspected up to abc1234. Review before merging.";
  const spans = [...`Guard the lookup${trailer} Handle a cart with no coupon`.matchAll(/\b(?:fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved):?\s+([A-Za-z0-9_\-\s,]+)\b/gi)];
  assert.deepEqual(spans.map((match) => match[1].match(/\b[A-Z0-9_-]+-[A-Z0-9]+\b/gi)), [["SHOP-1A"]]);
});

const commit = (message: string, sha = "abcdef1234") => ({ sha, commit: { message } });

test("refuses a branch with a closing reference in any commit message", () => {
  assert.equal(branchProblem({ total_commits: 2, commits: [commit("Add test"), commit("Guard the lookup")] }), null);
  assert.match(branchProblem({ total_commits: 2, commits: [commit("Add test"), commit("Guard lookup. Fixes #12", "1234567890")] }) ?? "", /commit 1234567/);
});

test("refuses a branch it cannot inspect in full", () => {
  const many = Array.from({ length: MAX_BRANCH_COMMITS + 1 }, () => commit("Add test"));
  assert.match(branchProblem({ total_commits: many.length, commits: many }) ?? "", /at most 20/);
  // GitHub reports more commits than the page it returned.
  assert.match(branchProblem({ total_commits: 5, commits: [commit("Add test")] }) ?? "", /has 5 commits/);
});

test("takes a concurrency slot before any network call", async () => {
  const config = { repo: parseRepo("https://github.com/acme/shop"), base: "main", githubToken: "x", agentId: "agent_x", environmentId: "env_x", vaultId: "vlt_x", maxCents: 100, maxActive: 0 };
  const issue = { id: "1", shortId: "SHOP-1A", title: "", url: "", project: "" };
  await assert.rejects(fixIssue(issue, config), /already running/);
});

test("gives the same answer every time it is asked", () => {
  // Regex objects with the global flag keep state between calls.
  for (let i = 0; i < 3; i++) {
    assert.equal(hasClosingReference("Handle missing coupon. Fixes #12, fixes BILLING-7"), true);
    assert.equal(hasClosingReference("Handle a cart with no coupon"), false);
  }
});

test("turns AUTOFIX_MAX_USD into whole cents and rejects values that are not money", () => {
  assert.equal(budgetCents(undefined), 1000);
  assert.equal(budgetCents(""), 1000);
  assert.equal(budgetCents("2.5"), 250);
  for (const bad of ["10usd", "NaN", "-5", "0", "0.001", "Infinity"]) assert.throws(() => budgetCents(bad), /AUTOFIX_MAX_USD/);
});

test("parses a GitHub repository URL and rejects other hosts", () => {
  assert.deepEqual(parseRepo("https://github.com/acme/shop.git"), { owner: "acme", name: "shop", url: "https://github.com/acme/shop" });
  assert.deepEqual(parseRepo("https://github.com/acme/shop/"), { owner: "acme", name: "shop", url: "https://github.com/acme/shop" });
  assert.throws(() => parseRepo("https://gitlab.com/acme/shop"));
  assert.throws(() => parseRepo("https://github.com/acme/shop/tree/main"));
});

// Answers GitHub calls from a table keyed by "METHOD path", and records them.
function stubGitHub(routes: Record<string, { status: number; body: unknown }>): { calls: string[]; restore: () => void } {
  const real = globalThis.fetch;
  const calls: string[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input));
    const key = `${init?.method ?? "GET"} ${url.pathname}`;
    calls.push(`${key}${url.search}`);
    const route = routes[key];
    if (!route) throw new Error(`unexpected GitHub call: ${key}`);
    return new Response(JSON.stringify(route.body), { status: route.status });
  }) as typeof fetch;
  return { calls, restore: () => void (globalThis.fetch = real) };
}

const repo = parseRepo("https://github.com/acme/shop");
const pull = { branch: "autofix/SHOP-1A", base: "main", title: "Fix the discount crash", body: "Guards the lookup." };

test("adopts the open pull request when GitHub says one already exists for the branch", async () => {
  const github = stubGitHub({
    "POST /repos/acme/shop/pulls": {
      status: 422,
      body: { message: "Validation Failed", errors: [{ message: "A pull request already exists for acme:autofix/SHOP-1A." }] },
    },
    "GET /repos/acme/shop/pulls": { status: 200, body: [{ html_url: "https://github.com/acme/shop/pull/7" }] },
  });
  try {
    assert.equal(await openPullRequest(repo, "token", pull), "https://github.com/acme/shop/pull/7");
    assert.match(github.calls[1], /head=acme%3Aautofix%2FSHOP-1A/);
    assert.match(github.calls[1], /base=main/);
    assert.match(github.calls[1], /state=open/);
  } finally {
    github.restore();
  }
});

test("still reports other failures to open a pull request, and a 422 with nothing to adopt", async () => {
  const noCommits = stubGitHub({
    "POST /repos/acme/shop/pulls": { status: 422, body: { message: "Validation Failed", errors: [{ message: "No commits between main and autofix/SHOP-1A" }] } },
  });
  try {
    await assert.rejects(openPullRequest(repo, "token", pull), /No commits between/);
    assert.equal(noCommits.calls.length, 1);
  } finally {
    noCommits.restore();
  }
  const nothingOpen = stubGitHub({
    "POST /repos/acme/shop/pulls": { status: 422, body: { message: "Validation Failed", errors: [{ message: "A pull request already exists for acme:autofix/SHOP-1A." }] } },
    "GET /repos/acme/shop/pulls": { status: 200, body: [] },
  });
  try {
    await assert.rejects(openPullRequest(repo, "token", pull), /already exists/);
  } finally {
    nothingOpen.restore();
  }
});

test("tells an open pull request from a merged or closed one", async () => {
  const url = "https://github.com/acme/shop/pull/7";
  for (const [body, expected] of [
    [{ state: "open", merged: false }, "open"],
    [{ state: "closed", merged: true }, "merged"],
    [{ state: "closed", merged: false }, "closed"],
  ] as const) {
    const github = stubGitHub({ "GET /repos/acme/shop/pulls/7": { status: 200, body } });
    try {
      assert.equal(await pullRequestState(repo, "token", url), expected);
    } finally {
      github.restore();
    }
  }
  await assert.rejects(pullRequestState(repo, "token", "https://github.com/acme/shop/issues/7"), /not a pull request URL/);
});
