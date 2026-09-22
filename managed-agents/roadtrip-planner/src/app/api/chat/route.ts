import { cookies } from "next/headers";
import { SESSION_COOKIE, client, ownedSession } from "@/lib/client";

/**
 * One chat turn is one `user.message` event. That is the entire route: the
 * reply streams to the client over its own session tail (`/api/stream`), so
 * nothing here waits for the agent, and the answer outlives this request:
 * close the tab mid-paragraph and the finished reply is in the event log
 * when you come back.
 */
const MAX_MESSAGE_CHARS = 8_000;

export async function POST(request: Request) {
  const { text } = (await request.json().catch(() => ({}))) as { text?: unknown };
  const jar = await cookies();
  let session;
  try {
    session = await ownedSession(jar.get(SESSION_COOKIE)?.value);
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : String(error) }, { status: 500 });
  }
  if (!session) {
    return Response.json({ error: "unknown session - reload the page" }, { status: 403 });
  }
  if (typeof text !== "string" || !text.trim()) {
    return Response.json({ error: "empty message" }, { status: 400 });
  }
  if (text.length > MAX_MESSAGE_CHARS) {
    return Response.json({ error: `message is over ${MAX_MESSAGE_CHARS} characters` }, { status: 400 });
  }

  try {
    await client.beta.sessions.events.send(session.id, {
      events: [{ type: "user.message", content: [{ type: "text", text }] }],
    });
    return Response.json({ ok: true });
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    return Response.json({ error: `send failed: ${detail}` }, { status: 502 });
  }
}
