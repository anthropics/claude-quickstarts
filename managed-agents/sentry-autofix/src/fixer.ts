// One Sentry issue in, one Managed Agents session out. The session clones the
// repository, reads the issue and Seer's analysis through the Sentry MCP
// server, reproduces and fixes the bug, pushes a branch, and asks this host to
// open the pull request. There is no database: a session's metadata records
// which issue it is for, and its event log records how far the fix got, so a
// restarted host picks up where the last one stopped.

import Anthropic from "@anthropic-ai/sdk";
import { readFileSync } from "node:fs";
import { baseBranchProtection, closePullRequest, defuseClosingReferences, inspectBranch, openPullRequest, parseRepo, pullRequestState, type Repo } from "./github";
import type { SentryIssue } from "./sentry";

export const client = new Anthropic();

type SessionEvent = Anthropic.Beta.Sessions.BetaManagedAgentsSessionEvent | Anthropic.Beta.Sessions.BetaManagedAgentsStreamSessionEvents;

export function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} must be set in .env (see .env.example)`);
  return value;
}

export type Config = {
  repo: Repo;
  base: string;
  githubToken: string;
  agentId: string;
  environmentId: string;
  vaultId: string;
  maxCents: number;
  maxActive: number;
};

// `ant apply` (run by ./agents/setup.sh) records what it created in
// claude-lock.json, keyed by file path. This quickstart has one agent and one
// environment, so the kind is enough to find each.
function lockedId(kind: "agent" | "environment"): string {
  let lock: { resources?: Record<string, { kind?: string; id?: string }> };
  try {
    lock = JSON.parse(readFileSync("claude-lock.json", "utf8"));
  } catch {
    throw new Error("claude-lock.json is missing or unreadable: run ./agents/setup.sh first");
  }
  const id = Object.values(lock.resources ?? {}).find((resource) => resource.kind === kind)?.id;
  if (!id) throw new Error(`claude-lock.json has no ${kind}: run ./agents/setup.sh`);
  return id;
}

// Dollars in .env, whole cents on the wire. Exported for the tests.
export function budgetCents(value: string | undefined): number {
  const dollars = Number(value || 10);
  if (!Number.isFinite(dollars) || dollars < 0.01) throw new Error(`AUTOFIX_MAX_USD must be a number of dollars like 10, got "${value}"`);
  return Math.round(dollars * 100);
}

// Every mistake in .env fails here, at startup, not in a session created
// after a webhook has already been answered 202.
export function loadConfig(): Config {
  const maxActive = Number(process.env.AUTOFIX_MAX_ACTIVE || 3);
  if (!Number.isInteger(maxActive) || maxActive < 1) throw new Error("AUTOFIX_MAX_ACTIVE must be a whole number, 1 or more");
  return {
    repo: parseRepo(requireEnv("GITHUB_REPO_URL")),
    base: process.env.GITHUB_BASE_BRANCH || "main",
    githubToken: requireEnv("GITHUB_TOKEN"),
    agentId: lockedId("agent"),
    environmentId: lockedId("environment"),
    vaultId: requireEnv("CLAUDE_VAULT_ID"),
    maxCents: budgetCents(process.env.AUTOFIX_MAX_USD),
    maxActive,
  };
}

// Must equal mcp_servers[].url in agents/issue-fixer/agent.yaml.
const SENTRY_MCP_URL = "https://mcp.sentry.dev/mcp";

// The two setup mistakes that would otherwise cost a session each time:
// nothing forcing the agent's work through a pull request, and no Sentry
// credential for the agent to read the issue with. Returns what to fix, or
// null when the setup is sound.
export async function preflight(config: Config): Promise<string | null> {
  const where = `${config.repo.url}@${config.base}`;
  const protection = await baseBranchProtection(config.repo, config.githubToken, config.base);
  if (protection === "classic_only") {
    return (
      `${where} has a classic branch protection rule but no ruleset. Classic rules let repository admins push directly unless\n` +
      `"Do not allow bypassing" is ticked, and GITHUB_TOKEN is usually an admin's. Add a branch ruleset with "Require a pull request\n` +
      `before merging" (Settings > Rules > Rulesets, enforcement Active), then start again.`
    );
  }
  if (protection === "none") {
    return (
      `${where} is not protected, so nothing forces the agent's work through a pull request.\n` +
      `Add a branch ruleset with "Require a pull request before merging" (Settings > Rules > Rulesets, enforcement Active), then start again.`
    );
  }
  for await (const credential of client.beta.vaults.credentials.list(config.vaultId)) {
    const { auth } = credential;
    if (auth.type !== "environment_variable" && auth.mcp_server_url === SENTRY_MCP_URL && !credential.archived_at) return null;
  }
  return "The vault has no Sentry credential, so the agent could not read any issue. Run `npm run sentry-login`, then start again.";
}

