// The GitHub side, all of it on the host: check that the base branch forces
// pull requests, and open the pull request for a branch the agent pushed. The
// agent asks for the latter through the `open_pull_request` custom tool (see
// src/fixer.ts), so the token that can open pull requests never enters a
// session.

export type Repo = { owner: string; name: string; url: string };

export function parseRepo(url: string): Repo {
  const match = /^https:\/\/github\.com\/([\w.-]+)\/([\w.-]+?)(?:\.git)?\/?$/.exec(url);
  if (!match) throw new Error(`GITHUB_REPO_URL must look like https://github.com/owner/repo, got ${url}`);
  return { owner: match[1], name: match[2], url: `https://github.com/${match[1]}/${match[2]}` };
}

const headers = (token: string) => ({
  authorization: `Bearer ${token}`,
  accept: "application/vnd.github+json",
  "x-github-api-version": "2022-11-28",
  "user-agent": "sentry-autofix-quickstart",
});

const api = (repo: Repo) => `https://api.github.com/repos/${repo.owner}/${repo.name}`;

// The pull request is the human checkpoint, and it only holds if the agent
// cannot skip it. The sandbox has an auto-approved shell and push access, and
// it reads error text that anyone who can trigger an error can write, so a
// prompt injection could try `git push origin HEAD:main`. A rule on the base
// branch is what makes that push fail.
//
// Only a ruleset counts. Classic branch protection exempts repository admins
// unless "Do not allow bypassing the above settings" is ticked, and
// GITHUB_TOKEN usually belongs to the repository's owner, so a classic rule
// would let the very push it is meant to stop go through. A ruleset binds
// everyone who is not on its bypass list, and that list starts empty.
export async function baseBranchProtection(repo: Repo, token: string, base: string): Promise<"ruleset" | "classic_only" | "none"> {
  const rules = await fetch(`${api(repo)}/rules/branches/${encodeURIComponent(base)}?per_page=100`, { headers: headers(token) });
  if (!rules.ok) throw new Error(`GitHub ${rules.status} reading rules for ${repo.owner}/${repo.name}@${base}: check GITHUB_TOKEN and GITHUB_REPO_URL`);
  const active = (await rules.json()) as { type?: string }[];
  if (Array.isArray(active) && active.some((rule) => rule.type === "pull_request")) return "ruleset";

  const branch = await fetch(`${api(repo)}/branches/${encodeURIComponent(base)}`, { headers: headers(token) });
  if (!branch.ok) throw new Error(`GitHub ${branch.status} reading ${repo.owner}/${repo.name}@${base}: does the branch exist?`);
  return ((await branch.json()) as { protected?: boolean }).protected === true ? "classic_only" : "none";
}

// GitHub and Sentry both act on closing keywords ("Fixes SHOP-1A", "Closes
// #12") when text reaches the default branch, in a pull request's title and
// body and in commit messages alike. The agent's text is shaped by untrusted
// error data, so the host adds the one real reference itself (see
// src/fixer.ts) and makes sure nothing else in the text is one.
//
// "Is one" is decided by the parsers that act on it, so these mirror them.
// Sentry's is src/sentry/utils/groupreference.py: markdown links are reduced
// to their text, then a keyword, an optional colon, and whitespace open a span
// of letters, digits, "_", "-", whitespace, and commas, and every short ID
// inside that span is resolved. The span runs through ordinary words and
// across newlines, so "Fix the crash" is only prose as long as no short ID
// follows before the next punctuation mark. GitHub's rule is adjacency: a
// keyword directly followed by #12, owner/repo#12, or an issue URL.
const KEYWORDS = "fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved";
const MARKDOWN_LINK = /\[([^\]]+)\]\([^)]+\)/g;
const sentrySpan = () => new RegExp(String.raw`\b(?:${KEYWORDS}):?\s+([A-Za-z0-9_\-\s,]+)\b`, "gi");
const SENTRY_SHORT_ID = /\b[A-Z0-9_-]+-[A-Z0-9]+\b/i;
const SENTRY_URL = new RegExp(String.raw`\b(?:${KEYWORDS}):?\s+https?:\/\/\S+`, "i");
const GITHUB_REFERENCE = new RegExp(String.raw`\b(?:${KEYWORDS})\s*:?\s*(?:#\d+|[\w.-]+\/[\w.-]+#\d+|https?:\/\/\S+)`, "i");

export function hasClosingReference(text: string): boolean {
  const plain = text.replace(MARKDOWN_LINK, "$1");
  if (SENTRY_URL.test(plain) || GITHUB_REFERENCE.test(plain) || GITHUB_REFERENCE.test(text)) return true;
  return [...plain.matchAll(sentrySpan())].some((match) => SENTRY_SHORT_ID.test(match[1]));
}

// Text with no closing reference is left exactly as written, which is nearly
// all of it ("Fix crash when the coupon is missing", a "## Fix" heading). Text
// that has one gets "(see)" after every keyword: "(" is outside Sentry's span
// and breaks GitHub's adjacency, so neither parser finds a reference.
export function defuseClosingReferences(text: string): string {
  if (!hasClosingReference(text)) return text;
  return text.replace(new RegExp(String.raw`\b(${KEYWORDS})\b`, "gi"), "$1 (see)");
}

// A fix for one issue is a handful of commits. More than this and the branch
// is not what the agent was asked for, and it would also run past the one page
// of commits the host reads.
export const MAX_BRANCH_COMMITS = 20;

