/**
 * Per-session Cloudflare Container that runs `ant beta:worker run`. The CLI
 * owns heartbeat, backlog reconcile, SSE stream, tool execution
 * (bash/read/write/edit/glob/grep), the work-item force-stop on exit, and the
 * idle policy: it exits `--max-idle` after `session.status_idle` with
 * `stop_reason: end_turn`, and any other event resets the clock.
 *
 * The DO owns the *Cloudflare* container lifetime: a session-status watcher
 * renews `sleepAfter` on every event so CF doesn't reclaim the VM out from
 * under a live `ant beta:worker run`. When the CLI exits (idle, terminate,
 * lease lapse) the container process exits and CF stops the container.
 */
import Anthropic from "@anthropic-ai/sdk";
import { Container } from "@cloudflare/containers";
import type { Env } from "./index";

const STREAM_BACKOFF_MS = 1_000;
const STREAM_BACKOFF_CAP_MS = 10_000;

export interface DispatchOpts {
  sessionId: string;
  environmentKey: string;
  workId: string;
  environmentId: string;
  baseURL: string;
}

export class SandboxContainer extends Container<Env> {
  // Backstop only: fires if lifecycleWatch's stream dies mid-session. The
  // watch loop renews this on every session event; `ant beta:worker run`'s
  // `--max-idle` is the real idle policy and exits the container long before
  // this fires.
  sleepAfter = "5m";
  manualStart = true;

  private watchCtrl: AbortController | undefined;

  async isLive(): Promise<boolean> {
    return this.ctx.container?.running ?? false;
  }

  async dispatch(opts: DispatchOpts): Promise<void> {
    if (await this.isLive()) return;
    await this.start({
      // Env contract for `ant beta:worker run`. ANTHROPIC_ENVIRONMENT_KEY
      // authenticates the work-item calls (heartbeat / ack / force-stop), the
      // session event stream, and the skills download. The CLI has no
      // per-session credential, so the agent's bash can read this key: see the
      // README, "One key, shared trust".
      envVars: {
        ANTHROPIC_BASE_URL: opts.baseURL,
        ANTHROPIC_ENVIRONMENT_KEY: opts.environmentKey,
        ANTHROPIC_SESSION_ID: opts.sessionId,
        ANTHROPIC_ENVIRONMENT_ID: opts.environmentId,
        ANTHROPIC_WORK_ID: opts.workId,
      },
    });

    this.watchCtrl?.abort();
    const ctrl = new AbortController();
    this.watchCtrl = ctrl;
    this.ctx.waitUntil(
      this.lifecycleWatch(opts, ctrl).finally(() => {
        if (this.watchCtrl === ctrl) this.watchCtrl = undefined;
      }),
    );
  }

  override onStop(): void {
    this.watchCtrl?.abort();
  }

  /**
   * Stream session status and renew the container's activity timeout on
   * every event. The CLI inside the container owns dispatch + heartbeat +
   * the work-item force-stop + the end_turn idle policy; this loop only
   * keeps Cloudflare's `sleepAfter` from reclaiming the VM mid-session.
   */
  private async lifecycleWatch(opts: DispatchOpts, ctrl: AbortController): Promise<void> {
    const client = new Anthropic({ authToken: opts.environmentKey, baseURL: opts.baseURL });
    let backoff = STREAM_BACKOFF_MS;
    while (!ctrl.signal.aborted) {
      try {
        const stream = await client.beta.sessions.events.stream(opts.sessionId, undefined, {
          signal: ctrl.signal,
        });
        for await (const ev of stream) {
          backoff = STREAM_BACKOFF_MS;
          this.renewActivityTimeout();
          if (ev.type === "session.status_terminated" || ev.type === "session.deleted") {
            await this.stop().catch(() => {});
            return;
          }
        }
      } catch {
        // network drop or abort: fall through to the backoff/abort check
      }
      if (ctrl.signal.aborted || !(await this.isLive())) break;
      await new Promise((r) => setTimeout(r, backoff));
      backoff = Math.min(backoff * 2, STREAM_BACKOFF_CAP_MS);
    }
  }
}
