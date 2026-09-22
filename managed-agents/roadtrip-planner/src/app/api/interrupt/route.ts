import { cookies } from "next/headers";
import { SESSION_COOKIE, client, ownedSession } from "@/lib/client";

/**
 * The stop button. `user.interrupt` stops the running turn: the agent winds
 * down, the session goes idle, and both land on the stream like everything
 * else (the `session.status_idle` that follows is what flips the UI back to
 * ready).
 */
export async function POST() {
  const jar = await cookies();
  const session = await ownedSession(jar.get(SESSION_COOKIE)?.value).catch(() => null);
  if (!session) return new Response(null, { status: 403 });
  await client.beta.sessions.events
    .send(session.id, { events: [{ type: "user.interrupt" }] })
    .catch(() => {
      // Already idle: interrupting a finished turn is a no-op worth ignoring.
    });
  return new Response(null, { status: 204 });
}
