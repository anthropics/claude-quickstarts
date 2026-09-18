import { cookies } from "next/headers";
import { SESSION_COOKIE, client, ownedSession } from "@/lib/client";

/**
 * The SSE proxy, and the only reason the server is in the streaming path at
 * all: the API key stays here. Everything else (accumulation, rendering,
 * reconnect) happens in the browser (see `src/lib/use-managed-agent-session.ts`).
 *
 * `event_deltas` is the query param this quickstart is about. It repeats per
 * event type: `agent.message` previews carry the reply token by token, and
 * `agent.thinking` previews are start-only: the `event_start` fires the
 * moment the model begins extended thinking, where the buffered event only
 * lands when it finishes. Without the param the same connection still works,
 * but the reply arrives as one buffered `agent.message` after seconds of
 * silence.
 *
 * The stream is a tail, not a replay: events emitted before the connection
 * existed only live in `events.list`, which is why the client re-fetches the
 * log on every connect. One connection per page, scoped to the session (not
 * a turn), opened by EventSource so the browser owns retry.
 */
export async function GET(request: Request) {
  const jar = await cookies();
  const cookie = jar.get(SESSION_COOKIE)?.value;
  if (!cookie) return new Response(null, { status: 401 });
  // The cookie is browser input. Only tail a session this app's agent owns.
  const session = await ownedSession(cookie).catch(() => null);
  if (!session) return new Response(null, { status: 403 });

  let tail;
  try {
    tail = await client.beta.sessions.events.stream(session.id, {
      event_deltas: ["agent.message", "agent.thinking"],
    });
  } catch (error) {
    // The session is gone (archived or deleted under this tab). The client's
    // error re-sync notices the cookie has moved and reloads into a new one.
    const detail = error instanceof Error ? error.message : String(error);
    return Response.json({ error: detail }, { status: 502 });
  }
  // The browser hung up (tab closed, page navigated): drop the upstream tail.
  request.signal.addEventListener("abort", () => tail.controller.abort());

  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      try {
        for await (const event of tail) {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
        }
      } catch {
        // aborted mid-iteration, and EventSource reconnects if the page is alive
      }
      try {
        controller.close();
      } catch {
        // already closed by the abort path
      }
    },
  });

  return new Response(body, {
    headers: {
      "content-type": "text/event-stream",
      "cache-control": "no-cache, no-transform",
    },
  });
}