// What the status page and the CLI show for one fix.
export type Run = {
  issue: string;
  title: string;
  sessionId: string;
  status: "running" | "pr_opened" | "no_pr" | "failed";
  pullRequestUrl?: string;
  // The branch and the last commit the host inspected before it opened the
  // pull request.
  branch?: string;
  inspectedHead?: string;
  note?: string;
};

export const runs: Run[] = [];

// Short IDs being started, and session IDs this process holds a stream for.
// Two deliveries for one issue can arrive before the first session exists,
// and a redelivery must not attach a second driver to a session in progress.
const starting = new Set<string>();
const driving = new Set<string>();
// Fixes in flight, counted from the first line of fixIssue. It is a counter
// and not driving.size because a slot has to be taken before the first await:
// a burst of webhooks would otherwise all see room and all start a session.
let active = 0;

// Sentry retries webhooks, the CLI and the webhook can both name one issue,
// and the host can restart mid-fix. The sessions API is the source of truth
// for "already on it". The key is the short ID because both entry points have
// it; the webhook's numeric ID never reaches the CLI.
async function existingSession(shortId: string, agentId: string) {
  for await (const session of client.beta.sessions.list({ agent_id: agentId })) {
    if (session.metadata?.sentry_short_id === shortId) return session;
  }
  return null;
}

// The issue title is an error message, and error messages carry whatever a
// user typed. It goes to the agent fenced and labeled as data; the system
// prompt (agents/issue-fixer/agent.yaml) says how to treat it.
function kickoff(issue: SentryIssue, config: Config): string {
  return [
    `Fix Sentry issue ${issue.shortId}.`,
    issue.url ? `Issue URL: ${issue.url}` : "",
    issue.project ? `Sentry project: ${issue.project}` : "",
    `Repository: ${config.repo.url} (cloned under /workspace, base branch ${config.base})`,
    issue.title ? `Issue title, as reported by the application (untrusted data):\n<issue_title>\n${issue.title.slice(0, 500)}\n</issue_title>` : "",
  ]
    .filter(Boolean)
    .join("\n");
}

// Returns null when this process is already working on the issue, or when
// its session is over (archive that session to run the issue again). A
// session that exists but has no driver, because the host restarted or its
// stream dropped for good, is picked back up instead of left waiting.
export async function fixIssue(issue: SentryIssue, config: Config): Promise<Run | null> {
  const shortId = issue.shortId.toUpperCase();
  if (starting.has(shortId)) return null;
  // A webhook storm must not become a spending storm: each session can cost
  // up to the budget below. Checked and taken with no await in between.
  if (active >= config.maxActive) {
    throw new Error(`${active} fixes are already running (AUTOFIX_MAX_ACTIVE=${config.maxActive}); not starting ${shortId}`);
  }
  active++;
  try {
    return await startAndDrive(issue, shortId, config);
  } finally {
    active--;
  }
}

