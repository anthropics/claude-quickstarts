/**
 * AG-UI thread ↔ Managed Agents session registry.
 *
 * The agent itself was created once by setup.ts; here we only create sessions
 * (one per chat thread) that reference it by ID. Sessions are stateful on
 * Anthropic's side — the conversation history lives in the session, so each
 * run only sends the newest user message.
 *
 * Demo scope: the registry is in-memory. A server restart forgets the
 * mapping, and orphaned sessions are not deleted.
 */
import type Anthropic from '@anthropic-ai/sdk';
import { loadAgentIds } from './setup.ts';

export interface ThreadEntry {
  sessionId: string;
  /** Console trace URL for this session — surfaced in the UI once per thread. */
  traceUrl: string;
  traceAnnounced: boolean;
  busy: boolean;
}

// Memoize the creation promise, not the result — two concurrent runs on a
// fresh threadId must share one session instead of racing to create two.
const threads = new Map<string, Promise<ThreadEntry>>();

/** Drop a thread's session mapping (the session ended); the next message
 *  provisions a fresh session. */
export function forgetThread(threadId: string): void {
  threads.delete(threadId);
}

export function getOrCreateThread(client: Anthropic, threadId: string): Promise<ThreadEntry> {
  const existing = threads.get(threadId);
  if (existing) return existing;

  const created = (async (): Promise<ThreadEntry> => {
    const ids = loadAgentIds();
    const session = await client.beta.sessions.create({
      agent: { type: 'agent', id: ids.agentId, version: ids.agentVersion },
      environment_id: ids.environmentId,
      title: `Finance assistant thread ${threadId}`,
    });
    // `default` resolves to the session's actual workspace when Console loads.
    const traceUrl = `https://platform.claude.com/workspaces/default/sessions/${session.id}`;
    console.log(`[session] thread ${threadId} -> ${session.id}\n  trace: ${traceUrl}`);
    return { sessionId: session.id, traceUrl, traceAnnounced: false, busy: false };
  })();

  // Don't cache a failed creation — let the next run retry.
  created.catch(() => threads.delete(threadId));
  threads.set(threadId, created);
  return created;
}
