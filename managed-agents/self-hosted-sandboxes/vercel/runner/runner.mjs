/**
 * Runs inside the Vercel Sandbox: the TS analogue of ../modal/sandbox_runner.py.
 *
 * `client.beta.environments.work.worker(...).handleItem()` is the whole runner:
 * it builds the per-session `AgentToolContext` at `workdir` and downloads the
 * agent's skills into `{workdir}/skills/<name>/`, then runs a `SessionToolRunner`
 * (heartbeat + reconcile + event stream + tool dispatch + result posting) for
 * the session, and force-stops the work item on exit. It reads the same
 * `ANTHROPIC_*` env vars `ant beta:worker poll --on-work` sets, which the webhook
 * injects when it starts this process.
 *
 * Idle policy is the SDK default: the runner stays alive for as long as the
 * session has activity and exits `DEFAULT_MAX_IDLE_MS` (60s) after
 * `session.status_idle` with `stop_reason: end_turn`. Any other event resets
 * the clock, including a `requires_action` idle, where the agent is blocked on
 * the sandbox.
 *
 * Credentials. The agent in this sandbox runs arbitrary bash, so it can read
 * every env var here. The webhook therefore prefers to hand over only the work
 * item's per-session `secret`: the sessions token inside it is scoped to this
 * one session. The environment key, which can claim any session's work in the
 * environment, arrives only when the webhook was deployed with
 * ALLOW_ENVIRONMENT_KEY_IN_SANDBOX=true and the work item carried no secret.
 *
 * Env vars (set per-command by the webhook, not on the sandbox default env):
 *   ANTHROPIC_BASE_URL        - API base URL
 *   ANTHROPIC_SESSION_ID      - session id
 *   ANTHROPIC_ENVIRONMENT_ID  - environment id
 *   ANTHROPIC_WORK_ID         - work item id
 *   ANTHROPIC_WORK_SECRET     - the work item's secret payload (base64url JSON
 *                               carrying `sessions_token`), when it had one
 *   ANTHROPIC_ENVIRONMENT_KEY - the environment key, only in the fallback above
 *   WORKDIR                   - agent working tree (default /workspace)
 */
import Anthropic from "@anthropic-ai/sdk";

// Created + chown'd by the webhook before the runner starts.
const WORKDIR = process.env.WORKDIR ?? "/workspace";

const ctrl = new AbortController();
process.once("SIGTERM", () => ctrl.abort());
process.once("SIGINT", () => ctrl.abort());

/** Extract the sessions token from a work item's secret payload, or null. */
function sessionsToken(secret) {
  if (!secret) return null;
  try {
    const payload = JSON.parse(Buffer.from(secret, "base64url").toString("utf-8"));
    const token = payload && typeof payload === "object" ? payload.sessions_token : null;
    return typeof token === "string" && token !== "" ? token : null;
  } catch {
    return null;
  }
}

const workSecret = process.env.ANTHROPIC_WORK_SECRET || undefined;
const token = sessionsToken(workSecret);
// handleItem() prefers the token inside workSecret for every call it makes.
// Passing it as `environmentKey` too keeps any standing key out of this
// process: left unset, the SDK would read ANTHROPIC_ENVIRONMENT_KEY itself.
const credential = token ?? process.env.ANTHROPIC_ENVIRONMENT_KEY;
if (!credential) {
  console.error(
    "[runner] no credential. Expected ANTHROPIC_WORK_SECRET (or, in the opt-in fallback, ANTHROPIC_ENVIRONMENT_KEY) from the webhook that started this sandbox.",
  );
  process.exit(1);
}

const client = new Anthropic({
  authToken: credential,
  logLevel: "info", // show worker lifecycle (start/idle/heartbeat shutdown) in sandbox logs
});

console.log(
  `[runner] attaching session=${process.env.ANTHROPIC_SESSION_ID} work=${process.env.ANTHROPIC_WORK_ID} credential=${token ? "per-session token" : "ENVIRONMENT KEY"}`,
);
try {
  await client.beta.environments.work
    .worker({
      environmentKey: credential,
      workdir: WORKDIR,
      unrestrictedPaths: true,
      signal: ctrl.signal,
    })
    .handleItem({ workSecret });
} finally {
  console.log("[runner] done");
}