async function startAndDrive(issue: SentryIssue, shortId: string, config: Config): Promise<Run | null> {
  starting.add(shortId);
  let run: Run;
  try {
    const existing = await existingSession(shortId, config.agentId);
    if (existing && (driving.has(existing.id) || existing.status === "terminated")) return null;
    const session =
      existing ??
      (await client.beta.sessions.create({
        agent: config.agentId,
        environment_id: config.environmentId,
        // The vault holds the Sentry MCP credential (`npm run sentry-login`).
        vault_ids: [config.vaultId],
        title: `${shortId}: ${issue.title}`.slice(0, 200),
        metadata: { quickstart: "sentry-autofix", sentry_short_id: shortId, sentry_issue_id: issue.id },
        // Nobody is watching a session a webhook started, so cap what it can
        // spend. The amount is whole cents, as a string.
        budget: { type: "limit", max_list_cost: { amount: String(config.maxCents), currency: "USD" } },
        resources: [
          {
            type: "github_repository",
            url: config.repo.url,
            // Held by a git proxy outside the sandbox; the agent can push but
            // cannot read the token.
            authorization_token: config.githubToken,
            checkout: { type: "branch", name: config.base },
          },
        ],
        // The kickoff travels with the create call, so a session can never
        // exist without its instructions. drive() replays the event log, so
        // nothing emitted before its stream opens is missed.
        initial_events: [{ type: "user.message", content: [{ type: "text", text: kickoff(issue, config) }] }],
      }));
    run = { issue: shortId, title: issue.title || (existing?.title ?? ""), sessionId: session.id, status: "running" };
    runs.unshift(run);
    driving.add(session.id);
    console.log(`[managed-agent] ${shortId} -> session ${session.id}${existing ? " (picked back up)" : ""}`);
  } finally {
    starting.delete(shortId);
  }

  try {
    await drive(run, { ...issue, shortId }, config);
  } catch (err) {
    run.status = "failed";
    run.note = err instanceof Error ? err.message : String(err);
    console.error(`[managed-agent] ${run.sessionId} failed:`, err);
  } finally {
    driving.delete(run.sessionId);
  }
  return run;
}

const RECONNECTS = 5;
// The tool result is also the record a restarted host rebuilds a run from.
const PR_OPENED = "Pull request opened: ";
const PR_RESULT = /^Pull request opened: (\S+) \(branch (\S+), inspected at ([0-9a-f]+)\)/;

