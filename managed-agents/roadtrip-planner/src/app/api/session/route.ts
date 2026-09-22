import { cookies } from "next/headers";
import type { BetaManagedAgentsSession } from "@anthropic-ai/sdk/resources/beta/sessions/sessions";
import { SESSION_COOKIE, client, ownedSession } from "@/lib/client";
import { environmentId, plannerAgentId, vaultId } from "@/lib/resources";
import { MODELS } from "@/lib/models";
import type { ManagedAgentEvent } from "@/lib/transcript";

/**
 * Ensure the browser has a usable Managed Agents session and hand back its
 * event log. Called on page load (so the sandbox is warm before the first
 * question) and again on every stream reconnect (the log re-sync). The
 * client folds the raw events into the transcript itself.
 *
 * Every session is created with the `agent_with_overrides` selector. With
 * no pick the selector carries no overrides and the agent's stored model
 * applies. A pick adds a `model` override for this session only. The
 * response always reports the session's effective model (from its resolved
 * agent snapshot), so the picker in the header shows what the API resolved,
 * not what the client asked for.
 */

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as { fresh?: boolean; model?: unknown };
  const jar = await cookies();

  // The override is caller input, so it is checked against the list the
  // picker offers before it goes anywhere near sessions.create.
  if (body.model !== undefined && !(MODELS as readonly unknown[]).includes(body.model)) {
    return Response.json({ error: `model must be one of: ${MODELS.join(", ")}` }, { status: 400 });
  }
  const model = body.model as (typeof MODELS)[number] | undefined;

  // Picking a model implies a fresh session: the model is fixed at create.
  // A cookie that is not this app's session (someone else's ID, an archived
  // one after teardown, a deleted one) counts as no cookie: quietly start a
  // new trip, and never return the other session's events.
  let session: BetaManagedAgentsSession | null = null;
  try {
    session = body.fresh || model ? null : await ownedSession(jar.get(SESSION_COOKIE)?.value);
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : String(error) }, { status: 500 });
  }
  let sessionId = session?.id ?? null;

  // The whole event log, oldest first. This is the chat's only persistence.
  const events: ManagedAgentEvent[] = [];
  if (sessionId) {
    const pages = client.beta.sessions.events.list(sessionId, { order: "asc", limit: 100 });
    for await (const event of pages) events.push(event);
  }

  try {
    session ??= await client.beta.sessions.create({
      // Every session is created through the agent_with_overrides selector:
      // one stored agent serves every visitor, and each provided field
      // replaces the agent's value for this session only. `model`, `system`,
      // `tools`, `mcp_servers`, and `skills` are overridable, and this app
      // only ever overrides `model`. With no override the stored agent
      // applies unchanged.
      agent: {
        type: "agent_with_overrides",
        id: plannerAgentId(),
        ...(model ? { model } : {}),
      },
      environment_id: environmentId(),
      // Vaults attach at create time only (sessions.update rejects vault_ids).
      vault_ids: [vaultId()],
      title: `Road trip - ${new Date().toISOString().slice(0, 10)}`,
    });
  } catch (error) {
    // Surface the API's own message, with one translation: a 400 naming
    // "agent_reference" means the org's agent_with_overrides gate is not
    // open yet, not a provisioning problem (see skill.md's debugging table).
    const detail = error instanceof Error ? error.message : String(error);
    const gated = /agent_reference|Extra inputs are not permitted/i.test(detail);
    return Response.json(
      {
        error: gated
          ? `this organization's agent_with_overrides gate is not open yet, so sessions cannot be created with the overrides selector. API said: ${detail}`
          : `create failed: ${detail}`,
      },
      { status: 502 },
    );
  }
  sessionId = session.id;

  jar.set(SESSION_COOKIE, sessionId, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    // The cookie is this app's only credential. `next dev` is plain http,
    // so the Secure flag is conditional or localhost could never set it.
    secure: process.env.NODE_ENV === "production",
  });

  // The model this session actually runs on, from its resolved agent
  // snapshot. With an override this differs from the stored agent's
  // configured model, which is the whole demonstration.
  const resolved: unknown = session.agent?.model;
  return Response.json({
    sessionId,
    events,
    model:
      typeof resolved === "string"
        ? resolved
        : resolved && typeof resolved === "object" && "id" in resolved
          ? String(resolved.id)
          : null,
    working: session.status === "running" || session.status === "rescheduling",
  });
}
