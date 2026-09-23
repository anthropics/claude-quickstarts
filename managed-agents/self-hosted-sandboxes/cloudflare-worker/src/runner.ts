/**
 * SandboxRunner Durable Object: the TS analogue of ../modal/sandbox_runner.py.
 *
 * Runs `client.beta.sessions.events.toolRunner()` (the session-side dispatch
 * loop: reconcile + event stream + tool execution + result posting) against an
 * in-isolate fake tool registry. `SessionToolRunner` is dispatch-only, so the
 * work-item lifecycle (heartbeat + force-stop) is owned here, since the DO is
 * the work-item lessee. `EnvironmentWorker` would compose all of this, but it
 * pulls in the Node-only `agent-toolset/node` module which a Workers isolate
 * can't run.
 *
 * Idle policy is the SDK default: `toolRunner()` exits `maxIdleMs` after
 * `session.status_idle` with `stop_reason: end_turn`. Any other event resets
 * the clock, including a `requires_action` idle, where the agent is blocked on
 * the DO.
 *
 * The environment key stays in this Durable Object, which is code you wrote.
 * The agent never sees it: its bash is a stub and its filesystem is a Map.
 */
import Anthropic from "@anthropic-ai/sdk";
import { DurableObject } from "cloudflare:workers";
import type { Env } from "./index";
import { type FakeFS, fakeTools } from "./tools";

const HEARTBEAT_DEFAULT_MS = 30_000;

export interface StartOpts {
  sessionId: string;
  environmentKey: string;
  workId: string;
  environmentId: string;
}

const isFatal4xx = (e: unknown): boolean => {
  const s = (e as { status?: number })?.status;
  return typeof s === "number" && s >= 400 && s < 500 && s !== 408 && s !== 429;
};

export class SandboxRunner extends DurableObject<Env> {
  private fs: FakeFS = new Map();
  private ctrl: AbortController | undefined;

  async isLive(): Promise<boolean> {
    return this.ctrl !== undefined && !this.ctrl.signal.aborted;
  }

  async start(opts: StartOpts): Promise<void> {
    if (await this.isLive()) return;
    const ctrl = new AbortController();
    this.ctrl = ctrl;

    const client = new Anthropic({
      authToken: opts.environmentKey,
      baseURL: this.env.ANTHROPIC_BASE_URL,
      logLevel: "info", // surface runner lifecycle in `wrangler tail`
    });

    // Run detached so the webhook can return.
    this.ctx.waitUntil(
      this.runWorkItem(client, opts, ctrl).finally(() => {
        if (this.ctrl === ctrl) this.ctrl = undefined;
      }),
    );
  }

  async stop(): Promise<void> {
    this.ctrl?.abort();
  }

  /**
   * Heartbeat the lease + run the session tool runner; force-stop on exit.
   * `SessionToolRunner` only owns the dispatch loop, so the work-item lifecycle
   * lives here. `EnvironmentWorker` composes the same thing internally.
   */
  private async runWorkItem(client: Anthropic, opts: StartOpts, ctrl: AbortController): Promise<void> {
    // `client` is authed with the environment key, the single credential for
    // every per-session call, the heartbeat, and the force-stop.
    const heartbeat = this.heartbeatLoop(client, opts, ctrl);
    try {
      for await (const call of client.beta.sessions.events.toolRunner(opts.sessionId, {
        tools: fakeTools(this.fs),
        // default: exit 60s after session.status_idle/end_turn, reset on any
        // other event. Pass 0 to run until the session ends.
        signal: ctrl.signal,
      })) {
        console.log(
          `[runner] dispatched tool=${call.name} tool_use_id=${call.toolUseId} is_error=${call.isError} posted=${call.posted}`,
        );
      }
    } finally {
      ctrl.abort();
      await heartbeat;
      await client.beta.environments.work
        .stop(opts.workId, { environment_id: opts.environmentId, force: true })
        .catch((e) => {
          const status = (e as { status?: number })?.status;
          if (status !== 409) console.error(`[runner] /stop failed status=${status ?? "?"}`);
        });
    }
  }

  private async heartbeatLoop(client: Anthropic, opts: StartOpts, ctrl: AbortController): Promise<void> {
    let last = "NO_HEARTBEAT";
    let intervalMs = HEARTBEAT_DEFAULT_MS;
    while (!ctrl.signal.aborted) {
      try {
        const r = await client.beta.environments.work.heartbeat(
          opts.workId,
          { environment_id: opts.environmentId, expected_last_heartbeat: last },
          { signal: ctrl.signal },
        );
        last = r.last_heartbeat;
        if (r.ttl_seconds > 0) intervalMs = Math.max(1_000, Math.min((r.ttl_seconds * 1000) / 2, HEARTBEAT_DEFAULT_MS));
        if (r.state === "stopping" || r.state === "stopped" || !r.lease_extended) {
          console.log(`[runner] heartbeat shutdown state=${r.state} extended=${r.lease_extended}`);
          ctrl.abort();
          return;
        }
      } catch (e) {
        if (ctrl.signal.aborted) return;
        if (isFatal4xx(e)) {
          console.error(`[runner] permanent heartbeat failure status=${(e as { status?: number })?.status}`);
          ctrl.abort();
          return;
        }
        console.warn(`[runner] transient heartbeat failure status=${(e as { status?: number })?.status ?? "?"}`);
      }
      await new Promise<void>((resolve) => {
        const t = setTimeout(resolve, intervalMs);
        ctrl.signal.addEventListener("abort", () => (clearTimeout(t), resolve()), { once: true });
      });
    }
  }
}