// Follows the session to the end of the fix (minutes), answering the one
// custom tool and logging progress. Tool names are logged; tool inputs are
// not, because they are derived from production error data.
//
// Every connect does the same thing: open the live stream, replay the whole
// event log, then tail the stream, skipping events already seen. A first
// connect, a reconnect after a dropped stream, and a host that restarted
// mid-fix are therefore one code path. The event log also says which tool
// calls already have an answer, so none is answered twice.
async function drive(run: Run, issue: SentryIssue, config: Config): Promise<void> {
  const seen = new Set<string>();
  const answered = new Set<string>();

  const handle = async (event: SessionEvent): Promise<boolean> => {
    switch (event.type) {
      case "agent.tool_use":
        console.log(`[managed-agent] ${run.sessionId} tool: ${event.name}`);
        break;
      case "agent.mcp_tool_use":
        console.log(`[managed-agent] ${run.sessionId} sentry: ${event.name}`);
        break;
      case "agent.custom_tool_use": {
        if (answered.has(event.id)) break;
        answered.add(event.id);
        const result = await handleCustomTool(event.name, event.input, run, issue, config);
        await client.beta.sessions.events.send(run.sessionId, {
          events: [
            {
              type: "user.custom_tool_result",
              custom_tool_use_id: event.id,
              content: [{ type: "text", text: result.text }],
              is_error: result.isError,
            },
          ],
        });
        break;
      }
      case "agent.message": {
        // The last message is the agent's own summary: the pull request URL,
        // or why there is none.
        const text = event.content.map((block) => (block.type === "text" ? block.text : "")).join("").trim();
        if (text) run.note = text.slice(0, 1000);
        break;
      }
      case "session.error":
        console.warn(`[managed-agent] ${run.sessionId} error: ${JSON.stringify(event.error)}`);
        break;
      case "session.status_idle": {
        // Idle with requires_action is the session waiting on a custom tool
        // result, not the end of the fix.
        const stop = event.stop_reason?.type;
        if (stop === "requires_action") break;
        if (run.status === "running") run.status = stop === "end_turn" ? "no_pr" : "failed";
        if (stop !== "end_turn") run.note = `stopped: ${stop}`;
        return true;
      }
      case "session.status_terminated":
        if (run.status === "running") run.status = "failed";
        run.note = "session terminated";
        return true;
    }
    return false;
  };

  for (let attempt = 0; attempt <= RECONNECTS; attempt++) {
    if (attempt > 0) {
      console.warn(`[managed-agent] ${run.sessionId} stream ended early, reconnecting (${attempt}/${RECONNECTS})`);
      await new Promise((resolve) => setTimeout(resolve, 2000 * attempt));
    }
    // Stream first: it buffers from the moment it opens, so nothing falls
    // between the end of the replay and the start of the tail.
    const stream = await client.beta.sessions.events.stream(run.sessionId);
    const history: Anthropic.Beta.Sessions.BetaManagedAgentsSessionEvent[] = [];
    for await (const event of client.beta.sessions.events.list(run.sessionId, { order: "asc" })) history.push(event);

    // Rebuild what an earlier connection (or an earlier process) already did
    // before replaying, so the replay does not do it again.
    for (const event of history) {
      if (event.type !== "user.custom_tool_result") continue;
      answered.add(event.custom_tool_use_id);
      const text = event.content?.map((block) => (block.type === "text" ? block.text : "")).join("") ?? "";
      const opened = event.is_error ? null : PR_RESULT.exec(text);
      if (opened) {
        [, run.pullRequestUrl, run.branch, run.inspectedHead] = opened;
        run.status = "pr_opened";
      }
    }

    let done = false;
    for (const event of history) {
      if (seen.has(event.id)) continue;
      seen.add(event.id);
      // The log can hold more than one idle. Only the last one is current.
      done = await handle(event);
    }
    if (!done) {
      // Step the iterator by hand. The SDK's stream rethrows every error but
      // an abort, so a TCP reset or a proxy idle timeout would otherwise throw
      // straight past the reconnect loop and orphan a session that is still
      // working. A stream error means "ended early". An error from handling an
      // event is a real failure and still propagates.
      const events = stream[Symbol.asyncIterator]();
      for (;;) {
        let next: Awaited<ReturnType<typeof events.next>>;
        try {
          next = await events.next();
        } catch (err) {
          console.warn(`[managed-agent] ${run.sessionId} stream error: ${err instanceof Error ? err.message : err}`);
          break;
        }
        if (next.done) break;
        const event = next.value;
        // Token previews (event_start, event_delta) carry no id of their own.
        const { id } = event as { id?: unknown };
        if (typeof id === "string") {
          if (seen.has(id)) continue;
          seen.add(id);
        }
        done = await handle(event);
        if (done) break;
      }
    } else {
      stream.controller.abort();
    }
    if (done) {
      await recheckBranch(run, config);
      console.log(`[managed-agent] ${run.sessionId} done: ${run.status} ${run.pullRequestUrl ?? ""}`);
      return;
    }
  }
  throw new Error("lost the event stream and could not reconnect. The session may still be working: run the issue again to pick it back up");
}

// Once the pull request is open the session has no more pushing to do, so the
// host takes its push access away: the repository's token lives on the
// session resource, outside the sandbox, and can be replaced while the
// session runs. The agent is paused on the tool call for the whole of
// inspect, open, and revoke, so nothing can land between them.
export async function revokePush(sessionId: string): Promise<void> {
  for await (const resource of client.beta.sessions.resources.list(sessionId)) {
    if (resource.type !== "github_repository") continue;
    await client.beta.sessions.resources.update(resource.id, { session_id: sessionId, authorization_token: "revoked-after-pull-request" });
  }
}

const RECHECKS = 3;