type Comparison = { total_commits?: number; commits?: { sha: string; commit: { message: string } }[] };

// Pure so the tests can drive it. Returns why the branch is refused, or null.
export function branchProblem(comparison: Comparison): string | null {
  const commits = comparison.commits ?? [];
  const total = comparison.total_commits ?? commits.length;
  if (total > MAX_BRANCH_COMMITS || total !== commits.length) {
    return `The branch has ${total} commits. A fix for one issue should have at most ${MAX_BRANCH_COMMITS}. Recreate it from the base branch with only the fix.`;
  }
  const flagged = commits.filter((entry) => hasClosingReference(entry.commit.message)).map((entry) => entry.sha.slice(0, 7));
  if (flagged.length === 0) return null;
  return (
    `The message of commit ${flagged.join(", ")} would close or resolve an issue when it reaches the default branch: it has one of the words ` +
    `fix, close, or resolve followed by an issue reference (#12, SHOP-1A) or by something that reads as one (off-by-one). ` +
    `Recreate the commits on a new autofix/ branch with a different verb (Handle, Guard, Correct, Prevent), push it, and call this tool again.`
  );
}

// Commit messages reach the default branch too (a squash merge copies them
// into the merge commit), and the agent writes those inside the sandbox where
// the host cannot edit them. So the host reads them back: every commit is
// inspected or the branch is refused (see branchProblem). `head` is the last
// commit inspected, so a later look can tell whether the branch has moved.
export async function inspectBranch(repo: Repo, token: string, base: string, branch: string): Promise<{ problem: string | null; head: string }> {
  const response = await fetch(`${api(repo)}/compare/${encodeURIComponent(base)}...${encodeURIComponent(branch)}?per_page=100`, {
    headers: headers(token),
  });
  if (!response.ok) throw new Error(`GitHub ${response.status} comparing ${base}...${branch}: was the branch pushed to origin?`);
  const comparison = (await response.json()) as Comparison;
  return { problem: branchProblem(comparison), head: comparison.commits?.at(-1)?.sha ?? "" };
}

// The session can still push between the inspection and the end of its turn.
// If what it pushed would not have passed, the pull request should not be
// waiting for a reviewer as though it had.
export async function closePullRequest(repo: Repo, token: string, url: string, reason: string): Promise<void> {
  const number = /\/pull\/(\d+)$/.exec(url)?.[1];
  if (!number) throw new Error(`not a pull request URL: ${url}`);
  const send = (path: string, method: string, body: unknown) =>
    fetch(`${api(repo)}${path}`, { method, headers: headers(token), body: JSON.stringify(body) });
  await send(`/issues/${number}/comments`, "POST", { body: `Closed by the autofix host.\n\n${reason}` });
  const closed = await send(`/pulls/${number}`, "PATCH", { state: "closed" });
  if (!closed.ok) throw new Error(`GitHub ${closed.status} closing ${url}`);
}

export type PullRequestInput = { branch: string; base: string; title: string; body: string };

export async function openPullRequest(repo: Repo, token: string, input: PullRequestInput): Promise<string> {
  const response = await fetch(`${api(repo)}/pulls`, {
    method: "POST",
    headers: headers(token),
    body: JSON.stringify({ head: input.branch, base: input.base, title: input.title, body: input.body }),
  });
  const payload = (await response.json()) as { html_url?: string; message?: string; errors?: unknown };
  // The host can open the pull request and then die, or fail to record the
  // tool result, before the session hears about it. On the retry GitHub says
  // one already exists. It is for this exact branch, which the caller has just
  // inspected again, so adopt it: reporting a failure here would leave an open
  // pull request the host never revokes push access for and never rechecks.
  if (response.status === 422 && JSON.stringify(payload.errors ?? "").includes("A pull request already exists")) {
    const existing = await findOpenPullRequest(repo, token, input.branch, input.base);
    if (existing) return existing;
  }
  if (!response.ok || !payload.html_url) {
    // The agent reads this text as the tool result, so say what GitHub said
    // ("No commits between main and autofix/...", "A pull request already exists").
    throw new Error(`GitHub ${response.status}: ${payload.message ?? "unknown error"} ${JSON.stringify(payload.errors ?? "")}`);
  }
  return payload.html_url;
}

async function findOpenPullRequest(repo: Repo, token: string, branch: string, base: string): Promise<string | null> {
  const query = new URLSearchParams({ state: "open", head: `${repo.owner}:${branch}`, base });
  const response = await fetch(`${api(repo)}/pulls?${query}`, { headers: headers(token) });
  if (!response.ok) return null;
  const pulls = (await response.json()) as Array<{ html_url?: string }>;
  return pulls[0]?.html_url ?? null;
}

// "open", "closed", or "merged". The recheck at the end of a session only
// makes sense for a pull request that is still waiting for a reviewer.
export async function pullRequestState(repo: Repo, token: string, url: string): Promise<"open" | "closed" | "merged"> {
  const number = /\/pull\/(\d+)$/.exec(url)?.[1];
  if (!number) throw new Error(`not a pull request URL: ${url}`);
  const response = await fetch(`${api(repo)}/pulls/${number}`, { headers: headers(token) });
  if (!response.ok) throw new Error(`GitHub ${response.status} reading ${url}`);
  const pull = (await response.json()) as { state?: string; merged?: boolean };
  if (pull.merged) return "merged";
  return pull.state === "closed" ? "closed" : "open";
}