// The backstop for revokePush, run when the session's turn is over and nothing
// else will send it messages. If the branch moved after the host inspected it
// and would no longer pass, or if the host cannot inspect it at all, the pull
// request is closed with a comment saying why. Failing closed costs a person a
// click to reopen a good pull request after a GitHub outage. Failing open
// would leave an uninspected one waiting for review as though it had passed.
async function recheckBranch(run: Run, config: Config): Promise<void> {
  if (!run.pullRequestUrl || !run.branch) return;
  // Picking a finished issue back up replays its log and lands here again.
  // If the pull request has since merged or been closed there is nothing left
  // to guard, and with "delete head branches" on the compare below would 404
  // and post a "closed by the host" comment on a merged pull request.
  try {
    if ((await pullRequestState(config.repo, config.githubToken, run.pullRequestUrl)) !== "open") return;
  } catch (err) {
    console.warn(`[managed-agent] ${run.sessionId} could not read the pull request's state, rechecking anyway:`, err instanceof Error ? err.message : err);
  }
  let reason = "";
  for (let attempt = 1; attempt <= RECHECKS; attempt++) {
    try {
      const { problem, head } = await inspectBranch(config.repo, config.githubToken, config.base, run.branch);
      if (head === run.inspectedHead || !problem) return;
      reason = `The session pushed more commits after this pull request was opened, and the branch no longer passes inspection.\n\n${problem}`;
      break;
    } catch (err) {
      reason = `The host could not inspect the branch again after the session ended (${err instanceof Error ? err.message : err}), so it cannot tell whether commits were added after this pull request was opened. Check the commits, then reopen it.`;
      if (attempt < RECHECKS) await new Promise((resolve) => setTimeout(resolve, 2000 * attempt));
    }
  }
  await closePullRequest(config.repo, config.githubToken, run.pullRequestUrl, reason);
  run.status = "failed";
  run.note = `closed ${run.pullRequestUrl}: ${reason.split("\n")[0]}`;
}

// The agent proposes; the host decides. Repository, base branch, and the link
// to the Sentry issue all come from this process's config and the trigger,
// never from the session.
async function handleCustomTool(
  name: string,
  input: Record<string, unknown>,
  run: Run,
  issue: SentryIssue,
  config: Config,
): Promise<{ text: string; isError: boolean }> {
  if (name !== "open_pull_request") return { text: `Unknown tool: ${name}`, isError: true };
  if (run.pullRequestUrl) return { text: `A pull request is already open: ${run.pullRequestUrl}`, isError: true };
  const { branch, title, body } = input;
  if (typeof branch !== "string" || !/^autofix\/[\w.-]{1,100}$/.test(branch)) {
    return { text: 'branch must look like "autofix/<issue-short-id>"', isError: true };
  }
  if (typeof title !== "string" || !title.trim() || typeof body !== "string" || !body.trim()) {
    return { text: "title and body are required", isError: true };
  }
  try {
    const { problem, head } = await inspectBranch(config.repo, config.githubToken, config.base, branch);
    if (problem) return { text: problem, isError: true };
    const url = await openPullRequest(config.repo, config.githubToken, {
      branch,
      base: config.base,
      title: defuseClosingReferences(title).slice(0, 200),
      // "Fixes SHORT-ID" is what links the pull request to the Sentry issue:
      // Sentry annotates the issue when it sees it and resolves the issue when
      // a release contains the merge commit.
      // The period after the short ID matters: Sentry reads a reference span
      // through words and newlines until punctuation, so without it the span
      // would run on into whatever follows. The rest of this trailer avoids
      // the closing verbs for the same reason.
      body: `${defuseClosingReferences(body).slice(0, 20_000)}\n\nFixes ${issue.shortId}.\n\nOpened by an automated session (${run.sessionId}), commits inspected up to ${head.slice(0, 7)}. Review before merging.`,
    });
    run.status = "pr_opened";
    run.pullRequestUrl = url;
    run.branch = branch;
    run.inspectedHead = head;
    // Best effort: if this fails the session can still push, and the recheck
    // at the end of the session is what catches it.
    await revokePush(run.sessionId).catch((err) => console.warn(`[managed-agent] ${run.sessionId} could not revoke push access:`, err));
    return { text: `${PR_OPENED}${url} (branch ${branch}, inspected at ${head})`, isError: false };
  } catch (err) {
    return { text: err instanceof Error ? err.message : String(err), isError: true };
  }
}
